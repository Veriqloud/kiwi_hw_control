#!/bin/python

import socket
import time
import struct  # For unpacking data size
import subprocess, sys, argparse
import numpy as np
import gmain as main
from lib.config_lib import get_tmp, save_tmp, update_tmp


# Client configuration
SERVER_HOST = '192.168.1.77'  # Server's IP address
SERVER_PORT = 9999  # Server's port
# BUFFER_SIZE = 65536  # Increased buffer size for receiving data
BUFFER_SIZE = 64  # Increased buffer size for receiving data
# ROUNDS = 1  # Number of rounds to perform
# DELAY_BETWEEN_ROUNDS = 2  # Delay between rounds in seconds




def client_start(commands_in):
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BUFFER_SIZE)
    client_socket.connect((SERVER_HOST, SERVER_PORT))

    try:
        for command in commands_in:
            # command = 'init'
            print(f"Sending command '{command}' to server...")
            client_socket.sendall(command.encode())

            if command == 'init':
                main.init_all()

            if command == 'find_am_bias':
                count_rcv_arr = []
                for i in range(21):
                    main.Set_Am_Bias(-1 + 0.1*i)
                    cmd = 'sv_done'
                    client_socket.sendall(cmd.encode())
                    count_rcv = client_socket.recv(4)
                    int_count_rcv = int.from_bytes(count_rcv, byteorder='big')
                    count_rcv_arr.append(int_count_rcv)
                print("Min count: ", min(count_rcv_arr), "index: ", count_rcv_arr.index(min(count_rcv_arr)))
                am_bias_opt = -1 + 0.1*count_rcv_arr.index(min(count_rcv_arr))
                main.Set_Am_Bias(am_bias_opt)
                #Initialize var file: am_bias, shift_am, shift_pm
                #with open("data/var.txt","w") as var_file:
                #    var_file.write("0.8"+'\n') #am_bias
                #    var_file.write("1"+'\n')   #shift_am
                #    var_file.write("0"+'\n')   #shift_pm
                #    var_file.write("0"+'\n')   #delay_mod
                #var_file.close()
                ##Write am_bias voltage to the file
                #lines = np.loadtxt("data/var.txt",dtype=str,encoding='utf-8')
                #lines[0] = str(round(am_bias_opt,2))+'\n'
                #np.savetxt("data/var.txt",lines,fmt="%s",encoding='utf-8')

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
                print("updateding am_shift to", am_shift)
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
                for s in range(10):
                    t['pm_shift'] = s
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
                update_tmp('pm_shift', pm_shift)
                main.Update_Dac()


            elif command == 'fd_b':
                main.Write_Dac1_Shift(2,0,0,0,0,0)

            elif command == 'fd_ab_mod':
                lines = np.loadtxt("data/var.txt",usecols=0)
                shift_pm_a = int(lines[2])
                ret_shift_am = int(lines[1])
                # main.Find_Opt_Delay_AB_mod64('alice',shift_pm_a)
                # main.Find_Opt_Delay_AB_mod64('alice',(ret_shift_am+6)%10)
                main.Find_Opt_Delay_AB_mod32('alice',0)
                #tell bob setting phase on alice done
                cmd = 'fd_mod_done'
                client_socket.sendall(cmd.encode())
                #Receive delay_mod from Bob
                delay_mod_rcv = client_socket.recv(4)
                int_delay_mod_rcv = int.from_bytes(delay_mod_rcv,byteorder='big')
                print("Delay in modulo mod received from bob: ", int_delay_mod_rcv, "[q_bins]")
                #Write to var file
                lines = np.loadtxt("data/var.txt",dtype=str,encoding='utf-8')
                lines[3] = str(int_delay_mod_rcv)
                np.savetxt("data/var.txt",lines,fmt="%s",encoding='utf-8')

            elif command == 'fd_ab':
                lines = np.loadtxt("data/var.txt",usecols=0)
                delay_mod = int(lines[3])
                shift_pm_a = int(lines[2])
                ret_shift_am = int(lines[1])
                # main.Find_Opt_Delay_AB('alice',shift_pm_a)
                # main.Find_Opt_Delay_AB('alice',(ret_shift_am+6)%10)
                main.Find_Opt_Delay_AB('alice',0,delay_mod)
                cmd = 'fd_ab_done'
                client_socket.sendall(cmd.encode())

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
