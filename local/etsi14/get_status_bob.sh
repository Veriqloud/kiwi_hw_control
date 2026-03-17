#!/bin/bash
source config.sh
curl -v \
    --url "http://$BOB_IP:$BOB_PORT/api/v1/keys/$ALICE_ID/status" | jq
