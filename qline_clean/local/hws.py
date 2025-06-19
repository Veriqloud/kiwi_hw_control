#!/bin/python

import socket
import json
import argparse
#from termcolor import colored
import struct

networkfile = '../config/network.json'


# get ip from config/network.json
with open(networkfile, 'r') as f:
    network = json.load(f)

# Server configuration
host = network['ip']['alice']
port = int(network['port']['hws'])

alice = socket.socket()
alice.connect((host, port))


# send command
def sendc(c):
    b = c.encode()
    m = len(c).to_bytes(1, 'little')+b
    alice.sendall(m)

# receive command
def rcvc():
    l = int.from_bytes(alice.recv(1), 'little')
    mr = alice.recv(l)
    while len(mr)<l:
        mr += alice.recv(l-len(mr))
    command = mr.decode().strip()
    return command

# send integer
def send_i(value):
    m = struct.pack('i', value)
    alice.sendall(m)

# receive integer
def rcv_i():
    m = alice.recv(4)
    value = struct.unpack('i', m)[0]
    return value

# receive long integer
def rcv_q():
    m = alice.recv(8)
    value = struct.unpack('q', m)[0]
    return value

# send double
def send_d(value):
    m = struct.pack('d', value)
    alice.sendall(m)

# receive double
def rcv_d():
    m = alice.recv(8)
    value = struct.unpack('d', m)[0]
    return value







#create top_level parser
parser = argparse.ArgumentParser()


parser.add_argument("--full_init", action="store_true", 
                         help="reset and calibrate")

parser.add_argument("--command", type=str, nargs="*", 
                        help="pass commands (see doc for list of commands)")


args = parser.parse_args()

if args.full_init:
    sendc('init')
    sendc('sync_gc')
    sendc('find_vca')
    sendc('find_am_bias')
    sendc('verify_am_bias')
    sendc('find_am2_bias')
    sendc('pol_bob')
    sendc('ad')
    sendc('find_sp')
    sendc('verify_gates')
    sendc('fs_b')
    sendc('fs_a')
    sendc('fd_b')
    sendc('fd_b_long')
    sendc('fd_a')
    sendc('fd_a_long')
    sendc('fz_a')
    sendc('fz_b')

elif args.command is not None:
    sendc(args.command[0])























