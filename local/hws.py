#!/bin/python

import socket
import json
import argparse
#from termcolor import colored
import struct
import os


network_file = os.path.join(os.environ['QLINE_CONFIG_DIR'], 'network.json')
ports_for_localhost_file = os.path.join(os.environ['QLINE_CONFIG_DIR'], 'ports_for_localhost.json')

def connect_to_alice(use_localhost=False):
    if use_localhost:
        with open(ports_for_localhost_file, 'r') as f:
            ports_for_localhost = json.load(f)
        host = 'localhost'
        port = ports_for_localhost['hws']
    else:
        with open(network_file, 'r') as f:
            network = json.load(f)
        host = network['ip']['alice']
        port = network['port']['hws']
    
    global alice
    alice = socket.socket()
    alice.connect((host, port))


def recv_exact(l):
    m = bytes(0)
    while len(m)<l:
        m += alice.recv(l - len(m))
    return m

# send command
def sendc(c):
    b = c.encode()
    m = len(c).to_bytes(1, 'little')+b
    alice.sendall(m)

# receive command
def rcvc():
    l = int.from_bytes(alice.recv(1), 'little')
    mr = recv_exact(l)
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
    m = recv_exact(4)
    value = struct.unpack('i', m)[0]
    return value

# receive long integer
def rcv_q():
    m = recv_exact(8)
    value = struct.unpack('q', m)[0]
    return value

# send double
def send_d(value):
    m = struct.pack('d', value)
    alice.sendall(m)

# receive double
def rcv_d():
    m = recv_exact(8)
    value = struct.unpack('d', m)[0]
    return value

def rcv_data():
    m = recv_exact(4)
    l = struct.unpack('i', m)[0]
    m = recv_exact(l)
    return m






#create top_level parser
parser = argparse.ArgumentParser()

parser.add_argument("--use_localhost", action="store_true", 
                    help="connect to localhost instead of ip from network.json; e.g. when port forwarding")

parser.add_argument("--full_init", action="store_true", 
                         help="reset and calibrate")

parser.add_argument("--command", type=str, nargs="*", 
                        help="pass commands (see doc for list of commands)")

parser.add_argument("--monitoring", action="store_true",
                    help=" monitoring loop")


args = parser.parse_args()

connect_to_alice(args.use_localhost)


def interact(command):
    sendc(command)
    if (command == 'verify_gates') or (command == 'loop_find_gates'):
        pic = rcv_data()
        with open('pics/verify_gates.png', 'wb') as f:
            f.write(pic)
    m = rcvc()
    print(m)
    if 'fail' in m:
        exit()




if args.full_init:
    interact('init')
    interact('sync_gc')
    interact('find_vca')
    interact('loop_find_am_bias')
    interact('find_am2_bias')
    interact('pol_bob')
    interact('find_vca_4000')
#    interact('loop_find_gates')
#    interact('qdistance')
    interact('loop_find_gates')
    interact('fs_b')
    interact('fs_a')
    interact('fd_b')
    interact('fd_b_long')
    interact('fd_a')
    interact('fd_a_long')
    interact('fz_a')
    interact('fz_b')
    interact('start')

if args.monitoring:
    for _ in range(3):
        interact('adjust_soft_gates')
        interact('adjust_am')


elif args.command is not None:
    interact(args.command[0])























