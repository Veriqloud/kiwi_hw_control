#!/bin/bash

Alice=$SSH_ALICE
Bob=$SSH_BOB
scp "$Bob:~/qline/hw_control/data/tdc/fd_*_single*.txt" .
scp "$Bob:~/qline/hw_control/config/tmp.txt" "tmp_b.txt"
scp "$Alice:~/qline/hw_control/config/tmp.txt" "tmp_a.txt"

python3 plot_fd.py
python3 plot_fd_long.py


