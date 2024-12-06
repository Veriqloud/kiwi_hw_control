import socket
import time
import struct  # For unpacking data size
import subprocess, sys, argparse
import numpy as np
import main


# def Write(base_add, value):
#     str_base = str(base_add)
#     str_value = str(value)
#     command ="../../tools/reg_rw /dev/xdma0_user "+ str_base + " w "+ str_value 
#     #print(command)
#     s = subprocess.check_call(command, shell = True)

# Client configuration
SERVER_HOST = '192.168.1.77'  # Server's IP address
SERVER_PORT = 9999  # Server's port
# BUFFER_SIZE = 65536  # Increased buffer size for receiving data
BUFFER_SIZE = 64  # Increased buffer size for receiving data
# ROUNDS = 1  # Number of rounds to perform
# DELAY_BETWEEN_ROUNDS = 2  # Delay between rounds in seconds

# Create TCP socket
# client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BUFFER_SIZE)
# client_socket.connect((SERVER_HOST, SERVER_PORT))

# try:
#     command = 'init'
#     print(f"Sending command '{command}' to server...")
#     client_socket.sendall(command.encode())
#     #Wait for server response
#     # res = client_socket.recv(1024)
#     # print("Server response: ", res.decode()) 
#     if command == 'init':
#         main.Config_Ltc()
#         main.Sync_Ltc()
#         main.Write_Sequence_Dacs('off_am')
#         main.Write_Sequence_Rng()
#         main.Write_Dac1_Shift(2, 0, 0, 0, 0, 0)
#         main.Config_Fda()
#         main.Config_Sda()
#         main.Set_vol(7, 0)
#         # while True:\
#         count_rcv_arr = []
#         for i in range(41):
#             main.Set_vol(4, -2 + 0.1*i)
#             cmd = 'sv_done'
#             client_socket.sendall(cmd.encode())
#             count_rcv = client_socket.recv(4)
#             int_count_rcv = int.from_bytes(count_rcv, byteorder='big')
#             count_rcv_arr.append(int_count_rcv)
#         print("Min count: ", min(count_rcv_arr), "index: ", count_rcv_arr.index(min(count_rcv_arr)))
#         main.Set_vol(4, -2 + 0.1*count_rcv_arr.index(min(count_rcv_arr)))
#         # response_rcv = client_socket.recv(1024)
#         # print("Response from server: ", response_rcv.decode())
#     elif command == 'gen_dp':
#         main.Gen_Dp('alice')

#     response_rcv = client_socket.recv(1024)
#     print("Response from server: ", response_rcv.decode())

# except KeyboardInterrupt:
#     print("Client stopped by keyboard interrupt.")
# finally:
#     client_socket.close()
#     print("Client has been shut down gracefully.")




def client_start(commands_in):
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BUFFER_SIZE)
    client_socket.connect((SERVER_HOST, SERVER_PORT))

    try:
        for command in commands_in:
            # command = 'init'
            print(f"Sending command '{command}' to server...")
            client_socket.sendall(command.encode())
            #Wait for server response
            # res = client_socket.recv(1024)
            # print("Server response: ", res.decode()) 
            if command == 'init':
                main.Config_Ltc()
                main.Sync_Ltc()
                main.Write_Sequence_Dacs('off_am')
                main.Write_Sequence_Rng()
                main.Write_Dac1_Shift(2, 0, 0, 0, 0, 0)
                main.Config_Fda()
                main.Config_Sda()
                main.Set_vol(7, 0)
                # while True:\
                count_rcv_arr = []
                for i in range(21):
                    main.Set_vol(4,  0.1*i)
                    cmd = 'sv_done'
                    client_socket.sendall(cmd.encode())
                    count_rcv = client_socket.recv(4)
                    int_count_rcv = int.from_bytes(count_rcv, byteorder='big')
                    count_rcv_arr.append(int_count_rcv)
                print("Min count: ", min(count_rcv_arr), "index: ", count_rcv_arr.index(min(count_rcv_arr)))
                am_bias_opt = 0.1*count_rcv_arr.index(min(count_rcv_arr))
                main.Set_vol(4, am_bias_opt)
                #Initialize var file: am_bias, shift_am, shift_pm
                with open("data/var.txt","w") as var_file:
                    var_file.write("0.8"+'\n') #am_bias
                    var_file.write("0"+'\n')   #shift_am
                    var_file.write("0"+'\n')   #shift_pm
                var_file.close()
                #Write am_bias voltage to the file
                lines = np.loadtxt("data/var.txt",dtype=str,encoding='utf-8')
                lines[0] = str(round(am_bias_opt,2))+'\n'
                np.savetxt("data/var.txt",lines,fmt="%s",encoding='utf-8')

            elif command == 'sp':
                #1.Send single pulse, shift_am 0
                main.Gen_Sp('alice', 0)
                #2. Receive shift_am value from Bob
                global int_shift_am_rcv
                shift_am_rcv = client_socket.recv(4)
                int_shift_am_rcv = int.from_bytes(shift_am_rcv, byteorder='big')
                #Write shift_am to var.txt
                lines = np.loadtxt("data/var.txt",dtype=str,encoding='utf-8')
                lines[1] = str(int_shift_am_rcv)
                np.savetxt("data/var.txt",lines,fmt="%s",encoding='utf-8')
                #3. Apply new value of shift_am
                main.Gen_Sp('alice',int_shift_am_rcv)
                cmd = 'ss_done'
                client_socket.sendall(cmd.encode())

            elif command == 'fg':
                lines = np.loadtxt("data/var.txt",usecols=0)
                int_shift_am_rcv = int(lines[1])
                main.Gen_Dp('alice', int_shift_am_rcv, 0)

            elif command == 'fs_b':
                lines = np.loadtxt("data/var.txt",usecols=0)
                int_shift_am_rcv = int(lines[1])
                main.Verify_Shift_B('alice',int_shift_am_rcv)

            elif command == 'fs_a':
                lines = np.loadtxt("data/var.txt",usecols=0)
                int_shift_am_rcv = int(lines[1])
                for i in range(10):
                    main.Verify_Shift_A('alice',i,int_shift_am_rcv)
                    # main.Verify_Shift_A('alice',i,2)
                    #tell bob setting is done on alice
                    cmd = 'shift_done'
                    client_socket.sendall(cmd.encode())
                    #Receive detection done from Bob
                    cmd_rcv = client_socket.recv(4)
                    int_cmd_rcv = int.from_bytes(cmd_rcv,byteorder='big')
                    print(int_cmd_rcv) #should return 7
                #Receive shift_pm value from bob and write it to var file
                shift_pm_rcv = client_socket.recv(4)
                int_shift_pm_rcv = int.from_bytes(shift_pm_rcv,byteorder='big')
                print("Received shift_pm from bob: ", int_shift_pm_rcv)
                #Save best shift of Alice reveiced from Bob to var file
                lines = np.loadtxt("data/var.txt",dtype=str,encoding='utf-8')
                lines[2] = str(int_shift_pm_rcv)
                np.savetxt("data/var.txt",lines,fmt="%s",encoding='utf-8')

            elif command == 'fd_b':
                main.Write_Dac1_Shift(2,0,0,0,0,0)

            elif command == 'fd_a_mod':
                lines = np.loadtxt("data/var.txt",usecols=0)
                shift_pm_a = int(lines[2])
                ret_shift_am = int(lines[1])
                # main.Find_Opt_Delay_AB_mod64('alice',shift_pm_a)
                # main.Find_Opt_Delay_AB_mod64('alice',(ret_shift_am+6)%10)
                main.Find_Opt_Delay_AB_mod64('alice',0)

            elif command == 'fd_a':
                lines = np.loadtxt("data/var.txt",usecols=0)
                shift_pm_a = int(lines[2])
                ret_shift_am = int(lines[1])
                # main.Find_Opt_Delay_AB('alice',shift_pm_a)
                # main.Find_Opt_Delay_AB('alice',(ret_shift_am+6)%10)
                main.Find_Opt_Delay_AB('alice',0)

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