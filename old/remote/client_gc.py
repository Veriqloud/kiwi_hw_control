#!/bin/python

import socket, time, numpy as np
import main_Alice as main
from termcolor import colored

from lib.config_lib import wait_for_pps_ret, sync, Ddr_Data_Init, Ddr_Data_Reg, get_tmp




# Client configuration
SERVER_HOST = '192.168.1.77'  # Server's IP address
#SERVER_HOST = 'localhost'  # Server's IP address
SERVER_PORT = 9998  # Server's port
# BUFFER_SIZE = 65536  # Increased buffer size for receiving data
BUFFER_SIZE = 512  # Increased buffer size for receiving data
#ROUNDS = 1  # Number of rounds to perform
#DELAY_BETWEEN_ROUNDS = 2  # Delay between rounds in seconds

# Create TCP socket
client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BUFFER_SIZE)
client_socket.connect((SERVER_HOST, SERVER_PORT))

BATCHSIZE = 16

# send command
def sendc(c):
    print(colored(c, 'cyan'))
    client_socket.sendall(c.encode())

#def gca_from_bytes(b):
#    gca = []
#    for i in range(8*BATHSIZE):
#        gca.append(int.from_bytes(b[i*8:(i+1)*8], byteorder='little'))
#    return gca

#def gca_to_bytes(gca, for_fpga=False):
#    gcab = bytes()
#    size = 16 if for_fpga else 8
#    for gc in gca:
#        gcab += gc.to_bytes(size, byteorder='little')
#    return gcab

def pad(data_filtered):
    # pad with zeros to get back to 16 bytes per gc
    data_padded = bytes()
    for i in range(BATCHSIZE):
        data_padded += data_filtered[i*8: (i+1)*8] + bytes(8)
    return data_padded

def rcv_all(bufsize):
    # make sure bufsize bytes have been received
    mr = client_socket.recv(bufsize)
    while (len(mr)<bufsize):
        mr += client_socket.recv(bufsize-len(mr))
    return mr

try:

    sendc('init_ddr')
    t = get_tmp()
    Ddr_Data_Reg(4, 0, 2000, t['fiber_delay']+128, delay_ab=5000)
    Ddr_Data_Reg(3, 0, 2000, t['fiber_delay']+128, delay_ab=5000)
    Ddr_Data_Init()

    wait_for_pps_ret()
    sendc('sync')
    sync()

    sendc('transfer_gc')
    i = 0
    l = 0
    f_gcw = open('/dev/xdma0_h2c_0', 'wb')
    while i<64000//BATCHSIZE:
        data_filtered = rcv_all(8*BATCHSIZE)
        l = l + len(data_filtered)
        if (i%100 == 0):
            gc = int.from_bytes(data_filtered[:6], byteorder='little')
            gc = gc*2 + (data_filtered[6]&1)
            print(l, gc, gc/80e6)
        bytes_written = f_gcw.write(pad(data_filtered))
        f_gcw.flush()
        i += 1
    f_gcw.close()
    
    sendc('exit')









except KeyboardInterrupt:
    print("Client stopped by keyboard interrupt.")
finally:
    client_socket.close()
    print("Client has been shut down gracefully.")






