#!/bin/python

from ctypes import *
import time
# Import OEM_SPD wrapper file  
import lib.aurea.SPD_OEM as SPD_OEM
import os
import threading

LOCKFILE = "/tmp/aurea.lock"
aurea_lock = threading.Lock()

class Aurea():
    def __init__(self):

        
        # wait for the lockfile to disappear
        while os.path.isfile(LOCKFILE):
            # delete the lockfile if it is too old
            file_age = time.time() - os.path.getmtime(LOCKFILE)
            if file_age > 10:
                os.remove(LOCKFILE)
            time.sleep(1)
        # lock 
        open(LOCKFILE, 'a').close()

        self.iDev = c_short(0) 
        nDev = c_short()
        devList = []

        #def init(self):
            # Scan and open selected device
        with aurea_lock:
            devList, nDev = SPD_OEM.listDevices()
        if nDev == 0:   # if no device detected, wait
            print("No device connected, waiting...")
            while nDev == 0:
                with aurea_lock:
                    devList, nDev = SPD_OEM.listDevices()
                time.sleep(1)
        elif nDev > 1:  # if more 1 device detected, select target
            print("Found " + str(nDev) + " device(s) :")
            for i in range(nDev):
                print(" -" + str(i) + ": " + devList[i])
            self.iDev = int(input("Select device to open (0 to n):")) 

        # Open device
        with aurea_lock:
            if SPD_OEM.openDevice(self.iDev) < 0:
                input(" -> Failed to open device, press enter to quit !")
                return 0    
        print("Device correctly opened")


    def mode(self, choice):
        #val = int(input("Enter detection mode to set (0=continuous, 1=gated): "))
        if choice == 'gated' : val = 1
        elif choice == 'continuous': val = 0
        # else: print('Non-existing mode')
        with aurea_lock:
            ret=SPD_OEM.setDetectionMode(self.iDev, val)
        if ret<0: print(" -> failed\n")
        else: print(" set mode to " + choice + " done\n")


    def deadtime(self, val):
        #val = float(input("Enter deadtime to set (in us): "))
        with aurea_lock:
            ret = SPD_OEM.setDeadtime(self.iDev, val)
        if ret < 0: print(" -> failed\n")
        else: print(" set deadtime " + str(val) + " us done\n")
    
    def temp(self):
        #val = float(input("Enter deadtime to set (in us): "))
        with aurea_lock:
            ret, temp = SPD_OEM.getBodySocketTemp(self.iDev)
        return temp


    def effi(self, val):
        #val = int(input("Enter efficiency to set (in %): "))
        with aurea_lock:
            ret=SPD_OEM.setEfficiency(self.iDev, val)
        if ret<0: print(" -> failed\n")
        else: print(" set efficiency " + str(val) + "(%) done\n")

    def close(self):
        with aurea_lock:
            ret = SPD_OEM.closeDevice(self.iDev)
        if ret<0: print(" -> failed\n")
        else: print(" Device correctly closed ")
        # remove the lock file
        os.remove(LOCKFILE)


if __name__=="__main__":
    import argparse

    parser = argparse.ArgumentParser(description='control the APD')

    parser.add_argument("--eff", type=int , help="set efficiency in %%")
    parser.add_argument("--dt", type=float , help="set deadtime in us")
    parser.add_argument("--mode", choices=["gated", "continuous"], help="choose running mode")
    
    args = parser.parse_args()
    

    aurea = Aurea()

    if args.eff is not None:
        aurea.effi(args.eff)
    if args.dt is not None:
        aurea.deadtime(args.dt)
    if args.mode is not None:
        aurea.mode(args.mode)
