#!/bin/bash
#
# Forward the Alice/Bob control ports to localhost over vq, and keep them up.
#
#   port_forwarding.sh            start, backgrounded and supervised
#   port_forwarding.sh --status   show supervisor, ssh and listener state
#   port_forwarding.sh --stop     stop
#
# The tunnel survives a dropped or half-dead connection: a supervisor restarts
# ssh whenever it exits, and kills it when the forwards stop listening.

set -uo pipefail

MODE=start
case "${1-}" in
    "")          ;;
    --status)    MODE=status ;;
    --stop)      MODE=stop ;;
    --supervise) MODE=supervise ;;   # internal: the backgrounded loop re-execs here
    *)           echo "usage: $0 [--status|--stop]" >&2; exit 2 ;;
esac

if [ -z "${QLINE_CONFIG_DIR:-}" ]; then
    echo "Please set QLINE_CONFIG_DIR" >&2
    exit 1
fi

RUNDIR="${XDG_RUNTIME_DIR:-/tmp}/qline"
PIDFILE="$RUNDIR/port_forwarding.pid"
LOGFILE="$RUNDIR/port_forwarding.log"
mkdir -p "$RUNDIR"

# ssh gives up on a peer that stops answering after
# ServerAliveInterval * ServerAliveCountMax = 45 s, and the supervisor rebuilds
# the tunnel.  TCPKeepAlive additionally lets the kernel tear down a connection
# whose peer vanished without sending a FIN, which is what leaves an ssh blocked
# on a socket that will never carry data again.
SSH_OPTS=(
    -N
    -o ControlMaster=no -o ControlPath=none
    -o ExitOnForwardFailure=yes
    -o ServerAliveInterval=15 -o ServerAliveCountMax=3
    -o TCPKeepAlive=yes
    -o ConnectTimeout=15
)
PROBE_INTERVAL=5     # s between liveness/listener checks
STARTUP_GRACE=20     # s to let a fresh ssh authenticate and bind its forwards
RETRY_MIN=5          # s before the first rebuild attempt
RETRY_MAX=300        # s ceiling for the backoff
HEALTHY_AFTER=60     # s of uptime that earn a tunnel a reset back to RETRY_MIN


# ---------------------------------------------------------------- config ----

PORTS_FILE=$QLINE_CONFIG_DIR/ports_for_localhost.json
NETWORK_FILE=$QLINE_CONFIG_DIR/alice/network.json

for f in "$PORTS_FILE" "$NETWORK_FILE"; do
    [ -r "$f" ] || { echo "cannot read $f" >&2; exit 1; }
done

# ports on localhost
localhost_hw_alice=$(jq -r '.hw_alice' "$PORTS_FILE")
localhost_hw_bob=$(jq -r '.hw_bob' "$PORTS_FILE")
localhost_hws=$(jq -r '.hws' "$PORTS_FILE")
localhost_mon_alice=$(jq -r '.mon_alice' "$PORTS_FILE")
localhost_mon_bob=$(jq -r '.mon_bob' "$PORTS_FILE")
localhost_restartd_alice=$(jq -r '.restartd_alice' "$PORTS_FILE")
localhost_restartd_bob=$(jq -r '.restartd_bob' "$PORTS_FILE")
localhost_logd_alice=$(jq -r '.logd_alice' "$PORTS_FILE")
localhost_logd_bob=$(jq -r '.logd_bob' "$PORTS_FILE")
localhost_kms_alice=$(jq -r '.kms_alice' "$PORTS_FILE")
localhost_kms_bob=$(jq -r '.kms_bob' "$PORTS_FILE")

# ip and ports on the machines.  network.json is generated per-node by
# gen_config; alice/network.json holds the full ip struct (alice, bob, *_wrs)
# and full port struct, so it has all we need.
ip_alice=$(jq -r '.ip.alice' "$NETWORK_FILE")
ip_bob=$(jq -r '.ip.bob' "$NETWORK_FILE")
hw_port=$(jq -r '.port.hw' "$NETWORK_FILE")
hws_port=$(jq -r '.port.hws' "$NETWORK_FILE")
mon_port=$(jq -r '.port.mon' "$NETWORK_FILE")
restartd_port=$(jq -r '.port.restartd' "$NETWORK_FILE")
logd_port=$(jq -r '.port.logd' "$NETWORK_FILE")
kms_alice_port=$(jq -r '.port.kms_alice' "$NETWORK_FILE")
kms_bob_port=$(jq -r '.port.kms_bob' "$NETWORK_FILE")

# All forwards go over ONE ssh, not one ssh each.
#
# ~/.ssh/config commonly puts vq on `ControlMaster auto`.  Every separate
# `ssh -N -L ... vq` then attaches to that shared master and consumes a session
# slot, and sshd's MaxSessions defaults to 10.  The eleven forwards below plus
# ordinary interactive use exceed that, and the master wedges: fresh sessions to
# vq -- and to every node reached through it by ProxyCommand -- hang, while
# `ssh -O check vq` still reports "Master running".  Killing the `ssh -N -L`
# clients does not release the forwards either, since they are registered on the
# master and outlive their client; recovering needs `ssh -O exit vq`.
#
# ControlMaster=no + ControlPath=none keeps this on its own connection, so it
# can neither starve interactive sessions nor be torn down with them.
FORWARDS=(
    # hw
    -L "$localhost_hw_alice:$ip_alice:$hw_port"
    -L "$localhost_hw_bob:$ip_bob:$hw_port"
    # hws
    -L "$localhost_hws:$ip_alice:$hws_port"
    # mon
    -L "$localhost_mon_alice:$ip_alice:$mon_port"
    -L "$localhost_mon_bob:$ip_bob:$mon_port"
    # restartd (runs on each node bound to its own IP)
    -L "$localhost_restartd_alice:$ip_alice:$restartd_port"
    -L "$localhost_restartd_bob:$ip_bob:$restartd_port"
    # logd (runs on each node bound to its own IP)
    -L "$localhost_logd_alice:$ip_alice:$logd_port"
    -L "$localhost_logd_bob:$ip_bob:$logd_port"
    # kms (Alice serves on kms_alice port, Bob on kms_bob port)
    -L "$localhost_kms_alice:$ip_alice:$kms_alice_port"
    -L "$localhost_kms_bob:$ip_bob:$kms_bob_port"
)

LOCAL_PORTS=(
    "$localhost_hw_alice" "$localhost_hw_bob" "$localhost_hws"
    "$localhost_mon_alice" "$localhost_mon_bob"
    "$localhost_restartd_alice" "$localhost_restartd_bob"
    "$localhost_logd_alice" "$localhost_logd_bob"
    "$localhost_kms_alice" "$localhost_kms_bob"
)


# --------------------------------------------------------------- helpers ----

log() { printf '%s %s\n' "$(date '+%F %T')" "$*"; }

# Ports the tunnel is currently listening on, one per line.
listening_ports() {
    ss -ltnH 2>/dev/null | awk '{ n = split($4, a, ":"); print a[n] }' | sort -u
}

# True when every forward has a listener.  Catches an ssh that is still running
# while its forwards are gone -- a state no keepalive reports, and the one that
# turns every client call into "connection refused".
listeners_ok() {
    local listening p
    listening=$(listening_ports) || return 1
    for p in "${LOCAL_PORTS[@]}"; do
        grep -qx "$p" <<<"$listening" || return 1
    done
    return 0
}

missing_ports() {
    local listening p out=()
    listening=$(listening_ports)
    for p in "${LOCAL_PORTS[@]}"; do
        grep -qx "$p" <<<"$listening" || out+=("$p")
    done
    echo "${out[*]-}"
}

supervisor_pid() {
    [ -r "$PIDFILE" ] || return 1
    local pid
    pid=$(cat "$PIDFILE" 2>/dev/null)
    [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null || return 1
    echo "$pid"
}

# Tunnel ssh processes, whether still parented to a live supervisor or orphaned
# by one that died.  Matched on the first forward, which no other ssh carries.
tunnel_ssh_pids() {
    pgrep -f "ssh .*-L $localhost_hw_alice:$ip_alice:$hw_port" || true
}


# ------------------------------------------------------------------ stop ----

if [ "$MODE" = stop ]; then
    stopped=()
    if pid=$(supervisor_pid); then
        kill "$pid" 2>/dev/null
        for _ in $(seq 20); do
            kill -0 "$pid" 2>/dev/null || break
            sleep 0.2
        done
        kill -0 "$pid" 2>/dev/null && kill -9 "$pid" 2>/dev/null
        stopped+=("supervisor $pid")
    fi
    rm -f "$PIDFILE"

    # Sweep the ssh rather than trusting the supervisor's TERM trap to take it
    # down.  bash defers a trap until the running foreground command returns,
    # and the supervisor spends its time in `sleep $PROBE_INTERVAL`, so the trap
    # usually has not run by the time the SIGKILL above -- untrappable -- leaves
    # the ssh orphaned.  An orphan keeps all the forwards listening and can hold
    # a half-open connection that blocks a node's server against every client.
    ssh_pids=$(tunnel_ssh_pids)
    if [ -n "$ssh_pids" ]; then
        kill $ssh_pids 2>/dev/null
        for _ in $(seq 20); do
            [ -z "$(tunnel_ssh_pids)" ] && break
            sleep 0.2
        done
        remaining=$(tunnel_ssh_pids)
        [ -n "$remaining" ] && kill -9 $remaining 2>/dev/null
        stopped+=("ssh $(echo $ssh_pids)")
    fi

    if [ ${#stopped[@]} -eq 0 ]; then
        echo "not running"
    else
        echo "stopped $(IFS=', '; echo "${stopped[*]}")"
    fi
    exit 0
fi


# ---------------------------------------------------------------- status ----

if [ "$MODE" = status ]; then
    if pid=$(supervisor_pid); then
        echo "supervisor : running (pid $pid)"
        echo "ssh        : $(pgrep -P "$pid" -f '^ssh ' | tr '\n' ' ')"
    else
        echo "supervisor : not running"
    fi
    missing=$(missing_ports)
    if [ -z "$missing" ]; then
        echo "forwards   : all ${#LOCAL_PORTS[@]} listening"
    else
        echo "forwards   : NOT listening on $missing"
    fi
    echo "log        : $LOGFILE"
    exit 0
fi


# ------------------------------------------------------------- supervise ----

if [ "$MODE" = supervise ]; then
    echo $$ > "$PIDFILE"
    ssh_pid=

    shutdown() {
        [ -n "$ssh_pid" ] && kill "$ssh_pid" 2>/dev/null
        rm -f "$PIDFILE"
        log "supervisor stopped"
        exit 0
    }
    trap shutdown TERM INT

    log "supervisor started (pid $$)"
    backoff=$RETRY_MIN
    while :; do
        started=$SECONDS
        ssh "${SSH_OPTS[@]}" "${FORWARDS[@]}" vq &
        ssh_pid=$!
        log "ssh started (pid $ssh_pid)"

        # Watch the child and the listeners.  Killing ssh here drops us out of
        # the inner loop and straight into a rebuild.
        #
        # The listener check guards a tunnel that came up and then lost its
        # forwards.  It stays off for STARTUP_GRACE, because a fresh ssh needs
        # time to authenticate and bind, and ExitOnForwardFailure already makes
        # ssh exit by itself when a bind fails -- checking too early turns a
        # slow jump host into a restart loop against that host.
        while kill -0 "$ssh_pid" 2>/dev/null; do
            sleep "$PROBE_INTERVAL"
            kill -0 "$ssh_pid" 2>/dev/null || break
            (( SECONDS - started < STARTUP_GRACE )) && continue
            if ! listeners_ok; then
                log "forwards gone [$(missing_ports)] -- restarting ssh $ssh_pid"
                kill "$ssh_pid" 2>/dev/null
                break
            fi
        done

        wait "$ssh_pid" 2>/dev/null; rc=$?
        uptime=$(( SECONDS - started ))
        ssh_pid=

        # A tunnel that held for HEALTHY_AFTER was a working one, so its next
        # failure starts the backoff over.  Otherwise the delay doubles, so an
        # unreachable jump host is retried on a widening interval rather than
        # hammered every few seconds.
        (( uptime >= HEALTHY_AFTER )) && backoff=$RETRY_MIN
        log "ssh exited (status $rc) after ${uptime}s -- retrying in ${backoff}s"
        sleep "$backoff"
        (( backoff *= 2 ))
        (( backoff > RETRY_MAX )) && backoff=$RETRY_MAX
    done
fi


# ----------------------------------------------------------------- start ----

if pid=$(supervisor_pid); then
    echo "already running (supervisor pid $pid) -- $0 --status"
    exit 0
fi

# A supervisor that died can leave an ssh holding the forwards, or holding a
# half-open connection to a node that keeps that node's server blocked on it.
# Clear those out before claiming the ports.
stale=$(tunnel_ssh_pids)
if [ -n "$stale" ]; then
    echo "clearing stale tunnel: $stale"
    kill $stale 2>/dev/null
    sleep 2
fi

# The supervisor re-execs this script, so it needs the config in its own
# environment and an absolute path to run from.
export QLINE_CONFIG_DIR
setsid "$(readlink -f "$0")" --supervise >>"$LOGFILE" 2>&1 &

for _ in $(seq 50); do
    pid=$(supervisor_pid) && break
    sleep 0.2
done

if pid=$(supervisor_pid); then
    for _ in $(seq 50); do
        listeners_ok && break
        sleep 0.2
    done
    missing=$(missing_ports)
    if [ -z "$missing" ]; then
        echo "port forwarding up on supervisor pid $pid -- stop it with: $0 --stop"
    else
        echo "supervisor pid $pid started, forwards pending on $missing -- see $LOGFILE"
    fi
else
    echo "supervisor failed to start -- see $LOGFILE" >&2
    exit 1
fi
