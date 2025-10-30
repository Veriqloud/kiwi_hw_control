#!/bin/python

from termcolor import colored
import socket
import numpy as np
import json
import datetime
import ctl_alice as ctl
import struct
from lib.fpga import update_tmp, save_tmp, get_tmp, get_gc, get_ltc_info, get_sda_info, get_fda_info
import lib.gen_seq as gen_seq
from tabulate import tabulate
from pathlib import Path

HW_CONTROL = '/home/vq-user/hw_control/'

qlinepath = '../'

networkfile = qlinepath+'config/network.json'
connection_logfile = '/tmp/log/ip_connections_to_hardware.log'

# make sure /tmp/log/ existists
Path("/tmp/log").mkdir(exist_ok=True)


# get ip from config/network.json
with open(networkfile, 'r') as f:
    network = json.load(f)

# Server configuration
host = network['ip']['alice']
port = int(network['port']['hw'])


# Create TCP socket
server_socket = socket.socket()
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_socket.bind((host, port))
server_socket.listen()


print(f"[hw_alice] {datetime.datetime.now()}\tServer listening on {host}:{port}")


while True:
    conn, addr = server_socket.accept()  # Accept incoming connection
    print(f"[hw_alice] {datetime.datetime.now()}\tConnected by {addr}")
    with open(connection_logfile, 'a') as f:
        f.write(f"[hw_alice] {datetime.datetime.now()}\t{addr}")

    # send command
    def sendc(c):
        print(colored(c, 'blue', force_color=True))
        b = c.encode()
        m = len(c).to_bytes(2, 'little')+b
        conn.sendall(m)

    # receive command
    def rcvc():
        l = int.from_bytes(conn.recv(2), 'little')
        mr = conn.recv(l)
        while len(mr)<l:
            mr += conn.recv(l-len(mr))
        command = mr.decode().strip()
        print(colored(command, 'cyan', force_color=True))
        return command
    
    # send integer
    def send_i(value):
        print(colored(value, 'blue', force_color=True))
        m = struct.pack('i', value)
        conn.sendall(m)
    
    # send long integer
    def send_q(value):
        print(colored(value, 'blue', force_color=True))
        m = struct.pack('q', value)
        conn.sendall(m)

    # receive integer
    def rcv_i():
        m = conn.recv(4)
        value = struct.unpack('i', m)[0]
        print(colored(value, 'cyan', force_color=True))
        return value

    # send double
    def send_d(value):
        print(colored(value, 'blue', force_color=True))
        m = struct.pack('d', value)
        conn.sendall(m)

    # receive double
    def rcv_d():
        m = conn.recv(8)
        value = struct.unpack('d', m)[0]
        print(colored(value, 'cyan', force_color=True))
        return value

    
    try:
        while True:
            try:
                # Receive command from client
                command = rcvc()
            except ConnectionResetError:
                print(f"[hw_alice] {datetime.datetime.now()}\tClient connection was reset. Exiting loop.")
                break

            if command == 'init_ltc':
                ctl.init_ltc()
            elif command == 'init_fda':
                ctl.init_fda()
            elif command == 'init_sync':
                ctl.init_sync()
            elif command == 'init_sda':
                ctl.init_sda()
            elif command == 'decoy_reset':
                ctl.decoy_reset()
            elif command == 'init_all':
                ctl.init_all()
            elif command == 'init_rst_default':
                ctl.init_rst_default()
            elif command == 'init_rst_tmp':
                ctl.init_rst_tmp()
            elif command == 'init_apply_default':
                ctl.init_apply_default()
            elif command == 'set_vca':
                value = rcv_d()
                ctl.Set_Vca(value)
            elif command == 'set_am_bias':
                value = rcv_d()
                ctl.Set_Am_Bias(value)
            elif command == 'set_am_bias_2':
                value = rcv_d()
                ctl.Set_Am_Bias_2(value)
            elif command == 'set_qdistance':
                value = rcv_d()
                ctl.update_tmp('qdistance', value)
                ctl.Update_Dac()
            elif command == 'set_pm_mode':
                pm_mode = rcvc()
                update_tmp('pm_mode', pm_mode)
                ctl.Update_Dac()
            elif command == 'set_fake_rng_seq':
                seq = rcvc()
                pos = rcv_i()
                if seq == 'single':
                    ctl.Write_To_Fake_Rng(gen_seq.seq_rng_single(pos))
                elif seq == 'off':
                    ctl.Write_To_Fake_Rng(gen_seq.seq_rng_zeros())
                elif seq == 'random':
                    ctl.Write_To_Fake_Rng(gen_seq.seq_rng_random())
                elif seq == 'all_one':
                    ctl.Write_To_Fake_Rng(gen_seq.seq_rng_all_one())
                elif seq == 'block1':
                    ctl.Write_To_Fake_Rng(gen_seq.seq_rng_block1())
                ctl.Update_Dac()
            elif command == 'set_insert_zeros':
                mode = rcvc()
                update_tmp('insert_zeros', mode)
                ctl.Update_Dac()
            elif command == 'set_pm_shift':
                print("waiting for value")
                shift = rcv_i()
                print("received value")
                update_tmp('pm_shift', shift)
                print("updated value")
                ctl.Update_Dac()
                print("updated dac")
            elif command == 'set_am_shift':
                shift = rcv_i()
                update_tmp('am_shift', shift)
                ctl.Update_Dac()
            elif command == 'set_am_mode':
                mode = rcvc()
                update_tmp('am_mode', mode)
                ctl.Update_Dac()
            elif command == 'set_am2_mode':
                mode = rcvc()
                update_tmp('am2_mode', mode)
                ctl.Update_Decoy()
            elif command == 'set_zero_pos':
                pos = rcv_i()
                update_tmp('zero_pos', pos)
                ctl.Update_Dac()
            elif command == 'set_angles':
                t = get_tmp()
                t['angle0'] = rcv_d()
                t['angle1'] = rcv_d()
                t['angle2'] = rcv_d()
                t['angle3'] = rcv_d()
                save_tmp(t)
                ctl.Update_Angles()
            
            elif command == 'get_info':
                with open(HW_CONTROL+'config/tmp.txt') as f:
                    s = f.read()
                    sendc(s)
            elif command == 'get_gc':
                #gc = ctl.Get_Current_Gc()
                gc = get_gc()
                send_q(gc)
            elif command == 'get_ddr_status':
                s = ctl.Ddr_Status()
                sendc(s)
            
            elif command == 'get_ltc_info':
                regs = get_ltc_info(verbose=True)
                header = ['add', 'exp', 'got']
                s = tabulate(regs, headers=header, tablefmt='plain') 
                sendc(s)
            
            elif command == 'get_sda_info':
                regs = get_sda_info(verbose=True)
                header = ['add', 'exp', 'got']
                s = tabulate(regs, headers=header, tablefmt='plain') 
                sendc(s)
            
            elif command == 'get_fda_info':
                regs = get_fda_info(verbose=True)
                header = ['add', 'exp', 'got']
                s = tabulate(regs, headers=header, tablefmt='plain') 
                sendc(s)

            elif not command:
                print(f"[hw_alice] {datetime.datetime.now()}\tClient disconnected.")
                break  # Exit loop if the client closes the connection


    except KeyboardInterrupt:
        print(f"[hw_alice] {datetime.datetime.now()}\tServer stopped by keyboard interrupt.")
    finally:
        try:
            conn.shutdown(socket.SHUT_RDWR)  # Properly shutdown connection
        except OSError:
            pass  # Ignore if connection is already closed
        conn.close()



