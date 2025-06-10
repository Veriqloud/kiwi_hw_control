#!/bin/bash

Alice=$SSH_ALICE
Bob=$SSH_BOB

rsync -v remote/hw_alice.py $Alice:~/qline_clean/hw_control/
rsync -v remote/ctl_alice.py $Alice:~/qline_clean/hw_control/
rsync -v remote/lib/*.py $Alice:~/qline_clean/hw_control/lib/
rsync -v remote/alice_server/*.py $Alice:~/qline_clean/server/

rsync -v remote/hw_bob.py $Bob:~/qline_clean/hw_control/
rsync -v remote/ctl_bob.py $Bob:~/qline_clean/hw_control/
rsync -v remote/lib/*.py $Bob:~/qline_clean/hw_control/lib/
rsync -v remote/lib/aurea/* $Bob:~/qline_clean/hw_control/lib/aurea/
rsync -v remote/bob_server/*.py $Bob:~/qline_clean/server/

#rsync -v remote/bob/hardware.py $Bob:~/qline/server/
#rsync -v remote/bob/ctl.py remote/bob/cal.py remote/bob/fpga.py $Bob:~/qline_clean/hw_control/

if [[ $# > 0 ]]; then
    if [[ $1 == "with_config" ]]; then
        rsync -v config/network.json $Alice:~/qline_clean/config/
        rsync -v config/network.json $Bob:~/qline_clean/config/
    else 
        echo "wrong argument"
    fi
fi







