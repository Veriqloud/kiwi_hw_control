#!/bin/bash

scp "KBob:~/qline/hw_control/data/tdc/fd_*_single.txt" .

python plot_fd.py


