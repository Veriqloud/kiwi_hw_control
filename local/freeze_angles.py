#!/usr/bin/env python3
"""Measure and freeze k2, the angle2/angle1 ratio, for both parties.

    QLINE_CONFIG_DIR=.../config/qline1 python3 freeze_angles.py --laser 1550

`angle2 = -angle1` assumes the phase modulator is odd. It is not: on qline1 at
1550 nm both modulators need about 13 % more drive on the negative side, and
setting it costs roughly a point of QBER when it is wrong. angle3 needs no
such factor -- 2*angle1 measured right twice -- so this is one number per
party.

The two k2 are coupled. Matrix cell 33 is Alice's angle2 against Bob's, so
measuring one while the other sits elsewhere gives a different answer; that
coupling is what once made a quantity repeatable to 0.3 % look like it was
drifting 10 % overnight. So each round measures Alice, applies it, measures
Bob, applies it, and the rounds repeat until neither moves.

Each measurement sweeps one party's angle2 across a span of angle1 and finds
where the two cells that angle2 trades cross -- 32 against 33 for Alice, 23
against 33 for Bob. The crossing, not the minimum of their sum: the sum is flat
to within the noise over a 20 % span while each cell moves by a factor three.

Run it after a full_init that ended cleanly, with node and kms stopped on both
machines. It refuses to start otherwise, and refuses if the modulator is
leaking, because a bad AM null moves the crossing.

KNOWN HAZARD, not yet fixed. Sweeping angle2 like this has twice decorrelated
the link outright -- QBER goes to exactly 50 %, the 4x4 matrix goes flat, and
it stays there. Counts, both fringes at 0.9 visibility, the fibre delays,
zero_pos, gc and White Rabbit all keep reading normal, and every calibration
step still reports success, so nothing in full_init notices. Neither full_init
nor --clean nor restarting gc, hw, hws or rng recovers it: the only thing that
does is rebooting BOTH machines. It happened on 2026-09-30 during an am_bias
sweep and again the same afternoon on the second point of a plain angle2 sweep,
while earlier sweeps of the same shape ran through fine, so the trigger is not
pinned down further than "repeated angle writes with qber cycling". Until it
is, expect to reboot both machines after a run, and do not run this on a system
that is generating keys.
"""

import argparse
import json
import os
import re
import socket
import struct
import shlex
import subprocess
import sys
import time

import numpy as np

HOST = {'alice': 'ql001', 'bob': 'ql002'}
# the (row, col) pair of matrix cells each party's angle2 trades, 0-indexed
CELLS = {'alice': ((2, 1), (2, 2)),    # c32 against c33
         'bob':   ((1, 2), (2, 2))}    # c23 against c33
# find_gates reports `rates <signal>/<leakage>`. That ratio separates a good
# null from a bad one cleanly, where the signal/leakage figure next to it does
# not: measured on qline1, 143/4384 = 0.03, 235/4622 = 0.05 and 224/4520 = 0.05
# on runs that gave 5-6 % QBER, against 2663/4831 = 0.55 with the bias a couple
# of tenths off the null.
MAX_LEAK_FRACTION = 0.15


def sh(host, cmd, timeout=140):
    return subprocess.run(['ssh', '-o', 'BatchMode=yes', f'vq-user@{host}', cmd],
                          stdin=subprocess.DEVNULL, capture_output=True,
                          text=True, timeout=timeout).stdout


def angles(party):
    t = dict(l.split() for l in
             sh(HOST[party], "grep -wE 'angle0|angle1|angle2|angle3' "
                             "~/hw_control/config/tmp.txt").splitlines()
             if len(l.split()) == 2)
    return [float(t[f'angle{i}']) for i in range(4)]


def set_angles(ip, a):
    s = socket.create_connection((ip, 13000), timeout=10)
    c = b'set_angles'
    s.sendall(len(c).to_bytes(2, 'little') + c)
    for v in a:
        s.sendall(struct.pack('d', v))
    time.sleep(0.4)
    s.close()


def qber(seconds):
    """(mean total QBER %, mean 4x4 matrix) over `seconds` of the qber binaries."""
    sh('ql002', 'pkill -x qber; cd ~/server; nohup ./qber > /tmp/qber_bob.log '
                '2>&1 < /dev/null & sleep 2', 40)
    try:
        out = sh('ql001', f'timeout -s INT -k 10 {seconds} ~/bin/qber 100000 2>&1',
                 seconds + 60)
    finally:
        sh('ql002', 'pkill -x qber; true', 40)
    tot = [float(m.group(3)) for m in re.finditer(
        r'qber \(alice, bob, total\):\s+(\S+)\s+(\S+)\s+(\S+)', out)]
    mats = [np.array([[float(x) for x in l.split()]
                      for l in b.group(1).strip().split('\n')])
            for b in re.finditer(
                r'counts: .*?\n((?:\s*[-\d.]+\s+[-\d.]+\s+[-\d.]+\s+[-\d.]+\s*\n){4})',
                out)]
    if not tot or not mats:
        return None, None
    return float(np.mean(tot)), np.mean(mats, axis=0)


def measure_k2(party, ip, seconds, points):
    """Sweep `party`'s angle2 and return the k2 where its two cells cross."""
    base = angles(party)
    a1 = base[1]
    (ra, ca), (rb, cb) = CELLS[party]
    grid = [round(-a1 * (0.95 + 0.40 * i / (points - 1)), 4) for i in range(points)]
    pts = []
    try:
        for a2 in grid:
            set_angles(ip, [base[0], a1, a2, base[3]])
            q, m = qber(seconds)
            if m is None:
                print(f'    angle2 {a2:8.4f}   no QBER', flush=True)
                continue
            A, B = m[ra, ca], m[rb, cb]
            pts.append((a2, A - B))
            print(f'    angle2 {a2:8.4f}  k2 {abs(a2)/a1:6.3f}  '
                  f'cells {A:5.2f} {B:5.2f}  diff {A-B:+6.2f}  QBER {q:5.2f}',
                  flush=True)
    finally:
        set_angles(ip, base)
    for (x0, d0), (x1, d1) in zip(pts, pts[1:]):
        if d0 * d1 <= 0 and d0 != d1:
            return abs(x0 + (x1 - x0) * d0 / (d0 - d1)) / a1
    return None


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--laser', type=int, required=True)
    p.add_argument('--seconds', type=int, default=15, help='qber time per point')
    p.add_argument('--points', type=int, default=7, help='points per sweep')
    p.add_argument('--rounds', type=int, default=4, help='max fixed-point rounds')
    p.add_argument('--tol', type=float, default=0.01,
                   help='stop when both k2 move less than this')
    p.add_argument('--dry-run', action='store_true', help='measure, do not write')
    args = p.parse_args()
    nm = args.laser

    cfg = os.environ.get('QLINE_CONFIG_DIR')
    if not cfg:
        sys.exit('please set QLINE_CONFIG_DIR')
    net = json.load(open(os.path.join(cfg, 'alice', 'network.json')))
    ip = {'alice': net['ip']['alice'], 'bob': net['ip']['bob']}

    for host in HOST.values():
        if sh(host, 'systemctl is-active node.service').strip() == 'active':
            sys.exit(f'node is running on {host}: the qber binaries need the angle '
                     f'and click fifos. Stop node and kms on both machines '
                     f'(sudo systemctl stop node kms). Note they come back at boot.')

    leak = sh(HOST['bob'], "sed 's/\\x1b\\[[0-9;]*m//g' ~/log/hws.log | "
                           "grep -a 'find_gates success' | tail -1")
    m = re.search(r'rates (\d+)/(\d+)', leak)
    if m:
        sig, lk = int(m.group(1)), int(m.group(2))
        frac = lk / max(sig, 1)
        if frac > MAX_LEAK_FRACTION:
            sys.exit(f'the last find_gates leaked {lk}/{sig} = {frac:.2f} (over '
                     f'{MAX_LEAK_FRACTION}): the AM null is off and it moves the '
                     f'crossing. Re-run full_init, or sweep the null with '
                     f'bias_sweep.py, before measuring angles.')
        print(f'last find_gates leak {lk}/{sig} = {frac:.2f}, ok')

    k2 = {'alice': None, 'bob': None}
    for rnd in range(1, args.rounds + 1):
        print(f'=== round {rnd}/{args.rounds}')
        moved = 0.0
        for party in ('alice', 'bob'):
            print(f'  {party}:')
            new = measure_k2(party, ip[party], args.seconds, args.points)
            if new is None:
                sys.exit(f'{party}: the two cells never crossed in the scanned '
                         f'range; widen it or check the calibration')
            if k2[party] is not None:
                moved = max(moved, abs(new - k2[party]))
            k2[party] = new
            base = angles(party)
            set_angles(ip[party], [base[0], base[1], -new * base[1], base[3]])
            print(f'  -> {party} k2 = {new:.3f}', flush=True)
        if rnd > 1 and moved < args.tol:
            print(f'settled after {rnd} rounds (largest move {moved:.4f})')
            break
    else:
        print(f'warning: still moving by {moved:.4f} after {args.rounds} rounds')

    q, mat = qber(30)
    print(f'\nalice k2 {k2["alice"]:.3f}   bob k2 {k2["bob"]:.3f}   QBER {q:.2f} %')
    if mat is not None:
        for r in mat:
            print('   ' + ' '.join(f'{x:6.2f}' for x in r))

    if args.dry_run:
        print('\n--dry-run: nothing written')
        return
    note = f'fixed point {time.strftime("%Y-%m-%d")}, QBER {q:.2f} %'
    code = ('import lib.sysconst as s\n'
            'd = s.load()\n'
            f's.put_k2(d, "alice", "{nm}", {k2["alice"]}, {note!r})\n'
            f's.put_k2(d, "bob", "{nm}", {k2["bob"]}, {note!r})\n'
            's.save(d)\n'
            'print("written")\n')
    print(sh(HOST['bob'], 'cd ~/hw_control && python3 -c ' + shlex.quote(code)).strip())
    print(f'fs_a and fs_b use these from now on. Run a full_init to confirm.')


if __name__ == '__main__':
    main()
