#!/bin/bash

usage() {
  echo "Usage: $0 {qline1|qline2}"
  exit 1
}

# Check that exactly one argument is provided
[ $# -eq 1 ] || usage

case "$1" in
  qline1)
      wakeonlan a8:a1:59:b7:de:fe
      wakeonlan a8:a1:59:be:7d:3e
    ;;
  qline2)
      wakeonlan 9c:6b:00:62:7d:bb
      wakeonlan 9c:6b:00:62:82:fc
    ;;
  *)
    echo "Error: Unknown command '$1'"
    usage
    ;;
esac










