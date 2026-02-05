#!/bin/python

import time, logging, subprocess
from lib.fpga import get_ltc_info, get_sda_info, get_fda_info, did_reboot, WriteFPGA
import ctl_alice as ctl
from lib.visuals import mylogger
from lib.statusfiles import HwiStatus, HwiValues



# This program monitors chips through spi and reinits them.
# Covers computer reboot and full system restart
def main():

    logger = mylogger()
    logger.info("start program")

    status = HwiStatus()

    # make sure Xilinx PCIE is connected
    ret = subprocess.run("lspci | grep Xilinx", shell=True, capture_output=True).returncode
    if ret:
        logger.error("no Xilinx PCIE. Make sure the cable is well attached!")
        exit()



    while True:
        apply_config_flag = False
        skip_fda = False

        # init chips through spi in case their registers don't match expected values
        if get_ltc_info() == 0:
            status.initing()
            logger.info("init ltc...")
            ctl.init_ltc()
            logger.info("init sync...")
            ctl.init_sync()
            logger.info("init fda...")
            if did_reboot():
                apply_config_flag = True
            ctl.init_fda()
            skip_fda = True
        if (get_fda_info() == 0) and (not skip_fda):
            status.initing()
            logger.info("init fda...")
            ctl.init_fda()
        if get_sda_info() == 0:
            time.sleep(1)
            if get_sda_info() == 0:
                status.initing()
                logger.info("init sda...")
                ctl.init_sda()

        # in case of reboot, init fpga regs and apply values from config
        if did_reboot():
            status.initing()
            logger.info("init fpga registers")
            WriteFPGA()
            ctl.init_decoy()
            ctl.apply_config()
            # not sure why but have to reinit fda
            ctl.init_fda()

        if apply_config_flag:
            status.initing()
            logger.info("apply config...")
            ctl.init_decoy()
            ctl.apply_config()
            # not sure why but have to reinit fda
            ctl.init_fda()


        status.done()

        time.sleep(2)





main()



