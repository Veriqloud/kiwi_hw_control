#!/usr/bin/env python3
"""
Sweep one Alice knob and read Bob's APD counts at each point.

    QLINE_CONFIG_DIR=.../config/ets/system1 python3 bias_sweep.py [--use_localhost] \
        --knob am2_bias --from 0 --to 10 --step 0.5

Knobs: am_bias, am2_bias, vca.  Counts come from Bob's mon `get_counts`
(total, click0, click1).  The entry value of the knob, and of am_mode when
--am_mode is given, are restored on exit including after an error.

Timing
------
The count register is a free-running 0.1 s window, so a read returns whatever
window latched most recently and reads inside one window repeat.  Waiting two
window periods after a write guarantees the next read covers a window that
began after that write: a write landing just after a latch is covered by 0.2 s,
and one landing just before a latch is covered with room to spare.  One point
is therefore one write, a 0.2 s dwell and one read.

Extra samples at a point are spaced one window apart, since that is the rate at
which independent values appear.  Precision at a point is Poisson-limited to
1/sqrt(N) -- about 1 % at 9000 counts and 5 % at 400 -- which locates a
transmission null comfortably.  Raise -n only when a point needs tighter error
bars than that.

Sweeping fast matters beyond throughput: a modulator null moves on a timescale
of a minute, so a sweep spread over minutes smears the feature it is looking
for, while a few-second sweep is a snapshot.
"""

import socket
import json
import argparse
import struct
import os
import sys
import time
import csv

WINDOW = 0.1     # s, hardware count-integration window

# Set_Am2_Bias exits the hw server when handed a value outside [0,10], which
# takes the server down with it, so every knob carries a hard range.
KNOBS = {
    'am_bias':  dict(cmd='set_am_bias',  lo=-10.0, hi=10.0),
    'am2_bias': dict(cmd='set_am2_bias', lo=0.0,   hi=10.0),
    'vca':      dict(cmd='set_vca',      lo=0.0,   hi=5.0),
}
AM_MODES = ['off', 'single', 'double', 'single64']


def get_targets(use_localhost):
    cfg = os.environ.get('QLINE_CONFIG_DIR')
    if not cfg:
        sys.exit("please set QLINE_CONFIG_DIR")
    network = json.load(open(os.path.join(cfg, 'alice/network.json')))
    if use_localhost:
        lp = json.load(open(os.path.join(cfg, 'ports_for_localhost.json')))
        return ('localhost', lp['hw_alice']), ('localhost', lp['mon_bob'])
    return ((network['ip']['alice'], network['port']['hw']),
            (network['ip']['bob'], network['port']['mon']))


def connect(target):
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    s.settimeout(20)
    s.connect(target)
    return s


def sendc(s, c):
    s.sendall(len(c).to_bytes(2, 'little') + c.encode())


def recv_exact(s, n):
    m = b''
    while len(m) < n:
        chunk = s.recv(n - len(m))
        if not chunk:
            raise ConnectionError("connection closed by peer")
        m += chunk
    return m


def rcvc(s):
    return recv_exact(s, int.from_bytes(recv_exact(s, 2), 'little')).decode().strip()


def rcv_i(s):
    return struct.unpack('i', recv_exact(s, 4))[0]


def send_d(s, v):
    s.sendall(struct.pack('d', v))


def get_info(alice):
    sendc(alice, 'get_info')
    return dict(l.split('\t') for l in rcvc(alice).splitlines() if '\t' in l)


def set_knob(alice, knob, value):
    spec = KNOBS[knob]
    if not spec['lo'] <= value <= spec['hi']:
        raise ValueError(f"{knob}={value} outside [{spec['lo']}, {spec['hi']}]")
    sendc(alice, spec['cmd'])
    send_d(alice, value)


def set_am_mode(alice, mode):
    sendc(alice, 'set_am_mode')
    sendc(alice, mode)


def read_counts(bob):
    sendc(bob, 'get_counts')
    return rcv_i(bob), rcv_i(bob), rcv_i(bob)   # total, click0, click1


def build_grid(start, stop, step):
    if step <= 0:
        sys.exit("--step must be positive")
    n = int(round(abs(stop - start) / step)) + 1
    sign = 1.0 if stop >= start else -1.0
    return [round(start + sign * step * i, 4) for i in range(n)]


def main():
    p = argparse.ArgumentParser(
        description="sweep an Alice knob against Bob's APD counts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="example:\n"
               "  bias_sweep.py --use_localhost --knob am2_bias "
               "--from 0 --to 10 --step 0.5 --am_mode off")
    p.add_argument("--use_localhost", action="store_true",
                   help="connect over the port_forwarding.sh tunnels")
    p.add_argument("--knob", required=True, choices=sorted(KNOBS),
                   help="which Alice knob to sweep")
    p.add_argument("--from", dest="start", type=float, help="grid start")
    p.add_argument("--to", dest="stop", type=float, help="grid end")
    p.add_argument("--step", type=float, help="grid step")
    p.add_argument("--values", type=str,
                   help="explicit comma-separated grid, instead of --from/--to/--step")
    p.add_argument("-n", "--samples", type=int, default=1,
                   help="reads per point (default 1)")
    p.add_argument("--dwell", type=float, default=2 * WINDOW,
                   help=f"s between a write and its read (default {2 * WINDOW})")
    p.add_argument("--am_mode", choices=AM_MODES,
                   help="hold this am_mode for the sweep; entry mode is restored")
    p.add_argument("--max_counts", type=float, default=60000,
                   help="abort above this many counts/0.1s (default 60000)")
    p.add_argument("--csv", type=str, help="write per-point results here")
    args = p.parse_args()

    if args.values:
        grid = [float(v) for v in args.values.split(',') if v.strip()]
    elif None not in (args.start, args.stop, args.step):
        grid = build_grid(args.start, args.stop, args.step)
    else:
        sys.exit("give --values, or all of --from --to --step")

    spec = KNOBS[args.knob]
    for v in grid:
        if not spec['lo'] <= v <= spec['hi']:
            sys.exit(f"{args.knob}={v} outside [{spec['lo']}, {spec['hi']}]")

    alice_t, bob_t = get_targets(args.use_localhost)
    alice, bob = connect(alice_t), connect(bob_t)

    info = get_info(alice)
    entry_knob = float(info[args.knob])
    entry_mode = info['am_mode']
    print(f"entry: {args.knob}={entry_knob}  am_mode={entry_mode}  vca={info['vca']}")

    est = len(grid) * (args.dwell + (args.samples - 1) * WINDOW)
    print(f"sweeping {args.knob} over {len(grid)} points, {args.samples} read(s) each "
          f"-- about {est:.1f} s\n")

    rows = []
    try:
        if args.am_mode:
            set_am_mode(alice, args.am_mode)
        for v in grid:
            set_knob(alice, args.knob, v)
            time.sleep(args.dwell)
            got = []
            for i in range(args.samples):
                if i:
                    time.sleep(WINDOW)
                got.append(read_counts(bob))
            total = sum(g[0] for g in got) / len(got)
            click0 = sum(g[1] for g in got) / len(got)
            click1 = sum(g[2] for g in got) / len(got)
            rows.append(dict(value=v, total=total, click0=click0, click1=click1))
            print(f"  {args.knob:>9} {v:8.3f}   total {total:9.1f}   "
                  f"click0 {click0:7.1f}   click1 {click1:7.1f}", flush=True)
            if total > args.max_counts:
                raise SystemExit(
                    f"abort: {total:.0f} counts/0.1s over --max_counts {args.max_counts:.0f}")
    finally:
        restore(alice, alice_t, args.knob, entry_knob,
                entry_mode if args.am_mode else None)
        for s in (alice, bob):
            try:
                s.close()
            except OSError:
                pass

    if not rows:
        return
    lo = min(rows, key=lambda r: r['total'])
    hi = max(rows, key=lambda r: r['total'])
    print(f"\nminimum: {args.knob}={lo['value']}  {lo['total']:.0f} counts/0.1s")
    print(f"maximum: {args.knob}={hi['value']}  {hi['total']:.0f} counts/0.1s")
    if lo['total'] > 0:
        print(f"ratio  : {hi['total'] / lo['total']:.1f}x")

    if args.csv:
        with open(args.csv, 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=['value', 'total', 'click0', 'click1'])
            w.writeheader()
            w.writerows(rows)
        print(f"wrote {args.csv}")


def restore(alice, alice_t, knob, value, mode):
    """Put the knob, and am_mode when it was held, back to their entry values.

    A sweep that ends because the link broke still has to restore, so a dead
    socket is replaced with a fresh one before giving up.
    """
    for sock in (alice, None):
        try:
            s = sock or connect(alice_t)
            set_knob(s, knob, value)
            if mode:
                set_am_mode(s, mode)
            time.sleep(1.0)
            got = get_info(s)
            print(f"\nrestored: {knob}={got[knob]}  am_mode={got['am_mode']}")
            if sock is None:
                s.close()
            return
        except Exception as e:
            print(f"restore over existing socket failed ({e}); retrying on a new one",
                  file=sys.stderr)
    print(f"RESTORE FAILED -- {knob} may still be at a swept value", file=sys.stderr)


if __name__ == '__main__':
    main()
