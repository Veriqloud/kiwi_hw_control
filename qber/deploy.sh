#!/bin/bash

Alice=$SSH_ALICE
Bob=$SSH_BOB

rsync -v target/release/alice $Alice:~/qline/bin/qber
rsync -v target/release/bob $Bob:~/qline/server/qber

if [[ $# > 0 ]]; then
    if [[ $1 == "with_config" ]]; then
        rsync -v config/network_alice.json $Alice:~/qline/config/network.json
        rsync -v config/fifos_alice.json $Alice:~/qline/config/fifos.json

        rsync -v config/fifos_bob.json $Bob:~/qline/config/fifos.json
    else 
        echo "wrong argument"
    fi
fi







