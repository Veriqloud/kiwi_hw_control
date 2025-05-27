#!/bin/bash

Alice=$SSH_ALICE
Bob=$SSH_BOB

rsync -v target/release/alice $Alice:~/qline/server/gc
rsync -v target/release/controller $Alice:~/qline/bin/gc_controller
rsync -v target/release/bob $Bob:~/qline/server/gc








