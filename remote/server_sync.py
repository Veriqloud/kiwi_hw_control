import socket
import time
import numpy as np
import os  # For generating random data
import struct  # For packing data size
import subprocess, sys, argparse
import main

def Write(base_add, value):
    str_base = str(base_add)
    str_value = str(value)
    command ="../dma_ip_drivers/XDMA/linux-kernel/tools/reg_rw /dev/xdma0_user "+ str_base + " w "+ str_value 
    #print(command)
    s = subprocess.check_call(command, shell = True)

def Read(base_add):
    str_base = str(base_add)
    # command ="../../tools/reg_rw /dev/xdma0_user "+ str_base + " w "+ "| grep  \"Read.*:\" | sed 's/Read.*: 0x\([a-z0-9]*\)/\\1/'" 
    command ="../dma_ip_drivers/XDMA/linux-kernel/tools/reg_rw /dev/xdma0_user "+ str_base + " w "+ "| grep  \"Read.*:\" | sed 's/Read.*: 0x\([a-z0-9]*\)/\\1/'" 
    #print(command)
    s = subprocess.check_output(command, shell = True)
    return s


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

        if command == 'get_gc':
            # print("Received 'get_gc' command from client. Generating data...")

            #Start to write 
            Write(0x00001000, 0x00) 
            Write(0x00001000, 0x01) 
            time.sleep(1)
            current_gc = main.Get_Current_Gc()
            print('Bob current_gc: ',current_gc)

            #Command_enable -> Reset the fifo_gc_out
            Write(0x00001000+28,0x0)
            Write(0x00001000+28,0x1)

            #Command enable to save alpha
            Write(0x00001000+24,0x0)
            Write(0x00001000+24,0x1)
            # Generate random data
            # data_size = 100 * 1024 * 1024  # 100 MB of data
            # data = os.urandom(data_size)
            # data_gc = b'' #declare bytes object
            # device_c2h = '/dev/xdma0_c2h_0'
            # device_h2c = '/dev/xdma0_h2c_0'
            # # count = 16
    
            # try:
            #     with open(device_c2h, 'rb') as f:
            #         with open(device_h2c, 'wb') as fw:
            #             # while True:
            #             for i in range(64):
            #                 data_gc = f.read(16)
            #                 print(data_gc,flush=True)
            #                 if not data_gc:
            #                     print("No available data on stream")
            #                     break
            #                 conn.sendall(data_gc)    
            #                 #Write back to h2c device of Bob
            #                 bytes_written = fw.write(data_gc)
            #                 fw.flush()

            # except FileNotFoundError:
            #     print(f"Device not found")    
            # except PermissionError:
            #     print(f"Permission to file is denied")
            # except Exception as e:
            #     print(f"Error occurres: {e}")




        elif command == 'shutdown':
            print("Received 'shutdown' command from client. Closing connection...")
            break  # Exit loop to close server properly

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
    server_socket.close()
    print("Server has been shut down gracefully.")
