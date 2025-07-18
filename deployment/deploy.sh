#!/bin/bash

Alice=$SSH_ALICE
Bob=$SSH_BOB
qline_config_dir=$QLINE_CONFIG_DIR

usage() {
    echo "Usage: $0 {gc|qber|control|config|registers|rng|all}"
    exit 1
}

gc(){
    cd ../gc/target/release
    rsync -v alice $Alice:~/qline/server/gc
    rsync -v bob $Bob:~/qline/server/gc
    cd -
}

qber(){
    cd ../qber/target/release
    rsync -v alice $Alice:~/qline/server/qber
    rsync -v bob $Bob:~/qline/server/qber
    cd -
}

control(){
    cd ../remote
    rsync -v hw_alice.py hws_alice.py ctl_alice.py mon_alice.py $Alice:~/qline/hw_control/
    rsync -v lib/*.py $Alice:~/qline/hw_control/lib/
    rsync -v alice_server/*.py $Alice:~/qline/server/
    rsync -v control_servers.sh $Alice:~/qline/server/

    rsync -v hw_bob.py ctl_bob.py hws_bob.py mon_bob.py $Bob:~/qline/hw_control/
    rsync -v lib/*.py $Bob:~/qline/hw_control/lib/
    rsync -v lib/test_tdc/dma_from_device lib/test_tdc/tdc_bin2txt $Bob:~/qline/hw_control/lib/test_tdc
    rsync -v lib/aurea/* $Bob:~/qline/hw_control/lib/aurea/
    rsync -v bob_server/*.py $Bob:~/qline/server/
    rsync -v control_servers.sh $Bob:~/qline/server/
    cd -
}

config(){
    cd $qline_config_dir
    rsync -v remote/alice/*.json $Alice:~/qline/config/
    rsync -v remote/bob/*.json $Bob:~/qline/config/
    cd -
}

registers(){
    cd ../remote
    rsync -v registers $Alice:~/qline/config/
    rsync -v registers $Bob:~/qline/config/
    cd -
}

rng(){
    cd ../remote
    rsync -v rng_fpga/rng2fpga $Alice:~/qline/rng_fpga/
    rsync -v rng_fpga/rng2fpga $Bob:~/qline/rng_fpga/
}

# Check that exactly one argument is provided
[ $# -eq 1 ] || usage

case "$1" in
    gc)
        gc
        ;;
    qber)
        qber
        ;;
    control)
        control
        ;;
    config)
        config
        ;;
    registers)
        registers
        ;;
    rng)
        rng
        ;;
    all)
        gc; qber; control; config; registers; rng
        ;;
    *)
        echo "Error: Unknown command '$1'"
        usage
        ;;
esac
