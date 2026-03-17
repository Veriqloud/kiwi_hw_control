#!/bin/bash
source config.sh

if [ $# -eq 1 ]; then
    # dec_keys
    curl -v -X POST \
        -H "Content-Type: application/json"\
        --data '{"number":1, "size":512, "key_IDs": [ { "key_ID": "'$1'"} ] }' \
        "http://$ALICE_IP:$ALICE_PORT/api/v1/keys/$BOB_ID/dec_keys" | jq
else
    # enc_keys
    curl -v -X POST \
        -H "Content-Type: application/json"\
        --data '{"number":1, "size":512}' \
        "http://$ALICE_IP:$ALICE_PORT/api/v1/keys/$BOB_ID/enc_keys" | jq
fi

