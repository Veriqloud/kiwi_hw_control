import socket
import time
import struct  # For unpacking data size
import subprocess, sys, argparse


def Write(base_add, value):
    str_base = str(base_add)
    str_value = str(value)
    command ="../dma_ip_drivers/XDMA/linux-kernel/tools/reg_rw /dev/xdma0_user "+ str_base + " w "+ str_value 
    #print(command)
    s = subprocess.check_call(command, shell = True)

# Client configuration
SERVER_HOST = '192.168.1.77'  # Server's IP address
SERVER_PORT = 9999  # Server's port
# BUFFER_SIZE = 65536  # Increased buffer size for receiving data
BUFFER_SIZE = 64  # Increased buffer size for receiving data
ROUNDS = 1  # Number of rounds to perform
DELAY_BETWEEN_ROUNDS = 2  # Delay between rounds in seconds

# Create TCP socket
client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BUFFER_SIZE)
client_socket.connect((SERVER_HOST, SERVER_PORT))

# try:
#     for round_num in range(1, ROUNDS + 1):
#         # Send 'get_gc' command to server
#         command = 'get_gc'
#         print(f"Round {round_num}: Sending command '{command}' to server...")
#         client_socket.sendall(command.encode())

#         # First, receive the size of the incoming data
#         raw_data_size = client_socket.recv(64)
#         if not raw_data_size:
#             print("Failed to receive data size. Exiting.")
#             break
#         data_size = struct.unpack('!I', raw_data_size)[0]  # Unpack the size

#         # Receive data from server and compute the rate
#         total_bytes_received = 0
#         start_time = time.time()  # Start timing when data reception begins

#         while total_bytes_received < data_size:
#             # Receive data in chunks
#             data = client_socket.recv(min(BUFFER_SIZE, data_size - total_bytes_received))
#             if not data:
#                 break  # No more data from server
#             print(f"Received {len(data)} bytes: {data.hex()}")
#             total_bytes_received += len(data)

#         elapsed_time = time.time() - start_time  # Stop timing after receiving all data
#         rate = total_bytes_received / elapsed_time  # Bytes per second
#         print(f"Round {round_num}: Data received: {total_bytes_received} bytes. Rate: {rate:.2f} bytes/sec")

#         # Wait for a short period before the next round
#         time.sleep(DELAY_BETWEEN_ROUNDS)

#     # Send 'shutdown' command to server after all rounds are done
#     print("Sending 'shutdown' command to server to close the connection.")
#     client_socket.sendall('shutdown'.encode())
#     client_socket.shutdown(socket.SHUT_RDWR)  # Properly shutdown the connection

try:
    command = 'get_gc'
    print(f"Sending command '{command}' to server...")
    client_socket.sendall(command.encode())

    time.sleep(0.1)
        #Start to write 
    Write(0x00001000, 0x00) 
    Write(0x00001000, 0x01) 
    #Command_enable -> Reset the fifo_gc_out
    Write(0x00001000+28,0x0)
    Write(0x00001000+28,0x1)
    
    #Command enable to save alpha
    Write(0x00001000+24,0x0)
    Write(0x00001000+24,0x1)

    #Write data to xdma
    device_h2c = '/dev/xdma0_h2c_0'
    try:
        with open(device_h2c,'wb') as f:    

        # First, receive the size of the incoming data
            while True:
            # for i in range (4):
                raw_data_size = client_socket.recv(4)
                if not raw_data_size:
                    print("Failed to receive data size. Exiting.")
                    # break
                data_size = struct.unpack('!I', raw_data_size)[0]  # Unpack the size

                total_bytes_received = 0
                while total_bytes_received < data_size:
                    # Receive data in chunks
                    data_gc = client_socket.recv(data_size - total_bytes_received)
                    if not data_gc:
                        break  # No more data from server
                    # print(f"Received {len(data_gc)} bytes: {data_gc.hex()}")
                    total_bytes_received += len(data_gc)

                bytes_written = f.write(data_gc)
                f.flush()
                # print(f"{bytes_written} are written back to h2c device")

    except FileNotFoundError:
        print(f"Device not found")    
    except PermissionError:
        print(f"Permission to file is denied")
    except Exception as e:
        print(f"Error occurres: {e}")



except KeyboardInterrupt:
    print("Client stopped by keyboard interrupt.")
finally:
    client_socket.close()
    print("Client has been shut down gracefully.")
