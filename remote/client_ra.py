#!/bin/python

import socket, time, numpy as np
import main_Alice as main
from termcolor import colored

from lib.config_lib import wait_for_pps_ret, sync




# Client configuration
SERVER_HOST = '192.168.1.77'  # Server's IP address
#SERVER_HOST = 'localhost'  # Server's IP address
SERVER_PORT = 9999  # Server's port
# BUFFER_SIZE = 65536  # Increased buffer size for receiving data
BUFFER_SIZE = 512  # Increased buffer size for receiving data
#ROUNDS = 1  # Number of rounds to perform
#DELAY_BETWEEN_ROUNDS = 2  # Delay between rounds in seconds

# Create TCP socket
client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BUFFER_SIZE)
client_socket.connect((SERVER_HOST, SERVER_PORT))


# send command
def sendc(c):
    print(colored(c, 'cyan'))
    client_socket.sendall(c.encode())

def gca_from_bytes(b):
    gca = []
    for i in range(8*64):
        gca.append(int.from_bytes(b[i*8:(i+1)*8], byteorder='big'))
    return gca

def rcv_all(bufsize):
    # make sure bufize bytes have been received
    mr = client_socket.recv(bufsize)
    while (len(mr)<bufsize):
        mr += client_socket.recv(bufsize-len(mr))
    return mr

try:

    sendc('init_ddr')
    main.init_ddr()

    wait_for_pps_ret()
    sendc('sync')
    sync()

    sendc('transfer_gc')
    i = 0
    l = 0
    while True:
        mr = rcv_all(8*64)
        gca = gca_from_bytes(mr)
        l = l + len(gca)
        if (i%1000 == 0):
            print(l, gca[0], gca[0]/80e6)
        i += 1
    print(i)
    sendc('exit')









except KeyboardInterrupt:
    print("Client stopped by keyboard interrupt.")
finally:
    client_socket.close()
    print("Client has been shut down gracefully.")






