#!/bin/python

import socket, time, numpy as np
import main_Bob as main
from termcolor import colored
from lib.config_lib import sync


# Server configuration
HOST = '192.168.1.77'  # Localhost
#HOST = 'localhost'  # Localhost
PORT = 9999  # Port to listen on
# BUFFER_SIZE = 65536  # Increased buffer size for sending data
BUFFER_SIZE = 512  # Increased buffer size for sending data

# Create TCP socket
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, BUFFER_SIZE)
server_socket.bind((HOST, PORT))
server_socket.listen(1)

print(f"Server listening on {HOST}:{PORT}")

conn, addr = server_socket.accept()  # Accept incoming connection
print(f"Connected by {addr}")


# receive command
def rcvc():
    command = conn.recv(BUFFER_SIZE).decode().strip()
    print(colored(command, 'cyan'))
    return command

def process_data(data):
    # in chunks of 64 gcs
    gca = []
    ra = []
    for i in range(64):
        data_cut = data[i*16:(i+1)*16]
        gc = int.from_bytes(data_cut[:6], 'little') # at 40MHz
        gc = gc*2- (not (data_cut[6] & 1))  # odd/even bit
        r = int((data_cut[6]>>1) & 1)       # click result
        gca.append(gc) 
        ra.append(r)
    return gca, ra

def gca_to_bytes(gca):
    gcab = bytes()
    for gc in gca:
        gcab += gc.to_bytes(8, byteorder='big')
    return gcab

try:
    while True:
        try:
            command = rcvc()
        except ConnectionResetError:
            print("Client connection was reset. Exiting loop.")
            break
            
        if command == 'init_ddr':
            main.init_ddr()
        
        elif command == 'sync':
            sync()

        elif command == 'transfer_gc':
            device_c2h = '/dev/xdma0_c2h_0'
            device_h2c = '/dev/xdma0_h2c_0'
            try:
                with open(device_c2h, 'rb') as f:
                    with open(device_h2c, 'wb') as fw:
                        t0 = time.time()
                        for i in range(10000):
                            data = f.read(16*64)
                            if not data:
                                print("No available data on stream")
                                break
                            gca, ra = process_data(data)
                            if (i%1000 == 0):
                                print(gca[0], gca[0]/80e6)
                                #time.sleep(0.1)
                            conn.sendall(gca_to_bytes(gca))    
                            ##Write back to h2c device of Bob
                            #bytes_written = fw.write(data_gc)
                            #fw.flush()
                        print("total time", time.time() - t0)

        
            except FileNotFoundError:
                print(f"Device not found")    
            except PermissionError:
                print(f"Permission to file is denied")
            except Exception as e:
                print(f"Error occurres: {e}")








        elif command == 'exit':
            print("Received 'exit' command from client. Closing connection...")
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
