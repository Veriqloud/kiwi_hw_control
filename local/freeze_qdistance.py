#!/usr/bin/env python3
"""Find and freeze the qdistance that minimises the QBER, for one laser.

    QLINE_CONFIG_DIR=.../config/qline1 python3 freeze_qdistance.py --laser 1550

Run once per laser and system, and again only after the hardware changed (a
fiber repatched, the interferometer touched).  It can be run on a machine that
was just powered on: step 1 brings the FPGA, the laser, the VCA and the
modulator nulls up, which is what the measurement in step 2 needs.  Steps:

  1. hws.py --full_init_<nm>: the bootstrap.  On a cold system nothing is
     calibrated yet, so find_gates_freeze would measure a histogram that has no
     light in it.  A find_gates failure at the end of this one is expected and
     ignored -- the geometry it complains about is exactly what step 2 goes on
     to re-measure; anything failing before it is fatal.  --skip-bootstrap
     leaves it out when the system is already running.
  2. hws.py --command find_gates_freeze: measures the interferometer (t1, t2)
     five times and freezes the median, its geometric qdistance and am_edge in
     Bob's config/system_constants.json, under the key of the laser that step 1
     set (so one freeze per wavelength, each independent of the others).
  3. hws.py --full_init_<nm>: a complete calibration on the frozen geometry.
     find_gates alone moves am_shift, t0 and the gates, which leaves the phase,
     delay and zero_pos steps after it stale -- the QBER is only meaningful
     after a whole full_init.
  4. QBER against qdistance: first a coarse pass on a --step grid around the
     geometric value, then a fine pass of four --fine-step points either side
     of the best coarse point.
  5. A parabola through the fine points; its vertex becomes the frozen
     qdistance.

Why the scan: the geometric qdistance puts Alice's pulse pair t1 apart, but the
QBER optimum sits a little off it (qline1 1550 nm: t1 5.161 ns, optimum at a
5.205 ns separation, 5.8 % QBER against 6.6 %), and the QBER rises steeply a
hundred ps either side, so it is worth measuring once and then never again.

The qber binaries need the angle and click fifos, so node must be stopped on
both machines first (sudo systemctl stop node kms).  gc must run.
"""

import argparse
import json
import os
import re
import socket
import struct
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))

FINE_POINTS = 4          # fine scan points either side of the best coarse point


def sh(host, cmd, timeout=60):
    """Run `cmd` on `host` over ssh; returns stdout."""
    r = subprocess.run(['ssh', '-o', 'BatchMode=yes', f'vq-user@{host}', cmd],
                       stdin=subprocess.DEVNULL, capture_output=True, text=True,
                       timeout=timeout)
    return r.stdout


def hws(*args):
    """Run local hws.py; returns (ok, output), retrying once on a lost link."""
    for attempt in range(2):
        r = subprocess.run([sys.executable, 'hws.py', *args], cwd=HERE,
                           capture_output=True, text=True)
        out = r.stdout + r.stderr
        if 'link lost' not in out:
            break
    return r.returncode == 0 and 'fail' not in out, out


def set_qdistance(alice, port, q):
    s = socket.create_connection((alice, port), timeout=10)
    c = 'set_qdistance'.encode()
    s.sendall(len(c).to_bytes(2, 'little') + c + struct.pack('d', q))
    time.sleep(0.5)
    s.close()


def measure_qber(alice, bob, seconds):
    """Mean total QBER (%) over `seconds` of qber, or None."""
    sh(bob, 'pkill -x qber; cd ~/server; nohup ./qber > /tmp/qber_bob.log 2>&1 '
            '< /dev/null & sleep 1', timeout=20)
    try:
        out = sh(alice, f'timeout -s INT -k 5 {seconds} ~/bin/qber 100000 2>&1',
                 timeout=seconds + 30)
    finally:
        sh(bob, 'pkill -x qber; true', timeout=20)
    vals = [float(m.group(1)) for m in
            re.finditer(r'qber \(alice, bob, total\):\s+\S+\s+\S+\s+(\S+)', out)]
    return float(np.mean(vals)) if vals else None


def frozen_entry(bob, nm):
    out = sh(bob, "cd ~/hw_control && python3 -c \"import json, lib.sysconst as s; "
                  f"print(json.dumps(s.get_frozen_interferometer(s.load(), '{nm}')))\"")
    return json.loads(out.strip() or 'null')


def write_frozen_qdistance(bob, nm, q, note):
    code = ("import lib.sysconst as s, lib.timing as t\n"
            "d = s.load()\n"
            f"e = s.get_frozen_interferometer(d, '{nm}')\n"
            "e.setdefault('qdistance_geometric', e['qdistance'])\n"
            f"e['qdistance'] = round({q}, 4)\n"
            f"e['separation_slots'] = round(t.separation_slots({q}), 4)\n"
            f"e['qdistance_source'] = {note!r}\n"
            "s.save(d)\n")
    sh(bob, f'cd ~/hw_control && python3 -c "{code}"')


def separation_ns(q):
    # the dac0_double knob, lib/timing.separation_slots, in ns
    slots = 5.0 + (q - 1.0) / (1.0 + q) if q >= 0 else 3.0 + (1.0 + q) / (1.0 - q)
    return slots * 1.25


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--laser', type=int, required=True, help='1310, 1510 or 1550')
    p.add_argument('--span', type=float, default=0.04,
                   help='scan qdistance this far either side of the geometric value')
    p.add_argument('--step', type=float, default=0.01, help='coarse scan step')
    p.add_argument('--fine-step', type=float, default=0.0025,
                   help='fine scan step, four points either side of the best '
                        'coarse point; 0 skips the fine pass')
    p.add_argument('--seconds', type=int, default=10, help='qber time per point')
    p.add_argument('--skip-bootstrap', action='store_true',
                   help='the system is already up and calibrated: do not run the '
                        'first full_init')
    p.add_argument('--skip-geometry', action='store_true',
                   help='geometry already frozen and the system calibrated on it: '
                        'go straight to the scan')
    args = p.parse_args()
    nm = args.laser

    cfg = os.environ.get('QLINE_CONFIG_DIR')
    if not cfg:
        sys.exit('please set QLINE_CONFIG_DIR')
    net = json.load(open(os.path.join(cfg, 'alice', 'network.json')))
    alice, bob, hw_port = net['ip']['alice'], net['ip']['bob'], net['port']['hw']

    for host in (alice, bob):
        if sh(host, 'systemctl is-active node.service').strip() == 'active':
            sys.exit(f'node is running on {host}: stop node and kms on both '
                     f'machines first (sudo systemctl stop node kms)')

    steps = ('1/5', '2/5', '3/5', '4/5', '5/5')

    if args.skip_bootstrap:
        # Everything below is keyed by the laser Alice has recorded, not by
        # --laser, so writing the freeze under the wrong wavelength is the one
        # mistake skipping the bootstrap can make.
        patched = sh(alice, "grep -w laser ~/hw_control/config/tmp.txt").split()
        if patched and patched[-1] != str(nm):
            sys.exit(f'Alice is set to the {patched[-1]} nm laser, not {nm}: '
                     f'run without --skip-bootstrap, or patch the right fiber')

    if not args.skip_bootstrap:
        print(f'[{steps[0]}] full_init_{nm}: bringing the system up before measuring it')
        ok, out = hws(f'--full_init_{nm}')
        if not ok and 'find_gates fail' not in out:
            sys.exit('the bootstrap full_init failed before find_gates:\n' + out)
        if not ok:
            print('  find_gates failed, as expected on a cold or moved system; '
                  'the freeze below re-measures the geometry')

    if not args.skip_geometry:
        print(f'[{steps[1]}] find_gates_freeze ({nm} nm)')
        ok, out = hws('--command', 'find_gates_freeze')
        print(out.strip())
        if not ok:
            sys.exit('find_gates_freeze failed')
        print(f'[{steps[2]}] full_init_{nm} on the frozen geometry')
        ok, out = hws(f'--full_init_{nm}')
        if not ok:
            sys.exit('full_init failed:\n' + out)

    entry = frozen_entry(bob, nm)
    if not entry:
        sys.exit(f'no frozen geometry for {nm} nm on Bob: run without --skip-geometry')
    q0 = entry.get('qdistance_geometric', entry['qdistance'])

    measured = {}          # qdistance -> [qber, ...], both passes pooled

    def scan(order, label):
        """Measure every qdistance in `order`; returns the best one."""
        print(f'  {label}: {len(order)} points, {args.seconds} s each')
        for q in order:
            set_qdistance(alice, hw_port, q)
            v = measure_qber(alice, bob, args.seconds)
            print(f'  qdistance {q:.4f}  separation {separation_ns(q):.3f} ns  '
                  f'QBER {v if v is None else round(v, 2)} %')
            if v is not None:
                measured.setdefault(q, []).append(v)
        if not measured:
            set_qdistance(alice, hw_port, entry['qdistance'])
            sys.exit('no QBER point came back; frozen qdistance left unchanged')
        return min(measured, key=lambda q: np.mean(measured[q]))

    print(f'[{steps[3]}] QBER scan around the geometric qdistance {q0:.4f}')
    try:
        n = int(round(args.span / args.step))
        coarse = [round(q0 + k * args.step, 4) for k in range(-n, n + 1)]
        best = scan(coarse, f'coarse, step {args.step}')

        window = args.step
        if args.fine_step > 0:
            fine = [round(best + j * args.fine_step, 4)
                    for j in range(-FINE_POINTS, FINE_POINTS + 1) if j]
            window = FINE_POINTS * args.fine_step
            best = scan(fine, f'fine around {best:.4f}, step {args.fine_step}')
    finally:
        set_qdistance(alice, hw_port, entry['qdistance'])

    # Fit only inside the window around the best point: further out the QBER
    # climbs steeply and not symmetrically, and those points drag the vertex.
    means = {q: float(np.mean(v)) for q, v in measured.items()}
    pts = [(q, v) for q, vs in measured.items() for v in vs
           if abs(q - best) <= window + 1e-9]
    if len(set(q for q, _ in pts)) < 3:
        pts = [(q, v) for q, vs in measured.items() for v in vs]
    if len(set(q for q, _ in pts)) < 3:
        sys.exit('too few QBER points to fit; frozen qdistance left unchanged')
    qs = [q for q, _ in pts]
    qbers = [v for _, v in pts]
    a, b, c = np.polyfit(qs, qbers, 2)
    if a > 0 and min(qs) <= -b / (2 * a) <= max(qs):
        q_opt, how = -b / (2 * a), 'parabola vertex'
    else:
        q_opt, how = min(means, key=means.get), 'best point (no usable parabola)'
    q_opt = round(float(q_opt), 4)
    qber_opt = float(np.polyval([a, b, c], q_opt))

    note = (f'qber scan {time.strftime("%Y-%m-%d")}: {how} {q_opt} '
            f'(QBER ~{qber_opt:.1f} %), geometric {q0}')
    write_frozen_qdistance(bob, nm, q_opt, note)
    set_qdistance(alice, hw_port, q_opt)
    print(f'[{steps[4]}] frozen qdistance for {nm} nm: {q_opt} ({how}, separation '
          f'{separation_ns(q_opt):.3f} ns, QBER ~{qber_opt:.1f} %; geometric was {q0})')
    print('Every full_init uses it from now on. Run a full_init to confirm the QBER.')


if __name__ == '__main__':
    main()
