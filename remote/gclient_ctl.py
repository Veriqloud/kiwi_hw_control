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
        print(colored(c, 'cyan'))
        b = c.encode()
        m = len(c).to_bytes(1, 'little')+b
        client_socket.sendall(m)

    def rcvc():
        l = int.from_bytes(client_socket.recv(1), 'little')
        mr = client_socket.recv(l)
        while len(mr)<l:
            mr += client_socket.recv(l-len(mr))
        command = mr.decode().strip()
        print(colored(command, 'cyan'))
        return command

    try:
        for command in commands_in:
            # command = 'init'
            sendc(command)

            if command == 'init':
                main.init_all()

                sendc('ready')
                rcvc()

                wait_for_pps_ret()
                sendc('sync_gc_go')

                Sync_Gc()

            if command == 'sync_gc':
                wait_for_pps_ret()
                sendc('go')
                Sync_Gc()

            if command == 'find_am_bias':
                t = get_tmp()
                bias_default = t['am_bias']
                t['am_mode'] = 'off'
                save_tmp(t)
                main.Update_Dac()
                count_rcv_arr = []
                for i in range(21):
                    main.Set_Am_Bias(-1 + 0.1*i)
                    cmd = 'sv_done'
                    client_socket.sendall(cmd.encode())
                    count_rcv = client_socket.recv(4)
                    int_count_rcv = int.from_bytes(count_rcv, byteorder='big')
                    count_rcv_arr.append(int_count_rcv)
                min_counts = min(count_rcv_arr)
                min_idx = count_rcv_arr.index(min_counts)
                print("Min count: ", min_counts , "index: ", min_idx)
                am_bias_opt = -1 + 0.1*min_idx
                main.Set_Am_Bias(am_bias_opt)
                update_tmp('am_bias', round(am_bias_opt, 2))
                update_default('am_bias', round(am_bias_opt, 2))

            elif command == 'find_sp':
                #1.Send single pulse, am_shift 0
                update_tmp('am_shift', 0)
                update_tmp('am_mode', 'single')
                main.Update_Dac()
                #2. Receive am_shift value from Bob
                global int_shift_am_rcv
                shift_am_rcv = client_socket.recv(4)
                am_shift = int.from_bytes(shift_am_rcv, byteorder='big')
                update_tmp('am_shift', am_shift)
                update_tmp('am_mode', 'single64')
                main.Update_Dac()
                rcv_message = client_socket.recv(4)
                coarse_shift = int.from_bytes(rcv_message, byteorder='big')

                am_shift = (am_shift + coarse_shift) % 640
                print("updating am_shift to", am_shift)
                update_tmp('am_shift', am_shift)
                main.Update_Dac()


            elif command == 'verify_gates':
                update_tmp('am_mode', 'off')
                main.Update_Dac()
                print(client_socket.recv(4))
                update_tmp('am_mode', 'double')
                main.Update_Dac()



            elif command == 'fs_b':
                t = get_tmp()
                t['am_mode'] = 'double'
                t['pm_mode'] = 'off'
                save_tmp(t)
                main.Update_Dac()

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
                    cmd = 'shift_done'
                    client_socket.sendall(cmd.encode())
                    cmd_rcv = client_socket.recv(4)
                    int_cmd_rcv = int.from_bytes(cmd_rcv,byteorder='big')
                    print(int_cmd_rcv) #should return 7
                pm_shift_rcv = client_socket.recv(4)
                pm_shift = int.from_bytes(pm_shift_rcv, byteorder='big')
                print("Received shift_pm from bob: ", pm_shift)
                update_tmp('pm_shift', pm_shift_coarse + pm_shift)
                main.Update_Dac()


            elif command == 'fd_b':
                update_tmp('am_mode', 'double')
                update_tmp('pm_mode', 'fake_rng')
                update_tmp('insert_zeros', 'off')
                main.Write_To_Fake_Rng(gen_seq.seq_rng_zeros())
                main.Update_Dac()
            
            elif command == 'fd_b_long':
                update_tmp('am_mode', 'double')
                update_tmp('pm_mode', 'fake_rng')
                update_tmp('insert_zeros', 'off')
                main.Write_To_Fake_Rng(gen_seq.seq_rng_zeros())
                main.Update_Dac()
            
            elif command == 'fd_a':
                main.Write_To_Fake_Rng(gen_seq.seq_rng_single())
                update_tmp('pm_mode', 'fake_rng')
                update_tmp('am_mode', 'double')
                update_tmp('insert_zeros', 'off')
                main.Update_Dac()
                m = client_socket.recv(4)
                fiber_delay = int.from_bytes(m, byteorder='big')
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
                client_socket.sendall(t['fiber_delay_mod'].to_bytes(4,byteorder='big'))
                m = client_socket.recv(4)
                fiber_delay_long = int.from_bytes(m, byteorder='big')
                t = get_tmp()
                t['fiber_delay_long'] = fiber_delay_long
                t['fiber_delay'] = t['fiber_delay_mod'] + fiber_delay_long*80 
                save_tmp(t)
            
            
            elif command == 'fz_b':
                update_tmp('am_mode', 'double')
                update_tmp('pm_mode', 'fake_rng')
                update_tmp('insert_zeros', 'off')
                main.Write_To_Fake_Rng(gen_seq.seq_rng_zeros())
                main.Update_Dac()
            
            elif command == 'fz_a':
                t = get_tmp()
                t['pm_mode'] = 'fake_rng'
                t['insert_zeros'] = 'on'
                t['zero_pos'] = 0
                save_tmp(t)
                main.Write_To_Fake_Rng(gen_seq.seq_rng_all_one())
                main.Update_Dac()
                client_socket.sendall(t['fiber_delay_mod'].to_bytes(4,byteorder='big'))
                m = client_socket.recv(4)
                zero_pos = int.from_bytes(m, byteorder='big')
                update_tmp('zero_pos', zero_pos)
                main.Update_Dac()
        
            #elif command == 'czp':
            #    update_tmp('pm_mode', 'off')
            #    update_tmp('am_mode', 'double')
            #    main.Update_Dac()


            elif command == 'ver_sync':
                current_gc = main.Get_Current_Gc()
                print('Alice current_gc: ', current_gc)
                #Receive Bob current gc
                gc_rcv = client_socket.recv(8)
                int_gc_rcv = np.frombuffer(gc_rcv,dtype=np.int64)[0]
                gc_diff = np.abs(current_gc - int_gc_rcv)
                time_diff = gc_diff/40000000
                print('gc diff: ', gc_diff, 'time_diff', time_diff)
                if (time_diff < 0.5):
                    cmd = 'sync'
                    client_socket.sendall(cmd.encode())
                    print('SYNC')
                else :
                    cmd = 'no_sync'
                    client_socket.sendall(cmd.encode())
                    print('NOT SYNC')

            elif command == 'ra':
                time.sleep(0.01)
                print("reading angles")
                num = 32000
                client_socket.sendall(num.to_bytes(4, byteorder='big'))
                angles = Angle(num, save=True)
            
            elif command == 'qber_a':
                main.Write_To_Fake_Rng(gen_seq.seq_rng_random())
                time.sleep(0.01)
                print("reading angles")
                num = 32000
                client_socket.sendall(num.to_bytes(4, byteorder='big'))
                while True:
                    angles = Angle(num)
                    rb = rcv_all(client_socket, num)
                    r = np.frombuffer(rb, dtype=np.uint8)
                    r0 = [
                            r[angles==0]==0, 
                            r[angles==1]==0, 
                            r[angles==2]==0, 
                            r[angles==3]==0]
                    r1 = [
                            r[angles==0]==1, 
                            r[angles==1]==1, 
                            r[angles==2]==1, 
                            r[angles==3]==1]
                    qber = r0/r1
                    print(qber)

            
            
            response_rcv = client_socket.recv(1024)
            print("Response from server: ", response_rcv.decode(),"--------------------------------")

    except KeyboardInterrupt:
        print("Client stopped by keyboard interrupt.")
    finally:
        client_socket.close()
        print("Client has been shut down gracefully.")

if __name__ =="__main__":
    parser = argparse.ArgumentParser(description="Send command")
    parser.add_argument("commands_in", nargs="+",type=str, help="init, exit")
    args = parser.parse_args()
    client_start(args.commands_in)
