#!/usr/bin/env python3
"""
Client for restartd - restart qline services on a node over TCP (no ssh, no sudo).

Usage:
    QLINE_CONFIG_DIR=.../config/qline1 python3 restart.py <alice|bob> <command> [service]

Examples:
    python3 restart.py alice restart gc      # recover a wedged gc on Alice
    python3 restart.py alice restart node
    python3 restart.py bob   status gc
    python3 restart.py alice list
    python3 restart.py bob   ping

The target host/port are read from <config>/alice/network.json (ip[node] and
port['restartd']); restartd runs on both nodes bound to that node's own IP.
"""

import socket, json, os, sys

CFG = os.environ.get('QLINE_CONFIG_DIR') or os.path.expanduser('~/kiwi_hw_control/config/qline1')


def send_cmd(s, text):
    b = text.encode()
    s.sendall(len(b).to_bytes(2, 'little') + b)

def recv_exact(s, n):
    buf = b''
    while len(buf) < n:
        chunk = s.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("connection closed by restartd")
        buf += chunk
    return buf

def recv_reply(s):
    length = int.from_bytes(recv_exact(s, 2), 'little')
    return recv_exact(s, length).decode(errors='replace')


def main():
    if len(sys.argv) < 3:
        sys.exit("usage: restart.py <alice|bob> <ping|list|status|restart> [service]")
    node = sys.argv[1].lower()
    command = ' '.join(sys.argv[2:])

    if node not in ('alice', 'bob'):
        sys.exit(f"error: node must be 'alice' or 'bob', got '{node}'")

    network = json.load(open(os.path.join(CFG, 'alice', 'network.json')))
    host = network['ip'][node]
    port = int(network['port']['restartd'])

    s = socket.socket()
    s.settimeout(30)          # restart waits ~10s for systemd to respawn
    try:
        s.connect((host, port))
    except OSError as e:
        sys.exit(f"error: cannot reach restartd on {node} ({host}:{port}): {e}")
    send_cmd(s, command)
    print(recv_reply(s))
    s.close()


if __name__ == '__main__':
    main()
