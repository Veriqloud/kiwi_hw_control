#!/bin/python
import sys
sys.path.insert(0, '/home/vq-user/hw_control')

from lib.visuals import mylogger
from lib.statusfiles import HwsStatus, HwsValues
from lib.communication import TcpServer



# this program is handling the calibration phase
# it starts a server for the alice-bob connection




def main():

    logger = mylogger()
    logger.info("start program")
    status = HwsStatus()
                
    server = TcpServer("hws", use_wrs=True)

    while True:
        conn = server.accept()
        while True:
            try:
                m = conn.prcv()
                print(m)
                conn.ack()
            except ConnectionError:
                logger.warning("client disconnected unexpectedly")
                break








main()













