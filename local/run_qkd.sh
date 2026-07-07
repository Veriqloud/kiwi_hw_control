#!/bin/bash
# run_qkd.sh - bring up the qline pair from the control host and report key status.
#   (default)  wake -> wait -> health-check -> report QBER + stored keys
#   --status   report only, no wake (and don't wait for a round)
#   --init     hws.py --full_init (retried up to 3x); REQUIRED after a power cycle.
#              Its `start` step auto-raises /tmp/qkd_ready, so the node resumes QKD.
#   --tune     hws.py --auto_control if QBER is above tolerance
#
# A cold-booted FPGA has 0 counts and the node idles until /tmp/qkd_ready exists,
# so after a power cycle the command you want is:  run_qkd.sh --init
# Notes live in memory: qline1-operations, restartd-tool, logd-tool.
set -u

QLINE=qline1; STATUS=0; INIT=0; TUNE=0
for a in "$@"; do case "$a" in
  --status) STATUS=1 ;; --init) INIT=1 ;; --tune) TUNE=1 ;;
  qline1|qline2) QLINE="$a" ;; *) echo "unknown arg: $a"; exit 2 ;;
esac; done
case "$QLINE" in qline1) AS=KAlice; BS=KBob ;; qline2) AS=KAlice2; BS=KBob2 ;; esac

HERE="$(cd "$(dirname "$0")" && pwd)"
export QLINE_CONFIG_DIR="${QLINE_CONFIG_DIR:-$HOME/kiwi_hw_control/config/$QLINE}"
SSH="ssh -o BatchMode=yes -o ConnectTimeout=8"
QTOL=0.09; fail=0
ok(){   echo "  [OK]   $*"; }
warn(){ echo "  [warn] $*"; }
act(){  echo "  [ACTION] $*"; fail=1; }
hdr(){  echo; echo "== $* =="; }
[ -f "$QLINE_CONFIG_DIR/alice/network.json" ] || { echo "config not found: $QLINE_CONFIG_DIR"; exit 2; }

# 1. wake + wait for ssh
if [ "$STATUS" = 0 ]; then
  hdr "Wake $QLINE"; bash "$HERE/wake.sh" "$QLINE"
  hdr "Wait for SSH"
  for h in $AS $BS; do printf "  %-8s " "$h"; up=0
    for _ in $(seq 1 60); do $SSH "$h" true 2>/dev/null && { up=1; echo up; break; }; sleep 5; done
    [ $up = 1 ] || act "$h not reachable (check power / WoL / BIOS)"
  done
  [ $fail = 1 ] && { echo; echo "A node did not boot - see ACTIONs."; exit 1; }
fi

# 2. WRS link + PCIe
hdr "WRS link + PCIe"
for h in $AS $BS; do
  [ "$($SSH "$h" 'cat /sys/class/net/eth_wrs/carrier 2>/dev/null')" = 1 ] \
    && ok "$h eth_wrs up" || act "$h eth_wrs DOWN - reseat the White Rabbit cable/SFP"
  [ "$($SSH "$h" 'test -e /dev/xdma0_user && echo y')" = y ] \
    && ok "$h xdma present" || act "$h xdma missing - PCIe/FPGA (lspci | grep -i xilinx)"
done

# 3. services (gc/hw/hws needed before calibration; node drives the pipeline)
hdr "Services"
for h in $AS $BS; do for s in hw hws gc kms node; do
  st=""; for _ in $(seq 1 24); do st=$($SSH "$h" "systemctl is-active $s" 2>/dev/null); [ "$st" = active ] && break; sleep 5; done
  [ "$st" = active ] && ok "$h $s" || warn "$h $s = ${st:-unknown}"
done; done

# 4. calibrate (cold FPGA needs it; full_init's `start` auto-raises /tmp/qkd_ready)
if [ "$INIT" = 1 ]; then
  hdr "Calibrate (hws --full_init, up to 3 tries)"
  for t in 1 2 3; do
    out=$(python3 "$HERE/hws.py" --full_init 2>&1)
    if echo "$out" | grep -q "start done" && ! echo "$out" | grep -qiE "command or error|CalledProcessError|can not open"; then
      ok "full_init succeeded (try $t)"; break
    fi
    [ $t = 3 ] && act "full_init failed 3x - inspect: local/logs.py alice tail hws" \
              || warn "full_init try $t failed (fs_a is stochastic); retrying"
  done
fi

# 5. QKD-ready flag (node idles until this exists)
hdr "QKD-ready"
if $SSH "$AS" 'test -e /tmp/qkd_ready'; then ready=1; ok "/tmp/qkd_ready up"
else ready=0; act "/tmp/qkd_ready absent - node is idle; run with --init (its start step raises it)"; fi

# 6. QBER + stored keys (wait up to ~90s for the first round, unless --status/not-ready)
hdr "QBER + keys"
qber=""
for _ in $(seq 1 9); do
  q=$($SSH "$AS" 'tail -1 /tmp/node_stats.csv 2>/dev/null | cut -d";" -f2')
  [[ "$q" =~ ^[0-9.]+$ ]] && { qber=$q; break; }
  { [ "$STATUS" = 1 ] || [ "$ready" = 0 ]; } && break
  sleep 10
done
if [ -n "$qber" ]; then
  echo "  latest QBER: $qber (tolerance $QTOL)"
  if awk "BEGIN{exit !($qber > $QTOL)}"; then
    warn "QBER above tolerance - no net key produced"
    if [ "$TUNE" = 1 ]; then
      echo "  running hws --auto_control..."; python3 "$HERE/hws.py" --auto_control
      echo "  QBER after tuning: $($SSH "$AS" 'tail -1 /tmp/node_stats.csv | cut -d";" -f2')"
    else act "tune it: re-run with --tune (hws.py --auto_control)"; fi
  else ok "QBER within tolerance"; fi
else warn "no round data in /tmp/node_stats.csv (node idle/just started, or needs --init)"; fi

read -r AIP APORT BID < <(python3 -c "
import json, os
c = os.environ['QLINE_CONFIG_DIR']
n = json.load(open(c + '/alice/network.json')); nd = json.load(open(c + '/alice/node.json'))
print(n['ip']['alice'], n['port']['kms_alice'], next(p[0] for p in nd['peers'] if p[1] == 'Detector'))
" 2>/dev/null)
if [ -n "${AIP:-}" ]; then
  cnt=$(curl -s --max-time 8 "http://$AIP:$APORT/api/v1/keys/$BID/status" \
        | python3 -c 'import sys,json; print(json.load(sys.stdin).get("stored_key_count","?"))' 2>/dev/null)
  [ -n "${cnt:-}" ] && ok "Alice KMS stored keys: $cnt" || warn "KMS status not reachable on $AIP:$APORT"
fi

# summary
hdr "Summary"
[ $fail = 0 ] && echo "  $QLINE is up. Retrieve keys: local/etsi14/get_key_alice.sh / get_key_bob.sh" \
             || echo "  $QLINE brought up with ACTIONS needed above."
exit $fail
