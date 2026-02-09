#!/bin/python
import sys, time
sys.path.insert(0, '../remote')

from lib.communication import TcpClient, HwsCommand
from lib.visuals import mylogger

import argparse


# this program is controlling hws, which handles the calibration phase

def main():
    logger = mylogger()
    logger.info("start program")

    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=[x.value for x in HwsCommand][:-1])
    parser.add_argument("--use_localhost", action='store_true', help="connect to localhost and port from ports_from_localhost.json; when port forwarding")
    args = parser.parse_args()

    client = TcpClient("hws", "alice", use_localhost=args.use_localhost).connect()


    client.psnd(HwsCommand(args.command))
    client.wait_ack()


if __name__=="__main__":
    main()










