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
        port = ports_for_localhost['hw_alice']
    else:
        with open(network_file, 'r') as f:
            network = json.load(f)
        host = network['ip']['alice']
        port = network['port']['hw']
    
    global alice
    alice = socket.socket()
    alice.connect((host, port))
    




# send command
def sendc(c):
    b = c.encode()
    m = len(c).to_bytes(2, 'little')+b
    alice.sendall(m)

# receive command
def rcvc():
    l = int.from_bytes(alice.recv(2), 'little')
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


def init(args):
    if args.ltc:
        sendc("init_ltc")
    elif args.fda:
        sendc("init_fda")
    elif args.sync:
        sendc("init_sync")
    elif args.sda:
        sendc("init_sda")
    elif args.decoy:
        sendc("decoy_reset")
    elif args.all:
        sendc("init_all")
    elif args.rst_default:
        sendc("init_rst_default")
    elif args.rst_tmp:
        sendc("init_rst_tmp")
    elif args.apply_default:
        sendc("init_apply_default")

def set(args):
    if args.vca is not None:
        sendc("set_vca")
        send_d(args.vca)
    elif args.am_bias is not None:
        sendc("set_am_bias")
        send_d(args.am_bias)
    elif args.am_bias_2 is not None:
        sendc("set_am_bias_2")
        send_d(args.am_bias_2)
    elif args.qdistance is not None:
        sendc("set_qdistance")
        send_d(args.qdistance)
    elif args.pm_mode:
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
    elif args.am_shift is not None:
        sendc('set_am_shift')
        send_i(args.am_shift)
    elif args.am_mode:
        sendc('set_am_mode')
        sendc(args.am_mode)
    elif args.am2_mode:
        sendc('set_am2_mode')
        sendc(args.am2_mode)
    elif args.zero_pos:
        sendc('set_zero_pos')
        send_i(args.zero_pos)
    elif args.angles:
        sendc('set_angles')
        for i in range(4):
            send_d(args.angles[i])

def get(args):
    if args.info:
        sendc('get_info')
        print(rcvc())
    elif args.gc:
        sendc('get_gc')
        #Ddr_Data_Init()
        #Get_Current_Gc()
        gc = rcv_q()
        t = gc/80e6
        print("current gc:", gc, '({:.2f} s)'.format(t))
    elif args.ddr_status:
        sendc('get_ddr_status')
        print(rcvc())
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

parser.add_argument("--use_localhost", action="store_true", 
                    help="connect to localhost instead of ip from network.json; e.g. when port forwarding")

parser_init.add_argument("--all", action="store_true", 
                         help="init all devices and sync")
parser_init.add_argument("--ltc", action="store_true", 
                         help="init clock chip ltc")
parser_init.add_argument("--fda", action="store_true", 
                         help="init fast dac")
parser_init.add_argument("--sda", action="store_true", 
                         help="init slow dac")
parser_init.add_argument("--decoy", action="store_true", 
                         help="reset decoy module")
parser_init.add_argument("--sync", action="store_true", 
                         help="sync to PPS")
parser_init.add_argument("--rst_default", action="store_true", 
                         help="reset default parameters in config/default.txt")
parser_init.add_argument("--rst_tmp", action="store_true", 
                         help="reset tmp file in config/default.txt")
parser_init.add_argument("--apply_default", action="store_true", 
                         help="apply values from config/default.txt")
#    parser_init.add_argument("--ddr", action="store_true", 
#                             help="init ddr data")


parser_set.add_argument("--vca", type=float, metavar=("voltage"), 
                        help="voltage controlled attenuator; float [0,5] V")
parser_set.add_argument("--am_bias", type=float, metavar=("voltage"), 
                        help="bias of amplitude modulator; float [-10,10] V")
parser_set.add_argument("--am_bias_2", type=float, metavar=("voltage"), 
                        help="bias of amplitude modulator; float [0,10] V")
parser_set.add_argument("--am_mode", choices=['off', 'single', 'double', 'single64'],
                        help="send single pulse at 40MHz or double pulse at 80MHz or single64 at 80MHz/64")
parser_set.add_argument("--am2_mode", choices=['off', 'single', 'fake_rng', 'true_rng'],
                        help="second amplitude modulator for decoy state")
parser_set.add_argument("--am_shift", type=int, metavar=("steps"), 
                        help="time shift pulse generation in steps of 1.25ns")
parser_set.add_argument("--pm_shift", type=int, metavar=("steps"), 
                        help="time shift signal for phase modulator in steps of 1.25ns")
parser_set.add_argument("--qdistance", type=float, metavar="value", 
                        help="fine tune double pulse separation; float [-1,1]; good value is 0.08")
parser_set.add_argument("--pm_mode", choices=['seq64', 'seq64tight', 'fake_rng', 'true_rng', 'off'],
                        help="fixed periodic sequece, fake rng or real rng")
parser_set.add_argument("--angles", nargs=4, type=float,
                        help="float [-1,1]")
parser_set.add_argument("--zero_pos", type=int, 
                        help="insert zeros at this position for feedback")
parser_set.add_argument("--fake_rng_seq", choices=['off', 'single', 'random', 'all_one', 'block1'],
                        help="set fake rng sequence")
parser_set.add_argument("--insert_zeros", choices=['on', 'off'], 
                        help="insert zeros into rng sequence for feedback")
parser_set.add_argument("--pos",type=int, default=0, help="peak position for single")



parser_get.add_argument("--info", action="store_true",
                        help="print hardware info")
parser_get.add_argument("--gc", action="store_true",
                        help="get current global counter")
parser_get.add_argument("--ddr_status", action="store_true",
                        help="print ddr status")
parser_get.add_argument("--ltc", action="store_true",
                        help="print clock chip registers")
parser_get.add_argument("--sda", action="store_true",
                        help="print slow dac registers")
parser_get.add_argument("--fda", action="store_true",
                        help="print fast dac registers")





parser_init.set_defaults(func=init)
parser_set.set_defaults(func=set)
parser_get.set_defaults(func=get)


args = parser.parse_args()

connect_to_alice(args.use_localhost)

args.func(args)



