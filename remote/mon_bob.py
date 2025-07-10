#!/bin/python

from termcolor import colored
import socket, threading
import json, struct
import datetime
from lib.fpga import update_tmp, save_tmp, get_tmp
import lib.gen_seq as gen_seq

import ctl_bob as ctl


qlinepath = '/home/vq-user/qline/'

networkfile = qlinepath+'config/network.json'
connection_logfile = qlinepath+'log/ip_connections_to_mon.log'
mon_logfile = qlinepath+'log/mon.log'


####### convenient send and receive commands ########

def recv_exact(socket, l):
    m = bytes(0)
    while len(m)<l:
        m += socket.recv(l - len(m))
    return m

# send command
def sendc(socket, command):
    b = command.encode()
    m = len(command).to_bytes(2, 'little')+b
    socket.sendall(m)

# receive command
def rcvc(socket):
    l = int.from_bytes(socket.recv(2), 'little')
    mr = recv_exact(socket, l)
    command = mr.decode().strip()
    return command

# send integer
def send_i(socket, value):
    m = struct.pack('i', value)
    socket.sendall(m)

# receive integer
def rcv_i(socket):
    m = recv_exact(socket, 4)
    value = struct.unpack('i', m)[0]
    return value

# receive long integer
def rcv_q(socket):
    m = recv_exact(socket, 8)
    value = struct.unpack('q', m)[0]
    return value

# send double
def send_d(socket, value):
    m = struct.pack('d', value)
    socket.sendall(m)

# receive double
def rcv_d(socket):
    m = recv_exact(socket, 8)
    value = struct.unpack('d', m)[0]
    return value

# send binary data
def send_data(socket, data):
    log.write(colored('sending data', 'blue')+'\n')
    l = len(data)
    print('sending', l)
    m = struct.pack('i', l) + data
    socket.sendall(m)

def rcv_data(socket):
    m = recv_exact(socket, 4)
    l = struct.unpack('i', m)[0]
    print('receiving', l)
    m = bytes(0)
    while len(m)<l:
        m += socket.recv(l - len(m))
    return m





def handle_client(conn, addr):
    print(f"[+] Connected: {addr}")
    with conn:
        while True:
            command = rcvc(conn)
            if not command:
                print(f"[-] Disconnected: {addr}")
                break
            elif command == 'get_counts':
                c = ctl.counts_fast()
                for i in range(3):
                    send_i(conn, c[i])
        






def main():

    # get ip from config/network.json
    with open(networkfile, 'r') as f:
        network = json.load(f)

    host = network['ip']['bob']
    port = int(network['port']['mon'])

    server_socket = socket.socket()
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((host, port))
    server_socket.listen()

    print(f"Server listening on {host}:{port}")
    
    while True:
        conn, addr = server_socket.accept()
        print(f"Connected by {addr}")
        with open(connection_logfile, 'a') as f:
            f.write(f"{datetime.datetime.now()}\t{addr}\n")
        
        # Spawn a new thread for each client connection
        thread = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
        thread.start()



if __name__ == "__main__":
    main()






