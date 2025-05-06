import time
import numpy as np
import subprocess, sys, argparse
import main

# Reset alpha fifo
main.Ddr_Data_Reg(4,0,2000,17,1,17,1,17)
# Setting ddr4 registers
main.Ddr_Data_Reg(3,0,2000,17,1,17,1,17)
# Init ddr4
main.Ddr_Data_Init()
# Capture PPS
while True:
    pps_ret = main.Read(0x00001000+48)
    pps_ret_int = np.int64(int(pps_ret.decode('utf-8').strip(),16))

    print(pps_ret_int)
    if (pps_ret_int == 1):
        break
time.sleep(0.02) #delay should be more than 10ms
# Start to write 
main.Write(0x00001000, 0x00) 
main.Write(0x00001000, 0x01) 
# time.sleep(1)
# current_gc = main.Get_Current_Gc()
# print('Bob current_gc: ',current_gc)

# Command_enable -> Reset the fifo_gc_out
main.Write(0x00001000+28,0x0)
main.Write(0x00001000+28,0x1)
# Command enable to save alpha
main.Write(0x00001000+24,0x0)
main.Write(0x00001000+24,0x1)
# Declare devices
data_gc = b'' #declare bytes object
device_c2h = '/dev/xdma0_c2h_0'
device_h2c = '/dev/xdma0_h2c_0'

try:
    with open(device_c2h, 'rb') as f:
        with open(device_h2c, 'wb') as fw:
            while True:
            # for i in range(64):
                data_gc = f.read(16)
                print(data_gc,flush=True)
                if not data_gc:
                    print("No available data on stream")
                    break
                #Write back to h2c device of Bob
                bytes_written = fw.write(data_gc)
                fw.flush()

except FileNotFoundError:
    print(f"Device not found")    
except PermissionError:
    print(f"Permission to file is denied")
except Exception as e:
    print(f"Error occurres: {e}")


