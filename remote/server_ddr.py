import socket
import time
import os  # For generating random data
import struct  # For packing data size
import subprocess, sys, argparse


def Write(base_add, value):
    str_base = str(base_add)
    str_value = str(value)
    command ="../dma_ip_drivers/XDMA/linux-kernel/tools/reg_rw /dev/xdma0_user "+ str_base + " w "+ str_value 
    #print(command)
    s = subprocess.check_call(command, shell = True)



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
            print("Received 'get_gc' command from client. Generating data...")

            #Start to write 
            Write(0x00001000, 0x00) 
            Write(0x00001000, 0x01) 
            #Command_enable -> Reset the fifo_gc_out
            Write(0x00001000+28,0x0)
            Write(0x00001000+28,0x1)

            #Command enable to save alpha
            Write(0x00001000+24,0x0)
            Write(0x00001000+24,0x1)
            # Generate random data
            # data_size = 100 * 1024 * 1024  # 100 MB of data
            # data = os.urandom(data_size)
            data_gc = b'' #declare bytes object
            device_c2h = '/dev/xdma0_c2h_0'
            device_h2c = '/dev/xdma0_h2c_0'
            # count = 16
    
            try:
                with open(device_c2h, 'rb') as f:
                    with open(device_h2c, 'wb') as fw:
                        while True:
                        # for i in range (4):
                            data_gc = f.read(16)
                            if not data_gc:
                                print("No available data on stream")
                                break
                            # print(f"Read {len(data_gc)} bytes: {data_gc.hex()}")
                            # First send the size of the data to the client
                            conn.sendall(struct.pack('!I', len(data_gc)))
                            conn.sendall(data_gc)

                            #Write back to h2c device of Bob
                            bytes_written = fw.write(data_gc)
                            fw.flush()
                            # print(f"{bytes_written} are written back to h2c device")
    
            except FileNotFoundError:
                print(f"Device not found")    
            except PermissionError:
                print(f"Permission to file is denied")
            except Exception as e:
                print(f"Error occurres: {e}")



            # # First send the size of the data to the client
            # conn.sendall(struct.pack('!I', len(data)))

            # # Send data back to the client and compute the rate
            # total_bytes_sent = 0
            # start_time = time.time()  # Start timing

            # # Send data in chunks
            # for i in range(0, len(data), BUFFER_SIZE):
            #     chunk = data[i:i + BUFFER_SIZE]
            #     try:
            #         conn.sendall(chunk)
            #         total_bytes_sent += len(chunk)
            #     except (BrokenPipeError, ConnectionResetError):
            #         print("Connection closed by client while sending data.")
            #         break

            # elapsed_time = time.time() - start_time  # End timing
            # rate = total_bytes_sent / elapsed_time  # Bytes per second
            # print(f"Data sent: {total_bytes_sent} bytes. Rate: {rate:.2f} bytes/sec")

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
