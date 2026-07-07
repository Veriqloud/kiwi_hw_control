#!/bin/bash
source config.sh
curl -v "${CURL_TLS[@]}" \
    --url "$SCHEME://$BOB_IP:$BOB_PORT/api/v1/keys/$ALICE_ID/status" | jq
