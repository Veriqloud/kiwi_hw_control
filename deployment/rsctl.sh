#!/bin/bash

Alice=$SSH_ALICE
Bob=$SSH_BOB
qline_config_dir=$QLINE_CONFIG_DIR

usage() {
    echo "Usage: $0 {start_hw|start_gc|stop_hw|stop_gc|restart_gc}"
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

start_hw(){
    ssh $Alice 'sudo systemctl start hw.service'
    ssh $Alice 'sudo systemctl start hws.service'
    ssh $Alice 'sudo systemctl start mon.service'

    ssh $Bob 'sudo systemctl start hw.service'
    ssh $Bob 'sudo systemctl start hws.service'
    ssh $Bob 'sudo systemctl start mon.service'

}

start_gc(){
    ssh $Alice 'sudo systemctl start gc.service'
    ssh $Bob 'sudo systemctl start gc.service'
}

stop_hw(){
    ssh $Alice 'sudo systemctl stop hw.service'
    ssh $Alice 'sudo systemctl stop hws.service'
    ssh $Alice 'sudo systemctl stop mon.service'

    ssh $Bob 'sudo systemctl stop hw.service'
    ssh $Bob 'sudo systemctl stop hws.service'
    ssh $Bob 'sudo systemctl stop mon.service'
}

stop_gc(){
    ssh $Alice 'sudo systemctl stop gc.service'
    ssh $Bob 'sudo systemctl stop gc.service'
}

restart_gc(){
    ssh $Alice 'sudo systemctl restart gc.service'
    ssh $Bob 'sudo systemctl restart gc.service'
}

# Check that exactly one argument is provided
[ $# -eq 1 ] || usage

case "$1" in
    start_hw)
        start_hw
        ;;
    start_gc)
        start_gc
        ;;
    stop_hw)
        stop_hw
        ;;
    stop_gc)
        stop_gc 
        ;;
    restart_gc)
        restart_gc
        ;;
    *)
        echo "Error: Unknown command '$1'"
        usage
        ;;
esac
