#!/bin/python

import socket, time, numpy as np
import main_Bob as main
from termcolor import colored
from lib.config_lib import sync, Ddr_Data_Init, Ddr_Data_Reg, get_tmp


# Server configuration
HOST = '192.168.1.77'  # Localhost
#HOST = 'localhost'  # Localhost
PORT = 9998  # Port to listen on
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
    data_filtered = bytes()
    for i in range(64):
        data_cut = data[i*16:i*16 + 7]
        gc = int.from_bytes(data_cut[:6], 'little') # at 40MHz
        #gc = gc*2- (not (data_cut[6] & 1))  # odd/even bit
        gc = gc*2+ (not (data_cut[6] & 1))  # odd/even bit
        r = int((data_cut[6]>>1) & 1)       # click result
        data_filtered += data_cut[:6] + (data_cut[6] & 0b01).to_bytes(2, byteorder='little') # remove result bit and make it 8 bytes
        gca.append(gc) 
        ra.append(r)
    return data_filtered, gca, ra

def pad(data_filtered):
    # pad with zeros to get back to 16 bytes per gc
    data_padded = bytes()
    for i in range(64):
        data_padded += data_filtered[i*8: (i+1)*8] + bytes(8)
    return data_padded



def gca_to_bytes(gca, for_fpga=False):
    gcab = bytes()
    size = 16 if for_fpga else 8
    for gc in gca:
        gcab += gc.to_bytes(size, byteorder='little')
    return gcab

try:
    while True:
        try:
            command = rcvc()
        except ConnectionResetError:
            print("Client connection was reset. Exiting loop.")
            break
            
        if command == 'init_ddr':
            t = get_tmp()
            Ddr_Data_Reg(4, 0, 2000, t['fiber_delay'])
            Ddr_Data_Reg(3, 0, 2000, t['fiber_delay'])
            Ddr_Data_Init()
        
        elif command == 'sync':
            sync()
        
        elif command == 'transfer_gc':
            all_gc = []
            all_r = []

            f_gc = open('/dev/xdma0_c2h_0', 'rb')
            f_gcw = open('/dev/xdma0_h2c_0', 'wb')
            #f_angle = open('/dev/xdma0_c2h_3', 'rb')
            for i in range(1000):
                data = f_gc.read(16*64)
                if not data:
                    print("No available data on stream")
                    break
                data_filtered, gca, ra = process_data(data)
                conn.sendall(data_filtered)    
                if (i%100 == 0):
                    print(gca[0], gca[0]/80e6)
                bytes_written = f_gcw.write(pad(data_filtered))
                f_gcw.flush()
                all_gc.extend(gca)
                all_r.extend(ra)
            f_gc.close()
            f_gcw.close()
            #f_angle.close()

            # save to file for testing
            gcr = np.zeros((len(all_gc), 2), dtype=int)
            gcr[:,0] = np.array(all_gc, dtype=int)
            gcr[:,1] = np.array(all_r, dtype=int)
            np.savetxt("data/ddr4/gcr.txt", gcr, fmt="%d")


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
