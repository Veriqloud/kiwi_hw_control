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

network_file = os.path.join(os.environ['QLINE_CONFIG_DIR'], 'alice/network.json')
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


def update_errorflag():
    global errorflag
    if errorflag==1:
        sendc(alice, 'set_error')
        sendc(bob, 'set_error')
    else:
        sendc(alice, 'clear_error')
        sendc(bob, 'clear_error')


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
    global errorflag
    sendc(socket, 'get_rng_status')
    rng_status = rcv_i(socket)
    if rng_status==0:
        rng_s = colored('ok', 'green')
    else:
        rng_s = colored(rng_status, 'red')
        errorflag = 1
    return rng_s

def fifo_status(socket):
    global errorflag
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
        errorflag = 1
    return fifo_s

def server_status(socket):
    global errorflag
    sendc(socket, 'get_server_status')
    hw = rcv_i(socket)
    hws = rcv_i(socket)
    gc = rcv_i(socket)
    rng = rcv_i(socket)
    server_s = ""
    if hw!=0:
        server_s += 'hw inactive '
    if hws!=0:
        server_s += 'hws inactive '
    if gc!=0:
        server_s += 'gc inactive '
    if rng!=0:
        server_s += 'rng inactive '
    if server_s == "":
        server_s = colored('ok', 'green')
    else:
        server_s = colored(server_s, 'yellow')
        errorflag = 1
    return server_s

def get_pci_status(socket):
    global errorflag
    sendc(socket, 'get_pci_status')
    m = rcvc(socket)
    if m=='ok':
        xilinx_s = colored(m, 'green')
    else:
        xilinx_s = colored(m, 'red')
        errorflag = 1
    return xilinx_s

def get_wrs_ip_status():
    global errorflag
    sendc(alice, 'get_wrs_ip_status')
    sendc(bob, 'get_wrs_ip_status')
    r_alice = rcv_i(alice)
    r_bob = rcv_i(bob)
    if r_alice==0:
        status_ip_alice = colored('ok', 'green')
    else:
        status_ip_alice = colored('no ip on wrs network', 'red')
        errorflag = 1
    if r_bob==0:
        status_ip_bob = colored('ok', 'green')
    else:
        status_ip_bob = colored('no ip on wrs network', 'red')
        errorflag = 1
    return status_ip_alice, status_ip_bob


def check_chip_status(command):
    global errorflag
    sendc(alice, command)
    sendc(bob, command)
    r_alice = rcv_i(alice)
    r_bob = rcv_i(bob)
    if r_alice:
        ltc_alice  = colored('ok', 'green')
    else: 
        ltc_alice  = colored('error', 'red')
        errorflag = 1
    if r_bob:
        ltc_bob  = colored('ok', 'green')
    else: 
        ltc_bob  = colored('error', 'red')
        errorflag = 1
    return ltc_alice, ltc_bob

def get_node_stats():
    global last_update_time 
    global last_key_length 
    global last_key_rate
    sendc(alice, "get_node_stats")
    key_length = rcv_i(alice)
    if key_length != last_key_length:
        now = time.time()
        key_rate  = key_length/(now-last_update_time)
        last_key_length = key_length
        last_update_time = time.time()
        last_key_rate = key_rate
    qber = rcv_d(alice)
    return last_key_rate, qber




#create top_level parser
parser = argparse.ArgumentParser()

parser.add_argument("--use_localhost", action="store_true", 
                    help="connect to localhost instead of ip from network.json; e.g. when port forwarding")

parser.add_argument("--status", action="store_true", help="print status")
parser.add_argument("--counts", action="store_true", help="counts per 0.1s")
parser.add_argument("--gates", action="store_true", help="plot gates")
parser.add_argument("--link", action="store_true", help="get link status")
parser.add_argument("--calfigures", action="store_true", help="plot calibration figures")

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

elif args.link:
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
    ax1.set_ylim(0, (max(h)//50 + 1)*50)
    fig.canvas.draw()
    fig.canvas.flush_events()
    fig.canvas.mpl_connect('close_event', handle_close) # listen to close event

    while close_flag == 0:
        h = get_gates()
        line1.set_ydata(h)
        ax1.set_ylim(0, (max(h)//50 + 1)*50)
        fig.canvas.draw()
        fig.canvas.flush_events()
        time.sleep(0.1)

elif args.calfigures:
    fig, axs = plt.subplots(1, 2)

    # falling edge
    sendc(bob, 'get_calfigures')
    m = rcv_data(bob)
    data = pickle.loads(m)
    axs[0].set_title("falling edge detection")
    axs[0].plot(data[:,0])
    edge = np.where(data[:,1]==1)
    axs[0].vlines(edge, 0, data.max(), color='green')
    axs[0].set_ylim(0)
    axs[0].set_xlim(0)
    
    # find_sp 
    m = rcv_data(bob)
    data = pickle.loads(m)
    axs[1].set_title("find single peak")
    axs[1].plot(data[:,0], data[:,1])
    edge = data[:,0][np.where(data[:,2]==1)]
    axs[1].vlines(edge, 0, data[:,1].max(), color='green')
    axs[1].set_ylim(0)
    axs[1].set_xlim(0)
    
    # fd_
    m = rcv_data(bob)
    data = pickle.loads(m)
    plt.figure()
    plt.title("find delay")
    plt.plot(data, '-x', label='Bob')
    m = rcv_data(bob)
    data = pickle.loads(m)
    plt.plot(data, '-o', label='Alice')
    plt.ylim(0)
    plt.xlim(0)
    plt.legend()
    
    # fd__long
    m = rcv_data(bob)
    data = pickle.loads(m)
    plt.figure()
    plt.title("find delay long")
    plt.plot(data, '-x', label='Bob')
    m = rcv_data(bob)
    data = pickle.loads(m)
    plt.plot(data, '-o', label='Alice')
    plt.ylim(0)
    plt.xlim(0)
    plt.legend()

    plt.show()


elif args.status:
    firstrun = True
    count = 0
    
    last_key_length = 0
    last_update_time  = 0
    last_key_rate = 0

    while 1:
        global errorflag
        errorflag = 0

        # rng 
        rng_alice = rng_status(alice)
        rng_bob = rng_status(bob)

        # fifos
        fifo_alice = fifo_status(alice)
        fifo_bob = fifo_status(bob)
        
        # servers
        server_alice = server_status(alice)
        server_bob = server_status(bob)

        # counts
        total, click0, click1 = get_counts()
        if firstrun:
            first_total = total
            first_click0 = click0
            first_click1 = click1
        if (total<(first_total/2)) or (total>(first_total*2)):
            total_s = colored(total, 'yellow')
        else:
            total_s = colored(total, 'green')
        if (click0<(first_click0/2)) or (click0>(first_click0*2)):
            click0_s = colored(click0, 'yellow')
        else:
            click0_s = colored(click0, 'green')
        if (click1<(first_click1/2)) or (click1>(first_click1*2)):
            click1_s = colored(click1, 'yellow')
        else:
            click1_s = colored(click1, 'green')
        if total == 0:
            ingates = 0
        else:
            ingates = round((click0 + click1)*100 / total)
        if 50 < ingates < 75:
            ingates_s = colored(str(ingates)+'%', 'yellow')
        elif ingates < 50:
            ingates_s = colored(str(ingates)+'%', 'red')
        else:
            ingates_s = colored(str(ingates)+'%', 'green')

        # spd temp
        if (count%100 == 0):
            # aure usb interface is slow; update rarely
            sendc(bob, 'get_spd_temp')
            temp = rcv_d(bob)
        if temp < 30:
            temp_s = colored(temp, 'green')

        # pci interface
        xilinx_bob = get_pci_status(bob)
        xilinx_alice = get_pci_status(alice)

        # sync
        sendc(alice, 'get_gc')
        sendc(bob, 'get_gc')
        gc_alice = int(rcv_d(alice))
        gc_bob = int(rcv_d(bob))
        gc_diff = gc_bob - gc_alice
        gc_time = gc_alice/40e6
        gc_time = gc_bob/40e6
        gc_diff_time = gc_diff / 40e6
        if abs(gc_diff_time) > 0.1:
            gc_diff_time_ms = colored(round(gc_diff_time*1000,2), 'red')
            errorflag = 1
        else:
            gc_diff_time_ms = colored(round(gc_diff_time*1000,2), 'green')

        # hw components
        #if (count%100 == 0):
        ltc_alice, ltc_bob = check_chip_status('get_ltc_info')
        sda_alice, sda_bob = check_chip_status('get_sda_info')
        fda_alice, fda_bob = check_chip_status('get_fda_info')

        # wrs ip status
        wrs_ip_status_alice, wrs_ip_status_bob = get_wrs_ip_status()

        key_rate, qber = get_node_stats()
            


        header1 = ['', 'Alice', 'Bob', '']
        table1 = [
                ["rng", rng_alice, rng_bob],
                ["fifos", fifo_alice, fifo_bob],
                ["servers", server_alice, server_bob],
                ["wrs ip", wrs_ip_status_alice, wrs_ip_status_bob, ],
                #["xilinx pci", xilinx_alice, xilinx_bob, "update in "+str(100-count%100)],
                #["clock chip", ltc_alice, ltc_bob, "update in "+str(100-count%100)],
                #["slow dac", sda_alice, sda_bob, "update in "+str(100-count%100)],
                #["fast dac", fda_alice, fda_bob, "update in "+str(100-count%100)],
                ["xilinx pci", xilinx_alice, xilinx_bob, ],
                ["clock chip", ltc_alice, ltc_bob, ],
                ["slow dac", sda_alice, sda_bob, ],
                ["fast dac", fda_alice, fda_bob, ],
                ]
        table2 = [
                ["initial counts (1/0.1s)", first_total, first_click0, first_click1],
                ["current counts (1/0.1s)", total_s, click0_s, click1_s, ingates_s],
                ["spd temp", temp_s, "", "", "update in "+str(100-count%100)],
                ["gc time (s)", round(gc_time,2)],
                ["gc A-B diff time (ms)", gc_diff_time_ms],
                ]
        
        table3 = [
                ["qber [%]", round(qber*100, 2)],
                ["key rate [bit/s]", round(key_rate)],
                ]

        print("\033[2J", tabulate(table2, tablefmt="plain"), "\n\n", tabulate(table1, tablefmt="plain", headers=header1), "\n\n", tabulate(table3, tablefmt="plain"))




        update_errorflag()


        time.sleep(1)
        firstrun = False
        count += 1









