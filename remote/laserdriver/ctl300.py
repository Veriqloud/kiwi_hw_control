#!/usr/bin/env python3
"""Koheron CTL300E bring-up and query over the FT232H UART bridge.

115200 8N1, no flow control, commands terminated \\r\\n. The board echoes each
command, returns the value, then a ">>" prompt.

Every Alice carries two drivers, one per laser, so every invocation names the
laser it means:

  -w 1310                   LD-PD 1310 nm
  -w 1510                   LD4B 1510 nm DFB

The two FT232H bridges report no serial number, so which of them becomes
/dev/ttyUSB0 is decided by enumeration order and changes across reboots -- the
`ttylaser` udev symlink matches both and lands on whichever came up last.  So
-w does not resolve to a fixed device node.  It reads `ilmax` off each driver
and picks the one whose limit matches the laser asked for: `save` writes ilmax,
the board keeps it across power cycles, and 120 vs 350 mA tells the two lasers
apart with no room for a near miss.  A board still at the 400 mA power-on
default carries no configuration and therefore no identity; it can only be
reached with an explicit --port, which is what programming a fresh board needs.

Subcommands:
  query                     read-only dump of the interesting registers
  up  [-c <mA>] -r <ohm>    full bring-up: TEC, settle, laser on
  arm / disarm              laser on/off with the TEC left running; arm also
                            enables tprot, which the board defaults to off
  temp -T <C>               move the TEC setpoint with the laser running
  down                      laser off, TEC off

Bring-up order matters. The protection window (rtmin/rtmax) is applied *after*
the TEC reaches setpoint: an unstabilised board sits at ambient, which on a warm
day is close enough to the hot limit to trip the moment it is armed.

Current and limit are **programmed parameters, not per-session ones**.  Each
driver carries a saved per-laser configuration, so:

  * `ilaser` is written only when `-c` is given.  Without it, `up`, `arm` and
    `save` leave the setpoint alone and the laser comes up at whatever is
    programmed.  `save -c` persists the setpoint, so a board that has been
    programmed arms at its own operating current with no `-c` on the command
    line.
  * `ilmax` is written only by `save`.  `up` reads it back and warns rather than
    setting it -- 400 mA is the board's power-on default, so seeing that means
    the saved config did not load, not that the limit needs writing.

Program a board once per laser.  A fresh board is still at ilmax 400 and cannot
be found by -w yet, so name it by port the first time; afterwards -w finds it:

    save -w 1310 --port /dev/serial/by-path/<...> -c 200   # LD-PD 1310
    save -w 1510 --port /dev/serial/by-path/<...> -c 115   # LD4B 1510

`--ilmax`, `-r/--rtset`, `--rtmin` and `--rtmax` default to the values for the
laser named by -w (see LASERS below); an explicit flag still wins.  The LD4B
1510 (S/N 2600935/36) has a spec MAX Iop of 120 mA, so its `--ilmax` is 120 and
must not be raised.  `-c` has no default at all, per-laser or otherwise -- an
absent -c leaves the programmed setpoint alone.
"""
import argparse
import fcntl, glob, math, os, re, sys, termios, time

# The bridges have no serial number, so the by-path names -- which carry the USB
# port the driver is plugged into -- are the only stable handles on them.
PORT_GLOB = "/dev/serial/by-path/*-port0"

# Per-laser saved configuration.  `ilmax` doubles as the board's identity: it is
# part of what `save` persists, and the two limits are 230 mA apart.
LASERS = {
    1310: dict(model="LD-PD 1310", ilmax=350.0, rtset=9939.4,
               rtmin=8144.6, rtmax=12122.9),
    1510: dict(model="LD4B 1510", ilmax=120.0, rtset=9939.4,
               rtmin=7986.9, rtmax=12471.3),
}

# The board's power-on ilmax.  50 mA above the LD-PD's absolute maximum and 280
# above the LD4B's, so it is never a configured value -- seeing it means the
# saved config did not load.
UNPROGRAMMED_ILMAX = 400.0

QUERY_SET = ["version", "err", "lason", "tecon", "lckon", "tprot", "ilmax",
             "ilaser", "vlaser", "iphd", "rtset", "rtact", "rtmin", "rtmax",
             "itec", "vtec", "tboard"]


class DriverUnavailable(Exception):
    """This driver could not be opened; another one may still be the right one."""


class CTL300:
    def __init__(self, port):
        if not os.path.exists(port):
            raise DriverUnavailable(f"{port} does not exist — driver unplugged?")
        try:
            self.fd = os.open(port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        except PermissionError:
            raise DriverUnavailable(f"no permission to open {port} — see "
                                    "laserdriver/99-ftdi-laserdriver.rules")
        self.port = port
        # Two processes on one tty interleave their replies, and a command that
        # reads back someone else's answer looks exactly like a register refusing
        # to take a value -- including on `lason`, where that reads as a laser
        # that will not switch off.  Take the port exclusively instead.
        try:
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(self.fd)
            raise DriverUnavailable(f"{port} is already open in another process — "
                                    "finish or stop that one first")
        self._configure()
        time.sleep(0.1)
        # Opening the port can wake a banner and a prompt out of the board.  This
        # one drain must wait out the full silence rather than stopping at the
        # first ">>", or the tail of that banner lands in the middle of the first
        # real reply and the first command of the session reads back garbage.
        self._drain(0.3, until_prompt=False)
        self.parse_failures = []

    def _configure(self):
        cc = list(termios.tcgetattr(self.fd)[6])
        cc[termios.VMIN] = 0
        cc[termios.VTIME] = 0
        termios.tcsetattr(self.fd, termios.TCSANOW,
                          [0, 0, termios.CS8 | termios.CREAD | termios.CLOCAL, 0,
                           termios.B115200, termios.B115200, cc])
        termios.tcflush(self.fd, termios.TCIOFLUSH)

    def _drain(self, timeout=0.4, until_prompt=True):
        # The board finishes every reply with its ">>" prompt, so stop there
        # rather than sitting out the full idle timeout -- that turns a command
        # from ~0.4 s into ~5 ms, which is what makes stepped scans practical.
        # The timeout stays as the fallback for a reply that never prompts.
        buf, last = b"", time.time()
        while time.time() - last < timeout:
            try:
                chunk = os.read(self.fd, 4096)
            except BlockingIOError:
                chunk = b""
            if chunk:
                buf, last = buf + chunk, time.time()
                if until_prompt and buf.rstrip().endswith(b">>"):
                    break
            else:
                time.sleep(0.001)
        return buf

    def cmd(self, text):
        """Send a command, return the response line with echo and prompt stripped."""
        termios.tcflush(self.fd, termios.TCIFLUSH)
        os.write(self.fd, (text + "\r\n").encode())
        raw = self._drain().decode("ascii", "replace")
        lines = [ln.strip() for ln in raw.replace(">>", "\n").splitlines()]
        lines = [ln for ln in lines if ln and ln != text.strip()]
        return lines[0] if lines else ""

    def num(self, text, tries=3):
        # A reply that does not parse is a framing problem, not an answer -- ask
        # again rather than reporting None, which callers read as "the register
        # is not what I asked for" and escalate into an alarming failure.
        for _ in range(tries):
            raw = self.cmd(text)
            m = re.match(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", raw)
            if m:
                return float(m.group())
            # Keep the evidence: these are rare and hard to catch in the act.
            self.parse_failures.append((text, raw))
            time.sleep(0.05)
        return None

    def set(self, name, value, tol=1e-6):
        """Write a register and verify it read back."""
        self.cmd(f"{name} {value}")
        got = self.num(name)
        if got is None or abs(got - float(value)) > max(tol, abs(value) * 1e-4):
            sys.exit(f"error: {name} readback {got}, expected {value} — aborting")
        return got

    def close(self):
        os.close(self.fd)


# A dark laser sits near vlaser 0.01 V / iphd 0.003 mA; an LD-PD 1310 lasing at
# 200 mA is ~1.4 V / ~0.27 mA.  The thresholds sit an order of magnitude above
# dark and an order below emitting, so no plausible reading is ambiguous.
#
# !! The LD4B 1510 units have NO monitor photodiode, so iphd reads ~0.003 mA
# whether they are dark or lasing (measured 2026-08-06 at 120 mA).  verify_dark
# still fails safe -- iphd never falsely reports emission, and vlaser goes to
# ~1.44 V when lasing -- but on this laser the iphd/vlaser cross-check below is
# not redundant: vlaser is the only channel carrying information.  Confirm dark
# on the power meter before unmating anything in the 1510 band.
DARK_VLASER, DARK_IPHD = 0.15, 0.03


def verify_dark(d, timeout=3.0):
    """Wait for the laser to actually go dark, then confirm it from three registers.

    Switching off is not instant.  Measured on this board after `lason 0`: lason
    itself still reads 1 for ~80 ms, iphd falls to dark at ~150 ms, and vlaser
    decays to dark at ~470 ms.  So this has to poll -- a single immediate readback
    reports a laser that is on, which is true at that instant and useless as an
    answer to "is it safe to touch the fiber".

    `lason` alone is also a single point of failure: one reply that does not parse
    and the caller cannot tell "the laser is still on" from "I did not hear the
    answer" -- and those want opposite reactions from whoever is at the bench.
    vlaser and iphd are physical consequences of emission, so agreement between
    them settles the question whichever way lason reads.
    """
    t0 = time.time()
    while True:
        lason, vlaser, iphd = d.num("lason"), d.num("vlaser"), d.num("iphd")
        dark = (vlaser is not None and vlaser < DARK_VLASER
                and iphd is not None and iphd < DARK_IPHD)
        if lason == 0 and dark:
            return
        if time.time() - t0 > timeout:
            break
        time.sleep(0.05)
    detail = (f"  after waiting {time.time()-t0:.1f} s\n"
              f"  lason  {lason}\n"
              f"  vlaser {vlaser} V   (dark < {DARK_VLASER}, ~1.4 lasing)\n"
              f"  iphd   {iphd} mA    (dark < {DARK_IPHD}, ~0.27 lasing)")
    if d.parse_failures:
        detail += f"\n  unparseable replies this session: {d.parse_failures[-3:]}"
    if dark:
        # Every physical indicator says no light.  Report it rather than sending
        # someone away from a bench that is actually safe.
        print(f"warning: lason read back {lason}, but vlaser and iphd both say dark\n"
              f"{detail}\n  treating as off — confirm on the power meter", file=sys.stderr)
        return
    sys.exit("error: laser is still emitting — do NOT touch the fiber\n"
             f"{detail}\n"
             "  re-run 'ctl300.py disarm', then check the meter reads dark")


def driver_ports():
    """The by-path names of the drivers, one per physical bridge.

    /dev/serial/by-path lists every device twice, once under `usb-0:` and once
    under `usbv2-0:`; both are the same tty.  Opening the duplicate of a board
    already held would fail the exclusive flock and report it as busy, so
    collapse them by the node they resolve to.
    """
    by_node = {}
    for port in sorted(glob.glob(PORT_GLOB)):
        by_node.setdefault(os.path.realpath(port), port)
    return sorted(by_node.values())


def open_driver(wavelength, explicit_port=None):
    """Open the driver of `wavelength`, identified by the ilmax it has saved.

    Opening each candidate in turn is what makes this safe against the bridges
    having no serial: the board is asked which laser it is configured for
    instead of being inferred from a device node that moves.  A board that is
    not the one asked for is closed again untouched -- reading ilmax writes
    nothing.

    Refusing on no match is the point of the function.  The failure this guards
    against is arming the 1310 board while meaning the 1510: `-c 200` into a
    laser whose absolute maximum is 120 mA destroys it, and a mixed-up device
    node is exactly how that happens.
    """
    spec = LASERS[wavelength]
    if explicit_port:
        d = CTL300(explicit_port)
        ilmax = d.num("ilmax")
        if ilmax != spec["ilmax"]:
            print(f"warning: {explicit_port} has ilmax {ilmax} mA, but "
                  f"{wavelength} nm ({spec['model']}) expects {spec['ilmax']} mA\n"
                  "  proceeding because --port was given explicitly — make sure "
                  "this is the board you mean", file=sys.stderr)
        return d

    matched, others = None, []
    for port in driver_ports():
        try:
            d = CTL300(port)
        except DriverUnavailable as e:
            others.append(f"{port}: {e}")
            continue
        ilmax = d.num("ilmax")
        if ilmax == spec["ilmax"] and matched is None:
            matched = d
            continue
        others.append(f"{port}: ilmax {ilmax} mA" +
                      ("  (unprogrammed — power-on default)"
                       if ilmax == UNPROGRAMMED_ILMAX else ""))
        d.close()

    if matched is None:
        detail = "\n".join("  " + o for o in others) or "  (no drivers found)"
        sys.exit(f"error: no driver is configured for {wavelength} nm "
                 f"({spec['model']}, ilmax {spec['ilmax']} mA)\n"
                 f"{detail}\n"
                 "  a board at 400 mA has no saved config and cannot be "
                 "identified — program it with an explicit --port, e.g.\n"
                 f"    ctl300.py save -w {wavelength} --port <by-path> -c <mA>")
    print(f"  driver       {matched.port}\n"
          f"  laser        {wavelength} nm  ({spec['model']})")
    return matched


def do_query(d):
    for q in QUERY_SET:
        print(f"  {q:8} {d.cmd(q)}")


def do_up(d, current, rtarget, rtmin, rtmax, settle_tol, timeout):
    err = d.cmd("err")
    print(f"  err          {err}" + ("  (latched, clearing)" if err.strip() != "0" else ""))
    if err.strip() != "0":
        # 0x100 LASER_OVERTEMPERATURE is expected after any TEC-off interval in a
        # room warmer than the hot limit. Clear it, then re-read: anything that
        # survives a clear is a live fault and must not be run through.
        d.cmd("errclr")
        again = d.cmd("err")
        if again.strip() != "0":
            sys.exit(f"error: err={again} persists after errclr — live fault, aborting")
        print("  errclr       ok, err now 0")

    # ilmax belongs to the saved configuration -- `save` writes it, `up` does
    # not.  Read it back instead: 400 mA is the power-on default, 50 mA above the
    # LD-PD's absolute maximum and 280 above the LD4B's, so finding it here means
    # this board came up on defaults rather than on its own config.
    ilmax = d.num("ilmax")
    print(f"  ilmax        {ilmax} mA  (limit, not written)")
    if ilmax == 400:
        print("  !! ilmax is at the 400 mA power-on default -- this board did not "
              "load its saved config.\n"
              "     Check CFG is tied to 3V3 and `save` it before running it up.")
    print(f"  rtset        {d.set('rtset', rtarget)} ohm")

    d.cmd("tecon 1")
    if d.num("tecon") != 1:
        sys.exit("error: tecon did not enable — aborting")
    print("  tecon        1  (TEC enabled)")

    print(f"\n  settling to {rtarget} ohm (tol +/-{settle_tol}), timeout {timeout}s")
    t0, settled_at = time.time(), None
    while time.time() - t0 < timeout:
        rt, it = d.num("rtact"), d.num("itec")
        dev = abs(rt - rtarget)
        print(f"    t={time.time()-t0:6.1f}s  rtact={rt:9.1f}  dev={dev:7.1f}  itec={it:+.4f} A")
        if dev <= settle_tol:
            if settled_at is None:
                settled_at = time.time()
            elif time.time() - settled_at >= 10:
                break
        else:
            settled_at = None
        time.sleep(5)
    else:
        sys.exit(f"error: TEC did not settle within {timeout}s — check PID gains")
    print(f"  settled after {time.time()-t0:.0f}s\n")

    # Protection window only now that we are at setpoint and safely inside it.
    print(f"  rtmin        {d.set('rtmin', rtmin)} ohm  (hot limit)")
    print(f"  rtmax        {d.set('rtmax', rtmax)} ohm  (cold limit)")
    if d.num("tprot") != 1:
        d.cmd("tprot 1")
    print("  tprot        1")

    if current is None:
        print(f"  ilaser       {d.num('ilaser')} mA  (programmed, unchanged)")
    else:
        print(f"  ilaser       {d.set('ilaser', current)} mA")
    d.cmd("lason 1")
    if d.num("lason") != 1:
        sys.exit("error: lason did not enable — aborting")
    print("  lason        1")
    time.sleep(1.5)  # ldelay defaults to 1000 ms

    print("\n  --- state after bring-up ---")
    do_query(d)


# Thermistor law: Rt = 10 kOhm * exp(3600 * (1/T[K] - 1/298)).  The LD-PD and
# LD4B datasheets quote it identically (10 kOhm at 25 C, B = 3600 K), so these
# constants and the rtset defaults serve both bands.
# Note the reference is 298 K exactly, so rtset 10000 is 24.85 C, not 25.00 --
# hence the 9939.4 default, which is 25.00 C and matches the LD4B test sheet.
THERM_B, THERM_T0, THERM_R0 = 3600.0, 298.0, 10000.0


def rt_of_c(celsius):
    return THERM_R0 * math.exp(THERM_B * (1.0 / (celsius + 273.15) - 1.0 / THERM_T0))


def c_of_rt(rt):
    return THERM_B / (math.log(rt / THERM_R0) + THERM_B / THERM_T0) - 273.15


def do_temp(d, celsius, window, tol, timeout):
    """Move the TEC setpoint with the laser running, without tripping protection.

    `rtmin`/`rtmax` are a *resistance* window, so the hot limit is the LOW number
    and it moves the opposite way to the temperature.  Going from 25 C to 30 C
    walks rtact from 10000 down to 8145 -- straight through a stock rtmin of 8000,
    which would cut the laser mid-transition.  So the window is opened to cover
    both the old and the new setpoint first, and closed around the new one only
    once the chip is there.
    """
    if d.num("tecon") != 1:
        sys.exit("error: TEC is not enabled — run 'up' first")
    target = rt_of_c(celsius)
    hot, cold = rt_of_c(celsius + window), rt_of_c(celsius - window)
    now = d.num("rtact")
    print(f"  target       {celsius:.2f} C = {target:.0f} ohm   "
          f"(now {now:.0f} ohm = {c_of_rt(now):.2f} C)")
    print(f"  window       +/-{window:.1f} C = {hot:.0f}..{cold:.0f} ohm")

    # Open the protection window across both setpoints before moving.
    print(f"  rtmin        {d.set('rtmin', round(min(hot, d.num('rtmin')), 1))} ohm  (opened)")
    print(f"  rtmax        {d.set('rtmax', round(max(cold, d.num('rtmax')), 1))} ohm  (opened)")
    print(f"  rtset        {d.set('rtset', round(target, 1))} ohm")

    t0, settled_at = time.time(), None
    while time.time() - t0 < timeout:
        rt, it = d.num("rtact"), d.num("itec")
        dev = abs(rt - target)
        print(f"    t={time.time()-t0:6.1f}s  rtact={rt:9.1f} ({c_of_rt(rt):5.2f} C)"
              f"  dev={dev:7.1f}  itec={it:+.4f} A")
        if dev <= tol:
            if settled_at is None:
                settled_at = time.time()
            elif time.time() - settled_at >= 10:
                break
        else:
            settled_at = None
        time.sleep(2)
    else:
        sys.exit(f"error: TEC did not settle within {timeout}s — setpoint left applied, "
                 "protection window still open")
    print(f"  settled after {time.time()-t0:.0f}s\n")

    print(f"  rtmin        {d.set('rtmin', round(hot, 1))} ohm  (hot limit, {celsius+window:.1f} C)")
    print(f"  rtmax        {d.set('rtmax', round(cold, 1))} ohm  (cold limit, {celsius-window:.1f} C)")
    if d.num("tprot") != 1:
        d.cmd("tprot 1")
    print(f"  tprot        1\n  lason        {d.cmd('lason')}   "
          f"vlaser {d.cmd('vlaser')} V   iphd {d.cmd('iphd')} mA")


def do_down(d):
    # tprot must go first: with the TEC off the chip drifts to ambient, and if
    # ambient sits outside rtmin..rtmax (a 31 C room against a 30 C hot limit)
    # that latches LASER_OVERTEMPERATURE every single time.
    d.cmd("lason 0")
    verify_dark(d)          # before tprot goes, while protection is still armed
    print(f"  lason        {d.cmd('lason')}")
    d.cmd("tprot 0")
    print(f"  tprot        {d.cmd('tprot')} (disarmed — chip is about to drift to ambient)")
    d.cmd("tecon 0")
    print(f"  tecon        {d.cmd('tecon')}")


def do_disarm(d):
    """Laser off, TEC left running — for swapping fibers between stages.

    Keeps the chip at setpoint so successive measurements stay thermally
    comparable, and avoids the ~25 s TEC re-settle a power cycle would cost.
    """
    d.cmd("lason 0")
    verify_dark(d)
    print(f"  lason        0    vlaser {d.cmd('vlaser')} V    iphd {d.cmd('iphd')} mA")
    print(f"  tecon        {d.cmd('tecon')} (left running)    rtact {d.cmd('rtact')} ohm")
    print("  laser disabled — verify dark on the power meter before unmating anything")


def do_arm(d, current):
    """Re-enable at a stated current, assuming the TEC is already locked.

    Arms `tprot` too.  The board's power-on default is `tprot 0` -- protection
    *disabled*, rtmin/rtmax ignored -- and it used to be `up` that turned it on
    at the end of its settle.  On a board whose saved config brings the TEC up
    already locked, `up` no longer runs every session and `arm` is the entry
    point, so without this the laser runs all session with nothing watching the
    thermistor.  It belongs here and not in the saved config: at power-up the
    chip sits at ambient, which on a warm day is past the hot limit, so a
    persisted `tprot 1` would latch 0x100 on every boot.
    """
    if d.num("tecon") != 1:
        sys.exit("error: TEC is not enabled — run 'up' instead")
    rt, rtset = d.num("rtact"), d.num("rtset")
    if abs(rt - rtset) > 50:
        sys.exit(f"error: rtact {rt} is {abs(rt-rtset):.0f} ohm off setpoint — not settled")

    # The settle check above is what makes this safe: it proves the chip is at
    # setpoint rather than at ambient.  Check the window explicitly anyway --
    # nothing guarantees rtset was saved inside rtmin..rtmax, and enabling
    # protection onto an out-of-window chip latches the fault it exists to
    # prevent.
    rtmin, rtmax = d.num("rtmin"), d.num("rtmax")
    if not rtmin < rt < rtmax:
        sys.exit(f"error: rtact {rt:.0f} is outside the protection window "
                 f"{rtmin:.0f}..{rtmax:.0f} ohm — refusing to arm tprot into a "
                 "latched fault; check rtset against the window")
    d.cmd("tprot 1")
    if d.num("tprot") != 1:
        sys.exit("error: tprot did not enable — refusing to arm an unprotected laser")
    print(f"  tprot        1    (window {rtmin:.0f}..{rtmax:.0f} ohm = "
          f"{c_of_rt(rtmax):.1f}..{c_of_rt(rtmin):.1f} C)")

    print(f"  ilmax        {d.num('ilmax')} mA (limit, unchanged)")
    if current is None:
        print(f"  ilaser       {d.num('ilaser')} mA  (programmed, unchanged)")
    else:
        print(f"  ilaser       {d.set('ilaser', current)} mA")
    d.cmd("lason 1")
    if d.num("lason") != 1:
        sys.exit("error: lason did not enable")
    time.sleep(1.5)  # ldelay
    print(f"  lason        1    vlaser {d.cmd('vlaser')} V    iphd {d.cmd('iphd')} mA")


def do_save(d, current, ilmax, rtarget, rtmin, rtmax, tecon):
    """Persist a per-laser configuration. Refuses to save with the laser armed.

    `lason` is part of the stored configuration and `ldelay` sets the gap between
    power-up and light, so a config saved with lason=1 produces a board that
    self-lases about a second after power is applied. Hence the hard refusal.
    """
    d.cmd("lason 0")
    verify_dark(d)          # polls: the bit lingers ~80 ms after the command
    print("  lason        0  (disarmed before save)")

    print(f"  ilmax        {d.set('ilmax', ilmax)} mA")
    if current is None:
        print(f"  ilaser       {d.num('ilaser')} mA  (setpoint, unchanged)")
    else:
        print(f"  ilaser       {d.set('ilaser', current)} mA  (setpoint)")
    print(f"  rtset        {d.set('rtset', rtarget)} ohm")
    print(f"  rtmin        {d.set('rtmin', rtmin)} ohm")
    print(f"  rtmax        {d.set('rtmax', rtmax)} ohm")
    d.cmd(f"tecon {int(tecon)}")
    print(f"  tecon        {d.num('tecon'):.0f}")

    if d.num("lason") != 0:            # re-check immediately before committing
        sys.exit("error: lason became non-zero — refusing to save")
    d.cmd("save")
    print("  save         issued\n")

    print("  --- live state after save ---")
    do_query(d)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("action", choices=["query", "up", "down", "save", "arm", "disarm", "temp"])
    p.add_argument("-w", "--wavelength", type=int, required=True, choices=sorted(LASERS),
                   help="which laser to address; selects the driver and the "
                        "ilmax/rtset/rtmin/rtmax defaults")
    p.add_argument("--port", default=None,
                   help="address this driver directly instead of finding it by "
                        "ilmax — needed for a board that is not programmed yet")
    p.add_argument("--tecon", type=int, default=1, choices=[0, 1],
                   help="TEC state to persist (save only)")
    # No default: an absent -c leaves the programmed setpoint alone (see the
    # module docstring).  contrast_run passes -c explicitly -- its own 200 mA
    # default -- so its current-ramp scan is unaffected by this.
    p.add_argument("-c", "--current", type=float, default=None,
                   help="ilaser, mA -- omit to keep the programmed setpoint")
    p.add_argument("-r", "--rtset", type=float, default=None,
                   help="thermistor setpoint, ohm (9939.4 = 25.00 C, the sheet's Tc)")
    p.add_argument("--ilmax", type=float, default=None,
                   help="software current limit, mA -- save only, up never writes it "
                        "(LD4B spec MAX Iop is 120, do not raise)")
    p.add_argument("--rtmin", type=float, default=None, help="hot limit, ohm")
    p.add_argument("--rtmax", type=float, default=None, help="cold limit, ohm")
    p.add_argument("--tol", type=float, default=20.0, help="settle tolerance, ohm")
    p.add_argument("--timeout", type=float, default=300.0, help="settle timeout, s")
    p.add_argument("-T", "--celsius", type=float, help="chip temperature setpoint, C (temp only)")
    p.add_argument("--window", type=float, default=5.5,
                   help="+/- C of protection window around the setpoint (temp only)")
    args = p.parse_args()

    spec = LASERS[args.wavelength]
    for key in ("ilmax", "rtset", "rtmin", "rtmax"):
        if getattr(args, key) is None:
            setattr(args, key, spec[key])

    try:
        d = open_driver(args.wavelength, args.port)
    except DriverUnavailable as e:
        sys.exit(f"error: {e}")
    try:
        if args.action == "query":
            do_query(d)
        elif args.action == "up":
            do_up(d, args.current, args.rtset, args.rtmin, args.rtmax,
                  args.tol, args.timeout)
        elif args.action == "save":
            do_save(d, args.current, args.ilmax, args.rtset, args.rtmin,
                    args.rtmax, args.tecon)
        elif args.action == "arm":
            do_arm(d, args.current)
        elif args.action == "disarm":
            do_disarm(d)
        elif args.action == "temp":
            if args.celsius is None:
                sys.exit("error: temp needs -T/--celsius")
            do_temp(d, args.celsius, args.window, args.tol, args.timeout)
        else:
            do_down(d)
    finally:
        d.close()
