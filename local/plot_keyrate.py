#!/usr/bin/env python3
"""
Plot QBER and key rate over time from a node's /tmp/node_stats.csv.

Fetches the CSV over logd (the 'stats' command) - no ssh - then plots QBER and
the per-round key rate (key_length / dt) versus time. Headless by default: saves
a PNG (use --show to open a window instead).

Usage:
    QLINE_CONFIG_DIR=.../config/qline1 python3 plot_keyrate.py <alice|bob> [-n N] [-o out.png]
    python3 plot_keyrate.py --use_localhost alice          # over port_forwarding tunnel
    python3 plot_keyrate.py alice -n 200 -o keyrate.png    # last 200 rounds

CSV row format: key_length;qber;timestamp  (timestamp = ISO8601 + [Etc/UTC]).
"""

import socket, json, os, sys, argparse, re
from datetime import datetime

import matplotlib
matplotlib.use('Agg')                         # headless; overridden by --show
import matplotlib.pyplot as plt


def fetch_stats(cfg, node, n, use_localhost):
    """Send the logd 'stats [n]' command and return the raw CSV text."""
    network = json.load(open(os.path.join(cfg, 'alice', 'network.json')))
    if use_localhost:
        lp = json.load(open(os.path.join(cfg, 'ports_for_localhost.json')))
        host, port = 'localhost', int(lp[f'logd_{node}'])
    else:
        host, port = network['ip'][node], int(network['port']['logd'])
    cmd = 'stats' if n is None else f'stats {n}'
    s = socket.socket(); s.settimeout(30); s.connect((host, port))
    s.sendall(len(cmd).to_bytes(4, 'little') + cmd.encode())
    length = int.from_bytes(_recv(s, 4), 'little')
    return _recv(s, length).decode(errors='replace') if length else ''


def _recv(s, n):
    buf = b''
    while len(buf) < n:
        chunk = s.recv(n - len(buf))
        if not chunk:
            raise ConnectionError('connection closed by logd')
        buf += chunk
    return buf


def parse(text):
    """Yield (datetime, key_length, qber) for each valid data row."""
    times, keylen, qber = [], [], []
    for line in text.splitlines():
        line = line.strip()
        if not line or ';' not in line:
            continue
        kl, q, ts = line.split(';')[:3]
        try:
            kl, q = int(kl), float(q)
        except ValueError:
            continue                          # header / partial line
        ts = ts.split('[')[0]                 # drop [Etc/UTC]
        m = re.match(r'(.*\.)(\d+)([+-]\d{2}:\d{2})$', ts)
        if m:                                 # ns -> us for fromisoformat
            ts = f'{m.group(1)}{m.group(2)[:6]}{m.group(3)}'
        times.append(datetime.fromisoformat(ts))
        keylen.append(kl)
        qber.append(q)
    return times, keylen, qber


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('node', choices=['alice', 'bob'])
    ap.add_argument('--use_localhost', action='store_true',
                    help='reach logd via port_forwarding.sh tunnel on localhost')
    ap.add_argument('-n', type=int, default=None, help='last N rounds (default: all)')
    ap.add_argument('-o', default='keyrate.png', help='output PNG (default: keyrate.png)')
    ap.add_argument('--show', action='store_true', help='open a window instead of saving')
    args = ap.parse_args()

    cfg = os.environ.get('QLINE_CONFIG_DIR') or os.path.expanduser('~/kiwi_hw_control/config/qline1')
    times, keylen, qber = parse(fetch_stats(cfg, args.node, args.n, args.use_localhost))
    if len(times) < 2:
        sys.exit('not enough data points to plot')

    # per-round key rate = key_length / time since previous round
    rate_t, rate = [], []
    for i in range(1, len(times)):
        dt = (times[i] - times[i - 1]).total_seconds()
        if dt > 0:
            rate_t.append(times[i])
            rate.append(keylen[i] / dt)

    if args.show:
        matplotlib.use('TkAgg', force=True)
    fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True, figsize=(10, 7))
    ax1.plot(times, qber, '.-', color='tab:red')
    ax1.axhline(0.09, ls='--', color='gray', lw=1, label='tolerance 0.09')
    ax1.set_ylabel('QBER'); ax1.legend(); ax1.grid(alpha=0.3)
    ax1.set_title(f'{args.node}: QBER and key rate over time ({len(times)} rounds)')
    ax2.plot(rate_t, rate, '.-', color='tab:blue')
    ax2.set_ylabel('key rate [bit/s]'); ax2.set_xlabel('time'); ax2.grid(alpha=0.3)
    fig.autofmt_xdate()
    fig.tight_layout()

    if args.show:
        plt.show()
    else:
        fig.savefig(args.o, dpi=120)
        print(f'wrote {args.o}  ({len(times)} rounds, '
              f'{times[0]:%H:%M:%S}–{times[-1]:%H:%M:%S})')


if __name__ == '__main__':
    main()
