# -*- coding: utf-8 -*-
#*********************************************************************
#					    SPD OEM 
#					Lib Python wrapper
#*********************************************************************
# Language: python 3.x
# Dependency: OEM dynamic library
# Description: library fonctions wrapper 
# Note: please check the path of OEM dynamic library
#*********************************************************************

from ctypes import *
import time
import logging
import platform

# Load library
def oem_shared_lib():
    if platform.system() == "Linux":
        return CDLL("/home/vq-user/qline/hw_control/lib/OEM.so")
    else:
        return None

# List devices
# Description: scan all SPD OEM devices available
def listDevices():
  global DEVICE
  devList=[]
  nDev = c_short()
  DEVICE = oem_shared_lib()
  listDev = DEVICE.CPC_listDevices
  listDev.argtypes = [POINTER(POINTER(c_char)), POINTER(c_short)]
  listDev.restype = c_int
  devicesList = (POINTER(c_char)*10)()
  pdevicesList = devicesList[0]
  if listDev(byref(pdevicesList),byref(nDev))!=0: 
    nDev=0
  else:
      for i in range(nDev.value):
        devList.append(str(string_at(devicesList[i]),'utf-8'))
  return devList, nDev.value

# Open device
# Description: connect the target SPD OEM device
def openDevice(iDev):
  if DEVICE.CPC_openDevice(iDev) == 0:
    return 0
  else:
    return -1
  
# Close device
# Description: close USB connection
def closeDevice(iDev):
  if DEVICE.CPC_closeDevice(iDev) == 0:
    return 0
  else:
    return -1


# Get system version
# Description: Return the system version (part/serial/firmware)
def getSystemVersion(iDev):
    DEVICE.CPC_getSystemVersion.restype = c_short
    version=create_string_buffer(64) 
    ret=DEVICE.CPC_getSystemVersion(iDev, byref(version))
    return ret,str(version.value,"utf-8")


# Save all settings
# Description: save on memory all system parameters
def saveAllSettings(iDev):
    DEVICE.CPC_saveAllSettings.restype = c_short
    ret=DEVICE.CPC_saveAllSettings(iDev)
    return ret


# Factory settings
# Description: reset all parameters as default values
# Note: use "saveAllSettings" after this command to keep those values at next start up
def applyFactorySettings(iDev):
    DEVICE.CPC_factorySettings.restype = c_short
    ret=DEVICE.CPC_factorySettings(iDev)
    return ret


# Reset system
# Descrition: reboot system
# Note: USB connection will stop 
def resetSystem(iDev):
    DEVICE.CPC_resetSystem.restype = c_short
    ret=DEVICE.CPC_resetSystem(iDev)
    return ret


# Get efficiency range
# Description: return all values available in %
def getEfficiencyRange(iDev):
    DEVICE.CPC_getEfficiencyRange.restype = c_short
    range=create_string_buffer(64) 
    ret=DEVICE.CPC_getEfficiencyRange(iDev, byref(range))
    return ret, str(range.value,"utf-8")

# Get efficiency
# Description: return the actual value in %
def getEfficiency(iDev):
  DEVICE.CPC_getEfficiency.restype = c_short
  DEVICE.CPC_getEfficiency.argtypes = [c_short, POINTER(c_short)]
  eff = c_short(0)
  ret=DEVICE.CPC_getEfficiency(iDev, byref(eff))
  return ret, eff.value

# Set efficiency
# Description: apply new value in %
# Note: report to the getEfficiencyRange function for available values
def setEfficiency(iDev, eff):
  DEVICE.CPC_setEfficiency.restype = c_short
  ret=DEVICE.CPC_setEfficiency(iDev, c_short(eff))
  return ret


# Get deadtime range
# Description: return bounds min and max in us
def getDeadtimeRange(iDev):
    DEVICE.CPC_getDeadTimeRange.restype = c_short
    DEVICE.CPC_getDeadTimeRange.argtypes = [c_short, POINTER(c_double), POINTER(c_double)]
    min = c_double(0)
    max = c_double(0)
    ret=DEVICE.CPC_getDeadTimeRange(iDev, byref(min),byref(max))
    return ret,min.value,max.value

# Get deadtime
# Description: return the actual value in us
def getDeadtime(iDev):
  DEVICE.CPC_getDeadTime.restype = c_short
  DEVICE.CPC_getDeadTime.argtypes = [c_short, POINTER(c_double)]
  deadtime = c_double(0)
  ret = DEVICE.CPC_getDeadTime(iDev, byref(deadtime))
  return ret, deadtime.value

# Set deadtime
# Description: apply new value in us
# Note: report to the getDeatimeRange function for available values
def setDeadtime(iDev, val):
  DEVICE.CPC_setDeadTime.restype = c_short
  ret=DEVICE.CPC_setDeadTime(iDev, c_double(val))
  return ret


# Get detection mode
# Description: return the detection mode (0=continuous or 1=gated)
def getDetectionMode(iDev):
  DEVICE.CPC_getDetectionMode.restype = c_short
  DEVICE.CPC_getDetectionMode.argtypes = [c_short, POINTER(c_short)]
  mode = c_short(0)
  ret = DEVICE.CPC_getDetectionMode(iDev, byref(mode))
  return ret, mode.value

# Set detection mode
# Description: apply detection mode (0=continuous or 1=gated)
def setDetectionMode(iDev, val):
  DEVICE.CPC_setDetectionMode.restype = c_short
  ret=DEVICE.CPC_setDetectionMode(iDev, c_short(val))
  return ret


# Get output format
# Description: return output format (0=numeric, 1=analogic or 2=NIM)
def getOutputFormat(iDev):
  DEVICE.CPC_getOutputFormat.restype = c_short
  DEVICE.CPC_getOutputFormat.argtypes = [c_short, POINTER(c_short)]
  format = c_short(0)
  ret = DEVICE.CPC_getOutputFormat(iDev, byref(format))
  return ret, format.value

# Set output format
# Description: apply output format (0=numeric, 1=analogic or 2=NIM)
def setOutputFormat(iDev, val):
  DEVICE.CPC_setOutputFormat.restype = c_short
  ret=DEVICE.CPC_setOutputFormat(iDev, c_short(val))
  return ret


# Get output state
# Description: return output state (0=ON or 1=OFF)
def getOutputState(iDev):
  DEVICE.CPC_getOutputState.restype = c_short
  DEVICE.CPC_getOutputState.argtypes = [c_short, POINTER(c_short)]
  state = c_short(0)
  ret = DEVICE.CPC_getOutputState(iDev, byref(state))
  return ret, state.value

# Set output state
# Description: apply output state (0=ON or 1=OFF)
def setOutputState(iDev, val):
  DEVICE.CPC_setOutputState.restype = c_short
  ret=DEVICE.CPC_setOutputState(iDev, c_short(val))
  return ret


# Get clock count data
# Description: Get both clock and detection data 
def getClockDetData(iDev):
    DEVICE.CPC_getCLKCountData.restype = c_short
    DEVICE.CPC_getCLKCountData.argtypes = [c_short, POINTER(c_ulong), POINTER(c_ulong)]
    clock = c_ulong(0)
    detections = c_ulong(0)
    ret = DEVICE.CPC_getCLKCountData(iDev, byref(clock), byref(detections))
    return ret,clock,detections


# Get body temperature
# Description: return the temperature of the body socket temperature
def getBodySocketTemp(iDev):
    DEVICE.CPC_getBodySocketTemp.restype = c_short
    DEVICE.CPC_getBodySocketTemp.argtypes = [c_short, POINTER(c_double)]
    temp = c_double(0)
    ret = DEVICE.CPC_getBodySocketTemp(iDev, byref(temp))
    return ret,temp.value

