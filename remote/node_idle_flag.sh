#!/bin/bash
# Hold /tmp/node_idle raised on a node-less system.
#
# gc raises this flag only in answer to the node's PollHwReady poll. hws `init`
# drops it on both nodes and then waits up to 60 s for it to come back before
# reconfiguring the FPGA, so where no node runs, every init pays the full
# timeout twice over.
#
# One instance per node, started from vq-user's crontab at boot. Stop it and
# remove the crontab entry as soon as a node runs here: the wait is what keeps
# calibration from resetting the FPGA under a live session.

exec 9>/tmp/node_idle_flag.lock
flock -n 9 || exit 0

while :; do
    [ -e /tmp/node_idle ] || : > /tmp/node_idle
    sleep 1
done
