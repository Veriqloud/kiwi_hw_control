#!/bin/bash
source config.sh
curl -v "${CURL_TLS[@]}" \
    --url "$SCHEME://$ALICE_IP:$ALICE_PORT/api/v1/keys/$BOB_ID/status" | jq
