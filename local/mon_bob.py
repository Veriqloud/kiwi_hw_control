#!/bin/python

import socket
import json
import argparse
#from termcolor import colored
import struct
import time
import os
import matplotlib.pylab as plt, numpy as np
import pickle

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


def recv_exact(socket, l):
    m = bytes(0)
    while len(m)<l:
        m += socket.recv(l - len(m))
    return m

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

def rcv_data():
    m = recv_exact(bob, 4)
    l = struct.unpack('i', m)[0]
    m = bytes(0)
    while len(m)<l:
        m += bob.recv(l - len(m))
    return m



def get_counts():
    sendc('get_counts')
    total = rcv_i()
    click0 = rcv_i()
    click1 = rcv_i()
    return total, click0, click1

def get_gates():
    sendc('get_gates')
    data = rcv_data()
    h = pickle.loads(data)
    return h


#create top_level parser
parser = argparse.ArgumentParser()

parser.add_argument("--use_localhost", action="store_true", 
                    help="connect to localhost instead of ip from network.json; e.g. when port forwarding")

parser.add_argument("--counts", action="store_true", help="counts per 0.1s")
parser.add_argument("--gates", action="store_true", help="plot gates")

args = parser.parse_args()

connect_to_bob(args.use_localhost)

def handle_close(evt):
    global close_flag # should be global variable to change the outside close_flag.
    close_flag = 1
    print('Closed Figure!')

if args.counts:
    close_flag = 0
    plt.ion()
    fig = plt.figure()
    ax1 = fig.add_subplot(1, 2, 1)
    ax2 = fig.add_subplot(1, 2, 2)
        
    total, click0, click1 = get_counts()
    #print(f"Total: {total}, Click0: {click0}, Click1: {click1}              ",flush=True)
    datat = np.ones(200)*total
    data0 = np.ones(200)*click0
    data1 = np.ones(200)*click1
    linet, = ax1.plot(np.arange(0, 20, 0.1), datat)
    line0, = ax2.plot(np.arange(0, 20, 0.1), data0)
    line1, = ax2.plot(np.arange(0, 20, 0.1), data1)
    ax1.set_ylim((datat.min()//200)*200, ((datat.max()//200)+1)*200)
    ax1.set_xticks([0, 5, 10, 15, 20])
    ax2.set_xticks([0, 5, 10, 15, 20])
    ax1.set_xlim(0, 20)
    ax2.set_xlim(0, 20)
    min2 = min(data0.min(), data1.min())
    max2 = max(data0.max(), data1.max())
    ax2.set_ylim((min2//200)*200, ((max2//200)+1)*200)
    ax1.set_xlabel('time [s]')
    ax1.set_ylabel('counts / 0.1s')
    ax2.set_xlabel('time [s]')
    fig.canvas.draw()
    fig.canvas.flush_events()
    fig.canvas.mpl_connect('close_event', handle_close) # listen to close event
    time.sleep(0.1)

    while close_flag == 0:
        total, click0, click1 = get_counts()
        #print(f"Total: {total}, Click0: {click0}, Click1: {click1}              ",flush=True)
        datat[:-1] = datat[1:]
        datat[-1] = total
        data0[:-1] = data0[1:]
        data0[-1] = click0
        data1[:-1] = data1[1:]
        data1[-1] = click1
        linet.set_ydata(datat)
        line0.set_ydata(data0)
        line1.set_ydata(data1)
        ax1.set_ylim((datat.min()//200)*200, ((datat.max()//200)+1)*200)
        min2 = min(data0.min(), data1.min())
        max2 = max(data0.max(), data1.max())
        ax2.set_ylim((min2//200)*200, ((max2//200)+1)*200)
        fig.canvas.draw()
        fig.canvas.flush_events()
        #if close_flag == 1:
        #    break
        time.sleep(0.1)


elif args.gates:
    close_flag = 0
    plt.ion()
    fig = plt.figure()
    ax1 = fig.add_subplot(1, 1, 1)
    h = get_gates()
    bins = np.arange(0,625, 2)
    line1, = ax1.plot(bins[:-1], h, '-o', markersize=2)
    ax1.set_xlabel('time bins [20ps]')
    ax1.set_ylabel('counts / bin')
    ax1.set_ylim(0, (max(h)//200 + 1)*200)
    fig.canvas.draw()
    fig.canvas.flush_events()
    fig.canvas.mpl_connect('close_event', handle_close) # listen to close event

    while close_flag == 0:
        h = get_gates()
        line1.set_ydata(h)
        ax1.set_ylim(0, (max(h)//200 + 1)*200)
        fig.canvas.draw()
        fig.canvas.flush_events()
        time.sleep(0.1)

