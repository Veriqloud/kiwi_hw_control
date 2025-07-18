#!/bin/python

import socket
import json
import argparse
#from termcolor import colored
import struct
import time
import os
import pickle
import matplotlib.pylab as plt, numpy as np

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
    m = recv_exact(4)
    l = struct.unpack('i', m)[0]
    m = bytes(0)
    while len(m)<l:
        m += bob.recv(l - len(m))
    return m


def init(args):
    if args.ltc:
        sendc("init_ltc")
    elif args.fda:
        sendc("init_fda")
    elif args.sync:
        sendc("init_sync")
    elif args.sda:
        sendc("init_sda")
    elif args.jic:
        sendc("init_jic")
    elif args.tdc:
        sendc("init_tdc")
    elif args.ttl:
        sendc("init_ttl")

    elif args.all:
        sendc("init_all")
    elif args.rst_default:
        sendc("init_rst_default")
    elif args.rst_tmp:
        sendc("init_rst_tmp")
    elif args.apply_default:
        sendc("init_apply_default")

def set(args):
    if args.pm_mode:
        sendc("set_pm_mode")
        sendc(args.pm_mode)
    elif args.fake_rng_seq:
        sendc("set_fake_rng_seq")
        sendc(args.fake_rng_seq)
        send_i(args.pos)
    elif args.insert_zeros:
        sendc("set_insert_zeros")
        sendc(args.insert_zeros)
    elif args.pm_shift is not None:
        sendc('set_pm_shift')
        send_i(args.pm_shift)
    elif args.zero_pos:
        sendc('set_zero_pos')
        send_i(args.zero_pos)
    elif args.angles:
        sendc('set_angles')
        for i in range(4):
            send_d(args.angles[i])
    elif args.soft_gate_filter:
        sendc('set_soft_gate_filter')
        sendc(args.soft_gate_filter)
    elif args.soft_gates:
        sendc('set_soft_gates')
        for i in range(3):
            send_i(args.soft_gates[i])
    elif args.feedback:
        sendc('set_feedback')
        sendc(args.feedback)
        print(rcvc())
    elif args.spd_mode:
        sendc('set_spd_mode')
        sendc(args.spd_mode)
    elif args.spd_deadtime:
        sendc('set_spd_deadtime')
        send_i(args.spd_deadtime)
    elif args.spd_eff:
        sendc('set_spd_eff')
        send_i(int(args.spd_eff))
    elif args.pol_bias:
        sendc('set_pol_bias')
        for i in range(4):
            send_d(args.pol_bias[i])
    elif args.optimize_pol:
        sendc('set_optimize_pol')

def get(args):
    if args.info:
        sendc('get_info')
        print(rcvc())
    if args.gc:
        sendc('get_gc')
        gc = rcv_q()
        t = gc/80e6
        print("current gc:", gc, '({:.2f} s)'.format(t))
    elif args.ddr_status:
        sendc('get_ddr_status')
        print(rcvc())
    elif args.counts:
        while 1:
            #sendc('get_counts3')
            #total = rcv_i()
            #click0 = rcv_i()
            #click1 = rcv_i()
            #print(f"Total: {total}, Click0: {click0}, Click1: {click1}              ",flush=True)
            sendc('get_counts')
            total = rcv_i()
            click0 = rcv_i()
            click1 = rcv_i()
            print(f"Total: {total}, Click0: {click0}, Click1: {click1}              ",flush=True)
            time.sleep(0.1)
    elif args.counts2:
        while 1:
            sendc('get_counts2')
            total = rcv_i()
            click0 = rcv_i()
            click1 = rcv_i()
            print(f"Total: {total}, Click0: {click0}, Click1: {click1}              ",flush=True)
            time.sleep(1)
    
    elif args.gates:
        sendc('get_gates')
        data = rcv_data()
        h = pickle.loads(data)
        plt.figure()
        bins = np.arange(0,625, 2)
        plt.plot(bins[:-1], h)
        plt.show()
    
    elif args.ltc:
        sendc('get_ltc_info')
        print(rcvc())
    elif args.sda:
        sendc('get_sda_info')
        print(rcvc())
    elif args.fda:
        sendc('get_fda_info')
        print(rcvc())






#create top_level parser
parser = argparse.ArgumentParser()
subparsers = parser.add_subparsers(required=True)

parser_init = subparsers.add_parser('init')
parser_set = subparsers.add_parser('set')
parser_get = subparsers.add_parser('get')
parser_debug = subparsers.add_parser('debug')

parser.add_argument("--use_localhost", action="store_true", 
                    help="connect to localhost instead of ip from network.json; e.g. when port forwarding")

######### init ###########
parser_init.add_argument("--all", action="store_true", 
                         help="init all devices and sync")
parser_init.add_argument("--ltc", action="store_true", 
                         help="init clock chip ltc")
parser_init.add_argument("--fda", action="store_true", 
                         help="init fast dac")
parser_init.add_argument("--sda", action="store_true", 
                         help="init slow dac")
parser_init.add_argument("--jic", action="store_true", 
                         help="init jitter cleaner for tdc")
parser_init.add_argument("--tdc", action="store_true", 
                         help="init tdc")
parser_init.add_argument("--sync", action="store_true", 
                         help="sync to PPS")
parser_init.add_argument("--ttl", action="store_true", 
                         help="delay module for the SPD gate")
parser_init.add_argument("--rst_default", action="store_true", 
                         help="reset default parameters in config/default.txt")
parser_init.add_argument("--rst_tmp", action="store_true", 
                         help="reset tmp file in config/default.txt")
parser_init.add_argument("--apply_default", action="store_true", 
                         help="apply values from config/default.txt")
parser_init.add_argument("--ddr", action="store_true", 
                         help="init ddr data")


######### set ###########
#    parser_set.add_argument("--rng_mode", choices=['seq', 'fake_rng', 'true_rng'],
#                            help="fixed periodic sequece, fake rng or real rng")
parser_set.add_argument("--fake_rng_seq", choices=['off', 'single', 'random', 'all_one', 'block1'],
                        help="set fake rng sequence")
parser_set.add_argument("--feedback", choices=['on', 'off'], 
                        help="balance interferometer")
parser_set.add_argument("--insert_zeros", choices=['on', 'off'], 
                        help="insert zeros into rng sequence for feedback")
parser_set.add_argument("--zero_pos", type=int, 
                        help="insert zeros at this position for feedback")
parser_set.add_argument("--spd_mode", choices=['free', 'gated'], 
                        help="free running or gated")
parser_set.add_argument("--spd_delay", type=int, metavar="time",  
                        help="delay time in ps")
parser_set.add_argument("--spd_deadtime", type=int, metavar="time",
                        help="dead time in us; recommended: 15us for gated; 50us for freerunning")
parser_set.add_argument("--spd_eff", choices=['10', '20', '30'], 
                        help="detection efficiency in percent; strongly recommended: 20")
parser_set.add_argument("--soft_gate_filter", choices=['off', 'on'], 
                        help="filter events through time gates")
parser_set.add_argument("--soft_gates", nargs=3, type=int, 
                        metavar=['gate0 gate1 width'],
                        help="set gate positions and width")
parser_set.add_argument("--pm_mode", choices=['seq64', 'seq64tight', 'fake_rng', 'true_rng', 'off'],
                        help="fixed periodic sequece, fake rng or real rng")

parser_set.add_argument("--pol_bias",nargs=4, type=float, metavar="V",  help="float [0,5] V")

parser_set.add_argument("--pos",type=int, default=0, help="peak position for single")

parser_set.add_argument("--optimize_pol", action="store_true", help="find best setting for polarization controller")



######### get  ###########
parser_get.add_argument("--info", action="store_true",
                        help="print hardware info")
parser_get.add_argument("--counts", action="store_true", 
                        help="get SPD counts")
parser_get.add_argument("--counts2", action="store_true", 
                        help="get SPD counts averaged over 1s")
parser_get.add_argument("--gates", action="store_true",
                        help="download timestamps of spd clicks")
parser_get.add_argument("--gc", action="store_true",
                        help="get current global counter")
#    parser_get.add_argument("--angles", action="store_true",
#                            help="download the postprocessed angles")
parser_get.add_argument("--ddr_status", action="store_true",
                        help="print ddr status")
parser_get.add_argument("--ltc", action="store_true",
                        help="print clock chip registers")
parser_get.add_argument("--sda", action="store_true",
                        help="print slow dac registers")
parser_get.add_argument("--fda", action="store_true",
                        help="print fast dac registers")

parser_set.add_argument("--angles", nargs=4, type=float, 
                        help="float [-1,1]")
parser_set.add_argument("--pm_shift", type=int, metavar=("steps"), 
                        help="time shift signal for phase modulator in steps of 1.25ns")




parser_init.set_defaults(func=init)
parser_set.set_defaults(func=set)
parser_get.set_defaults(func=get)

args = parser.parse_args()

connect_to_bob(args.use_localhost)

args.func(args)





