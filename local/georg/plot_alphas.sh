#!/bin/bash

Alice=$SSH_ALICE
Bob=$SSH_BOB

scp "$Alice:~/qline/hw_control/data/ddr4/alpha.txt" alpha_a.txt
scp "$Bob:~/qline/hw_control/data/ddr4/alpha.txt" alpha_b.txt
scp "$Bob:~/qline/hw_control/data/ddr4/gcr.txt" .

python plot_alphas.py


