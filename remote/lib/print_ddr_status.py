#!/bin/python

import time
from fpga import Ddr_Status


i = 0
while True:
    print(i, Ddr_Status())
    time.sleep(0.01)
    i +=  1




