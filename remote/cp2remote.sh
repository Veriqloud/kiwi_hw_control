#!/bin/bash

Alice=$SSH_ALICE

rsync -v lib/*.py $Alice:~/qline/hw_control/lib/
rsync -v main_Alice.py $Alice:~/qline/hw_control/
rsync -v client*.py $Alice:~/qline/hw_control/
rsync -v ../gc/target/release/gc_client ../gc/target/release/gc_control $Alice:~/qline/hw_control/
rsync -v ../gc/target/release/qber_client ../gc/target/release/gc_control $Alice:~/qline/hw_control/

Bob=$SSH_BOB

rsync -v lib/*.py $Bob:~/qline/hw_control/lib/
rsync -v main_Bob.py $Bob:~/qline/hw_control/
rsync -v server*.py $Bob:~/qline/hw_control/
rsync -v ../gc/target/release/gc_server $Bob:~/qline/hw_control/
rsync -v ../gc/target/release/qber_server $Bob:~/qline/hw_control/



