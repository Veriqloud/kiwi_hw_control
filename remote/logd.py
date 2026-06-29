#!/usr/bin/python3 -u
"""
logd - tiny read-only log server.

Lets the control host read the qline log files under ~/log over TCP, without
ssh. Companion to restartd (which does restarts over TCP); same spirit, same
node, different port. logd is strictly read-only: it lists, tails and greps the
log files and can do nothing else, so it needs no privileges beyond reading
files vq-user can already read.

Protocol: 4-byte little-endian length prefix + UTF-8 payload, both directions
(4 bytes, not restartd's 2, because log tails routinely exceed 64 KiB). One
request string per message; the reply is a single string.

Commands:
    ping                      -> "ok"
    list                      -> name / size / mtime of every available log
    tail <name> [n]           -> last n lines of <name>      (default 200)
    head <name> [n]           -> first n lines of <name>     (default 200)
    grep <pat> <name> [n]     -> last n lines matching <pat> (default 200)

Only *.log files directly inside LOG_DIR may be read (the name is resolved and
must live in LOG_DIR - no path traversal). Output is capped (MAX_LINES /
MAX_BYTES) and large files are tailed by seeking from the end, so serving a
multi-gigabyte gc.log stays cheap.
"""

import socket, threading, json, os, datetime

NETWORK_FILE = '/home/vq-user/config/network.json'
LOG_DIR = '/home/vq-user/log'

DEFAULT_LINES = 200
MAX_LINES = 10000           # hard cap on lines returned
MAX_BYTES = 5 * 1024 * 1024  # hard cap on reply payload (5 MiB)
GREP_SCAN_LIMIT = 512 * 1024 * 1024  # only scan the last 512 MiB when grepping


# ---- length-prefixed string protocol (4-byte frames) ----

def recv_exact(conn, n):
    buf = b''
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf

def recv_cmd(conn):
    head = recv_exact(conn, 4)
    if head is None:
        return None
    length = int.from_bytes(head, 'little')
    if length == 0:
        return ''
    body = recv_exact(conn, length)
    if body is None:
        return None
    return body.decode(errors='replace').strip()

def send_cmd(conn, text):
    b = text.encode()
    conn.sendall(len(b).to_bytes(4, 'little') + b)


# ---- log file access (read-only, confined to LOG_DIR) ----

def available_logs():
    try:
        names = [f for f in os.listdir(LOG_DIR) if f.endswith('.log')]
    except OSError:
        return []
    return sorted(names)

def resolve(name):
    """Map a requested name to a real path inside LOG_DIR, or None if invalid."""
    if not name:
        return None
    # accept "hws" or "hws.log"
    if not name.endswith('.log'):
        name = name + '.log'
    if '/' in name or '\\' in name:
        return None
    path = os.path.realpath(os.path.join(LOG_DIR, name))
    if os.path.dirname(path) != os.path.realpath(LOG_DIR) or not os.path.isfile(path):
        return None
    return path

def clamp_lines(arg):
    try:
        n = int(arg)
    except (TypeError, ValueError):
        return DEFAULT_LINES
    return max(1, min(n, MAX_LINES))

def cap_payload(s):
    b = s.encode(errors='replace')
    if len(b) <= MAX_BYTES:
        return s
    return ("[... output truncated to %d bytes ...]\n" % MAX_BYTES) + \
        b[-MAX_BYTES:].decode(errors='replace')


def do_list():
    out = []
    for name in available_logs():
        try:
            st = os.stat(os.path.join(LOG_DIR, name))
            mtime = datetime.datetime.fromtimestamp(st.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            out.append(f"{name:24s} {st.st_size:>16d} B  {mtime}")
        except OSError:
            out.append(f"{name:24s} (stat failed)")
    return '\n'.join(out) if out else "(no logs)"

def do_tail(path, n):
    """Return the last n lines, reading backward so huge files stay cheap."""
    n = clamp_lines(n)
    with open(path, 'rb') as f:
        f.seek(0, os.SEEK_END)
        end = f.tell()
        block = 64 * 1024
        data = b''
        pos = end
        while pos > 0 and data.count(b'\n') <= n and (end - pos) < MAX_BYTES:
            step = min(block, pos)
            pos -= step
            f.seek(pos)
            data = f.read(step) + data
        lines = data.split(b'\n')
        tail = lines[-(n + 1):]
        return cap_payload(b'\n'.join(tail).decode(errors='replace'))

def do_head(path, n):
    n = clamp_lines(n)
    out = []
    with open(path, 'rb') as f:
        for _ in range(n):
            line = f.readline()
            if not line:
                break
            out.append(line.decode(errors='replace').rstrip('\n'))
    return cap_payload('\n'.join(out))

def do_grep(path, pattern, n):
    """Return up to the last n lines containing <pattern>, scanning at most the
    last GREP_SCAN_LIMIT bytes so a giant log can't stall the daemon."""
    n = clamp_lines(n)
    size = os.path.getsize(path)
    start = max(0, size - GREP_SCAN_LIMIT)
    matches = []
    with open(path, 'rb') as f:
        f.seek(start)
        if start:
            f.readline()  # skip the partial first line
        for raw in f:
            line = raw.decode(errors='replace').rstrip('\n')
            if pattern in line:
                matches.append(line)
                if len(matches) > n:
                    matches.pop(0)
    note = '' if start == 0 else f"[scanned last {GREP_SCAN_LIMIT // (1024*1024)} MiB only]\n"
    return cap_payload(note + '\n'.join(matches)) if matches else (note + "(no matches)")


# ---- request dispatch ----

def handle_request(line):
    parts = line.split()
    if not parts:
        return "error: empty command"
    cmd = parts[0].lower()

    if cmd == 'ping':
        return 'ok'
    if cmd == 'list':
        return do_list()
    if cmd in ('tail', 'head'):
        if len(parts) < 2:
            return f"error: usage '{cmd} <name> [lines]'"
        path = resolve(parts[1])
        if path is None:
            return f"error: '{parts[1]}' is not a readable log; try 'list'"
        n = parts[2] if len(parts) > 2 else None
        return do_tail(path, n) if cmd == 'tail' else do_head(path, n)
    if cmd == 'grep':
        if len(parts) < 3:
            return "error: usage 'grep <pattern> <name> [lines]'"
        pattern = parts[1]
        path = resolve(parts[2])
        if path is None:
            return f"error: '{parts[2]}' is not a readable log; try 'list'"
        n = parts[3] if len(parts) > 3 else None
        return do_grep(path, pattern, n)
    return ("error: unknown command '" + cmd +
            "'; try: ping, list, tail <name> [n], head <name> [n], grep <pat> <name> [n]")


def handle_client(conn, addr):
    with conn:
        while True:
            try:
                line = recv_cmd(conn)
            except OSError:
                break
            if line is None:
                break
            print(f"{datetime.datetime.now()} {addr} -> {line!r}")
            try:
                reply = handle_request(line)
            except Exception as e:
                reply = f"error: {type(e).__name__}: {e}"
            try:
                send_cmd(conn, reply)
            except OSError:
                break


def main():
    with open(NETWORK_FILE) as f:
        network = json.load(f)
    host = network['ip'][network['myname']]
    port = int(network['port']['logd'])

    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((host, port))
    srv.listen()
    print(f"logd listening on {host}:{port}; serving {LOG_DIR}/*.log (read-only)")

    while True:
        conn, addr = srv.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()


if __name__ == '__main__':
    main()
