#!/bin/python

import socket
import json
import argparse
#from termcolor import colored
import struct
import time
import os

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
        port = network['port']['mon']
        
    global bob 
    bob = socket.socket()
    bob.connect((host, port))



# send command
def sendc(c):
    b = c.encode()
    m = len(c).to_bytes(2, 'little')+b
    bob.sendall(m)

# receive command
def rcvc():
    l = int.from_bytes(bob.recv(2), 'little')
    mr = bob.recv(l)
    while len(mr)<l:
        mr += bob.recv(l-len(mr))
    command = mr.decode().strip()
    return command

# send integer
def send_i(value):
    m = struct.pack('i', value)
    bob.sendall(m)

# receive integer
def rcv_i():
    m = bob.recv(4)
    value = struct.unpack('i', m)[0]
    return value

# receive long integer
def rcv_q():
    m = bob.recv(8)
    value = struct.unpack('q', m)[0]
    return value

# send double
def send_d(value):
    m = struct.pack('d', value)
    bob.sendall(m)

# receive double
def rcv_d():
    m = bob.recv(8)
    value = struct.unpack('d', m)[0]
    return value




def get_counts():
    sendc('get_counts')
    total = rcv_i()
    click0 = rcv_i()
    click1 = rcv_i()
    return total, click0, click1



#create top_level parser
parser = argparse.ArgumentParser()

parser.add_argument("--use_localhost", action="store_true", 
                    help="connect to localhost instead of ip from network.json; e.g. when port forwarding")

parser.add_argument("--counts", action="store_true", help="counts per 0.1s")

args = parser.parse_args()

connect_to_bob(args.use_localhost)

if args.counts:
    while 1:
        total, click0, click1 = get_counts()
        print(f"Total: {total}, Click0: {click0}, Click1: {click1}              ",flush=True)
        time.sleep(0.1)






