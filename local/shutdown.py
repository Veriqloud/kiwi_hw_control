#!/usr/bin/env python3
"""
Power off qline nodes remotely via restartd (no ssh) - in the spirit of restart.py.

Usage:
    QLINE_CONFIG_DIR=.../config/qline1 python3 shutdown.py <alice|bob|both> --yes

Sends the `shutdown` command to restartd (TCP port restartd in network.json), which
runs `sudo -n /usr/sbin/shutdown -h +0` on the node. Requires vq-user to have
NOPASSWD sudo for /usr/sbin/shutdown; otherwise restartd replies with a clear error.

--yes is required (shutdown is destructive). Recover a powered-off node with
local/wake.sh (wake-on-LAN).
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


def shutdown_node(node, network):
    host = network['ip'][node]
    port = int(network['port']['restartd'])
    s = socket.socket()
    s.settimeout(15)
    try:
        s.connect((host, port))
    except OSError as e:
        print(f"{node}: cannot reach restartd ({host}:{port}): {e}")
        return
    send_cmd(s, 'shutdown')
    try:
        print(f"{node}: {recv_reply(s)}")
    except (OSError, ConnectionError) as e:
        # The node may drop the link as it powers off before the reply arrives.
        print(f"{node}: shutdown sent (no reply, node likely going down): {e}")
    finally:
        s.close()


def main():
    args = sys.argv[1:]
    if len(args) < 1 or args[0].lower() not in ('alice', 'bob', 'both'):
        sys.exit("usage: shutdown.py <alice|bob|both> --yes")
    target = args[0].lower()
    if '--yes' not in args[1:]:
        sys.exit(f"refusing: shutdown is destructive. Re-run: shutdown.py {target} --yes "
                 "(recover with local/wake.sh)")

    network = json.load(open(os.path.join(CFG, 'alice', 'network.json')))
    nodes = ['alice', 'bob'] if target == 'both' else [target]
    for n in nodes:
        shutdown_node(n, network)


if __name__ == '__main__':
    main()
