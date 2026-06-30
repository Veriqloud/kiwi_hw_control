#!/usr/bin/env python3
"""
wrs_logger - record White Rabbit (eth_wrs) link state to ~/log/wrs.log over time.

Why: there was no network history, so "did the WRS drop during the session?" was
unanswerable. This samples the WRS carrier (/sys/class/net/eth_wrs/carrier) and the
presence of the 192.168.10.x IP on eth_wrs every INTERVAL seconds and appends a
timestamped line whenever the state CHANGES, plus a periodic heartbeat so the log
proves the monitor is alive and shows "still up" across long quiet periods. A drop
then shows up as a `CHANGE carrier=0` / `ip=none` line with its exact timestamp.

Read it over TCP with logd (no ssh):  logs.py --use_localhost <alice|bob> tail wrs

No root needed. Persisted via an @reboot user-cron entry; a flock guard (in the cron
command) keeps a single instance. Runs on both nodes; each logs its own eth_wrs.
"""
import os
import time
import shutil
import subprocess
import datetime

IFACE = "eth_wrs"
SUBNET = "192.168.10"
CARRIER_PATH = f"/sys/class/net/{IFACE}/carrier"
LOG_PATH = os.path.expanduser("~/log/wrs.log")
INTERVAL = 5      # seconds between samples
HEARTBEAT = 300   # seconds: emit an "ok" line even when state is unchanged

# Resolve `ip` absolutely: cron @reboot runs with a minimal PATH that often lacks /usr/sbin.
IP_BIN = shutil.which("ip") or next(
    (p for p in ("/usr/sbin/ip", "/sbin/ip", "/usr/bin/ip", "/bin/ip") if os.path.exists(p)),
    "ip",
)


def read_carrier():
    # carrier: "1" up, "0" down. Read errors usually mean the interface is gone
    # (ENODEV) or admin-down (EINVAL) -> report that rather than crashing.
    try:
        with open(CARRIER_PATH) as f:
            return f.read().strip() or "empty"
    except OSError as e:
        return f"noiface({e.errno})"


def read_ip():
    try:
        out = subprocess.run(
            [IP_BIN, "-o", "-4", "addr", "show", IFACE],
            capture_output=True, text=True, timeout=5,
        ).stdout
    except Exception:
        return None
    for tok in out.split():
        if tok.startswith(SUBNET):
            return tok.split("/")[0]
    return None


def sample():
    ip = read_ip()
    return f"carrier={read_carrier()} ip={ip if ip else 'none'}"


def log(line):
    ts = datetime.datetime.now().isoformat(timespec="milliseconds")
    with open(LOG_PATH, "a") as f:
        f.write(f"{ts} {line}\n")
        f.flush()


def main():
    log(f"wrs_logger started (iface={IFACE} subnet={SUBNET} "
        f"interval={INTERVAL}s heartbeat={HEARTBEAT}s ip_bin={IP_BIN})")
    last = None
    last_emit = 0.0
    while True:
        s = sample()
        now = time.time()
        if s != last:
            log(f"{'INIT' if last is None else 'CHANGE'} {s}")
            last = s
            last_emit = now
        elif now - last_emit >= HEARTBEAT:
            log(f"ok {s}")
            last_emit = now
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
