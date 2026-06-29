#!/bin/bash
# run_qkd.sh - bring up the qline QKD pair from the control host and report key
# status. Encodes the bring-up/recovery routine: wake -> wait for boot ->
# check WRS/PCIe -> wait for services -> recover a wedged gc -> report QBER + keys.
#
# Usage:
#   QLINE_CONFIG_DIR=.../config/qline1 ./run_qkd.sh [qline1] [--status] [--init] [--tune]
#     (default)   wake nodes, wait, health-check, recover gc if wedged, report
#     --status    skip wake/boot-wait; just report health + QBER + key count
#     --init      run `hws.py --full_init` during bring-up (full recalibration)
#     --tune      run `hws.py --auto_control` if QBER is above tolerance
#
# Recover a powered-off node afterwards with: ./wake.sh qline1
# Notes live in memory: qline1-operations, restartd-tool.
set -u

# ---- args ----
QLINE=qline1; STATUS=0; INIT=0; TUNE=0
for a in "$@"; do
  case "$a" in
    --status) STATUS=1 ;;
    --init)   INIT=1 ;;
    --tune)   TUNE=1 ;;
    qline1|qline2) QLINE="$a" ;;
    *) echo "unknown arg: $a"; exit 2 ;;
  esac
done

case "$QLINE" in
  qline1) AS=KAlice;  BS=KBob  ;;
  qline2) AS=KAlice2; BS=KBob2 ;;
esac

HERE="$(cd "$(dirname "$0")" && pwd)"
export QLINE_CONFIG_DIR="${QLINE_CONFIG_DIR:-$HOME/kiwi_hw_control/config/$QLINE}"
SSH="ssh -o BatchMode=yes -o ConnectTimeout=8"
QTOL=0.09
fail=0

ok()   { echo "  [OK]   $*"; }
warn() { echo "  [warn] $*"; }
act()  { echo "  [ACTION NEEDED] $*"; fail=1; }
hdr()  { echo; echo "== $* =="; }

if [ ! -f "$QLINE_CONFIG_DIR/alice/network.json" ]; then
  echo "config not found: $QLINE_CONFIG_DIR/alice/network.json"; exit 2
fi

# ---- 1. wake + wait for boot ----
if [ "$STATUS" = 0 ]; then
  hdr "1. Wake $QLINE"
  bash "$HERE/wake.sh" "$QLINE"

  hdr "2. Wait for SSH"
  for h in $AS $BS; do
    printf "  %-8s " "$h"; up=0
    for _ in $(seq 1 60); do
      if $SSH "$h" true 2>/dev/null; then up=1; echo "reachable"; break; fi
      sleep 5
    done
    [ $up = 1 ] || act "$h not reachable after ~5min (check power / WoL / BIOS)"
  done
  [ $fail = 1 ] && { hdr "Summary"; echo "A node did not boot - see ACTIONs above."; exit 1; }
fi

# ---- 3. WRS link + PCIe (today's failure mode) ----
hdr "3. WRS link + PCIe"
for h in $AS $BS; do
  c=$($SSH "$h" 'cat /sys/class/net/eth_wrs/carrier 2>/dev/null')
  x=$($SSH "$h" 'test -e /dev/xdma0_user && echo yes || echo no')
  [ "$c" = 1 ]   && ok "$h eth_wrs carrier up"     || act "$h eth_wrs DOWN - reseat the White Rabbit cable/SFP"
  [ "$x" = yes ] && ok "$h xdma0_user present"      || act "$h xdma missing - PCIe/FPGA problem (lspci | grep -i xilinx)"
done

# ---- optional full recalibration ----
if [ "$INIT" = 1 ]; then
  hdr "3b. hws --full_init (recalibrate)"
  python3 "$HERE/hws.py" --full_init
fi

# ---- 4. wait for services ----
hdr "4. Services (gc / kms / node)"
for h in $AS $BS; do
  for s in gc kms node; do
    st=""
    for _ in $(seq 1 24); do            # node waits on boot-node; allow ~2min
      st=$($SSH "$h" "systemctl is-active $s.service" 2>/dev/null)
      [ "$st" = active ] && break
      sleep 5
    done
    [ "$st" = active ] && ok "$h $s" || warn "$h $s = ${st:-unknown}"
  done
done

# ---- 5. gc wedge detection + recovery ----
hdr "5. gc health"
wchan=$($SSH "$AS" 'cat /proc/$(systemctl show -p MainPID --value gc.service)/wchan 2>/dev/null')
if [ "$wchan" = futex_wait_queue ]; then
  warn "alice gc wedged (futex) - restarting gc (bob,alice) then node (alice,bob)"
  python3 "$HERE/restart.py" bob   restart gc
  python3 "$HERE/restart.py" alice restart gc
  python3 "$HERE/restart.py" alice restart node
  python3 "$HERE/restart.py" bob   restart node
  echo "  giving the pipeline time to produce a round..."; sleep 60
else
  ok "alice gc not wedged (wchan=${wchan:-?})"
fi

# ---- 6. QBER + keys ----
hdr "6. QBER + keys"
qber=$($SSH "$AS" 'tail -1 /tmp/node_stats.csv 2>/dev/null | cut -d";" -f2')
if [ -n "$qber" ]; then
  echo "  latest QBER: $qber (tolerance $QTOL)"
  if awk "BEGIN{exit !($qber > $QTOL)}"; then
    warn "QBER above tolerance - no net key will be produced"
    if [ "$TUNE" = 1 ]; then
      echo "  running hws --auto_control (a few minutes)..."
      python3 "$HERE/hws.py" --auto_control
      qber=$($SSH "$AS" 'tail -1 /tmp/node_stats.csv 2>/dev/null | cut -d";" -f2')
      echo "  QBER after tuning: $qber"
    else
      act "tune it: QLINE_CONFIG_DIR=$QLINE_CONFIG_DIR python3 hws.py --auto_control (or re-run with --tune)"
    fi
  else
    ok "QBER within tolerance"
  fi
else
  warn "no QBER in /tmp/node_stats.csv yet - node may need more time, or calibrate: hws.py --full_init (or --init)"
fi

# stored key count from the KMS (ETSI 014), derived from config (qline-agnostic)
read -r AIP APORT BID < <(python3 -c "
import json, os
c = os.environ['QLINE_CONFIG_DIR']
n = json.load(open(c + '/alice/network.json'))
nd = json.load(open(c + '/alice/node.json'))
bid = next(p[0] for p in nd['peers'] if p[1] == 'Detector')
print(n['ip']['alice'], n['port']['kms_alice'], bid)
" 2>/dev/null)
if [ -n "${AIP:-}" ]; then
  cnt=$(curl -s --max-time 8 "http://$AIP:$APORT/api/v1/keys/$BID/status" \
        | python3 -c 'import sys,json; print(json.load(sys.stdin).get("stored_key_count","?"))' 2>/dev/null)
  [ -n "${cnt:-}" ] && ok "Alice KMS stored keys: $cnt" || warn "KMS status not reachable on $AIP:$APORT"
fi

# ---- summary ----
hdr "Summary"
if [ $fail = 0 ]; then
  echo "  $QLINE is up. Retrieve keys with local/etsi14/get_key_alice.sh / get_key_bob.sh"
else
  echo "  $QLINE brought up with ACTIONS needed above."
fi
exit $fail
