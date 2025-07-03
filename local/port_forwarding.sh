#!/bin/bash


# get ports on localhost 
localhost_hw_alice=`jq '.hw_alice' ../config/ports_for_localhost.json`
localhost_hw_bob=`jq '.hw_bob' ../config/ports_for_localhost.json`
localhost_hws=`jq '.hws' ../config/ports_for_localhost.json`

# get ip and ports on machines
ip_alice=`jq '.ip.alice' ../config/network.json | tr -d '"'`
ip_bob=`jq '.ip.bob' ../config/network.json | tr -d '"'`
hw_port=`jq '.port.hw' ../config/network.json`
hws_port=`jq '.port.hws' ../config/network.json`

ssh -N -L $localhost_hw_alice:$ip_alice:$hw_port vq &
ssh -N -L $localhost_hw_bob:$ip_bob:$hw_port vq &
ssh -N -L $localhost_hws:$ip_alice:$hws_port vq &



