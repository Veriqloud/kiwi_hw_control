#!/bin/bash

Alice=$SSH_ALICE
Bob=$SSH_BOB
qline_config_dir=$QLINE_CONFIG_DIR

usage() {
    echo "Usage: $0 {gc|qber|control|config|registers|rng|all}"
    exit 1
}

if [ -z "$QLINE_CONFIG_DIR" ]; then
    echo "Please set QLINE_CONFIG_DIR"
    exit
fi
if [ -z "$SSH_ALICE" ]; then
    echo "Please set SSH_ALICE"
    exit
fi
if [ -z "$SSH_BOB" ]; then
    echo "Please set SSH_BOB"
    exit
fi

gc(){
    cd ../gc/target/release
    ssh $Alice "mkdir -p server"
    ssh $Alice "mkdir -p bin"
    rsync -v alice $Alice:~/server/gc
    rsync -v controller $Alice:~/bin/
    ssh $Bob "mkdir -p server"
    rsync -v bob $Bob:~/server/gc
    cd -
}

qber(){
    cd ../qber/target/release
    ssh $Alice "mkdir -p bin"
    rsync -v alice $Alice:~/bin/qber
    ssh $Bob "mkdir -p server"
    rsync -v bob $Bob:~/server/qber
    cd -
}

control(){
    cd ../remote
    rsync -v hw_alice.py hws_alice.py ctl_alice.py mon_alice.py $Alice:~/hw_control/
    rsync -v lib/*.py $Alice:~/hw_control/lib/
    rsync -v alice_server/*.py $Alice:~/server/

    rsync -v hw_bob.py ctl_bob.py hws_bob.py mon_bob.py $Bob:~/hw_control/
    rsync -v lib/*.py $Bob:~/hw_control/lib/
    rsync -v lib/test_tdc/dma_from_device lib/test_tdc/tdc_bin2txt $Bob:~/hw_control/lib/test_tdc
    rsync -v lib/aurea/* $Bob:~/hw_control/lib/aurea/
    rsync -v bob_server/*.py $Bob:~/server/
    cd -
}

config(){
    cd $qline_config_dir
    rsync -v remote/alice/*.json $Alice:~/config/
    rsync -v remote/bob/*.json $Bob:~/config/
    cd -
}

registers(){
    cd ../remote
    rsync -v -a registers $Alice:~/config/
    rsync -v -a registers $Bob:~/config/
    cd -
}

rng(){
    cd ../remote
    rsync -v rng_fpga/rng2fpga $Alice:~/rng_fpga/
    rsync -v rng_fpga/rng2fpga $Bob:~/rng_fpga/
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
