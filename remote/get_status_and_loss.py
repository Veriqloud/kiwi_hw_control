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
        port = ports_for_localhost['mon_bob']
        host = 'localhost'
    else:
        with open(network_file, 'r') as f:
            network = json.load(f)
        host = network['ip']['bob']
        port = network['port']['mon']
        
    global bob 
    bob = socket.socket()
    bob.connect((host, port))

def connect_to_alice(use_localhost=False):
    if use_localhost:
        with open(ports_for_localhost_file, 'r') as f:
            ports_for_localhost = json.load(f)
        port = ports_for_localhost['mon_alice']
        host = 'localhost'
    else:
        with open(network_file, 'r') as f:
            network = json.load(f)
        host = network['ip']['alice']
        port = network['port']['mon']
        
    global alice 
    alice = socket.socket()
    alice.connect((host, port))


def recv_exact(socket, l):
    m = bytes(0)
    while len(m)<l:
        m += socket.recv(l - len(m))
    return m

# send command
def sendc(socket, c):
    b = c.encode()
    m = len(c).to_bytes(2, 'little')+b
    socket.sendall(m)

# receive command
def rcvc(socket):
    l = int.from_bytes(socket.recv(2), 'little')
    mr = socket.recv(l)
    while len(mr)<l:
        mr += socket.recv(l-len(mr))
    command = mr.decode().strip()
    return command

# send integer
def send_i(socket, value):
    m = struct.pack('i', value)
    socket.sendall(m)

# receive integer
def rcv_i(socket):
    m = socket.recv(4)
    value = struct.unpack('i', m)[0]
    return value


# estimate losses from counts
def loss(counts):
    # counts/s at zero loss
    c0 = 50e3
    # dead time in seconds
    d = 15e-6
    # generation rate
    g = 80e6
    # probability of detection corrected for dead time; at zero loss
    p0 = c0/g/(1.-c0*d)
    # probability of detection corrected for dead time; at current loss
    p = counts/g/(1.-counts*d)
    return p/p0


# get counts from machine
def get_counts(socket):
    sendc(socket, 'get_counts')
    total = rcv_i(socket)
    click0 = rcv_i(socket)
    click1 = rcv_i(socket)
    #print(f"Total: {total}, Click0: {click0}, Click1: {click1}              ",flush=True)

    # return counts/s; the measurement interval is 0.1s
    return (click0 + click1)*10



connect_to_alice()
connect_to_bob()



counts = get_counts(bob)
print("counts:", counts)
print("estimated transmisstion:", loss(counts))


# get link status
sendc(alice, 'get_link')
sendc(bob, 'get_link')
link_a = rcvc(alice)
link_b = rcvc(bob)
if link_a=='error' or link_b=='error':
    link_status = 'error'
elif link_a=='calibrating' or link_b=='calibrating':
    link_status = 'calibrating'
else:
    link_status = 'online'
print("link status:", link_status)







