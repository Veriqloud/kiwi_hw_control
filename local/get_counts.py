#!/bin/python

import socket
import json
#import argparse
#from termcolor import colored
import struct
#import time
import os
#import pickle
#import matplotlib.pylab as plt, numpy as np

network_file = os.path.join(os.environ['QLINE_CONFIG_DIR'], 'network.json')
ports_for_localhost_file = os.path.join(os.environ['QLINE_CONFIG_DIR'], 'ports_for_localhost.json')


def connect_to_bob(use_localhost=False):
    if use_localhost:
        with open(ports_for_localhost_file, 'r') as f:
            ports_for_localhost = json.load(f)
        port = ports_for_localhost['hw_bob']
        host = 'localhost'
    else:
        with open(network_file, 'r') as f:
            network = json.load(f)
        host = network['ip']['bob']
        port = network['port']['hw']
        
    global bob 
    bob = socket.socket()
    bob.connect((host, port))



def recv_exact(l):
    m = bytes(0)
    while len(m)<l:
        m += bob.recv(l - len(m))
    return m

# send command
def sendc(c):
    b = c.encode()
    m = len(c).to_bytes(2, 'little')+b
    bob.sendall(m)

# receive integer
def rcv_i():
    m = bob.recv(4)
    value = struct.unpack('i', m)[0]
    return value




def get_counts():
    sendc('get_counts')
    total = rcv_i()
    click0 = rcv_i()
    click1 = rcv_i()
    print(f"Total: {total}, Click0: {click0}, Click1: {click1}              ",flush=True)



connect_to_bob()
get_counts()






