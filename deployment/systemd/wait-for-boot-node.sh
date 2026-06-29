#!/bin/bash
# ExecStartPre helper for node.service.
#
# Enforces cross-host start ordering that systemd cannot express on its own:
# the Detector node bootstraps into the libp2p mesh through the Source node
# (its configured boot_node), so it must not start until the Source node is
# listening.
#
# The IP and port are read from the node config (libp2p.boot_node.address) so
# nothing is hardcoded here. The Source node is its own boot_node, so on that
# host the addresses match and we exit immediately without waiting.
set -u

CONFIG="${NODE_CONFIG:-/home/vq-user/config/node.json}"
TRIES=150      # give up after ~5 min (TRIES * SLEEP); node.service then retries
SLEEP=2

# Parse boot_node + our own address from the config. Print "" when we ARE the
# boot node, otherwise print "<ip> <port>" extracted from the /ip4/<ip>/tcp/<port>
# multiaddr.
read -r ip port < <(python3 - "$CONFIG" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
boot = d["libp2p"]["boot_node"]["address"]
own = d.get("external_address", "")
if boot == own:
    print("")                       # this node is the boot node -> no wait
else:
    p = boot.split("/")             # ['', 'ip4', '<ip>', 'tcp', '<port>']
    print(p[2], p[4])
PY
)

if [ -z "${ip:-}" ]; then
    echo "wait-for-boot-node: this node is the boot node; not waiting"
    exit 0
fi

echo "wait-for-boot-node: waiting for boot node ${ip}:${port}"
for i in $(seq 1 "$TRIES"); do
    if timeout 2 bash -c "exec 3<>/dev/tcp/${ip}/${port}" 2>/dev/null; then
        echo "wait-for-boot-node: ${ip}:${port} reachable after $((i * SLEEP))s"
        exit 0
    fi
    sleep "$SLEEP"
done

echo "wait-for-boot-node: timed out waiting for ${ip}:${port}" >&2
exit 1
