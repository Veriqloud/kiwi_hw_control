#!/bin/bash

scp "KBob:~/qline/hw_control/data/tdc/verify_gate*.txt" .

python plot_sp.py


