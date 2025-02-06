#!/bin/python

from ctypes import *
import time
# Import OEM_SPD wrapper file  
import lib.SPD_OEM as SPD_OEM
class Aurea():
	def __init__(self):
		self.iDev = c_short(0) 
		nDev = c_short()
		devList = []

	#def init(self):
	    # Scan and open selected device
		devList,nDev=SPD_OEM.listDevices()
		if nDev==0:   # if no device detected, wait
			print ("No device connected, waiting...")
			while nDev==0:
			    devList,nDev=SPD_OEM.listDevices()
			    time.sleep(1)
		elif nDev>1:  # if more 1 device detected, select target
			print("Found " + str(nDev) + " device(s) :")
			for i in range(nDev):
			    print (" -"+str(i)+": " + devList[i])
			self.iDev=int(input("Select device to open (0 to n):")) 

		# Open device
		if SPD_OEM.openDevice(self.iDev)<0:
			input(" -> Failed to open device, press enter to quit !")
			return 0	
		print("Device correctly opened")

	def mode(self, choice):
		#val = int(input("Enter detection mode to set (0=continuous, 1=gated): "))
		if choice == 'gated' : val = 1
		elif choice == 'continuous': val = 0
		# else: print('Non-existing mode')
		ret=SPD_OEM.setDetectionMode(self.iDev, val)
		if ret<0: print(" -> failed\n")
		else: print(" set mode to " + choice + " done\n")

	def deadtime(self, val):
        #val = float(input("Enter deadtime to set (in us): "))
		ret=SPD_OEM.setDeadtime(self.iDev, val)
		if ret<0: print(" -> failed\n")
		else: print(" set deadtime " + str(val) + " us done\n")

	def effi(self, val):
		#val = int(input("Enter efficiency to set (in %): "))
		ret=SPD_OEM.setEfficiency(self.iDev, val)
		if ret<0: print(" -> failed\n")
		else: print(" set efficiency " + str(val) + "(%) done\n")

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
