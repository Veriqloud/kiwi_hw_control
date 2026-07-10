#!/usr/bin/env bash
# Control the hardware-ready flag that gc serves to the nodes.
#
# gc answers the node's PollHwReady from the existence of the ready flag file
# (gc config `ready_flag_path`, default /tmp/qkd_ready). On real hardware the
# calibration scripts (hws) manage this file; on the simulator nothing does,
# so this script is the manual knob:
#
#   start  - raise the flag: gc reports HwReady, nodes open the hardware and
#            run QKD sessions
#   stop   - lower the flag (as calibration would): gc reports HwNotReady,
#            nodes finish their current round, close their hardware fds and
#            go idle; gc then raises the per-node idle flag
#   status - show the ready flag and any node-idle acks
#
# The flag path can be overridden with $QKD_READY_FLAG or as a second
# argument, e.g. `qkd_ready_ctl.sh start /tmp/qkd_ready`.

set -eu

FLAG=${2:-${QKD_READY_FLAG:-/tmp/qkd_ready}}

case "${1:-}" in
    start)
        touch "$FLAG"
        echo "raised $FLAG: gc reports HwReady, nodes will start/resume"
        ;;
    stop)
        rm -f "$FLAG"
        echo "lowered $FLAG: gc reports HwNotReady, nodes will pause once idle"
        ;;
    status)
        if [ -e "$FLAG" ]; then
            echo "ready flag $FLAG: RAISED (nodes may run)"
        else
            echo "ready flag $FLAG: lowered (nodes pause / calibration may run)"
        fi
        for idle in /tmp/node_idle*; do
            [ -e "$idle" ] && echo "node idle ack: $idle (node closed its hardware fds)"
        done
        true
        ;;
    *)
        echo "usage: $(basename "$0") start|stop|status [ready-flag-path]" >&2
        exit 1
        ;;
esac
