#!/bin/python
import sys
sys.path.insert(0, '/home/vq-user/hw_control')

from lib.visuals import mylogger
from lib.statusfiles import HwsStatus, HwsValues
from lib.communication import TcpServer




# this program is handling the calibration phase

def main():

    logger = mylogger()
    logger.info("start program")
    status = HwsStatus()
                
    server = TcpServer("hws")





main()








