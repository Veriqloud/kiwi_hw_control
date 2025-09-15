#!/bin/python

from termcolor import colored
import socket
#import numpy as np
import json
import datetime
import ctl_bob as ctl
import struct
from lib.fpga import update_tmp, save_tmp, get_tmp, get_gc, get_ltc_info, get_sda_info, get_fda_info
import lib.gen_seq as gen_seq
import pickle   # serialize numpy data
import numpy as np
from tabulate import tabulate

HW_CONTROL = '/home/vq-user/hw_control/'

qlinepath = '../'

networkfile = qlinepath+'config/network.json'
connection_logfile = qlinepath+'log/ip_connections_to_hardware.log'


# get ip from config/network.json
with open(networkfile, 'r') as f:
    network = json.load(f)

# Server configuration
host = network['ip']['bob']
port = int(network['port']['hw'])


# Create TCP socket
server_socket = socket.socket()
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_socket.bind((host, port))
server_socket.listen()


print(f"[hw_bob] {datetime.datetime.now()}\tServer listening on {host}:{port}")


while True:
    conn, addr = server_socket.accept()  # Accept incoming connection
    print(f"[hw_bob] {datetime.datetime.now()}\tConnected by {addr}")
    with open(connection_logfile, 'a') as f:
        f.write(f"[hw_bob] {datetime.datetime.now()}\t{addr}")


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

    # send binary data
    def send_data(data):
        print(colored('sending data', 'blue', force_color=True))
        l = len(data)
        m = struct.pack('i', l) + data
        conn.sendall(m)

    
    try:
        while True:
            try:
                # Receive command from client
                command = rcvc()
            except ConnectionResetError:
                print(f"[hw_bob] {datetime.datetime.now()}\tClient connection was reset. Exiting loop.")
                break

            if command == 'init_ltc':
                ctl.init_ltc()
            elif command == 'init_fda':
                ctl.init_fda()
            elif command == 'init_sync':
                ctl.init_sync()
            elif command == 'init_sda':
                ctl.init_sda()
            elif command == 'init_jic':
                ctl.init_jic()
            elif command == 'init_tdc':
                ctl.init_tdc()
            elif command == 'init_ttl':
                ctl.init_ttl()
            elif command == 'init_all':
                ctl.init_all()
            elif command == 'init_rst_default':
                ctl.init_rst_default()
            elif command == 'init_rst_tmp':
                ctl.init_rst_tmp()
            elif command == 'init_apply_default':
                ctl.init_apply_default()
            
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
                shift = rcv_i()
                update_tmp('pm_shift', shift)
                ctl.Update_Dac()
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
            elif command == 'set_soft_gate_filter':
                mode = rcvc()
                update_tmp('soft_gate', mode)
                ctl.Update_Softgate()
            elif command == 'set_soft_gates':
                t = get_tmp()
                t['soft_gate0'] = rcv_i()
                t['soft_gate1'] = rcv_i()
   #             t['soft_gatew'] = rcv_i()
                t['w0'] = rcv_i()
                t['w1'] = rcv_i()
                save_tmp(t)
                ctl.Update_Softgate()
            elif command == 'set_feedback':
                mode = rcvc()
                update_tmp('feedback', mode)
                ctl.Update_Dac()
                t = get_tmp()
                if t['soft_gate'] == 'off':
                    s = "WARNING: softgate filter is OFF. Feedback will not work"
                else:
                    s = "ok"
                sendc(s)
            elif command == 'set_spd_mode':
                mode = rcvc()
                #print("opening SPD...")
                aurea = ctl.Aurea()
                if mode=="free":
                    update_tmp('spd_mode', 'continuous')
                    aurea.mode("continuous")
                    aurea.close()
                elif mode=="gated":
                    update_tmp('spd_mode', 'gated')
                    aurea.mode("gated")
                    aurea.close()
            elif command == 'set_spd_deadtime':
                deadtime = rcv_i()
                #print("opening SPD...")
                aurea = ctl.Aurea()
                aurea.deadtime(deadtime)
                aurea.close()
                update_tmp('deadtime_gated', deadtime)
            elif command == 'set_spd_eff':
                eff = rcv_i()
                #print("opening SPD...")
                aurea = ctl.Aurea()
                aurea.effi(eff)
                aurea.close()
                update_tmp('spd_eff', eff)
            elif command == 'set_pol_bias':
                t = get_tmp()
                t['pol0'] = rcv_d()
                t['pol1'] = rcv_d()
                t['pol2'] = rcv_d()
                t['pol3'] = rcv_d()
                save_tmp(t)
                ctl.Update_Pol()
            elif command == 'set_optimize_pol':
                ctl.Polarisation_Control()
            
            elif command == 'get_info':
                with open(HW_CONTROL+'config/tmp.txt') as f:
                    s = f.read()
                    sendc(s)
            elif command == 'get_gc':
                gc = get_gc()
                #gc = ctl.Get_Current_Gc()
                send_q(gc)
            elif command == 'get_ddr_status':
                s = ctl.Ddr_Status()
                sendc(s)
            elif command == 'get_counts':
                c = ctl.counts_fast()
                for i in range(3):
                    send_i(c[i])
            elif command == 'get_counts3':
                c = ctl.counts_single()
                for i in range(3):
                    send_i(c[i])
            elif command == 'get_counts2':
                c = ctl.counts_slow()
                for i in range(3):
                    send_i(c[i])
            
            elif command == 'get_gates':
                ctl.Download_Time(10000, 'get_gates')
                input_file = HW_CONTROL+'data/tdc/get_gates.txt'
                data = np.loadtxt(input_file, usecols=1) % 625
                bins = np.arange(0, 625, 2)
                h1, _ = np.histogram(data, bins=bins)
                serialized = pickle.dumps(h1)
                send_data(serialized)
                
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
                print(f"[hw_bob] {datetime.datetime.now()}\tClient disconnected.")
                break  # Exit loop if the client closes the connection


    except KeyboardInterrupt:
        print(f"[hw_bob] {datetime.datetime.now()}\tServer stopped by keyboard interrupt.")
    finally:
        try:
            conn.shutdown(socket.SHUT_RDWR)  # Properly shutdown connection
        except OSError:
            pass  # Ignore if connection is already closed
        conn.close()



