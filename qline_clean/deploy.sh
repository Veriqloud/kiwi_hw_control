#!/bin/bash

Alice=$SSH_ALICE
Bob=$SSH_BOB

rsync -v remote/hw_alice.py remote/hws_alice.py remote/ctl_alice.py $Alice:~/qline/hw_control/
rsync -v remote/lib/*.py $Alice:~/qline/hw_control/lib/
rsync -v remote/alice_server/*.py $Alice:~/qline/server/

rsync -v remote/hw_bob.py remote/ctl_bob.py remote/hws_bob.py $Bob:~/qline/hw_control/
rsync -v remote/lib/*.py $Bob:~/qline/hw_control/lib/
rsync -v remote/lib/test_tdc/dma_from_device remote/lib/test_tdc/tdc_bin2txt $Bob:~/qline/hw_control/lib/test_tdc
rsync -v remote/lib/aurea/* $Bob:~/qline/hw_control/lib/aurea/
rsync -v remote/bob_server/*.py $Bob:~/qline/server/

#rsync -v remote/bob/hardware.py $Bob:~/qline/server/
#rsync -v remote/bob/ctl.py remote/bob/cal.py remote/bob/fpga.py $Bob:~/qline/hw_control/

if [[ $# > 0 ]]; then
    if [[ $1 == "with_config" ]]; then
        rsync -v config/network.json $Alice:~/qline/config/
        rsync -v config/network.json $Bob:~/qline/config/
        
        rsync -v -r config/registers $Alice:~/qline/config/
        rsync -v -r config/registers $Bob:~/qline/config/
    else 
        echo "wrong argument"
    fi
fi







