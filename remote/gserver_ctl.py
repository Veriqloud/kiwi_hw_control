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
from termcolor import colored



# Server configuration
HOST = '192.168.1.77'  # Localhost
PORT = 9999  # Port to listen on
# BUFFER_SIZE = 65536  # Increased buffer size for sending data
BUFFER_SIZE = 64  # Increased buffer size for sending data


# Create TCP socket
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, BUFFER_SIZE)
server_socket.bind((HOST, PORT))
server_socket.listen(1)


print(f"Server listening on {HOST}:{PORT}")
conn, addr = server_socket.accept()  # Accept incoming connection
print(f"Connected by {addr}")

def sendc(c):
    print(colored(c, 'cyan'))
    b = c.encode()
    m = len(c).to_bytes(1, 'little')+b
    conn.sendall(m)

def rcvc():
    l = int.from_bytes(conn.recv(1), 'little')
    mr = conn.recv(l)
    while len(mr)<l:
        mr += conn.recv(l-len(mr))
    command = mr.decode().strip()
    print(colored(command, 'cyan'))
    return command

try:
    while True:
        try:
            # Receive command from client
            command = rcvc()
        except ConnectionResetError:
            print("Client connection was reset. Exiting loop.")
            break

        response = ''
        if command == 'init':
            main.init_all()

            command = rcvc()
            sendc('ready')    
            command = rcvc()
            Sync_Gc()

            response = "init done"
            
        elif command == 'sync_gc':
            command = rcvc()
            Sync_Gc()
            
            response = "sync done"

        elif command == 'find_am_bias':
            for i in range(21):
                cmd = conn.recv(BUFFER_SIZE).decode().strip()
                if cmd == 'sv_done':
                    time.sleep(0.2)
                    current_count = main.Read_Count()
                    conn.sendall(current_count.to_bytes(4,byteorder='big'))
            response = "find_am_bias done"

        elif command == 'find_sp':
            t = get_tmp()
            t['t0'] = 10 #to have some space to the left
            t['soft_gate'] = 'off'
            save_tmp(t)
            main.Update_Softgate()

            # detection single pulse at shift_am 0
            global ret_shift_am
            print("measure and search single peak")
            shift_am, t0  = main.Measure_Sp(20000)
            Set_t0(10+t0)
            update_tmp('t0', 10+t0)
            
            # send back shift_am value to alice
            conn.sendall(shift_am.to_bytes(4,byteorder='big'))

            # detect single64 pulse and send to Alice
            update_tmp('soft_gate', 'on')
            main.Update_Softgate()
            print("measure sp64")
            coarse_shift = main.Measure_Sp64()
            conn.sendall(coarse_shift.to_bytes(4,byteorder='big'))
            response = "Gen_Sp 2 rounds done"

        elif command == 'verify_gates':
            update_tmp('soft_gate', 'off')
            main.Update_Softgate()
            aurea = Aurea()
            aurea.mode("gated")
            main.Download_Time(10000, 'verify_gate_off')
            conn.sendall("done".encode())
            main.Download_Time(10000, 'verify_gate_double')
            aurea.mode("continuous")
            aurea.close()
            update_tmp('spd_mode', 'continuous')
            response = "Verify gates done"



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
            response = "Find Shift Bob done"
       
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
                cmd = conn.recv(BUFFER_SIZE).decode().strip()
                if cmd == 'shift_done':
                    main.Download_Time(10000, 'pm_a_shift_'+str(s))
                    cmd = int(7)
                    conn.sendall(cmd.to_bytes(4,byteorder='big'))

            pm_shift = main.Find_Best_Shift('alice')
            conn.sendall(pm_shift.to_bytes(4,byteorder='big'))
            response = 'Find shift alice done'
       
        elif command == 'fd_b':
            main.Ensure_Spd_Mode('gated')
            fiber_delay = main.Find_Opt_Delay_B()
            response = 'Find delay bob done'
            update_tmp('fiber_delay_mod', fiber_delay)
            update_tmp('fiber_delay', fiber_delay-1)
        
        elif command == 'fd_b_long':
            main.Ensure_Spd_Mode('gated')
            fiber_delay = main.Find_Opt_Delay_B_long()
            response = 'Find delay bob done'
            update_tmp('fiber_delay_long', fiber_delay)
            update_tmp('fiber_delay', fiber_delay-1)
        
        elif command == 'fd_a':
            main.Ensure_Spd_Mode('gated')
            fiber_delay = main.Find_Opt_Delay_A()
            conn.sendall(fiber_delay.to_bytes(4,byteorder='big'))
            response = 'Find delay bob done'
        
        elif command == 'fd_a_long':
            main.Ensure_Spd_Mode('gated')
            m = conn.recv(4)
            fiber_delay_mod = int.from_bytes(m, byteorder='big')
            fiber_delay = main.Find_Opt_Delay_A_long(fiber_delay_mod)
            conn.sendall(fiber_delay.to_bytes(4,byteorder='big'))
            response = 'Find delay bob done'
        
        elif command == 'fz_a':
            main.Ensure_Spd_Mode('gated')
            print("received command fz_a")
            m = conn.recv(4)
            fiber_delay_mod = int.from_bytes(m, byteorder='big')
            zero_pos = main.Find_Zero_Pos_A(fiber_delay_mod)
            conn.sendall(zero_pos.to_bytes(4,byteorder='big'))
            response = 'Find zero position bob done'
        
        elif command == 'fz_b':
            main.Ensure_Spd_Mode('gated')
            zero_pos = main.Find_Zero_Pos_B()
            update_tmp('zero_pos', zero_pos)
            main.Update_Dac()
            response = 'Find zero position bob done'
        
        #elif command == 'czp':
        #    main.Ensure_Spd_Mode('gated')
        #    main.Check_Zeros_Pos()
        #    response = 'Find zero position bob done'
            
        elif command == 'ra':
            main.Ensure_Spd_Mode('gated')
            print("received command ra")
            m = conn.recv(4)
            num = int.from_bytes(m, byteorder='big')
            print(num)
            Angle(num)
            response = 'Angles download done'
            
        elif command == 'ver_sync':
            current_gc = main.Get_Current_Gc()
            print('Bob current_gc: ',current_gc)
            #send current gc to Alice
            conn.sendall(current_gc.tobytes())
            #receive sync result from Alice
            cmd = conn.recv(BUFFER_SIZE).decode().strip()
            if (cmd == 'sync'):
                print('SYNC')
            elif (cmd == 'no_sync'):
                print('NOT SYNC')
            response = 'Verify SYNC done'

            
        #elif command == 'fd_ab_mod':
        #    lines = np.loadtxt("data/var.txt",usecols=0)
        #    shift_pm_b = int(lines[2])
        #    ret_shift_am = int(lines[0])
        #    # time.sleep(1)
        #    # main.Find_Opt_Delay_AB_mod64('bob',shift_pm_b)
        #    # main.Find_Opt_Delay_AB_mod64('bob',(ret_shift_am+4)%10)
        #    cmd = conn.recv(BUFFER_SIZE).decode().strip()
        #    if cmd == 'fd_mod_done':
        #        ret_delay_mod = main.Find_Opt_Delay_AB_mod32('bob',8)
        #        #Send delay_mod to alice
        #        conn.sendall(ret_delay_mod.to_bytes(4,byteorder='big'))
        #        #Write ddelay_mod to var file
        #        lines = np.loadtxt("data/var.txt",dtype=str,encoding='utf-8')
        #        lines[3] = str(ret_delay_mod)
        #        np.savetxt("data/var.txt",lines,fmt="%s",encoding='utf-8')
        #    response = 'Find delay alice in modulo mode done'

        #elif command == 'fd_ab':
        #    lines = np.loadtxt("data/var.txt",usecols=0)
        #    delay_mod = int(lines[3])
        #    shift_pm_b = int(lines[2])
        #    ret_shift_am = int(lines[0])
        #    # time.sleep(4)
        #    # main.Find_Opt_Delay_AB('bob',shift_pm_b)
        #    # main.Find_Opt_Delay_AB('bob',(ret_shift_am+4)%10)
        #    cmd = conn.recv(BUFFER_SIZE).decode().strip()
        #    if cmd == 'fd_ab_done':
        #        time.sleep(2)
        #        main.Find_Opt_Delay_AB('bob',8,delay_mod)
        #    response = 'Find delay alice done'

        elif command == 'shutdown':
            response = "Shutdown done"
            print("Received 'shutdown' command from client. Closing connection...")
            break  # Exit loop to close server properly

        elif not command:
            print("Client disconnected.")
            break  # Exit loop if the client closes the connection

        conn.sendall(response.encode())

except KeyboardInterrupt:
    print("Server stopped by keyboard interrupt.")
finally:
    try:
        conn.shutdown(socket.SHUT_RDWR)  # Properly shutdown connection
    except OSError:
        pass  # Ignore if connection is already closed
    conn.close()
    server_socket.close()
    print("Server has been shut down gracefully.")



# def server_start():
#     # Create TCP socket
#     server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#     server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, BUFFER_SIZE)
#     server_socket.bind((HOST, PORT))
#     server_socket.listen(1)

#     print(f"Server listening on {HOST}:{PORT}")

#     while True:
#         conn, addr = server_socket.accept()  # Accept incoming connection
#         print(f"Connected by {addr}")

#         try:
#             while True:
#                 # Receive command from client
#                 command = conn.recv(BUFFER_SIZE).decode().strip()
#                 print("Received command {command} from client")
#                 if command == 'init':
#                     main.Config_Ltc()
#                     main.Sync_Ltc()
#                     main.Write_Sequence_Dacs('dp')
#                     main.Write_Sequence_Rng()
#                     main.Write_Dac1_Shift(2, 0, 0, 0, 0, 0)
#                     main.Config_Fda()
#                     main.Config_Sda()
#                     main.Config_Jic()
#                     main.Time_Calib_Reg(1, 0, 0, 0, 0, 0, 0)
#                     main.Time_Calib_Init()
#                     # main.Count_Mon()
#                     # while True:
#                     for i in range(41):
#                         cmd = conn.recv(BUFFER_SIZE).decode().strip()
#                         if cmd == 'sv_done':
#                             time.sleep(0.05)
#                             current_count = main.Read_Count()
#                             # print(current_count.to_bytes(4,byteorder='big'))
#                             conn.sendall(current_count.to_bytes(4,byteorder='big'))
#                     response = "Init done"

#                 elif command == 'exit':
#                     response = "Server connection closed by client"
#                     conn.sendall(response.encode())
#                     print("Received 'exit' command from client. Closing connection...")
#                     break

#                 elif not command:
#                     response = "No command"
#                     print("Client disconnected.")
#                 conn.sendall(response.encode())

#         except KeyboardInterrupt:
#             print("Server stopped by keyboard interrupt.")
#         finally:
#             try:
#                 conn.shutdown(socket.SHUT_RDWR)  # Properly shutdown connection
#             except OSError:
#                 pass  # Ignore if connection is already closed
#             conn.close()
#             server_socket.close()
#             print("Server has been shut down gracefully.")

# if __name__ =="__main__":
#     server_start()
