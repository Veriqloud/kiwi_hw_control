# ETSI-014 KMS connection settings for the qline1 SAE pair.
# Sourced by get_key_*.sh / get_status_*.sh.
#
# Flags (recognised anywhere in the args and stripped from the positional
# parameters, so a trailing key_ID still works):
#   --use_localhost   reach the KMS via the port_forwarding.sh tunnels on localhost
#                     instead of the node IPs.
#   --auth            talk to the KMS over HTTPS with mutual TLS, presenting the SAE
#                     client certificate. Use this when the KMS has mTLS enabled
#                     (meta_config kms.authentication=true -> kms.json SAEs.mtls=true).
#                     Without it the scripts use plain HTTP (works only when mTLS is off).
# e.g.  ./get_status_alice.sh --use_localhost --auth
#       ./get_key_alice.sh    --use_localhost --auth            # enc_keys (mTLS)
#       ./get_key_bob.sh      --use_localhost --auth <key_ID>   # dec_keys (mTLS)
#
# Localhost ports are read from <QLINE_CONFIG_DIR>/ports_for_localhost.json.
# With --auth the client cert/key/CA come from $KMS_CLIENT_CERTS
# (default ~/qline1_kms_client): ca.crt, sae_cert.pem, sae_key.pem -- the client/
# bundle produced by `gen_config --gen-certs`. The generated server cert's SAN
# covers localhost/127.0.0.1 and the node IP, so --auth works both over the tunnel
# and against the node IP directly.

ALICE_ID="QmTsMUaLQZh2PuRCAVRyH4CCSgg23bgoPmVa5mqDT1DL6S"
BOB_ID="QmcRZWX5XnVFXDceknYLEu7LaRceU2W2StNAznpg4kafnd"

USE_LOCALHOST=0
AUTH=0
_args=()
for _a in "$@"; do
    case "$_a" in
        --use_localhost) USE_LOCALHOST=1 ;;
        --auth)          AUTH=1 ;;
        *)               _args+=("$_a") ;;
    esac
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

# Scheme + curl TLS options. CURL_TLS is an array so the scripts can splice it in
# as `curl "${CURL_TLS[@]}" ...` (empty and harmless when --auth is not given).
if [ "$AUTH" = 1 ]; then
    SCHEME="https"
    CERT_DIR="${KMS_CLIENT_CERTS:-$HOME/qline1_kms_client}"
    CURL_TLS=(--cert "$CERT_DIR/sae_cert.pem" --key "$CERT_DIR/sae_key.pem" --cacert "$CERT_DIR/ca.crt")
    if [ ! -f "$CERT_DIR/sae_cert.pem" ]; then
        echo "warning: --auth set but SAE client cert not found in $CERT_DIR" >&2
        echo "         (set KMS_CLIENT_CERTS or run 'gen_config --gen-certs' and copy client/)" >&2
    fi
else
    SCHEME="http"
    CURL_TLS=()
fi
