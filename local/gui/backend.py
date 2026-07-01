#!/usr/bin/env python3
"""
Backend abstraction for the qline control GUI.

Two implementations behind one interface:

  * RealBackend  - shells out to the existing local/ tools
    (run_qkd.sh, hws.py, shutdown.py, logs.py, wake.sh) exactly the way an
    operator would from the shell.  It reads live data over `logs.py stats`
    (/tmp/node_stats.csv: key_length;qber;timestamp), `logs.py bob tail counts`
    (counts_logger heartbeat: total/click0/click1) and the KMS /status endpoint.

  * DemoBackend  - a self-driving mock that produces synthetic counts / QBER /
    key-store data and reacts to the control actions, so the GUI can be run and
    verified without any hardware or generated config.

The GUI never imports subprocess itself; it talks to a Backend.  Read paths go
through `refresh()` (called from a poller thread) which returns a Snapshot.
Control actions are exposed as argv builders (`action_argv`) that the GUI runs
in a thread and streams into its log pane, or - for the demo - as `demo_action`.
"""

from __future__ import annotations

import json
import math
import os
import random
import re
import socket
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Status vocabulary (matches what the user asked to see)
# ---------------------------------------------------------------------------
DOWN = "down"
CALIBRATING = "calibrating"
PRODUCING = "producing key"
ERROR = "error"
UNKNOWN = "unknown"

STATUS_COLORS = {
    DOWN: "#9e9e9e",
    CALIBRATING: "#f0ad4e",
    PRODUCING: "#5cb85c",
    ERROR: "#d9534f",
    UNKNOWN: "#777777",
}

# A node_stats row older than this (seconds) means "not currently producing".
FRESH_SECONDS = 150


# ---------------------------------------------------------------------------
# Data carriers
# ---------------------------------------------------------------------------
@dataclass
class Sample:
    t: datetime
    key_length: int
    qber: float


@dataclass
class Counts:
    t: datetime
    total: int
    click0: int
    click1: int


@dataclass
class Params:
    """Basic system parameters shown in the GUI.

    dead_time_us  - detector (Bob) dead time in us, set via
                    `hw_bob.py set --spd_deadtime`.
    mean_photon   - mean photon number per pulse on Alice (0.003..3), set via
                    `hw_alice.py set --photons`; can also be driven indirectly by
                    a detector count target through `find_vca`.
    distance_km   - Alice-Bob distance; informational (no clean live query
                    off-network).
    Persisted per qline in a small JSON alongside this module so edits survive.
    """
    dead_time_us: float | None = None
    mean_photon: float | None = None      # photons per pulse on Alice
    distance_km: float | None = None


@dataclass
class Snapshot:
    status: str = UNKNOWN
    error: str = ""
    stats: list[Sample] = field(default_factory=list)
    counts: Counts | None = None
    key_store: int | None = None
    loss_db: float | None = None
    params: Params = field(default_factory=Params)
    reachable: bool = False


# ---------------------------------------------------------------------------
# Parsing helpers (shared by real backend and any tests)
# ---------------------------------------------------------------------------
def parse_stats(text: str) -> list[Sample]:
    """Parse node_stats.csv rows 'key_length;qber;timestamp'."""
    out: list[Sample] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or ";" not in line:
            continue
        parts = line.split(";")
        if len(parts) < 3:
            continue
        kl, q, ts = parts[0], parts[1], parts[2]
        try:
            kl_i, q_f = int(kl), float(q)
        except ValueError:
            continue
        dt = _parse_ts(ts)
        if dt is None:
            continue
        out.append(Sample(dt, kl_i, q_f))
    return out


def _parse_ts(ts: str) -> datetime | None:
    ts = ts.split("[")[0].strip()             # drop [Etc/UTC]
    m = re.match(r"(.*\.)(\d+)([+-]\d{2}:\d{2})$", ts)
    if m:                                     # trim ns -> us for fromisoformat
        ts = f"{m.group(1)}{m.group(2)[:6]}{m.group(3)}"
    try:
        dt = datetime.fromisoformat(ts)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


_COUNTS_RE = re.compile(r"total=(\d+)\s+click0=(\d+)\s+click1=(\d+)")


def parse_counts(text: str) -> Counts | None:
    """Parse the last 'total=.. click0=.. click1=..' line from counts.log."""
    last = None
    for line in text.splitlines():
        m = _COUNTS_RE.search(line)
        if m:
            last = (line, m)
    if not last:
        return None
    line, m = last
    # leading token is an ISO timestamp; fall back to now if unparseable
    tok = line.split(" ", 1)[0]
    try:
        t = datetime.fromisoformat(tok)
    except ValueError:
        t = datetime.now()
    return Counts(t, int(m.group(1)), int(m.group(2)), int(m.group(3)))


# Alice-Bob distance is derived from `hw_alice.py get --info`, which dumps
# config/tmp.txt (key\tvalue lines).  `fiber_delay` there is the one-way fiber
# propagation Alice compensates for, expressed in 80 MHz clock cycles.  Only
# meaningful after a full_init (it is 0 on a fresh/default config).
CLOCK_HZ = 80e6
FIBER_GROUP_INDEX = 1.468                 # SMF-28 group index @ 1550 nm
C_M_S = 299_792_458.0


def parse_fiber_delay(info_text: str) -> int | None:
    """Pull the integer fiber_delay from `hw_alice.py get --info` output."""
    for line in info_text.splitlines():
        parts = line.replace("\t", " ").split()
        if len(parts) >= 2 and parts[0] == "fiber_delay":
            try:
                return int(parts[1])
            except ValueError:
                return None
    return None


def distance_km_from_fiber_delay(fiber_delay: int | None) -> float | None:
    """Convert an 80 MHz-cycle fiber delay to an Alice-Bob distance in km."""
    if not fiber_delay or fiber_delay <= 0:
        return None                       # 0 = not calibrated yet
    v_group = C_M_S / FIBER_GROUP_INDEX   # m/s in fiber
    delay_s = fiber_delay / CLOCK_HZ
    return delay_s * v_group / 1000.0


# Total (end-to-end) channel loss from Alice's mean photon number and Bob's count
# rate, dead-time corrected.  The count register (get_counts, offset 56) integrates
# over a 0.1 s window (the mon path returns clicks*10 = counts/s); g is the 80 MHz
# pulse rate.  p = detections/pulse = R/(g*(1-R*tau)); transmission T = -ln(1-p)/mu;
# loss = -10 log10(T).  For the real system at 0 fiber with mu=0.2 this reads ~20 dB
# (detector efficiency + optics), rising with fiber length.
PULSE_RATE_HZ = 80e6
COUNT_WINDOW_S = 0.1        # integration window of the free-running counts register


def loss_db_from_counts(clicks: int | None, mean_photon: float | None,
                        dead_time_us: float | None) -> float | None:
    """Total loss [dB] from Bob clicks-per-window, Alice mu, and detector dead time."""
    if not clicks or clicks <= 0 or not mean_photon or mean_photon <= 0:
        return None
    R = clicks / COUNT_WINDOW_S                       # counts/s
    tau = (dead_time_us or 0.0) * 1e-6
    denom = 1.0 - R * tau
    if denom <= 0:                                    # detector saturated / bad tau
        return None
    p = R / (PULSE_RATE_HZ * denom)                   # detections per pulse
    if not 0 < p < 1:
        return None
    T = -math.log(1.0 - p) / mean_photon              # end-to-end transmission
    if T <= 0:
        return None
    return -10.0 * math.log10(T)


def key_rates(stats: list[Sample]) -> tuple[list[datetime], list[float]]:
    """Per-round key rate [bit/s] = key_length / dt vs previous round."""
    ts, rate = [], []
    for i in range(1, len(stats)):
        dt = (stats[i].t - stats[i - 1].t).total_seconds()
        if dt > 0:
            ts.append(stats[i].t)
            rate.append(stats[i].key_length / dt)
    return ts, rate


# ---------------------------------------------------------------------------
# Base backend
# ---------------------------------------------------------------------------
class Backend:
    ACTIONS = ("wake_produce", "full_init", "auto_control", "shutdown",
               "set_dead_time", "set_mean_photon")

    def __init__(self, qline: str, config_root: str):
        self.qline = qline
        self.config_dir = os.path.join(config_root, qline)
        self.params_path = os.path.join(os.path.dirname(__file__), f"params_{qline}.json")

    # ---- params persistence (shared) -----------------------------------
    def load_params(self) -> Params:
        try:
            d = json.load(open(self.params_path))
            return Params(d.get("dead_time_us"), d.get("mean_photon"), d.get("distance_km"))
        except (OSError, ValueError):
            # dead time / mean photon are operator settings; distance is derived
            # live from fiber_delay, so it starts unknown.
            # mu defaults to 0.2 (currently the vca sets it implicitly; treated as
            # 0.2 until the operator sets it explicitly).
            return Params(dead_time_us=15.0, mean_photon=0.2, distance_km=None)

    def save_params(self, p: Params) -> None:
        try:
            json.dump(
                {"dead_time_us": p.dead_time_us, "mean_photon": p.mean_photon,
                 "distance_km": p.distance_km},
                open(self.params_path, "w"), indent=2,
            )
        except OSError:
            pass

    # ---- to be implemented ---------------------------------------------
    def refresh(self, n: int = 200) -> Snapshot:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Real backend - drives the existing local/ tools
# ---------------------------------------------------------------------------
class RealBackend(Backend):
    def __init__(self, qline: str, config_root: str, use_localhost: bool):
        super().__init__(qline, config_root)
        self.use_localhost = use_localhost
        self.local_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # local/
        self._distance_km: float | None = None    # cached; refreshed from get --info
        self._info_t = 0.0

    # ---- environment / connection --------------------------------------
    def _env(self) -> dict:
        e = dict(os.environ)
        e["QLINE_CONFIG_DIR"] = self.config_dir
        return e

    def _ll(self, argv: list[str]) -> list[str]:
        # hws.py / logs.py / shutdown.py accept --use_localhost anywhere.
        return argv + (["--use_localhost"] if self.use_localhost else [])

    def _hw(self, script: str, rest: list[str]) -> list[str]:
        # hw_alice.py / hw_bob.py use argparse subparsers, so the top-level
        # --use_localhost must come BEFORE the `set` subcommand.
        argv = ["python3", script]
        if self.use_localhost:
            argv.append("--use_localhost")
        return argv + rest

    def _run(self, argv: list[str], timeout: int = 30) -> tuple[int, str]:
        try:
            p = subprocess.run(argv, cwd=self.local_dir, env=self._env(),
                               capture_output=True, text=True, timeout=timeout)
            return p.returncode, (p.stdout or "") + (p.stderr or "")
        except subprocess.TimeoutExpired:
            return 124, "timeout"
        except OSError as e:
            return 1, str(e)

    # ---- read paths -----------------------------------------------------
    def _logs(self, node: str, cmd: str, timeout: int = 20) -> tuple[int, str]:
        return self._run(self._ll(["python3", "logs.py", node, *cmd.split()]), timeout)

    def _kms_key_store(self) -> int | None:
        # Mirror run_qkd.sh: read Alice KMS stored_key_count for the detector peer.
        try:
            net = json.load(open(os.path.join(self.config_dir, "alice", "network.json")))
            nd = json.load(open(os.path.join(self.config_dir, "alice", "node.json")))
            if self.use_localhost:
                lp = json.load(open(os.path.join(self.config_dir, "ports_for_localhost.json")))
                host, port = "localhost", int(lp["kms_alice"])
            else:
                host, port = net["ip"]["alice"], int(net["port"]["kms_alice"])
            bob_id = next(peer[0] for peer in nd["peers"] if peer[1] == "Detector")
        except (OSError, ValueError, KeyError, StopIteration):
            return None
        try:
            import urllib.request
            url = f"http://{host}:{port}/api/v1/keys/{bob_id}/status"
            with urllib.request.urlopen(url, timeout=8) as r:
                return json.load(r).get("stored_key_count")
        except Exception:
            return None

    def _distance(self) -> float | None:
        # Throttled: query `hw_alice.py get --info`, parse fiber_delay -> km, and
        # cache.  fiber_delay is only nonzero after a full_init, so we keep the
        # last good value and only re-query once a minute.
        now = time.time()
        if self._distance_km is not None and now - self._info_t < 60:
            return self._distance_km
        rc, out = self._run(self._hw("hw_alice.py", ["get", "--info"]), timeout=20)
        self._info_t = now
        if rc == 0:
            d = distance_km_from_fiber_delay(parse_fiber_delay(out))
            if d is not None:
                self._distance_km = d
        return self._distance_km

    def refresh(self, n: int = 200) -> Snapshot:
        snap = Snapshot(params=self.load_params())

        rc, stats_txt = self._logs("alice", f"stats {n}")
        reachable = rc == 0 and "cannot reach" not in stats_txt and "error:" not in stats_txt
        snap.reachable = reachable
        if reachable:
            snap.stats = parse_stats(stats_txt)
            snap.params.distance_km = self._distance()

        rc_c, counts_txt = self._logs("bob", "tail counts 20")
        if rc_c == 0:
            snap.counts = parse_counts(counts_txt)
        if snap.counts is not None:
            snap.loss_db = loss_db_from_counts(
                snap.counts.click0 + snap.counts.click1,
                snap.params.mean_photon, snap.params.dead_time_us)

        snap.key_store = self._kms_key_store() if reachable else None

        # --- derive status ----------------------------------------------
        if not reachable:
            snap.status = DOWN
            return snap

        # counts alert (detector dark) -> error
        if "ALERT" in counts_txt and "RECOVER" not in counts_txt.splitlines()[-1:]:
            last = counts_txt.strip().splitlines()[-1] if counts_txt.strip() else ""
            if "ALERT" in last:
                snap.status = ERROR
                snap.error = last
                return snap

        fresh = False
        if snap.stats:
            age = (datetime.now(timezone.utc) - snap.stats[-1].t).total_seconds()
            fresh = age < FRESH_SECONDS
        if fresh:
            snap.status = PRODUCING
        else:
            # reachable but no fresh key rounds: calibrating / idle
            snap.status = CALIBRATING
        return snap

    # ---- control actions (argv builders; GUI streams them) --------------
    def action_argv(self, name: str, **kw) -> tuple[list[str], dict, int]:
        """Return (argv, env, timeout) for a control action."""
        env = self._env()
        if name == "wake_produce":
            # wake.sh + run_qkd.sh --init : full bring-up and start producing.
            return (["bash", "run_qkd.sh", self.qline, "--init"], env, 1800)
        if name == "full_init":
            return (self._ll(["python3", "hws.py", "--full_init"]), env, 1800)
        if name == "auto_control":
            return (self._ll(["python3", "hws.py", "--auto_control"]), env, 900)
        if name == "shutdown":
            return (self._ll(["python3", "shutdown.py", "both", "--yes"]), env, 60)
        if name == "set_dead_time":
            us = int(round(float(kw["us"])))
            return (self._hw("hw_bob.py", ["set", "--spd_deadtime", str(us)]), env, 60)
        if name == "set_mean_photon":
            if kw.get("mode") == "photons":
                # direct mean photon number per pulse on Alice (0.003..3)
                return (self._hw("hw_alice.py", ["set", "--photons", str(float(kw["value"]))]),
                        env, 60)
            # indirect: drive the detector count target with find_vca
            target = int(kw["value"])
            return (self._ll(["python3", "hws.py", "--command", f"find_vca_{target}"]), env, 600)
        raise ValueError(f"unknown action {name}")


# ---------------------------------------------------------------------------
# Demo backend - self-driving synthetic system
# ---------------------------------------------------------------------------
class DemoBackend(Backend):
    def __init__(self, qline: str, config_root: str):
        super().__init__(qline, config_root)
        self._state = DOWN
        self._t0 = time.time()
        self._state_since = time.time()
        self._key_store = 0
        self._history: list[Sample] = []
        self._last_round = 0.0
        self._error = ""
        self._photons = 0.2          # mean photon number per pulse (default assumption)
        self._dead_time_us = 15.0    # detector dead time
        self._fiber_delay = 3900     # 80 MHz cycles (~9.95 km) -> distance
        self._loss_floor_db = 20.0   # system loss at 0 fiber (detector eff + optics)
        # qline2 starts already producing so both tabs show data out of the box
        if qline == "qline2":
            self._enter(PRODUCING)

    # channel loss the synthetic system exhibits: 20 dB floor + fiber attenuation
    def _loss_db(self) -> float:
        d = distance_km_from_fiber_delay(self._fiber_delay) or 0.0
        return self._loss_floor_db + 0.2 * d          # ~0.2 dB/km fiber

    # clicks per 0.1 s window Bob would see for a given mu at the current loss
    def _expected_clicks(self, mu: float) -> float:
        T = 10 ** (-self._loss_db() / 10)
        p = 1 - math.exp(-mu * T)
        lam = p * PULSE_RATE_HZ
        tau = self._dead_time_us * 1e-6
        R = lam / (1 + lam * tau)
        return R * COUNT_WINDOW_S

    # ---- state machine --------------------------------------------------
    def _enter(self, s: str):
        self._state = s
        self._state_since = time.time()

    def _advance(self):
        now = time.time()
        dwell = now - self._state_since
        if self._state == CALIBRATING and dwell > 8:
            self._enter(PRODUCING)
        if self._state == PRODUCING:
            # one round roughly every 10s
            if now - self._last_round > 10:
                self._last_round = now
                base_q = 0.035 + 0.01 * math.sin(now / 40)
                qber = max(0.005, random.gauss(base_q, 0.004))
                # key length scales with the sift/click rate and shrinks with qber
                kl = int(self._expected_clicks(self._photons) * 60 * max(0.0, 1 - qber / 0.11))
                self._history.append(Sample(datetime.now(timezone.utc), kl, qber))
                self._history = self._history[-500:]
                self._key_store += max(0, kl // 512)

    def refresh(self, n: int = 200) -> Snapshot:
        self._advance()
        p = self.load_params()
        p.mean_photon = round(self._photons, 3)
        p.dead_time_us = self._dead_time_us
        # distance is known only once calibrated (fiber_delay set by full_init)
        if self._state == PRODUCING:
            d = distance_km_from_fiber_delay(self._fiber_delay)
            p.distance_km = round(d, 2) if d else None
        else:
            p.distance_km = None
        snap = Snapshot(status=self._state, error=self._error, params=p)
        snap.reachable = self._state != DOWN
        if self._state != DOWN:
            snap.stats = self._history[-n:]
            snap.key_store = self._key_store
            # counts follow from mu and the channel loss (during calibration the
            # link isn't aligned, so only a fraction of clicks land)
            clicks = self._expected_clicks(self._photons)
            if self._state == CALIBRATING:
                clicks *= 0.4
            clicks = max(0, int(clicks + random.gauss(0, max(3, 0.02 * clicks))))
            snap.counts = Counts(datetime.now(), clicks, clicks // 2, clicks - clicks // 2)
            snap.loss_db = loss_db_from_counts(clicks, self._photons, self._dead_time_us)
        return snap

    # ---- actions --------------------------------------------------------
    def demo_action(self, name: str, log, **kw):
        """Run a fake action, streaming lines to `log(line)`; return an exit note."""
        def emit(msg):
            log(msg)
            time.sleep(0.25)

        if name == "shutdown":
            emit("[demo] sending shutdown to alice, bob via restartd ...")
            emit("[demo] alice: shutdown sent")
            emit("[demo] bob:   shutdown sent")
            self._error = ""
            self._enter(DOWN)
            emit("[demo] nodes powering off.")
            return
        if name == "wake_produce":
            emit(f"[demo] wake.sh {self.qline}  (Wake-on-LAN)")
            emit("[demo] waiting for SSH ... up")
            emit("[demo] WRS link + PCIe ok; services active")
            emit("[demo] hws.py --full_init: calibrating ...")
            self._error = ""
            self._enter(CALIBRATING)
            emit("[demo] start done -> /tmp/qkd_ready raised; producing shortly.")
            return
        if name == "full_init":
            emit("[demo] hws.py --full_init on a running system ...")
            for step in ("init", "config_laser", "sync_gc", "find_vca",
                         "loop_find_gates", "fs_a", "adjust_am", "start"):
                emit(f"[demo]   {step} done")
            self._error = ""
            self._enter(CALIBRATING)
            return
        if name == "auto_control":
            emit("[demo] hws.py --auto_control: re-tuning to lower QBER ...")
            emit("[demo]   adjust_soft_gates / adjust_am_qber done")
            return
        if name == "set_dead_time":
            us = int(round(float(kw["us"])))
            self._dead_time_us = float(us)
            p = self.load_params()
            p.dead_time_us = float(us)
            self.save_params(p)
            emit(f"[demo] hw_bob.py set --spd_deadtime {us}: dead time -> {us} us")
            return
        if name == "set_mean_photon":
            if kw.get("mode") == "photons":
                val = float(kw["value"])
                self._photons = val
                p = self.load_params()
                p.mean_photon = val
                self.save_params(p)
                emit(f"[demo] hw_alice.py set --photons {val}: mean photon # -> {val} /pulse")
                return
            # counts mode: find_vca drives the VCA (hence mu) to hit a click target.
            # clicks are ~linear in mu here, so invert with the per-unit-mu slope.
            target = int(kw["value"])
            slope = self._expected_clicks(1.0)
            self._photons = round(min(3.0, max(0.003, target / slope)), 3) if slope else self._photons
            emit(f"[demo] hws.py --command find_vca_{target}: driving VCA to {target} counts ...")
            emit(f"[demo] success: ~{target} counts (mu ~= {self._photons} photons/pulse)")
            return
        emit(f"[demo] unknown action {name}")


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------
def make_backend(qline: str, config_root: str, demo: bool, use_localhost: bool) -> Backend:
    if demo:
        return DemoBackend(qline, config_root)
    return RealBackend(qline, config_root, use_localhost)
