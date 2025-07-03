#!/bin/bash

Bob=$SSH_BOB

scp "$Bob:~/qline/hw_control/data/tdc/verify_gate*.txt" .

python plot_sp.py


