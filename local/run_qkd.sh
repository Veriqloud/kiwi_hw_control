#!/bin/bash
# run_qkd.sh - bring up one qline pair from the control host and report key status.
#   (default)          wake -> wait -> health-check -> report QBER + stored keys
#   --status           report only, no wake (and don't wait for a round)
#   --init             hws.py --full_init_<nm> (retried up to 3x); REQUIRED after a
#                      power cycle. Needs --laser, because Alice carries a 1310 and
#                      a 1510 laser and which one is patched in is a fact about the
#                      bench, not the config. Its `start` step raises
#                      /tmp/qkd_ready, so the node resumes QKD.
#   --laser 1310|1510  the laser currently patched in (required with --init)
#   --tune             hws.py --auto_control if QBER is above tolerance
#   --use_localhost    reach the nodes through port_forwarding.sh tunnels
#
# The nodes are driven over their own TCP servers -- restartd for service state,
# mon for hardware state, hws for calibration -- so bring-up needs neither ssh nor
# sudo on the nodes. QLINE_CONFIG_DIR names the pair completely; there is no
# qline1|qline2 argument. Wake reads the MACs from $QLINE_CONFIG_DIR/wake.json.
set -u

STATUS=0; INIT=0; TUNE=0; LASER=; LOCAL=
for a in "$@"; do case "$a" in
  --status) STATUS=1 ;; --init) INIT=1 ;; --tune) TUNE=1 ;;
  --use_localhost) LOCAL=--use_localhost ;;
  --laser=*) LASER="${a#--laser=}" ;;
  1310|1510) LASER="$a" ;;
  *) echo "unknown arg: $a"; exit 2 ;;
esac; done
case "$LASER" in ''|1310|1510) ;; *) echo "unknown laser: $LASER (1310|1510)"; exit 2 ;; esac
[ "$INIT" = 0 ] || [ -n "$LASER" ] || {
  echo "--init needs the laser: run_qkd.sh --init --laser 1310|1510"; exit 2; }

HERE="$(cd "$(dirname "$0")" && pwd)"
export QLINE_CONFIG_DIR="${QLINE_CONFIG_DIR:?please set it to the config dir for this pair}"
PAIR="$(basename "$QLINE_CONFIG_DIR")"
QTOL=0.09; fail=0
ok(){   echo "  [OK]   $*"; }
warn(){ echo "  [warn] $*"; }
act(){  echo "  [ACTION] $*"; fail=1; }
hdr(){  echo; echo "== $* =="; }
[ -f "$QLINE_CONFIG_DIR/alice/network.json" ] || { echo "config not found: $QLINE_CONFIG_DIR"; exit 2; }

PROBE="$(mktemp)"; trap 'rm -f "$PROBE"' EXIT
probe(){ python3 "$HERE/mon_readonly_probe.py" --quiet --brief $LOCAL >"$PROBE" 2>/dev/null; }
jget(){ python3 -c "import json;print(json.load(open('$PROBE')).get('$1',''))" 2>/dev/null; }
rd(){ python3 "$HERE/restart.py" $LOCAL "$@" 2>/dev/null; }

# 1. wake + wait for restartd. A node answering restartd has booted AND brought
#    its supervisor up, which is what the later steps actually need.
if [ "$STATUS" = 0 ]; then
  hdr "Wake $PAIR"
  if [ -f "$QLINE_CONFIG_DIR/wake.json" ]; then
    for m in $(python3 -c "
import json, os
d = json.load(open(os.environ['QLINE_CONFIG_DIR'] + '/wake.json'))
print(d['alice'], d['bob'])"); do
      wakeonlan "$m" >/dev/null 2>&1 && echo "  WoL -> $m" || warn "wakeonlan failed for $m"
    done
  else
    warn "no wake.json in $QLINE_CONFIG_DIR - skipping wake, power the nodes by hand"
  fi
  hdr "Wait for restartd"
  for n in alice bob; do printf "  %-6s " "$n"; up=0
    for _ in $(seq 1 60); do
      [ "$(rd "$n" ping | tail -1)" = ok ] && { up=1; echo up; break; }
      sleep 5
    done
    [ $up = 1 ] || { echo; act "$n restartd not answering (check power / WoL / BIOS)"; }
  done
  [ $fail = 1 ] && { echo; echo "A node did not come up - see ACTIONs."; exit 1; }
fi

# 2. hardware state, one mon probe for both nodes
hdr "WRS link + PCIe (mon)"
if probe; then
  for n in alice bob; do
    v="$(jget "pci_$n")"
    [ "$v" = ok ] && ok "$n xdma ok" || act "$n ${v:-mon gave no pci status}"
    [ "$(jget "wrs_ip_$n")" = 0 ] && ok "$n eth_wrs up" \
      || act "$n eth_wrs down or without a 192.168.10 address - reseat the WRS cable/SFP"
  done
else
  act "mon not reachable on both nodes - is mon.service up? (local/logs.py <node> tail mon)"
fi

# 3. services, via restartd
hdr "Services (restartd)"
for n in alice bob; do
  miss=""
  for _ in $(seq 1 24); do
    l="$(rd "$n" list)"; miss=""
    for s in hw hws gc kms node; do
      echo "$l" | grep -q "^$s: active" || miss="$miss $s"
    done
    [ -z "$miss" ] && break
    sleep 5
  done
  if [ -z "$miss" ]; then ok "$n hw hws gc kms node"
  else for s in $miss; do
         warn "$n $s = $(echo "$l" | sed -n "s|^$s: \([^ ]*\).*|\1|p")"
       done
  fi
done

# 4. calibrate (cold FPGA needs it; full_init's `start` raises /tmp/qkd_ready)
if [ "$INIT" = 1 ]; then
  hdr "Calibrate (hws --full_init_$LASER, up to 3 tries)"
  for t in 1 2 3; do
    out=$(python3 "$HERE/hws.py" $LOCAL "--full_init_$LASER" 2>&1)
    if echo "$out" | grep -q "start done" && ! echo "$out" | grep -qiE "command or error|CalledProcessError|can not open"; then
      ok "full_init_$LASER succeeded (try $t)"; break
    fi
    [ $t = 3 ] && act "full_init failed 3x - inspect: local/logs.py alice tail hws" \
              || warn "full_init try $t failed (fs_a is stochastic); retrying"
  done
fi

# 5. QKD-ready flag + QBER, both from mon. Re-probe: calibration changes each.
hdr "QKD-ready"
probe
ready=0
if [ "$(jget qkd_ready)" = up ]; then ready=1; ok "/tmp/qkd_ready up"
else act "/tmp/qkd_ready absent - node is idle; run with --init (its start step raises it)"; fi

hdr "QBER + keys"
qber=""
for _ in $(seq 1 9); do
  q="$(jget qber)"
  [[ "$q" =~ ^[0-9.]+$ ]] && [ "$q" != 0 ] && [ "$q" != 0.0 ] && { qber=$q; break; }
  { [ "$STATUS" = 1 ] || [ "$ready" = 0 ]; } && break
  sleep 10; probe
done
if [ -n "$qber" ]; then
  echo "  latest QBER: $qber (tolerance $QTOL)"
  if awk "BEGIN{exit !($qber > $QTOL)}"; then
    warn "QBER above tolerance - no net key produced"
    if [ "$TUNE" = 1 ]; then
      echo "  running hws --auto_control..."; python3 "$HERE/hws.py" $LOCAL --auto_control
      probe; echo "  QBER after tuning: $(jget qber)"
    else act "tune it: re-run with --tune (hws.py --auto_control)"; fi
  else ok "QBER within tolerance"; fi
else warn "no round data from mon (node idle/just started, or needs --init)"; fi

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
[ $fail = 0 ] && echo "  $PAIR is up. Retrieve keys: local/etsi14/get_key_alice.sh / get_key_bob.sh" \
             || echo "  $PAIR brought up with ACTIONS needed above."
exit $fail
