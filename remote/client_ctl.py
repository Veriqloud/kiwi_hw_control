#!/bin/python

import socket
import time
import struct  # For unpacking data size
import subprocess, sys, argparse
import numpy as np
import main_Alice as main
from lib.config_lib import get_tmp, save_tmp, update_tmp, update_default, get_default, Angle, Sync_Gc, wait_for_pps_ret
import lib.gen_seq as gen_seq
from termcolor import colored


# Client configuration
SERVER_HOST = '192.168.1.77'  # Server's IP address
SERVER_PORT = 9999  # Server's port
# BUFFER_SIZE = 65536  # Increased buffer size for receiving data
BUFFER_SIZE = 64  # Increased buffer size for receiving data
# ROUNDS = 1  # Number of rounds to perform
# DELAY_BETWEEN_ROUNDS = 2  # Delay between rounds in seconds



#def rcv_all(bufsize):
#    # make sure bufsize bytes have been received
#    mr = client_socket.recv(bufsize)
#    while (len(mr)<bufsize):
#        mr += client_socket.recv(bufsize-len(mr))
#    return mr

def rcv_all(socket, num):
    # make sure bufsize bytes have been received
    mr = socket.recv(num)
    while (len(mr)<num):
        mr += socket.recv(num-len(mr))
    return mr

def client_start(commands_in):
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BUFFER_SIZE)
    client_socket.connect((SERVER_HOST, SERVER_PORT))

    # send command
    def sendc(c):
#        print(colored(c, 'cyan'))
        b = c.encode()
        m = len(c).to_bytes(1, 'little')+b
        client_socket.sendall(m)
    
    def send_u32(value):
#        print(colored(value, 'green'))
        m = value.to_bytes(4, byteorder='little')
        client_socket.sendall(m)
    
    def rcv_u32():
        m = client_socket.recv(4)
        value = int.from_bytes(m, byteorder='little')
#        print(colored(value, 'green'))
        return value

    def rcvc():
        l = int.from_bytes(client_socket.recv(1), 'little')
        mr = client_socket.recv(l)
        while len(mr)<l:
            mr += client_socket.recv(l-len(mr))
        command = mr.decode().strip()
 #       print(colored(command, 'cyan'))
        return command

    try:
        for command in commands_in:
            # command = 'init'
            sendc(command)

            if command == 'init':
                main.init_all()
                sendc('Alice init done')
                rcvc()
                print(colored('sync_gc \n', 'cyan'))
                wait_for_pps_ret()
                sendc('sync gc')
                Sync_Gc()

            if command == 'sync_gc':
                print(colored('sync_gc \n', 'cyan'))
                wait_for_pps_ret()
                sendc('go')
                Sync_Gc()

            if command == 'find_max_vca':
                print(colored('find_max_vca', 'cyan'))
                update_tmp('am_mode', 'double')
                main.Update_Dac()
                d = get_default()
                vca = d['vca']
                count = 0
                while  (count < 3000) and (vca <= 4.8) :
                    vca = round(vca + 0.2, 2)
                    main.Set_Vca(round(vca, 2))
                    time.sleep(0.2)
                    sendc('get counts')
                    count = rcv_u32()

                if count >= 3000:
                   print(colored(f"Success, {vca}V / {count} cts \n", "green"))
                else:
                   print(colored(f"Fail, {vca}V / {count} cts \n", "red"))

                update_tmp('vca_calib', vca)
                sendc('done')

            if command == 'find_am_bias':
                print(colored('find_am_bias', 'cyan'))
                update_tmp('am_mode', 'off')
                main.Update_Dac()
                t = get_tmp()
                d = get_default()
                bias_default = d['am_bias']
                bias_default_1 = t['am_bias_2']
                t['am_mode'] = 'off'
                save_tmp(t)
                main.Update_Dac()
                counts = []
                main.Set_Am_Bias_2(0) 
                time.sleep(0.2)
                for i in range(11):
                    main.Set_Am_Bias(bias_default -0.5 + 0.1*i)
                    sendc('get counts')
                    counts.append(rcv_u32())
                min_counts = min(counts)
                min_idx = counts.index(min_counts)
                print("Min count: ", min_counts , "index: ", min_idx,"\n")
                am_bias_opt = bias_default -0.5 + 0.1*min_idx
                main.Set_Am_Bias(am_bias_opt)
                main.Set_Am_Bias_2(bias_default_1)


            if command == 'verify_am_bias':
                print(colored('verify_am_bias', 'cyan'))
                update_tmp('am_mode', 'off')
                main.Update_Dac()
                sendc('get counts')
                count_off = rcv_u32()

                update_tmp('am_mode', 'double')
                main.Update_Dac()
                time.sleep(0.2)

                sendc('get counts')
                count_double = rcv_u32()

                ratio = count_double / count_off
                if ratio >= 1.9:
                   print(colored(f"Success: double/off  = {ratio:.2f} ({count_double}/{count_off}) \n", "green"))
                else:
                   print(colored(f"Fail: double/off = {ratio:.2f} ({count_double}/{count_off}) \n", "red"))
                update_tmp('am_mode', 'off')
                main.Update_Dac()




            if command == 'find_am_bias_2':
                print(colored('find_am_bias_2', 'cyan'))
                update_tmp('am_mode', 'double')
                main.Update_Dac()
                #t = get_tmp()
                d = get_default()
                bias_default = d['am_bias_2']
                #bias_default_1 = t['am_bias'] 
                #t['am_mode'] = 'off'
                #save_tmp(t)
                main.Update_Dac()
                counts = []
                #main.Set_Am_Bias(0) 
                time.sleep(0.2)
                for i in range(21):
                    value = bias_default - 3 + 0.1 * i
                    if value < 0:
                       value = 0
                    main.Set_Am_Bias_2(value)
                   # main.Set_Am_Bias_2(bias_default -3 + 0.1*i)
                    sendc('get counts')
                    counts.append(rcv_u32())
                min_counts = min(counts)
                min_idx = counts.index(min_counts)
                print("Min count: ", min_counts , "index: ", min_idx)
                am_bias_opt = bias_default -3 + 0.1*min_idx
                main.Set_Am_Bias_2(max(0, round(am_bias_opt + 2, 2))) 
                #main.Set_Am_Bias(bias_default_1)


            elif command == 'pol_bob':
                print(colored('Bob polarization in progress…', 'cyan'))
                rcvc()


            elif command == 'ad':
                print(colored('ad', 'cyan'))
                update_tmp('am_mode', 'off')
                main.Update_Dac()
           #     t = get_tmp()
            #    main.Set_Am_Bias(t['am_bias'] + 1)
                rcvc()
                update_tmp('am_mode', 'double')
                main.Update_Dac()
             #   main.Set_Am_Bias(t['am_bias'])
                rcvc()



            elif command == 'find_sp':
                print(colored('find_sp', 'cyan'))
                #1.Send single pulse, am_shift 0
                update_tmp('am_shift', 0)
                update_tmp('am_mode', 'single')
                main.Update_Dac()
                #2. Receive am_shift value from Bob
                am_shift = rcv_u32()
                update_tmp('am_shift', am_shift)
                update_tmp('am_mode', 'single64')
                main.Update_Dac()
                coarse_shift = rcv_u32()

                am_shift = (am_shift + coarse_shift) % 640
                print("updating am_shift to", am_shift)
                update_tmp('am_shift', am_shift)
                main.Update_Dac()


            elif command == 'verify_gates':
                print(colored('verify_gates', 'cyan'))
                update_tmp('am_mode', 'off')
                main.Update_Dac()
                rcvc()
                update_tmp('am_mode', 'double')
                main.Update_Dac()
                status = rcvc()
                if status == "success":
                    print(colored("Success: good gates found \n", "green"))
                else:
                    print(colored("Fail: bad gates \n", "red"))


            elif command == 'fs_b':
                t = get_tmp()
                t['am_mode'] = 'double'
                t['pm_mode'] = 'off'
                save_tmp(t)
                main.Update_Dac()
                rcvc()

            elif command == 'fs_a':
                t = get_tmp()
                t['am_mode'] = 'double'
                t['pm_mode'] = 'seq64'
                save_tmp(t)
                d = get_default()
                pm_shift_coarse = (d['pm_shift']//10) * 10
                for s in range(10):
                    t['pm_shift'] = pm_shift_coarse + s
                    save_tmp(t)
                    main.Update_Dac()
                    time.sleep(0.1)
                    sendc('download data')
                    rcvc()
                pm_shift = rcv_u32()
                update_tmp('pm_shift', pm_shift_coarse + pm_shift)
                main.Update_Dac()


            elif command == 'fd_b':
                update_tmp('am_mode', 'double')
                update_tmp('pm_mode', 'fake_rng')
                update_tmp('insert_zeros', 'off')
                main.Write_To_Fake_Rng(gen_seq.seq_rng_zeros())
                main.Update_Dac()
                rcvc()
            
            elif command == 'fd_b_long':
                update_tmp('am_mode', 'double')
                update_tmp('pm_mode', 'fake_rng')
                update_tmp('insert_zeros', 'off')
                main.Write_To_Fake_Rng(gen_seq.seq_rng_zeros())
                main.Update_Dac()
                rcvc()
            
            elif command == 'fd_a':
                main.Write_To_Fake_Rng(gen_seq.seq_rng_single())
                update_tmp('pm_mode', 'fake_rng')
                update_tmp('am_mode', 'double')
                update_tmp('insert_zeros', 'off')
                main.Update_Dac()
                fiber_delay = rcv_u32()
                t = get_tmp()
                t['fiber_delay_mod'] = fiber_delay
                t['fiber_delay'] = (fiber_delay-1)%80 + t['fiber_delay_long']
                save_tmp(t)
            
            elif command == 'fd_a_long':
                t = get_tmp()
                t['pm_mode'] = 'fake_rng'
                t['am_mode'] = 'double'
                t['insert_zeros'] = 'off'
                save_tmp(t)
                main.Write_To_Fake_Rng(gen_seq.seq_rng_block1())
                main.Update_Dac()
                send_u32(t['fiber_delay_mod'])
                fiber_delay_long = rcv_u32()
                t = get_tmp()
                t['fiber_delay_long'] = fiber_delay_long
                t['fiber_delay'] = t['fiber_delay_mod'] + fiber_delay_long*80 
                t['decoy_delay'] = t['fiber_delay'] 
                save_tmp(t)
            
            #elif command == 'fd_decoy':
            #    main.Write_To_Fake_Rng(gen_seq.seq_rng_single())
            #    update_tmp('pm_mode', 'fake_rng')
            #    update_tmp('am_mode', 'double')
            #    update_tmp('insert_zeros', 'off')
            #    main.Update_Dac()
            #    m = client_socket.recv(4)
            #    fiber_delay = int.from_bytes(m, byteorder='big')
            #    t = get_tmp()
            #    t['fiber_delay_mod'] = fiber_delay
            #    t['fiber_delay'] = (fiber_delay-1)%80 + t['fiber_delay_long']
            #    save_tmp(t)
            
            
            elif command == 'fz_b':
                update_tmp('am_mode', 'double')
                update_tmp('pm_mode', 'fake_rng')
                update_tmp('insert_zeros', 'off')
                main.Write_To_Fake_Rng(gen_seq.seq_rng_zeros())
                main.Update_Dac()
                rcvc()
            
            elif command == 'fz_a':
                t = get_tmp()
                t['pm_mode'] = 'fake_rng'
                t['insert_zeros'] = 'on'
                t['zero_pos'] = 0
                save_tmp(t)
                main.Write_To_Fake_Rng(gen_seq.seq_rng_all_one())
                main.Update_Dac()
                send_u32(t['fiber_delay_mod'])
                zero_pos = rcv_u32()
                update_tmp('zero_pos', zero_pos)
                main.Update_Dac()
        
            #elif command == 'czp':
            #    update_tmp('pm_mode', 'off')
            #    update_tmp('am_mode', 'double')
            #    main.Update_Dac()


            #elif command == 'ver_sync':
            #    current_gc = main.Get_Current_Gc()
            #    print('Alice current_gc: ', current_gc)
            #    #Receive Bob current gc
            #    gc_rcv = client_socket.recv(8)
            #    int_gc_rcv = np.frombuffer(gc_rcv,dtype=np.int64)[0]
            #    gc_diff = np.abs(current_gc - int_gc_rcv)
            #    time_diff = gc_diff/40000000
            #    print('gc diff: ', gc_diff, 'time_diff', time_diff)
            #    if (time_diff < 0.5):
            #        cmd = 'sync'
            #        client_socket.sendall(cmd.encode())
            #        print('SYNC')
            #    else :
            #        cmd = 'no_sync'
            #        client_socket.sendall(cmd.encode())
            #        print('NOT SYNC')

            #elif command == 'ra':
            #    time.sleep(0.01)
            #    print("reading angles")
            #    num = 32000
            #    client_socket.sendall(num.to_bytes(4, byteorder='big'))
            #    angles = Angle(num, save=True)
            #
            #elif command == 'qber_a':
            #    main.Write_To_Fake_Rng(gen_seq.seq_rng_random())
            #    time.sleep(0.01)
            #    print("reading angles")
            #    num = 32000
            #    client_socket.sendall(num.to_bytes(4, byteorder='big'))
            #    while True:
            #        angles = Angle(num)
            #        rb = rcv_all(client_socket, num)
            #        r = np.frombuffer(rb, dtype=np.uint8)
            #        r0 = [
            #                r[angles==0]==0, 
            #                r[angles==1]==0, 
            #                r[angles==2]==0, 
            #                r[angles==3]==0]
            #        r1 = [
            #                r[angles==0]==1, 
            #                r[angles==1]==1, 
            #                r[angles==2]==1, 
            #                r[angles==3]==1]
            #        qber = r0/r1
            #        print(qber)

            
            
            #response_rcv = client_socket.recv(1024)
            #print("Response from server: ", response_rcv.decode(),"--------------------------------")

    except KeyboardInterrupt:
        print("Client stopped by keyboard interrupt.")
    finally:
        client_socket.close()
        print("Client has been shut down gracefully.")

if __name__ =="__main__":
    parser = argparse.ArgumentParser(description="Send command")
    #parser.add_argument("commands", nargs='+',  choices=['init_all', 'find_gates', 'find_delays', 'verify_gates'])
    parser.add_argument("commands", nargs='+', help="init_all find_gates find_delays verify_gates")
    args = parser.parse_args()
    commands_in = []

    for cmd in args.commands:
        if cmd not in commands_in:
            commands_in.append(cmd)

    if 'init_all' in args.commands:
        commands_in.append('init')
        commands_in.append('sync_gc')
        commands_in.append('find_max_vca')
        commands_in.append('find_am_bias')
        commands_in.append('verify_am_bias')
        commands_in.append('find_am_bias_2')
        commands_in.append('pol_bob')
        commands_in.append('find_max_vca')

    if 'find_gates' in args.commands:
        commands_in.append('ad')
        commands_in.append('find_sp')
        commands_in.append('ad')
        commands_in.append('verify_gates')
    if 'find_delays' in args.commands:
        commands_in.append('fs_b')
        commands_in.append('fs_a')
        commands_in.append('fd_b')
        commands_in.append('fd_b_long')
        commands_in.append('fd_a')
        commands_in.append('fd_a_long')
        commands_in.append('fz_b')
        commands_in.append('fz_a')


    if commands_in == []:
        commands_in = args.commands

    client_start(commands_in)









