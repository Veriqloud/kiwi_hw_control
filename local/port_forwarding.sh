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


# get ip and ports on machines
# network.json is generated per-node by gen_config; alice/network.json holds the
# full ip struct (alice, bob, *_wrs) and full port struct, so it has all we need.
NETWORK_FILE=$QLINE_CONFIG_DIR/alice/network.json
ip_alice=$(jq '.ip.alice' $NETWORK_FILE | tr -d '"')
ip_bob=$(jq '.ip.bob' $NETWORK_FILE | tr -d '"')
hw_port=$(jq '.port.hw' $NETWORK_FILE)
hws_port=$(jq '.port.hws' $NETWORK_FILE)
mon_port=$(jq '.port.mon' $NETWORK_FILE)

# hw
ssh -N -L $localhost_hw_alice:$ip_alice:$hw_port vq &
ssh -N -L $localhost_hw_bob:$ip_bob:$hw_port vq &
# hws
ssh -N -L $localhost_hws:$ip_alice:$hws_port vq &
# mon
ssh -N -L $localhost_mon_alice:$ip_alice:$mon_port vq &
ssh -N -L $localhost_mon_bob:$ip_bob:$mon_port vq &



