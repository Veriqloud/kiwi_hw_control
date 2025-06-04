#!/bin/python

import socket
import time
import os  # For generating random data
import struct  # For packing data size
import subprocess, sys, argparse
import numpy as np
from lib.Aurea import Aurea
import main_Bob as main
from lib.config_lib import get_tmp, save_tmp, update_tmp, Set_t0, update_default, get_default, Angle, Sync_Gc, wait_for_pps_ret
import lib.gen_seq as gen_seq
from termcolor import colored



# Server configuration
HOST = '192.168.1.77'  # Localhost
PORT = 9999  # Port to listen on
# BUFFER_SIZE = 65536  # Increased buffer size for sending data
BUFFER_SIZE = 64  # Increased buffer size for sending data


# Create TCP socket
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, BUFFER_SIZE)
server_socket.bind((HOST, PORT))
server_socket.listen()


print(f"Server listening on {HOST}:{PORT}")


while True:
    conn, addr = server_socket.accept()  # Accept incoming connection
    print(f"Connected by {addr}")

    def sendc(c):
#        print(colored(c, 'cyan'))
        b = c.encode()
        m = len(c).to_bytes(1, 'little')+b
        conn.sendall(m)

    def rcvc():
        l = int.from_bytes(conn.recv(1), 'little')
        mr = conn.recv(l)
        while len(mr)<l:
            mr += conn.recv(l-len(mr))
        command = mr.decode().strip()
#        print(colored(command, 'cyan'))
        return command
    
    def send_u32(value):
#        print(colored(value, 'green'))
        m = value.to_bytes(4, byteorder='little')
        conn.sendall(m)
    
    def rcv_u32():
        m = conn.recv(4)
        value = int.from_bytes(m, byteorder='little')
#        print(colored(value, 'green'))
        return value

    try:
        while True:
            try:
                # Receive command from client
                command = rcvc()
            except ConnectionResetError:
                print("Client connection was reset. Exiting loop.")
                break

            if command == 'init':
                main.init_all()
                rcvc()
                sendc('Alice and Bob init done')    
                print(colored('Alice and Bob init done \n', 'cyan'))
                print(colored('sync_gc \n', 'cyan'))
                rcvc()
                Sync_Gc()


            elif command == 'sync_gc':
                rcvc()
                Sync_Gc()
                print(colored('sync_gc', 'cyan'))
                
            elif command == 'find_max_vca':
                print(colored('find_max_vca', 'cyan'))
                main.Ensure_Spd_Mode('continuous')
                while rcvc() == 'get counts':
                    count = main.Read_Count()
                    send_u32(count)


            elif command == 'find_am_bias':
                print(colored('find_am_bias', 'cyan'))
                for i in range(11):
                    rcvc()
                    time.sleep(0.2)
                    count = main.Read_Count()
                    send_u32(count)

            elif command == 'find_am_bias_2':
                print(colored('find_am_bias_2', 'cyan'))
                for i in range(21):
                    rcvc()
                    time.sleep(0.2)
                    count = main.Read_Count()
                    send_u32(count)







            elif command == 'verify_am_bias':
                print(colored('verify_am_bias', 'cyan'))
                for i in range(2):
                    rcvc()
                    time.sleep(0.2)
                    count = main.Read_Count()
                    send_u32(count)



            elif command == 'pol_bob':
                    print(colored('pol_bob', 'cyan'))
                    main.Polarisation_Control()
                    sendc('ok')

            elif command == 'ad':
                print(colored('ad', 'cyan'))
                update_tmp('soft_gate', 'off')
                main.Update_Softgate()
                main.Ensure_Spd_Mode('gated')
                main.Download_Time(10000, 'verify_gate_ad_0')
                file_off = "~/qline/hw_control/data/tdc/verify_gate_ad_0.txt"

                max_iter = 2
                iter_count = 0

                while True:
                    lf = main.fall_edge(file_off, 200, 900)
               #     print("Last falling edge off between 200 and 900:", lf)

                    if abs(lf - 725) <= 2 or iter_count >= max_iter:
                        break

                    d = get_tmp()
                    tmp_delay0=d['gate_delay0']
                #    print("gate_delay0 =", tmp_delay0)
                    tmp_delay=d['gate_delay']
                 #   print("tmp_delay =", tmp_delay)
                    if lf > 725:
                        ad = tmp_delay - ((lf - 725) * 20)
                    else:
                        ad = tmp_delay + ((725 - lf) * 20)

                    ad = abs(ad)
                    ad = 5000 if ad > 12500 else ad

                    update_tmp('gate_delay', ad)
                    update_tmp('gate_delay0', ad)
                    main.Gen_Gate()
                    iter_count += 1
                    main.Download_Time(10000, 'verify_gate_ad_'+str(iter_count))
                    file_off = "~/qline/hw_control/data/tdc/verify_gate_ad_"+str(iter_count)+".txt"

                sendc('done')
                main.Ensure_Spd_Mode('continuous')
                sendc('ok')
                time.sleep(0.2)


            elif command == 'find_sp':
                print(colored('find_sp', 'cyan'))
                t = get_tmp()
                t['t0'] = 10 #to have some space to the left
                t['soft_gate'] = 'off'
                save_tmp(t)
                main.Update_Softgate()

                # detection single pulse at shift_am 0
                print("measure and search single peak")
                shift_am, t0  = main.Measure_Sp(20000)
                Set_t0(10+t0)
                update_tmp('t0', 10+t0)
                d = get_tmp()
                update_tmp('gate_delay', (d['gate_delay0']-t0*20) % 12500)
                main.Gen_Gate()
                
                # send back shift_am value to alice
                send_u32(shift_am)

                # detect single64 pulse and send to Alice
                update_tmp('soft_gate', 'on')
                main.Update_Softgate()
                print("measure sp64")
                coarse_shift = main.Measure_Sp64()
                send_u32(coarse_shift)



            elif command == 'verify_gates':
                print(colored('verify_gates', 'cyan'))
                update_tmp('soft_gate', 'off')
                main.Update_Softgate()
                main.Ensure_Spd_Mode('gated')
                main.Download_Time(10000, 'verify_gate_off')
                sendc("gates off done")
                time.sleep(0.1)
                main.Download_Time(10000, 'verify_gate_double')                
                t = get_tmp()
                gate0=t['soft_gate0']
                gate1=t['soft_gate1']
                width=t['soft_gatew']
                binstep = 2
                maxtime = gate1 + width
                input_file = os.path.join("data", "tdc", "verify_gate_double.txt")
                input_file2 = os.path.join("data", "tdc", "verify_gate_off.txt")
                status = main.verify_gate_double(input_file,input_file2, gate0, gate1, width, binstep, maxtime)
                sendc(status)


            elif command == 'fs_b':
                main.Ensure_Spd_Mode('gated')
                t = get_tmp()
                t['pm_mode'] = 'seq64'
                t['feedback'] = 'off'
                t['soft_gate'] = 'on'
                save_tmp(t)
                main.Update_Softgate()
                d = get_default()
                pm_shift_coarse = (d['pm_shift']//10) * 10
                for s in range(10):
                    t['pm_shift'] = pm_shift_coarse + s
                    save_tmp(t)
                    main.Update_Dac()
                    main.Download_Time(10000, 'pm_b_shift_'+str(s))
                pm_shift = main.Find_Best_Shift('bob')
                update_tmp('pm_shift', pm_shift_coarse + pm_shift)
                main.Update_Dac()
                sendc('ok')
           
            elif command == 'fs_a':
                main.Ensure_Spd_Mode('gated')
                t = get_tmp()
                t['pm_mode'] = 'off'
                t['feedback'] = 'off'
                t['soft_gate'] = 'on'
                save_tmp(t)
                main.Update_Softgate()
                main.Update_Dac()
                for s in range(10):
                    rcvc()
                    main.Download_Time(10000, 'pm_a_shift_'+str(s))
                    sendc("ok")
                pm_shift = main.Find_Best_Shift('alice')
                send_u32(pm_shift)



           
            elif command == 'fd_b':
                main.Ensure_Spd_Mode('gated')
                fiber_delay = main.Find_Opt_Delay_B()
                response = 'Find delay bob done'
                t = get_tmp()
                t['fiber_delay_mod'] = fiber_delay
                t['fiber_delay'] = fiber_delay % 80 + t['fiber_delay_long']
                save_tmp(t)
                sendc('ok')
            
            elif command == 'fd_b_long':
                main.Ensure_Spd_Mode('gated')
                fiber_delay = main.Find_Opt_Delay_B_long()
                response = 'Find delay bob done'
                t = get_tmp()
                t['fiber_delay_long'] = fiber_delay
                t['fiber_delay'] = t['fiber_delay_mod']%80 + fiber_delay*80
                save_tmp(t)
                sendc('ok')
            
            elif command == 'fd_a':
                main.Ensure_Spd_Mode('gated')
                fiber_delay = main.Find_Opt_Delay_A()
                send_u32(fiber_delay)
            
            elif command == 'fd_a_long':
                main.Ensure_Spd_Mode('gated')
                fiber_delay_mod = rcv_u32()
                fiber_delay = main.Find_Opt_Delay_A_long(fiber_delay_mod)
                send_u32(fiber_delay)
            
            elif command == 'fz_b':
                main.Ensure_Spd_Mode('gated')
                zero_pos = main.Find_Zero_Pos_B()
                update_tmp('zero_pos', zero_pos)
                main.Update_Dac()
                sendc('ok')
            
            elif command == 'fz_a':
                main.Ensure_Spd_Mode('gated')
                print("received command fz_a")
                fiber_delay_mod = rcv_u32()
                zero_pos = main.Find_Zero_Pos_A(fiber_delay_mod)
                update_tmp('insert_zeros', 'on')
                main.Update_Dac()
                send_u32(zero_pos)
            
            #elif command == 'czp':
            #    main.Ensure_Spd_Mode('gated')
            #    main.Check_Zeros_Pos()
            #    response = 'Find zero position bob done'
                
            #elif command == 'ra':
            #    main.Ensure_Spd_Mode('gated')
            #    print("received command ra")
            #    m = conn.recv(4)
            #    num = int.from_bytes(m, byteorder='big')
            #    print(num)
            #    angles = Angle(num, save=True)
            #
            #elif command == 'qber_a':
            #    main.Write_To_Fake_Rng(gen_seq.seq_rng_zeros())
            #    main.Ensure_Spd_Mode('gated')
            #    print("received command ra")
            #    m = conn.recv(4)
            #    num = int.from_bytes(m, byteorder='big')
            #    print(num)
            #    fr = open("result", "rb")
            #    while True:
            #        angles = Angle(num)
            #        rb = fr.read(num)
            #        conn.sendall(rb)

            #elif command == 'ver_sync':
            #    current_gc = main.Get_Current_Gc()
            #    print('Bob current_gc: ',current_gc)
            #    #send current gc to Alice
            #    conn.sendall(current_gc.tobytes())
            #    #receive sync result from Alice
            #    cmd = conn.recv(BUFFER_SIZE).decode().strip()
            #    if (cmd == 'sync'):
            #        print('SYNC')
            #    elif (cmd == 'no_sync'):
            #        print('NOT SYNC')

                
            #elif command == 'shutdown':
            #    response = "Shutdown done"
            #    print("Received 'shutdown' command from client. Closing connection...")
            #    break  # Exit loop to close server properly

            elif not command:
                print("Client disconnected.")
                break  # Exit loop if the client closes the connection


    except KeyboardInterrupt:
        print("Server stopped by keyboard interrupt.")
    finally:
        try:
            conn.shutdown(socket.SHUT_RDWR)  # Properly shutdown connection
        except OSError:
            pass  # Ignore if connection is already closed
        conn.close()
        #server_socket.close()
        #print("Server has been shut down gracefully.")



