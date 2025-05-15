#!/bin/bash

Alice=$SSH_ALICE
Bob=$SSH_BOB

rsync -v target/release/alice $Alice:~/qline/bin/qber
#rsync -v config/ipc.json $Alice:~/qline/config/

rsync -v target/release/bob $Bob:~/qline/servers/qber
#rsync -v config/ipc.json $Bob:~/qline/config/




