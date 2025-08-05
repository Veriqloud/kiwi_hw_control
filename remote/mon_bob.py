#!/bin/python

from termcolor import colored
import socket, threading
import json, struct
import datetime
from lib.fpga import update_tmp, save_tmp, get_tmp
import lib.gen_seq as gen_seq
from lib.fpga import get_arrival_time, ddr_status2, get_gc, get_ltc_info, get_sda_info, get_fda_info
import numpy as np, pickle
import subprocess

import ctl_bob as ctl

HW_CONTROL = '/home/vq-user/hw_control/'

qlinepath = '/home/vq-user/'

networkfile = qlinepath+'config/network.json'
connection_logfile = qlinepath+'log/ip_connections_to_mon.log'
mon_logfile = qlinepath+'log/mon.log'
rng_errorfile = qlinepath+'rng_fpga/errorflag'


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
    #mon_logfile.write(colored('sending data', 'blue')+'\n')
    l = len(data)
    m = struct.pack('i', l) + data
    socket.sendall(m)






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
            
            elif command == 'get_gates':
                #ctl.Download_Time(10000, 'get_gates')
                #input_file = HW_CONTROL+'data/tdc/get_gates.txt'
                #data = np.loadtxt(input_file, usecols=1) % 625
                data = get_arrival_time('/dev/xdma0_c2h_2', 10000)
                bins = np.arange(0, 625, 2)
                h1, _ = np.histogram(data, bins=bins)
                serialized = pickle.dumps(h1)
                send_data(conn, serialized)
        

            elif command == 'get_rng_status':
                with open(rng_errorfile, 'rb') as f:
                    status = f.read()
                status = int.from_bytes(status, byteorder='little')
                send_i(conn, int(status))
            
            elif command == 'get_spd_temp':
                temp = ctl.get_spd_temp()
                send_d(conn, temp)

            elif command == 'get_pci_status':
                ret = subprocess.check_output("lspci | grep Xilinx", shell=True)
                if "Xilinx" in str(ret):
                    sendc(conn, 'ok')
                else:
                    sendc(conn, 'missing')
            
            elif command == 'get_fifo_status':
                status = ddr_status2()
                for i in range(4):
                    send_i(conn, status[i])

            elif command == 'get_gc':
                gc = get_gc()
                send_d(conn, gc)
            
            elif command == 'get_ltc_info':
                r = get_ltc_info()
                send_i(conn, r)
            
            elif command == 'get_sda_info':
                r = get_sda_info()
                send_i(conn, r)

            elif command == 'get_fda_info':
                r = get_fda_info()
                send_i(conn, r)
            
            elif command == 'get_server_status':
                status = []
                status.append(subprocess.run("systemctl is-active hw.service", shell=True).returncode)
                status.append(subprocess.run("systemctl is-active hws.service", shell=True).returncode)
                status.append(subprocess.run("systemctl is-active gc.service", shell=True).returncode)
                status.append(subprocess.run("systemctl is-active rng.service", shell=True).returncode)
                for i in range(4):
                    send_i(conn, status[i])

            elif command == 'get_wrs_ip_status':
                r = subprocess.run("ip ad | grep 192.168.10", shell=True).returncode
                send_i(conn, r)



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






