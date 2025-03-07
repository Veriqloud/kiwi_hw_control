#!/bin/bash

Bob=$SSH_BOB
scp "$Bob:~/qline/hw_control/data/tdc/fd_*_single.txt" .

python plot_fd.py


