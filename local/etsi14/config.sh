# ETSI-014 KMS connection settings for the qline1 SAE pair.
# Sourced by get_key_*.sh / get_status_*.sh.
#
# Pass --use_localhost (anywhere in the args) to reach the KMS via the
# port_forwarding.sh tunnels on localhost instead of the node IPs. The flag is
# stripped from the positional parameters so the caller's key_ID arg still works,
# e.g.  ./get_key_alice.sh --use_localhost           # enc_keys over tunnel
#       ./get_key_alice.sh --use_localhost <key_ID>  # dec_keys over tunnel
# Localhost ports are read from <QLINE_CONFIG_DIR>/ports_for_localhost.json.

ALICE_ID="QmTsMUaLQZh2PuRCAVRyH4CCSgg23bgoPmVa5mqDT1DL6S"
BOB_ID="QmcRZWX5XnVFXDceknYLEu7LaRceU2W2StNAznpg4kafnd"

USE_LOCALHOST=0
_args=()
for _a in "$@"; do
    if [ "$_a" = "--use_localhost" ]; then
        USE_LOCALHOST=1
    else
        _args+=("$_a")
    fi
done
set -- "${_args[@]}"

if [ "$USE_LOCALHOST" = 1 ]; then
    CFG="${QLINE_CONFIG_DIR:-$HOME/kiwi_hw_control/config/qline1}"
    ALICE_IP="localhost"
    BOB_IP="localhost"
    ALICE_PORT=$(jq '.kms_alice' "$CFG/ports_for_localhost.json")
    BOB_PORT=$(jq '.kms_bob' "$CFG/ports_for_localhost.json")
else
    ALICE_IP="192.168.1.14"
    BOB_IP="192.168.1.77"
    ALICE_PORT=13003
    BOB_PORT=13004
fi
