#!/usr/bin/env python3
"""
fifo_logger - record the FPGA DDR FIFO status flags to ~/log/fifo.log over time.

Sibling of counts_logger / wrs_logger. The FIFO flags were previously only visible as
a momentary snapshot via mon's `get_fifo_status` (mon_readonly_probe) -- nothing
recorded them over time, so "what were the FIFO flags doing when the link wedged?"
was unanswerable after the fact. This fills that gap: it samples the flags every
INTERVAL seconds and appends a line on any state CHANGE, plus a periodic heartbeat so
the log proves the monitor is alive across long unchanged stretches -- exactly the
wrs_logger model.

Deliberately NOT an overflow alarm: these are FIFO fill/empty/idle flags, and a set
`*_full` flag tracks *FIFO occupancy*, which is ambiguous -- it can mean data is
flowing normally OR that the pipeline is backed up. mon itself just reports the raw
values and treats none of them as an error. So this logger records the time-series
and leaves interpretation to whoever reads it (correlate a CHANGE with an incident);
it does not hardcode a "bad value" threshold that would false-alarm. The one
unambiguous fault -- the device becoming unreadable (driver gone / FPGA wedged) -- is
the only condition that fires an ALERT.

What it reads: a pure mmap READ of the two DDR status registers at byte offsets 52 and
56 within the 0x1000 page of the shared /dev/xdma0_user BAR -- the exact registers
lib/fpga.ddr_status2() / Ddr_Status() decode, and the source of mon's get_fifo_status.
Read-only (no register writes), so it is safe to poll concurrently with hw/mon and a
running session, just like counts_logger's counts read (unlike the exclusive c2h DMA
channels, or rng_fifos_mon() which WRITES a trigger bit -- deliberately not sampled
here to keep this purely passive).

Decoded flags (see lib/fpga.Ddr_Status):
  reg52: vfifo_full(2b) vfifo_empty(2b) vfifo_idle(2b) gc_out_full gc_in_empty alpha_out_full
  reg56: gc_out_empty gc_in_full alpha_out_empty
The raw registers are logged too so a new decode can be recovered from history.

Runs on BOTH nodes (both have the DDR FIFOs). Read it over TCP via logd (no ssh):
    logs.py <alice|bob> tail fifo               # recent flags + heartbeats
    logs.py <alice|bob> grep CHANGE fifo         # flag transitions, with timestamps
    logs.py <alice|bob> grep ALERT fifo          # device unreadable (hard fault)

No root needed. Persisted via an @reboot user-cron entry; a flock guard (in the cron
command) keeps a single instance.
"""
import os
import time
import mmap
import datetime

DEVICE = "/dev/xdma0_user"
DDR_STATUS_OFFSET = 0x1000   # page offset of the DDR status registers (see lib/fpga.read)
REG_DDR = 52                 # ddr_fifos_status  (vfifo_*, gc_out_full, gc_in_empty, alpha_out_full)
REG_FIFO = 56                # fifos_status      (gc_out_empty, gc_in_full, alpha_out_empty)
LOG_PATH = os.path.expanduser("~/log/fifo.log")
INTERVAL = 5                 # seconds between samples
HEARTBEAT = 60               # seconds: emit an "ok" line even when unchanged


def read_flags():
    # Pure mmap read of the two DDR status registers; returns a dict of decoded
    # flags (+ raw regs), or None if the device can't be read (driver gone / wedged).
    try:
        with open(DEVICE, "r+b", buffering=0) as fd:
            with mmap.mmap(fd.fileno(), 0x1000, offset=DDR_STATUS_OFFSET) as mm:
                reg52 = int.from_bytes(mm[REG_DDR:REG_DDR + 4], "little")
                reg56 = int.from_bytes(mm[REG_FIFO:REG_FIFO + 4], "little")
    except OSError as e:
        return None, e

    return {
        # "full" flags (occupancy -- NOT inherently a fault; see module docstring)
        "vf": (reg52 & 0x180) >> 7,   # vfifo_full (2 bits)
        "gof": (reg52 >> 2) & 1,      # gc_out_full
        "gif": (reg56 & 0x10) >> 4,   # gc_in_full
        "aof": reg52 & 0x1,           # alpha_out_full
        # "empty" / idle flags (from the same two registers, free to include)
        "ve": (reg52 & 0x60) >> 5,    # vfifo_empty
        "vi": (reg52 & 0x600) >> 9,   # vfifo_idle
        "gie": (reg52 >> 1) & 1,      # gc_in_empty
        "goe": (reg56 & 0x4) >> 2,    # gc_out_empty
        "aoe": reg56 & 0x1,           # alpha_out_empty
        "raw": (reg52, reg56),
    }, None


FLAG_KEYS = ("vf", "gof", "gif", "aof", "ve", "vi", "gie", "goe", "aoe")


def fmt(f):
    return (f"vf={f['vf']} gof={f['gof']} gif={f['gif']} aof={f['aof']} | "
            f"ve={f['ve']} vi={f['vi']} gie={f['gie']} goe={f['goe']} aoe={f['aoe']} "
            f"| reg52={f['raw'][0]:#x} reg56={f['raw'][1]:#x}")


def flag_key(f):
    # everything except the raw regs -- so a CHANGE is a genuine flag transition,
    # not just a raw-register counter wiggle.
    return tuple(f[k] for k in FLAG_KEYS)


def log(line):
    ts = datetime.datetime.now().isoformat(timespec="milliseconds")
    with open(LOG_PATH, "a") as f:
        f.write(f"{ts} {line}\n")
        f.flush()


def main():
    log(f"fifo_logger started (device={DEVICE} offset={DDR_STATUS_OFFSET:#x} "
        f"regs={REG_DDR},{REG_FIFO} interval={INTERVAL}s heartbeat={HEARTBEAT}s)")
    last_key = None      # last decoded flag tuple (None until first sample)
    last_emit = 0.0
    unreadable = False
    while True:
        f, err = read_flags()
        now = time.time()

        if f is None:
            # device unreadable -> the one unambiguous fault; log on entry then heartbeat
            if not unreadable:
                log(f"ALERT fifo unreadable ({DEVICE}: {err})")
                unreadable = True
                last_emit = now
            elif now - last_emit >= HEARTBEAT:
                log(f"ok-fault fifo still unreadable ({DEVICE}: {err})")
                last_emit = now
            time.sleep(INTERVAL)
            continue

        key = flag_key(f)
        if unreadable:
            log(f"RECOVER fifo readable again ({fmt(f)})")
            unreadable = False
            last_key, last_emit = key, now
        elif last_key is None:
            log(f"INIT {fmt(f)}")
            last_key, last_emit = key, now
        elif key != last_key:
            log(f"CHANGE {fmt(f)}")
            last_key, last_emit = key, now
        elif now - last_emit >= HEARTBEAT:
            log(f"ok {fmt(f)}")
            last_emit = now

        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
