#!/bin/bash

usage() {
  echo "Usage: $0 {qline1|qline2|system1|system2|ets}"
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
  # The ETS systems. These are the eth_client NICs (192.168.1.85-88); the
  # eth_wrs interfaces on 192.168.10.x are a different MAC and will not wake
  # anything. WoL is L2-only, so send it from inside the 192.168.1.0/24 subnet.
  #
  # eth_client is the onboard e1000e on all four. It has to be: the add-in igc
  # card does not wake from power-off, which is what kept alice2 down until its
  # client link was moved to the onboard port.
  system1)
      wakeonlan 9c:6b:00:a3:fa:71   # alice1 192.168.1.85
      wakeonlan 9c:6b:00:a3:f9:cb   # bob1   192.168.1.86
    ;;
  system2)
      wakeonlan 9c:6b:00:62:85:05   # alice2 192.168.1.87
      wakeonlan 9c:6b:00:a6:dd:1e   # bob2   192.168.1.88
    ;;
  ets)
      "$0" system1
      "$0" system2
    ;;
  *)
    echo "Error: Unknown command '$1'"
    usage
    ;;
esac










