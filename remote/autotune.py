#!/usr/bin/env python3
"""
autotune - periodic live re-tune of the running qline link (cron, every 10 min).

Runs pol_bob, adjust_soft_gates, adjust_am_qber against the LOCAL hws server to
counter slow drift, and logs the outcome to ~/log/autotune.log (read over TCP via
logd:  logs.py --use_localhost alice tail autotune).

WHY THIS IS SAFE NEXT TO MANUAL COMMANDS
  * hws_alice.py is single-threaded and single-connection: it only accept()s a new
    client after the current one disconnects, so this NEVER runs concurrently with a
    manual `hws.py` session -- the two are serialized by the server itself.
  * Each hws command sets/clears the /tmp/calibrating.txt flag itself and only
    `start` arms /tmp/qkd_ready, so these adjust steps neither stop the node nor
    leave the system stuck "calibrating" (see hws_alice.py main loop).
  * It SKIPS (does nothing) unless the link is actually up and tunable:
      - /tmp/qkd_ready exists            (system calibrated; node meant to be running)
      - /tmp/calibrating.txt != calibrating  (no full_init / manual op mid-command)
      - /tmp/node_stats.csv is fresh     (node producing rounds -> live QBER exists)
  * A flock guard (in the cron line) stops overlapping runs; a socket timeout makes
    it give up quickly ('busy') instead of queuing behind a manual op.

Disable by removing the autotune line from `crontab -e`; one cycle is exactly the
manual `hws.py --command pol_bob ; --command adjust_soft_gates ; --command
adjust_am_qber` you would run by hand.
"""
import os
import json
import time
import socket
import datetime

NETWORK_FILE = os.path.expanduser("~/config/network.json")
LOG_PATH = os.path.expanduser("~/log/autotune.log")
# pol_bob first (it shifts polarisation, which feeds gates+AM), then gates, then AM.
COMMANDS = ["pol_bob", "adjust_soft_gates", "adjust_am_qber"]

READY_FLAG = "/tmp/qkd_ready"
CALIB_FLAG = "/tmp/calibrating.txt"
STATS_FILE = "/tmp/node_stats.csv"
STATS_MAX_AGE = 120          # s: node must have written a round at least this recently
CONNECT_TIMEOUT = 10         # s
CMD_TIMEOUT = 120            # s to wait for each command's reply


def log(line):
    ts = datetime.datetime.now().isoformat(timespec="seconds")
    with open(LOG_PATH, "a") as f:
        f.write(f"{ts} {line}\n")
        f.flush()


def calibrating():
    try:
        with open(CALIB_FLAG) as f:
            return f.read().strip() == "calibrating"
    except OSError:
        return False


def stats_fresh():
    try:
        return (time.time() - os.path.getmtime(STATS_FILE)) <= STATS_MAX_AGE
    except OSError:
        return False


def precheck():
    if not os.path.isfile(READY_FLAG):
        return "system not calibrated (/tmp/qkd_ready absent)"
    if calibrating():
        return "calibration/manual op in progress (/tmp/calibrating.txt)"
    if not stats_fresh():
        return f"node not producing rounds (/tmp/node_stats.csv older than {STATS_MAX_AGE}s)"
    return None


# --- minimal hws wire protocol (mirrors local/hws.py: 1-byte length prefix + utf8) ---
def sendc(sock, c):
    b = c.encode()
    sock.sendall(len(c).to_bytes(1, "little") + b)


def rcvc(sock):
    l = int.from_bytes(sock.recv(1), "little")
    buf = b""
    while len(buf) < l:
        chunk = sock.recv(l - len(buf))
        if not chunk:
            break
        buf += chunk
    return buf.decode(errors="replace").strip()


def main():
    skip = precheck()
    if skip:
        log(f"skipped: {skip}")
        return

    try:
        net = json.load(open(NETWORK_FILE))
        host, port = net["ip"]["alice"], int(net["port"]["hws"])
    except Exception as e:
        log(f"skipped: cannot read {NETWORK_FILE} ({e})")
        return

    sock = socket.socket()
    sock.settimeout(CONNECT_TIMEOUT)
    try:
        sock.connect((host, port))
    except OSError as e:
        log(f"skipped: cannot reach hws {host}:{port} ({e})")
        return

    log(f"start autotune cycle ({', '.join(COMMANDS)})")
    sock.settimeout(CMD_TIMEOUT)
    try:
        for cmd in COMMANDS:
            # re-check the calibrating flag between steps: if a manual op slipped in,
            # stop rather than fight it (the server would serialise us anyway).
            if calibrating():
                log(f"aborted before {cmd}: calibration/manual op started")
                break
            t0 = time.time()
            sendc(sock, cmd)
            reply = rcvc(sock)
            dt = time.time() - t0
            tag = "WARN" if ("fail" in reply.lower() or "error" in reply.lower()) else "ok"
            log(f"{tag} {cmd} -> {reply!r} ({dt:.1f}s)")
        else:
            log("autotune cycle complete")
    except socket.timeout:
        log("aborted: hws busy/timeout (manual op likely holding the connection)")
    except OSError as e:
        log(f"aborted: socket error ({e})")
    finally:
        try:
            sendc(sock, "")        # empty command -> server ends its client loop cleanly
        except OSError:
            pass
        sock.close()


if __name__ == "__main__":
    main()
