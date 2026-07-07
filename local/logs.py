#!/usr/bin/env python3
"""
Client for logd - read qline log files on a node over TCP (no ssh).

Usage:
    QLINE_CONFIG_DIR=.../config/qline1 python3 logs.py [--use_localhost] <alice|bob> <command> [args]

Examples:
    python3 logs.py alice list                # what logs exist, with sizes
    python3 logs.py alice tail hws            # last 200 lines of hws.log
    python3 logs.py alice tail hws 50         # last 50 lines
    python3 logs.py bob   head node 30        # first 30 lines of node.log
    python3 logs.py alice grep fs_a hws       # last 200 lines of hws.log matching 'fs_a'
    python3 logs.py alice stats               # /tmp/node_stats.csv (keylength/qber/ts)
    python3 logs.py alice stats 50            # last 50 lines of node_stats.csv
    python3 logs.py alice ping
    python3 logs.py --use_localhost alice tail hws   # over port_forwarding.sh tunnels

The target host/port are read from <config>/alice/network.json (ip[node] and
port['logd']); logd runs on both nodes bound to that node's own client IP.
With --use_localhost, connect to localhost on the logd_<node> port from
<config>/ports_for_localhost.json instead (requires port_forwarding.sh tunnels).
Read-only: logd can only list/tail/head/grep the *.log files under ~/log.
"""

import socket, json, os, sys

CFG = os.environ.get('QLINE_CONFIG_DIR') or os.path.expanduser('~/kiwi_hw_control/config/qline1')


def send_cmd(s, text):
    b = text.encode()
    s.sendall(len(b).to_bytes(4, 'little') + b)

def recv_exact(s, n):
    buf = b''
    while len(buf) < n:
        chunk = s.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("connection closed by logd")
        buf += chunk
    return buf

def recv_reply(s):
    length = int.from_bytes(recv_exact(s, 4), 'little')
    if length == 0:
        return ''
    return recv_exact(s, length).decode(errors='replace')


def main():
    args = sys.argv[1:]
    use_localhost = '--use_localhost' in args
    args = [a for a in args if a != '--use_localhost']
    if len(args) < 2:
        sys.exit("usage: logs.py [--use_localhost] <alice|bob> <ping|list|tail|head|grep|stats> [args]")
    node = args[0].lower()
    command = ' '.join(args[1:])

    if node not in ('alice', 'bob'):
        sys.exit(f"error: node must be 'alice' or 'bob', got '{node}'")

    network = json.load(open(os.path.join(CFG, 'alice', 'network.json')))
    if use_localhost:
        lp = json.load(open(os.path.join(CFG, 'ports_for_localhost.json')))
        host = 'localhost'
        port = int(lp[f'logd_{node}'])
    else:
        host = network['ip'][node]
        port = int(network['port']['logd'])

    s = socket.socket()
    s.settimeout(30)
    try:
        s.connect((host, port))
    except OSError as e:
        sys.exit(f"error: cannot reach logd on {node} ({host}:{port}): {e}")
    send_cmd(s, command)
    print(recv_reply(s))
    s.close()


if __name__ == '__main__':
    main()
