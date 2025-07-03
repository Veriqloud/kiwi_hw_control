#!/bin/bash

usage() {
  echo "Usage: $0 {start|stop}"
  exit 1
}

# Check that exactly one argument is provided
[ $# -eq 1 ] || usage

case "$1" in
  start)
    /home/vq-user/qline/server/hw.py &
    /home/vq-user/qline/server/hws.py &
    /home/vq-user/qline/server/gc &
    ;;
  stop)
    pkill -e hw.py
    pkill -e hws.py
    pkill -e gc
    ;;
  *)
    echo "Error: Unknown command '$1'"
    usage
    ;;
esac










