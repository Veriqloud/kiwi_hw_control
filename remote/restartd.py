#!/usr/bin/python3 -u
"""
restartd - tiny remote service supervisor.

Lets the control host restart qline services over TCP, without ssh and without
sudo. It runs as vq-user; the qline service processes also run as vq-user, and
every unit is Restart=always, so this daemon simply kills the (vq-user-owned)
main process and lets systemd respawn it. No privilege escalation is involved:
- MainPID/ActiveState come from `systemctl show` (readable unprivileged),
- the kill is permitted because we own the target process.

Protocol (matches mon.py): 2-byte little-endian length prefix + UTF-8 string,
both directions. One request line per message; the reply is a single string.

Commands:
    ping                 -> "ok"
    list                 -> state + MainPID of every allowed service
    status <service>     -> state + MainPID of one service
    restart <service>    -> kill MainPID, wait for systemd to respawn, report
    shutdown             -> power the node off (needs NOPASSWD sudo for shutdown)

Only the services in ALLOWED may be acted on (restartd refuses anything else,
and intentionally cannot restart itself).
"""

import socket, threading, json, os, signal, subprocess, time, datetime

NETWORK_FILE = '/home/vq-user/config/network.json'

# Whitelisted units this daemon is allowed to touch. restartd is deliberately
# absent: if it wedges, recover it over ssh.
ALLOWED = ['gc', 'node', 'kms', 'hw', 'hws', 'mon', 'rng', 'decoy_rng', 'webinterface']


# ---- length-prefixed string protocol (same framing as mon.py) ----

def recv_exact(conn, n):
    buf = b''
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf

def recv_cmd(conn):
    head = recv_exact(conn, 2)
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
    conn.sendall(len(b).to_bytes(2, 'little') + b)


# ---- systemd helpers (all unprivileged) ----

def unit_info(svc):
    """Return dict with MainPID/ActiveState/SubState for <svc>.service."""
    out = subprocess.run(
        ['systemctl', 'show', svc + '.service',
         '-p', 'MainPID', '-p', 'ActiveState', '-p', 'SubState', '-p', 'LoadState'],
        capture_output=True, text=True)
    info = {}
    for line in out.stdout.splitlines():
        if '=' in line:
            k, v = line.split('=', 1)
            info[k] = v
    return info

def pid_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True

def status_line(svc):
    i = unit_info(svc)
    return f"{svc}: {i.get('ActiveState','?')}/{i.get('SubState','?')} (MainPID={i.get('MainPID','?')}, load={i.get('LoadState','?')})"

def restart(svc):
    i = unit_info(svc)
    if i.get('LoadState') != 'loaded':
        return f"{svc}: unit not loaded (LoadState={i.get('LoadState','?')}); nothing to restart"
    old = int(i.get('MainPID', '0') or '0')
    if old <= 0:
        return (f"{svc}: not running (MainPID=0, state={i.get('ActiveState','?')}); "
                f"cannot kill. If it is enabled, systemd should bring it up on its own.")

    # SIGTERM first so it can shut down cleanly, escalate to SIGKILL if it lingers.
    try:
        os.kill(old, signal.SIGTERM)
    except ProcessLookupError:
        pass
    for _ in range(30):                      # up to ~3s for graceful exit
        if not pid_alive(old):
            break
        time.sleep(0.1)
    forced = False
    if pid_alive(old):
        forced = True
        try:
            os.kill(old, signal.SIGKILL)
        except ProcessLookupError:
            pass

    # systemd respawns after RestartSec (10s); wait for a fresh MainPID.
    new, state, sub = 0, '?', '?'
    for _ in range(200):                      # up to ~20s
        time.sleep(0.1)
        ni = unit_info(svc)
        npid = int(ni.get('MainPID', '0') or '0')
        if npid > 0 and npid != old:
            new, state, sub = npid, ni.get('ActiveState', '?'), ni.get('SubState', '?')
            break

    how = 'SIGKILL' if forced else 'SIGTERM'
    if new:
        return f"{svc}: restarted via {how} (pid {old} -> {new}, now {state}/{sub})"
    return (f"{svc}: killed pid {old} via {how} but no new pid after ~20s "
            f"(state={unit_info(svc).get('ActiveState','?')}; check StartLimitBurst)")


# ---- node shutdown ----

# Requires vq-user NOPASSWD sudo for /usr/sbin/shutdown. `sudo -n` never prompts,
# so without that rule this returns a clear error instead of hanging. shutdown
# forks and returns, so the reply is sent before the box actually halts. Recover
# a powered-off node with local/wake.sh (wake-on-LAN).
SHUTDOWN_CMD = ['sudo', '-n', '/usr/sbin/shutdown', '-h', '+0']

def do_shutdown():
    r = subprocess.run(SHUTDOWN_CMD, capture_output=True, text=True)
    if r.returncode == 0:
        return "shutdown initiated (shutdown -h +0); node powering off. Recover with local/wake.sh"
    msg = r.stderr.strip() or r.stdout.strip() or "unknown error"
    return (f"shutdown FAILED (rc={r.returncode}): {msg}. "
            "vq-user needs NOPASSWD sudo for /usr/sbin/shutdown.")


# ---- request dispatch ----

def handle_request(line):
    parts = line.split()
    if not parts:
        return "error: empty command"
    cmd = parts[0].lower()

    if cmd == 'ping':
        return 'ok'
    if cmd == 'list':
        return '\n'.join(status_line(s) for s in ALLOWED)
    if cmd == 'shutdown':
        return do_shutdown()
    if cmd in ('status', 'restart'):
        if len(parts) < 2:
            return f"error: usage '{cmd} <service>'"
        svc = parts[1]
        if svc not in ALLOWED:
            return f"error: '{svc}' not allowed; choose one of: {', '.join(ALLOWED)}"
        return status_line(svc) if cmd == 'status' else restart(svc)
    return ("error: unknown command '" + cmd +
            "'; try: ping, list, status <svc>, restart <svc>, shutdown")


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
    port = int(network['port']['restartd'])

    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((host, port))
    srv.listen()
    print(f"restartd listening on {host}:{port}; allowed: {', '.join(ALLOWED)}")

    while True:
        conn, addr = srv.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()


if __name__ == '__main__':
    main()
