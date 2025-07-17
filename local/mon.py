#!/bin/python

import socket
import json
import argparse
from termcolor import colored
import struct
import time
import os
import matplotlib.pylab as plt, numpy as np
import pickle
from tabulate import tabulate

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

def connect_to_alice(use_localhost=False):
    if use_localhost:
        with open(ports_for_localhost_file, 'r') as f:
            ports_for_localhost = json.load(f)
        port = ports_for_localhost['hw_alice']
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

# receive long integer
def rcv_q(socket):
    m = socket.recv(8)
    value = struct.unpack('q', m)[0]
    return value

# send double
def send_d(value):
    m = struct.pack('d', value)
    socket.sendall(m)

# receive double
def rcv_d(socket):
    m = socket.recv(8)
    value = struct.unpack('d', m)[0]
    return value

def rcv_data(socket):
    m = recv_exact(socket, 4)
    l = struct.unpack('i', m)[0]
    m = bytes(0)
    while len(m)<l:
        m += socket.recv(l - len(m))
    return m



def get_counts():
    sendc(bob, 'get_counts')
    total = rcv_i(bob)
    click0 = rcv_i(bob)
    click1 = rcv_i(bob)
    return total, click0, click1

def get_gates():
    sendc(bob, 'get_gates')
    data = rcv_data(bob)
    h = pickle.loads(data)
    return h

def rng_status(socket):
    sendc(socket, 'get_rng_status')
    rng_status = rcv_i(socket)
    if rng_status==0:
        rng_s = colored('ok', 'green')
    else:
        rng_s = colored(rng_status, 'red')
    return rng_s

def fifo_status(socket):
    sendc(socket, 'get_fifo_status')
    vfifo_f = rcv_i(socket)
    gc_out_f = rcv_i(socket)
    gc_in_f = rcv_i(socket)
    alpha_out_f = rcv_i(socket)
    fifo_s = ""
    if vfifo_f!=0:
        fifo_s += 'vfifo_full'
    if gc_out_f!=0:
        fifo_s += 'gc_out_full'
    if gc_in_f !=0:
        fifo_s += 'gc_in_full'
    if alpha_out_f !=0:
        fifo_s += 'alpha_out_full'
    if fifo_s == "":
        fifo_s = colored('ok', 'green')
    else:
        fifo_s = colored(fifo_s, 'red')
    return fifo_s

def get_pci_status(socket):
    sendc(socket, 'get_pci_status')
    m = rcvc(socket)
    if m=='ok':
        xilinx_s = colored(m, 'green')
    else:
        xilinx_s = colored(m, 'red')
    return xilinx_s





#create top_level parser
parser = argparse.ArgumentParser()

parser.add_argument("--use_localhost", action="store_true", 
                    help="connect to localhost instead of ip from network.json; e.g. when port forwarding")

parser.add_argument("--status", action="store_true", help="print status")
parser.add_argument("--counts", action="store_true", help="counts per 0.1s")
parser.add_argument("--gates", action="store_true", help="plot gates")

args = parser.parse_args()

connect_to_bob(args.use_localhost)
connect_to_alice(args.use_localhost)

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


elif args.status:
    firstrun = True
    count = 0

    while 1:
        # rng 
        rng_alice = rng_status(alice)
        rng_bob = rng_status(bob)

        # fifos
        fifo_alice = get_fifo_status(alice)
        fifo_bob = get_fifo_status(bob)

        # counts
        total, click0, click1 = get_counts()
        if firstrun:
            first_total = total
            first_click0 = click0
            first_click1 = click1
        if (total<(first_total/2)) or (total>(first_total*2)):
            total_s = colored(total, 'red')
        else:
            total_s = colored(total, 'green')
        if (click0<(first_click0/2)) or (click0>(first_click0*2)):
            click0_s = colored(click0, 'red')
        else:
            click0_s = colored(click0, 'green')
        if (click1<(first_click1/2)) or (click1>(first_click1*2)):
            click1_s = colored(click1, 'red')
        else:
            click1_s = colored(click1, 'green')

        # spd temp
        if (count%100 == 0):
            # aure usb interface is slow; update rarely
            sendc('get_spd_temp')
            temp = rcv_d(bob)
        if temp < 30:
            temp_s = colored(temp, 'green')

        # pci interface
        xilinx_bob = get_pci_status(bob)
        xilinx_alice = get_pci_status(alice)

        # sync
        sendc(alice, 'get_gc')
        sendc(bob, 'get_gc')
        gc_alice = rcv_d(alice)
        gc_bob = rcv_d(bob)
        gc_diff = gc_bob - gc_alice
        gc_time = gc_alice/80e6
        gc_time = gc_bob/80e6
        gc_diff_time = gc_diff / 80e6
        if abs(gc_diff_time) > 0.1:
            gc_diff_time_ms = colored(str(round(gc_diff_time*1000))+'ms', 'red')
        else:
            gc_diff_time_ms = colored(str(round(gc_diff_time*1000))+'ms', 'green')



        header1 = ['', 'Alice', 'Bob', 'diff']
        table1 = [
                ["rng status", rng_alice, rng_bob],
                ["xilinx pci (update in "+str(100-count%100)+")", xilinx_alice, xilinx_bob],
                ["fifos", fifo_alice, fifo_bob],
                ["gc", gc_alice, gc_bob, str(gc_diff)+" ("+gc_diff_time_ms+')'],
                ]
        table2 = [
                ["initial counts (1/0.1s)", first_total, first_click0, first_click1],
                ["current counts (1/0.1s)", total_s, click0_s, click1_s],
                ["spd temp (update in "+str(100-count%100)+")", temp_s],
                ["gctime", gc_time],
                ]
        print("\033[2J")
        #print("")
        print(tabulate(table2, tablefmt="plain")+"\r")
        print(tabulate(table1, tablefmt="plain", header=header1)+"\r")
        time.sleep(1)
        firstrun = False
        count += 1













