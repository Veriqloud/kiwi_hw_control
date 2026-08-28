#!/bin/bash
set -euo pipefail

usage() {
    cat <<'USAGE'
Usage: gen_defaut_config.sh [-h|--help]

Generates the default network configuration for an Alice/Bob qline pair
(steps 2 and 3 of deploy_qline_files.sh), with an optional SSH key copy
(step 1) asked interactively as a yes/no.
Run from config/ on the control machine (no arguments, everything is
asked interactively).

What the script asks for:
  - Copy the SSH key to Alice/Bob first? [y/N]
  - Alice's machine name (e.g. alice1)
  - Alice's client IP
  - Bob's machine name (e.g. bob1)
  - Bob's client IP
  - SSH user                   (default: vq-user, only asked if copying the key)
  - Alice's internal WRS IP    (default: 192.168.10.11)
  - Bob's internal WRS IP      (default: 192.168.10.12)

What it does next, in order:
  1. ssh-copy-id to Alice and Bob            (only if you answered yes)
  2. make                                    (build gc/qber/gen_config)
  3. gen_config -c meta_config.json -g       (network config + certificates,
                                               written to qline_<alice>_<bob>/)

Does NOT deploy files (deploy.sh) nor set up systemd services -- run
deploy_qline_files.sh (deployment/) or the manual steps for that.
USAGE
    exit 0
}

for arg in "$@"; do
    case "$arg" in
        -h|--help) usage ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Default qline config generation (Alice / Bob) ==="
echo "(run with --help for the full step-by-step detail)"
echo

read -rp "1/3 Copy SSH key to Alice/Bob first? [y/N] " COPY_SSH_KEY

read -rp "Alice's machine name (e.g. alice1): " ALICE_NAME
read -rp "Alice's IP address (client network): " ALICE_IP
read -rp "Bob's machine name (e.g. bob1): " BOB_NAME
read -rp "Bob's IP address (client network): " BOB_IP
read -rp "Alice's internal WRS IP [192.168.10.11]: " ALICE_WRS
ALICE_WRS=${ALICE_WRS:-192.168.10.11}
read -rp "Bob's internal WRS IP [192.168.10.12]: " BOB_WRS
BOB_WRS=${BOB_WRS:-192.168.10.12}

CONFIG_NAME="qline_${ALICE_NAME}_${BOB_NAME}"
QLINE_CONFIG_DIR="$SCRIPT_DIR/$CONFIG_NAME"

echo
echo "Summary:"
echo "  Alice : $ALICE_IP  (wrs: $ALICE_WRS)"
echo "  Bob   : $BOB_IP  (wrs: $BOB_WRS)"
echo "  Config: $QLINE_CONFIG_DIR"
read -rp "Continue? [y/N] " CONFIRM
[[ "$CONFIRM" =~ ^[oOyY] ]] || { echo "Aborted."; exit 1; }

if [[ "$COPY_SSH_KEY" =~ ^[oOyY] ]]; then
    read -rp "SSH user [vq-user]: " SSH_USER
    SSH_USER=${SSH_USER:-vq-user}

    echo
    echo "==> 1/3 Copying SSH key (password prompt if needed)"
    ssh-copy-id "$SSH_USER@$ALICE_IP"
    ssh-copy-id "$SSH_USER@$BOB_IP"
else
    echo
    echo "==> 1/3 Skipped (no SSH key copy)"
fi

echo
echo "==> 2/3 Build (make)"
make -C "$SCRIPT_DIR/../deployment"

echo
echo "==> 3/3 Generating the network configuration"
mkdir -p "$QLINE_CONFIG_DIR"
TEMPLATE="$SCRIPT_DIR/qline1/meta_config.json"
if [ ! -f "$QLINE_CONFIG_DIR/meta_config.json" ]; then
    cp "$TEMPLATE" "$QLINE_CONFIG_DIR/meta_config.json"
fi

python3 - "$QLINE_CONFIG_DIR/meta_config.json" "$ALICE_IP" "$BOB_IP" "$ALICE_WRS" "$BOB_WRS" <<'PYEOF'
import json, sys
path, alice_ip, bob_ip, alice_wrs, bob_wrs = sys.argv[1:6]
with open(path) as f:
    cfg = json.load(f)
cfg["ip"]["alice"] = alice_ip
cfg["ip"]["bob"] = bob_ip
cfg["ip"]["alice_wrs"] = alice_wrs
cfg["ip"]["bob_wrs"] = bob_wrs
with open(path, "w") as f:
    json.dump(cfg, f, indent=4)
PYEOF

GEN_CONFIG_BIN="$SCRIPT_DIR/gen_config/target/release/gen_config"
if [ ! -x "$GEN_CONFIG_BIN" ]; then
    echo "gen_config not found at $GEN_CONFIG_BIN (did 'make' succeed?)"
    exit 1
fi
( cd "$QLINE_CONFIG_DIR" && "$GEN_CONFIG_BIN" -c meta_config.json -g )

echo
echo "Config generation done."
echo "QLINE_CONFIG_DIR=$QLINE_CONFIG_DIR"
