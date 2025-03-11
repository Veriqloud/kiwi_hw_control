#!/bin/bash

player=$SSH_BOB
Bob=$SSH_BOB

scp "$player:~/qline/hw_control/data/ddr4/alpha.txt" .
scp "$Bob:~/qline/hw_control/data/ddr4/gcr.txt" .

python plot_alphas.py


