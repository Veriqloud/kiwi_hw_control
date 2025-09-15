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
ip_alice=$(jq '.ip.alice' $QLINE_CONFIG_DIR/network.json | tr -d '"')
ip_bob=$(jq '.ip.bob' $QLINE_CONFIG_DIR/network.json | tr -d '"')
hw_port=$(jq '.port.hw' $QLINE_CONFIG_DIR/network.json)
hws_port=$(jq '.port.hws' $QLINE_CONFIG_DIR/network.json)
mon_port=$(jq '.port.mon' $QLINE_CONFIG_DIR/network.json)

# hw
ssh -N -L $localhost_hw_alice:$ip_alice:$hw_port vq &
ssh -N -L $localhost_hw_bob:$ip_bob:$hw_port vq &
# hws
ssh -N -L $localhost_hws:$ip_alice:$hws_port vq &
# mon
ssh -N -L $localhost_mon_alice:$ip_alice:$mon_port vq &
ssh -N -L $localhost_mon_bob:$ip_bob:$mon_port vq &



