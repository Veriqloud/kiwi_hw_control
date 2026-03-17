#!/bin/bash
source config.sh
curl -v \
    --url "http://$ALICE_IP:$ALICE_PORT/api/v1/keys/$BOB_ID/status" | jq
