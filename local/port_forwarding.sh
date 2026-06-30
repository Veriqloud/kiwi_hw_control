#!/bin/bash

if [ -z "$QLINE_CONFIG_DIR" ]; then
    echo "Please set QLINE_CONFIG_DIR"
    exit
fi

# get ports on localhost 
# hw
localhost_hw_alice=$(jq '.hw_alice' $QLINE_CONFIG_DIR/ports_for_localhost.json)
localhost_hw_bob=$(jq '.hw_bob' $QLINE_CONFIG_DIR/ports_for_localhost.json)
# hws
localhost_hws=$(jq '.hws' $QLINE_CONFIG_DIR/ports_for_localhost.json)
# mon
localhost_mon_alice=$(jq '.mon_alice' $QLINE_CONFIG_DIR/ports_for_localhost.json)
localhost_mon_bob=$(jq '.mon_bob' $QLINE_CONFIG_DIR/ports_for_localhost.json)
# restartd
localhost_restartd_alice=$(jq '.restartd_alice' $QLINE_CONFIG_DIR/ports_for_localhost.json)
localhost_restartd_bob=$(jq '.restartd_bob' $QLINE_CONFIG_DIR/ports_for_localhost.json)
# logd
localhost_logd_alice=$(jq '.logd_alice' $QLINE_CONFIG_DIR/ports_for_localhost.json)
localhost_logd_bob=$(jq '.logd_bob' $QLINE_CONFIG_DIR/ports_for_localhost.json)
# kms (ETSI-014 key retrieval REST API)
localhost_kms_alice=$(jq '.kms_alice' $QLINE_CONFIG_DIR/ports_for_localhost.json)
localhost_kms_bob=$(jq '.kms_bob' $QLINE_CONFIG_DIR/ports_for_localhost.json)


# get ip and ports on machines
# network.json is generated per-node by gen_config; alice/network.json holds the
# full ip struct (alice, bob, *_wrs) and full port struct, so it has all we need.
NETWORK_FILE=$QLINE_CONFIG_DIR/alice/network.json
ip_alice=$(jq '.ip.alice' $NETWORK_FILE | tr -d '"')
ip_bob=$(jq '.ip.bob' $NETWORK_FILE | tr -d '"')
hw_port=$(jq '.port.hw' $NETWORK_FILE)
hws_port=$(jq '.port.hws' $NETWORK_FILE)
mon_port=$(jq '.port.mon' $NETWORK_FILE)
restartd_port=$(jq '.port.restartd' $NETWORK_FILE)
logd_port=$(jq '.port.logd' $NETWORK_FILE)
kms_alice_port=$(jq '.port.kms_alice' $NETWORK_FILE)
kms_bob_port=$(jq '.port.kms_bob' $NETWORK_FILE)

# hw
ssh -N -L $localhost_hw_alice:$ip_alice:$hw_port vq &
ssh -N -L $localhost_hw_bob:$ip_bob:$hw_port vq &
# hws
ssh -N -L $localhost_hws:$ip_alice:$hws_port vq &
# mon
ssh -N -L $localhost_mon_alice:$ip_alice:$mon_port vq &
ssh -N -L $localhost_mon_bob:$ip_bob:$mon_port vq &
# restartd (restartd runs on each node bound to its own IP)
ssh -N -L $localhost_restartd_alice:$ip_alice:$restartd_port vq &
ssh -N -L $localhost_restartd_bob:$ip_bob:$restartd_port vq &
# logd (logd runs on each node bound to its own IP)
ssh -N -L $localhost_logd_alice:$ip_alice:$logd_port vq &
ssh -N -L $localhost_logd_bob:$ip_bob:$logd_port vq &
# kms (Alice serves on kms_alice port, Bob on kms_bob port)
ssh -N -L $localhost_kms_alice:$ip_alice:$kms_alice_port vq &
ssh -N -L $localhost_kms_bob:$ip_bob:$kms_bob_port vq &



