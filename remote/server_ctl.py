import socket
import time
import os  # For generating random data
import struct  # For packing data size
import subprocess, sys, argparse
import numpy as np
import main


# def Write(base_add, value):
#     str_base = str(base_add)
#     str_value = str(value)
#     command ="../../tools/reg_rw /dev/xdma0_user "+ str_base + " w "+ str_value 
#     #print(command)
#     s = subprocess.check_call(command, shell = True)



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

try:
    while True:
        try:
            # Receive command from client
            command = conn.recv(BUFFER_SIZE).decode().strip()
        except ConnectionResetError:
            print("Client connection was reset. Exiting loop.")
            break

        response = ''
        if command == 'init':
            main.Config_Ltc()
            main.Sync_Ltc()
            main.Write_Sequence_Dacs('dp')
            main.Write_Sequence_Rng()
            main.Write_Dac1_Shift(2, 0, 0, 0, 0, 0)
            main.Config_Fda()
            main.Config_Sda()
            main.Config_Jic()
            subprocess.run("cd /home/vq-user/Aurea_API/OEM_API_Linux/Examples/Python && python Aurea.py --mode continuous && python Aurea.py --dt 100 ", shell = True)
            main.Time_Calib_Reg(1, 0, 0, 0, 0, 0, 0)
            main.Time_Calib_Init()

            # main.Count_Mon()
            # while True:
            for i in range(21):
                cmd = conn.recv(BUFFER_SIZE).decode().strip()
                if cmd == 'sv_done':
                    time.sleep(0.5)
                    current_count = main.Read_Count()
                    # print(current_count.to_bytes(4,byteorder='big'))
                    conn.sendall(current_count.to_bytes(4,byteorder='big'))
            #Initialize var file: shift_am, peak, shift_pm
            with open("data/var.txt","w") as var_file:
                var_file.write("0"+'\n')     #shift_am
                var_file.write("550"+'\n')   #first peak
                var_file.write("0"+'\n')     #shift_pm
                var_file.write("0"+'\n')     #delay_mod
            var_file.close()
            #Response end of command
            response = "Init done"

        elif command == 'sp':
            time.sleep(2)
            #1.detection single pulse at shift_am 0
            global ret_shift_am
            ret_first_peak, ret_shift_am = main.Gen_Sp('bob',0)
            #Write shift_am value to var.txt
            lines = np.loadtxt("data/var.txt",dtype=str,encoding='utf-8')
            lines[0] = str(ret_shift_am)+'\n'
            np.savetxt("data/var.txt",lines,fmt="%s",encoding='utf-8')
            #2. send back shift_am value to alice
            conn.sendall(ret_shift_am.to_bytes(4,byteorder='big'))
            #3. detection single pulse at new shift_am
            cmd = conn.recv(BUFFER_SIZE).decode().strip()
            if cmd == 'ss_done':
                time.sleep(2)
                global ret_fp2, ret_sa2
                ret_fp2, ret_sa2 = main.Gen_Sp('bob',ret_shift_am)
                #Write new first peak to var.txt
                lines = np.loadtxt("data/var.txt",dtype=str,encoding='utf-8')
                lines[1] = str(ret_fp2)+'\n'
                np.savetxt("data/var.txt",lines,fmt="%s",encoding='utf-8')
            #4. Response end of the command
            response = "Gen_Sp 2 rounds done"

        elif command == 'fg':
            lines = np.loadtxt("data/var.txt",usecols=0)
            ret_shift_am = int(lines[0])
            ret_fp2 = int(lines[1])
            main.Gen_Dp('bob',ret_shift_am, ret_fp2)
            response = "Gen_Dp done"
       
        elif command == 'fs_b':
            lines = np.loadtxt("data/var.txt",usecols=0)
            ret_shift_am = int(lines[0])
            main.Verify_Shift_B('bob',ret_shift_am)
            ret_shift_pm_b = main.Find_Best_Shift('bob')
            #Write best shift on Bob to var file
            lines = np.loadtxt("data/var.txt",dtype=str,encoding='utf-8')
            lines[2] = str(ret_shift_pm_b)
            np.savetxt("data/var.txt",lines,fmt="%s",encoding='utf-8')
            response = "Find Shift Bob done"
       
        elif command == 'fs_a':
            lines = np.loadtxt("data/var.txt",usecols=0)
            ret_shift_am = int(lines[0])
            for i in range(10):
                cmd = conn.recv(BUFFER_SIZE).decode().strip()
                if cmd == 'shift_done':
                    time.sleep(1)
                    main.Verify_Shift_A('bob',i,ret_shift_am)
                    #Send command 7 to tell detection for 1 round is done
                    cmd = int(7)
                    conn.sendall(cmd.to_bytes(4,byteorder='big'))
            ret_shift_pm_a = main.Find_Best_Shift('alice')
            #Send back shift_pm value to alice
            conn.sendall(ret_shift_pm_a.to_bytes(4,byteorder='big'))
            #Response end of command
            response = 'Find shift alice done'
       
        elif command == 'fd_b':
            # main.Find_Opt_Delay_B(ret_shift_am + 4)
            lines = np.loadtxt("data/var.txt",usecols=0)
            best_shift_b = int(lines[2])
            ret_shift_am = int(lines[0])
            print(best_shift_b)
            # main.Find_Opt_Delay_B(best_shift_b)
            # main.Find_Opt_Delay_B((ret_shift_am+4)%10)
            main.Find_Opt_Delay_B(8)
            response = 'Find delay bob done'
            
        elif command == 'fd_ab_mod':
            lines = np.loadtxt("data/var.txt",usecols=0)
            shift_pm_b = int(lines[2])
            ret_shift_am = int(lines[0])
            # time.sleep(1)
            # main.Find_Opt_Delay_AB_mod64('bob',shift_pm_b)
            # main.Find_Opt_Delay_AB_mod64('bob',(ret_shift_am+4)%10)
            cmd = conn.recv(BUFFER_SIZE).decode().strip()
            if cmd == 'fd_mod_done':
                ret_delay_mod = main.Find_Opt_Delay_AB_mod32('bob',8)
                #Send delay_mod to alice
                conn.sendall(ret_delay_mod.to_bytes(4,byteorder='big'))
                #Write ddelay_mod to var file
                lines = np.loadtxt("data/var.txt",dtype=str,encoding='utf-8')
                lines[3] = str(ret_delay_mod)
                np.savetxt("data/var.txt",lines,fmt="%s",encoding='utf-8')
            response = 'Find delay alice in modulo mode done'

        elif command == 'fd_ab':
            lines = np.loadtxt("data/var.txt",usecols=0)
            delay_mod = int(lines[3])
            shift_pm_b = int(lines[2])
            ret_shift_am = int(lines[0])
            # time.sleep(4)
            # main.Find_Opt_Delay_AB('bob',shift_pm_b)
            # main.Find_Opt_Delay_AB('bob',(ret_shift_am+4)%10)
            cmd = conn.recv(BUFFER_SIZE).decode().strip()
            if cmd == 'fd_ab_done':
                main.Find_Opt_Delay_AB('bob',8,delay_mod)
            response = 'Find delay alice done'

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