#!/usr/bin/env python3
"""
qline control GUI - a Tkinter + matplotlib panel to operate qline1 / qline2.

Per-tab it shows:
  * live count-rate, key-rate and QBER history plots
  * a status light: down / calibrating / producing key / error (+ error message)
  * basic system parameters: dead time, mean photon number (Alice), Alice-Bob distance
  * controls: Wake & Produce, Full Init, Auto-tune, Shutdown, and Adjust mean photon #

Data and actions go through backend.py (RealBackend shells out to the local/ tools;
DemoBackend is a self-driving mock).  Run the mock with:

    python3 local/gui/qline_gui.py --demo

Against real hardware (needs generated config under config/<qline>/):

    python3 local/gui/qline_gui.py                 # direct IPs from network.json
    python3 local/gui/qline_gui.py --use_localhost # over port_forwarding.sh tunnels

The --use_localhost flag only sets the initial state of each tab's toggle.
"""

from __future__ import annotations

import argparse
import os
import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import matplotlib.dates as mdates

import backend as be

POLL_MS = 3000          # snapshot refresh cadence
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_CONFIG_ROOT = os.path.join(REPO_ROOT, "config")


class QlineTab(ttk.Frame):
    def __init__(self, parent, qline, demo, config_root, use_localhost):
        super().__init__(parent)
        self.qline = qline
        self.demo = demo
        self.config_root = config_root

        self.use_localhost = tk.BooleanVar(value=use_localhost)
        self.latest: be.Snapshot | None = None
        self.log_q: queue.Queue[str] = queue.Queue()
        self.snap_q: queue.Queue[be.Snapshot] = queue.Queue()
        self.action_running = False
        self._poll_lock = threading.Lock()

        self.backend = self._make_backend()
        self._build()
        self._poll_tick()
        self._drain_log()

    # ---- backend (re)creation on toggle --------------------------------
    def _make_backend(self):
        return be.make_backend(self.qline, self.config_root, self.demo,
                               self.use_localhost.get())

    def _on_toggle_localhost(self):
        self.backend = self._make_backend()
        self._append_log(f"[gui] connection mode: "
                         f"{'localhost/port-forward' if self.use_localhost.get() else 'direct IPs'}")

    # ---- layout ---------------------------------------------------------
    def _build(self):
        # Top bar: status + connection toggle
        top = ttk.Frame(self, padding=(8, 6))
        top.pack(fill="x")

        ttk.Label(top, text="Status:", font=("TkDefaultFont", 11, "bold")).pack(side="left")
        self.status_canvas = tk.Canvas(top, width=18, height=18, highlightthickness=0)
        self.status_dot = self.status_canvas.create_oval(2, 2, 16, 16, fill="#777", outline="")
        self.status_canvas.pack(side="left", padx=(6, 4))
        self.status_lbl = ttk.Label(top, text="unknown", font=("TkDefaultFont", 11, "bold"))
        self.status_lbl.pack(side="left")

        self.key_lbl = ttk.Label(top, text="stored keys: -")
        self.key_lbl.pack(side="right")
        if not self.demo:
            ttk.Checkbutton(top, text="localhost (port-forward)",
                            variable=self.use_localhost,
                            command=self._on_toggle_localhost).pack(side="right", padx=10)
        else:
            ttk.Label(top, text="[DEMO]", foreground="#b58900").pack(side="right", padx=10)

        # Error line (hidden unless error)
        self.err_lbl = ttk.Label(self, text="", foreground="#d9534f", padding=(10, 0))
        self.err_lbl.pack(fill="x")

        # Parameters (readouts) + adjusters
        params = ttk.LabelFrame(self, text="System parameters", padding=8)
        params.pack(fill="x", padx=8, pady=4)

        # row 0: readouts
        self.p_dead = ttk.Label(params, text="dead time: - us")
        self.p_dead.grid(row=0, column=0, sticky="w", padx=6)
        self.p_mu = ttk.Label(params, text="mean photon #: - /pulse")
        self.p_mu.grid(row=0, column=1, sticky="w", padx=6)
        self.p_dist = ttk.Label(params, text="A-B distance: - km")
        self.p_dist.grid(row=0, column=2, sticky="w", padx=6)
        self.p_loss = ttk.Label(params, text="loss: - dB")
        self.p_loss.grid(row=0, column=3, sticky="w", padx=6)

        # row 1: dead-time adjuster  (hw_bob.py set --spd_deadtime <us>)
        ttk.Label(params, text="Dead time (us):").grid(row=1, column=0, sticky="e", pady=(6, 0))
        self.dead_entry = ttk.Entry(params, width=8)
        self.dead_entry.insert(0, "15")
        self.dead_entry.grid(row=1, column=1, sticky="w", pady=(6, 0))
        self.dead_btn = ttk.Button(params, text="Set", command=self._on_set_dead)
        self.dead_btn.grid(row=1, column=2, sticky="w", pady=(6, 0))

        # row 2: mean-photon adjuster, two methods
        ttk.Label(params, text="Mean photon #:").grid(row=2, column=0, sticky="e", pady=(6, 0))
        self.mu_mode = tk.StringVar(value="photons/pulse")
        self.mu_combo = ttk.Combobox(params, textvariable=self.mu_mode, width=13, state="readonly",
                                     values=("photons/pulse", "target counts"))
        self.mu_combo.grid(row=2, column=1, sticky="w", pady=(6, 0))
        self.mu_combo.bind("<<ComboboxSelected>>", self._on_mu_mode)
        self.mu_entry = ttk.Entry(params, width=8)
        self.mu_entry.insert(0, "0.2")
        self.mu_entry.grid(row=2, column=2, sticky="w", pady=(6, 0))
        self.mu_btn = ttk.Button(params, text="Set", command=self._on_set_mu)
        self.mu_btn.grid(row=2, column=3, sticky="w", padx=6, pady=(6, 0))
        self.mu_hint = ttk.Label(params, text="(0.003-3 photons/pulse)", foreground="#777")
        self.mu_hint.grid(row=2, column=4, sticky="w", pady=(6, 0))

        # Control buttons
        ctl = ttk.Frame(self, padding=(8, 2))
        ctl.pack(fill="x")
        self.btn_wake = ttk.Button(ctl, text="Wake & Produce", command=self._on_wake)
        self.btn_wake.pack(side="left", padx=4)
        self.btn_init = ttk.Button(ctl, text="Full Init", command=self._on_full_init)
        self.btn_init.pack(side="left", padx=4)
        self.btn_tune = ttk.Button(ctl, text="Auto-tune", command=self._on_tune)
        self.btn_tune.pack(side="left", padx=4)
        self.btn_down = ttk.Button(ctl, text="Shutdown", command=self._on_shutdown)
        self.btn_down.pack(side="left", padx=4)
        self.action_lbl = ttk.Label(ctl, text="")
        self.action_lbl.pack(side="left", padx=10)

        # Plots
        self.fig = Figure(figsize=(7.5, 5.2), dpi=96)
        self.ax_counts = self.fig.add_subplot(311)
        self.ax_rate = self.fig.add_subplot(312, sharex=self.ax_counts)
        self.ax_qber = self.fig.add_subplot(313, sharex=self.ax_counts)
        self.fig.subplots_adjust(hspace=0.35, left=0.12, right=0.97, top=0.96, bottom=0.08)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=4)

        # counts trend (single scalar over time we accumulate client-side)
        self._counts_hist: list = []

        # Log pane
        logf = ttk.LabelFrame(self, text="Action output", padding=4)
        logf.pack(fill="x", padx=8, pady=(0, 8))
        self.log = tk.Text(logf, height=6, wrap="none", font=("TkFixedFont", 9))
        self.log.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(logf, command=self.log.yview)
        sb.pack(side="right", fill="y")
        self.log.config(yscrollcommand=sb.set, state="disabled")

    # ---- polling --------------------------------------------------------
    # A worker thread computes snapshots and drops them on snap_q; the main
    # thread drains the queue via `after` (Tk calls must stay on the main thread).
    def _poll_tick(self):
        if self._poll_lock.acquire(blocking=False):
            threading.Thread(target=self._poll_worker, daemon=True).start()
        # drain whatever the worker has produced, render the newest
        snap = None
        try:
            while True:
                snap = self.snap_q.get_nowait()
        except queue.Empty:
            pass
        if snap is not None:
            self.latest = snap
            self._render(snap)
        self.after(POLL_MS, self._poll_tick)

    def _poll_worker(self):
        try:
            snap = self.backend.refresh()
        except Exception as e:            # never let a poll error kill the GUI
            snap = be.Snapshot(status=be.ERROR, error=f"poll failed: {e}")
        finally:
            self._poll_lock.release()
        self.snap_q.put(snap)

    def _render(self, snap: be.Snapshot):
        color = be.STATUS_COLORS.get(snap.status, "#777")
        self.status_canvas.itemconfig(self.status_dot, fill=color)
        self.status_lbl.config(text=snap.status)
        self.err_lbl.config(text=(f"error: {snap.error}" if snap.status == be.ERROR and snap.error else ""))
        self.key_lbl.config(text=f"stored keys: {snap.key_store if snap.key_store is not None else '-'}")

        p = snap.params
        self.p_dead.config(text=f"dead time: {_fmt(p.dead_time_us)} us")
        self.p_mu.config(text=f"mean photon #: {_fmt(p.mean_photon)} /pulse")
        self.p_dist.config(text=f"A-B distance: {_fmt(p.distance_km)} km")
        self.p_loss.config(text=f"loss: {_fmt(round(snap.loss_db, 1)) if snap.loss_db is not None else '-'} dB")

        # accumulate counts trend
        if snap.counts is not None:
            self._counts_hist.append((snap.counts.t, snap.counts.total))
            self._counts_hist = self._counts_hist[-400:]

        self._draw_plots(snap)

    def _draw_plots(self, snap: be.Snapshot):
        for ax in (self.ax_counts, self.ax_rate, self.ax_qber):
            ax.clear()

        # counts  (all x-values normalised to naive local time; the axes share
        # x, and matplotlib refuses to mix tz-aware and tz-naive datetimes)
        if self._counts_hist:
            ts = [_naive(t) for t, _ in self._counts_hist]
            cs = [c for _, c in self._counts_hist]
            self.ax_counts.plot(ts, cs, ".-", color="tab:green", ms=3)
        self.ax_counts.set_ylabel("counts")
        self.ax_counts.grid(alpha=0.3)

        # key rate
        rt, rate = be.key_rates(snap.stats)
        if rt:
            self.ax_rate.plot([_naive(t) for t in rt], rate, ".-", color="tab:blue", ms=3)
        self.ax_rate.set_ylabel("key rate\n[bit/s]")
        self.ax_rate.grid(alpha=0.3)

        # qber
        if snap.stats:
            qts = [_naive(s.t) for s in snap.stats]
            q = [s.qber for s in snap.stats]
            self.ax_qber.plot(qts, q, ".-", color="tab:red", ms=3)
        self.ax_qber.axhline(0.09, ls="--", color="gray", lw=1)
        self.ax_qber.set_ylabel("QBER")
        self.ax_qber.grid(alpha=0.3)
        self.ax_qber.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
        for lbl in self.ax_qber.get_xticklabels():
            lbl.set_rotation(20)
            lbl.set_ha("right")
        self.canvas.draw_idle()

    # ---- actions --------------------------------------------------------
    def _busy(self, on: bool, label=""):
        self.action_running = on
        state = "disabled" if on else "normal"
        for b in (self.btn_wake, self.btn_init, self.btn_tune, self.btn_down,
                  self.mu_btn, self.dead_btn):
            b.config(state=state)
        self.action_lbl.config(text=label)

    def _on_wake(self):
        self._start_action("wake_produce", "Waking & starting key production...")

    def _on_full_init(self):
        if messagebox.askyesno("Full Init",
                               "Re-run full_init on the running system?\n"
                               "Key production pauses during calibration."):
            self._start_action("full_init", "Full init / calibrating...")

    def _on_tune(self):
        self._start_action("auto_control", "Auto-tuning...")

    def _on_shutdown(self):
        if messagebox.askyesno("Shutdown",
                               f"Power off both {self.qline} nodes?\n"
                               "Recover with Wake & Produce (Wake-on-LAN)."):
            self._start_action("shutdown", "Shutting down...")

    def _on_mu_mode(self, _evt=None):
        # swap hint + a sensible default when the method changes
        if self.mu_mode.get() == "photons/pulse":
            self.mu_hint.config(text="(0.003-3 photons/pulse)")
            self.mu_entry.delete(0, "end"); self.mu_entry.insert(0, "0.2")
        else:
            self.mu_hint.config(text="(detector count target, e.g. 3000)")
            self.mu_entry.delete(0, "end"); self.mu_entry.insert(0, "3000")

    def _on_set_dead(self):
        val = self.dead_entry.get().strip()
        try:
            us = int(round(float(val)))
        except ValueError:
            messagebox.showerror("Adjust dead time", "Enter dead time in microseconds (e.g. 15).")
            return
        if not 1 <= us <= 1000:
            messagebox.showerror("Adjust dead time", "Dead time out of range (1-1000 us).")
            return
        self._start_action("set_dead_time", f"Setting dead time -> {us} us...", us=us)

    def _on_set_mu(self):
        val = self.mu_entry.get().strip()
        if self.mu_mode.get() == "photons/pulse":
            try:
                mu = float(val)
            except ValueError:
                messagebox.showerror("Adjust mean photon #", "Enter photons/pulse (e.g. 0.5).")
                return
            if not 0.003 <= mu <= 3:
                messagebox.showerror("Adjust mean photon #", "Out of range (0.003-3 photons/pulse).")
                return
            self._start_action("set_mean_photon", f"Setting mean photon # -> {mu} /pulse...",
                               mode="photons", value=mu)
        else:
            if not val.isdigit():
                messagebox.showerror("Adjust mean photon #", "Enter an integer count target.")
                return
            self._start_action("set_mean_photon", f"Driving to {val} counts (find_vca)...",
                               mode="counts", value=int(val))

    def _start_action(self, name, label, **kw):
        if self.action_running:
            return
        self._busy(True, label)
        self._append_log(f"\n=== {name} ({self.qline}) ===")
        threading.Thread(target=self._run_action, args=(name, kw), daemon=True).start()

    def _run_action(self, name, kw):
        try:
            if self.demo:
                self.backend.demo_action(name, self._append_log_threadsafe, **kw)
            else:
                self._run_real_action(name, kw)
        except Exception as e:
            self._append_log_threadsafe(f"[error] {e}")
        finally:
            self.after(0, lambda: self._busy(False))

    def _run_real_action(self, name, kw):
        import subprocess
        argv, env, timeout = self.backend.action_argv(name, **kw)
        self._append_log_threadsafe("$ " + " ".join(argv))
        try:
            proc = subprocess.Popen(argv, cwd=self.backend.local_dir, env=env,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, bufsize=1)
        except OSError as e:
            self._append_log_threadsafe(f"[error] cannot launch: {e}")
            return
        for line in proc.stdout:                       # stream
            self._append_log_threadsafe(line.rstrip("\n"))
        proc.wait(timeout=timeout)
        self._append_log_threadsafe(f"[exit {proc.returncode}]")

    # ---- log pane -------------------------------------------------------
    def _append_log_threadsafe(self, line):
        self.log_q.put(line)

    def _append_log(self, line):
        self.log_q.put(line)

    def _drain_log(self):
        try:
            while True:
                line = self.log_q.get_nowait()
                self.log.config(state="normal")
                self.log.insert("end", line + "\n")
                self.log.see("end")
                self.log.config(state="disabled")
        except queue.Empty:
            pass
        self.after(200, self._drain_log)


def _naive(dt):
    """Normalise to naive *local* time so mixed sources share the x-axis.

    node_stats timestamps are tz-aware UTC; counts_logger timestamps are naive
    local (datetime.now()). Convert the aware ones to local before stripping tz,
    otherwise UTC stats and local counts are offset by the UTC->local delta.
    """
    if dt.tzinfo is not None:
        dt = dt.astimezone().replace(tzinfo=None)   # -> local, then drop tzinfo
    return dt


def _fmt(v):
    if v is None:
        return "-"
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return f"{v:g}" if isinstance(v, float) else str(v)


def main():
    ap = argparse.ArgumentParser(description="qline control GUI")
    ap.add_argument("--demo", action="store_true", help="run the self-driving mock backend")
    ap.add_argument("--use_localhost", action="store_true",
                    help="start tabs in localhost/port-forward mode (real backend)")
    ap.add_argument("--config-root", default=DEFAULT_CONFIG_ROOT,
                    help="dir holding qline1/ qline2/ config subdirs")
    args = ap.parse_args()

    root = tk.Tk()
    root.title("qline control" + (" [DEMO]" if args.demo else ""))
    root.geometry("820x780")

    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True)
    for q in ("qline1", "qline2"):
        tab = QlineTab(nb, q, args.demo, args.config_root, args.use_localhost)
        nb.add(tab, text=q)

    root.mainloop()


if __name__ == "__main__":
    main()
