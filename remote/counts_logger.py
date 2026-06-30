#!/usr/bin/env python3
"""
counts_logger - record detector counts to ~/log/counts.log and flag drops to zero.

Sibling of wrs_logger. Runs on the detector node (Bob). It polls the *nonblocking*
counts query every INTERVAL seconds and appends to ~/log/counts.log: a periodic
heartbeat (current total/click0/click1, for a rate trend) plus an immediate ALERT
the moment total counts drop to 0 (detector dark / FPGA stopped / lost calibration)
and a RECOVER line when they come back. A "drop to 0 counts" is the trigger event.

Nonblocking query: this mirrors lib/fpga.get_counts() / ctl_bob.counts_fast() — a
pure mmap READ of the click0/click1/total registers at offset 56 of the shared
/dev/xdma0_user BAR. It is read-only, so it is safe to poll concurrently with hw/mon
and with a running session (unlike request_counts(), which WRITES a start bit, and
unlike the exclusive c2h DMA channels that calibration uses).

Read it over TCP via logd (no ssh):  logs.py --use_localhost bob tail counts
                                      logs.py --use_localhost bob grep ALERT counts

No root needed. Persisted via an @reboot user-cron entry; a flock guard (in the cron
command) keeps a single instance.
"""
import os
import time
import mmap
import datetime

DEVICE = "/dev/xdma0_user"
COUNTS_ADDR = 56          # offset of [click0, click1, total] u32 triplet (see lib/fpga.get_counts)
LOG_PATH = os.path.expanduser("~/log/counts.log")
INTERVAL = 5              # seconds between samples (fast enough to catch a drop to 0)
HEARTBEAT = 60            # seconds: emit a trend line even when not at a 0-transition
ZERO_THRESHOLD = 0        # "drop to 0 counts": total <= this fires the ALERT


def read_counts():
    # Pure mmap read of the free-running counts register; returns (total, click0, click1)
    # or None if the device can't be read (driver gone / FPGA wedged).
    try:
        with open(DEVICE, "r+b", buffering=0) as fd:
            with mmap.mmap(fd.fileno(), 0x1000, offset=0) as mm:
                click0 = int.from_bytes(mm[COUNTS_ADDR:COUNTS_ADDR + 4], "little")
                click1 = int.from_bytes(mm[COUNTS_ADDR + 4:COUNTS_ADDR + 8], "little")
                total = int.from_bytes(mm[COUNTS_ADDR + 8:COUNTS_ADDR + 12], "little")
        return total, click0, click1
    except OSError as e:
        return None, e


def log(line):
    ts = datetime.datetime.now().isoformat(timespec="milliseconds")
    with open(LOG_PATH, "a") as f:
        f.write(f"{ts} {line}\n")
        f.flush()


def main():
    log(f"counts_logger started (device={DEVICE} addr={COUNTS_ADDR} "
        f"interval={INTERVAL}s heartbeat={HEARTBEAT}s zero_threshold={ZERO_THRESHOLD})")
    in_zero = None        # None until first sample; then True/False
    last_emit = 0.0
    while True:
        c = read_counts()
        now = time.time()
        if c[0] is None:
            # device unreadable -> treat as a (severe) zero/fault condition, log on entry
            if in_zero is not True:
                log(f"ALERT counts unreadable ({DEVICE}: {c[1]})")
                in_zero = True
                last_emit = now
            elif now - last_emit >= HEARTBEAT:
                log(f"ok-fault counts still unreadable ({DEVICE}: {c[1]})")
                last_emit = now
            time.sleep(INTERVAL)
            continue

        total, click0, click1 = c
        stats = f"total={total} click0={click0} click1={click1}"
        zero = total <= ZERO_THRESHOLD

        if in_zero is None:
            log(f"INIT {stats}")
            last_emit = now
        elif zero and not in_zero:
            log(f"ALERT counts dropped to 0 ({stats})")
            last_emit = now
        elif not zero and in_zero:
            log(f"RECOVER counts back ({stats})")
            last_emit = now
        elif now - last_emit >= HEARTBEAT:
            log(f"{'ok-zero' if zero else 'ok'} {stats}")
            last_emit = now

        in_zero = zero
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
