#!/bin/python

from termcolor import colored
import socket, threading
import json, struct
import datetime
from lib.fpga import update_tmp, save_tmp, get_tmp
import lib.gen_seq as gen_seq
from lib.fpga import get_arrival_time, ddr_status2, get_gc, get_ltc_info, get_sda_info, get_fda_info, rng_fifos_mon_v2
import numpy as np, pickle
import subprocess
from pathlib import Path

import ctl_alice as ctl

HW_CONTROL = '/home/vq-user/hw_control/'

qlinepath = '/home/vq-user/'

networkfile = qlinepath+'config/network.json'
connection_logfile = '/tmp/log/ip_connections_to_mon.log'
mon_logfile = '/tmp/log/mon.log'
rng_errorfile = '/tmp/rng_errorflag'


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

            elif command == 'get_link':
                with open('/tmp/errorflag.txt', 'r') as f:
                    s = f.read()
                    if s == 'error':
                        sendc(conn, s)
                        continue
                with open('/tmp/calibrating.txt', 'r') as f:
                    s = f.read()
                    if s == 'calibrating':
                        sendc(conn, s)
                        continue
                sendc(conn, "probably online")

            elif command == 'get_link':
                with open('/tmp/errorflag.txt', 'r') as f:
                    s = f.read()


            elif command == 'set_error':
                with open('/tmp/errorflag.txt', 'w') as f:
                    f.write('error')
            
            elif command == 'clear_error':
                with open('/tmp/errorflag.txt', 'w') as f:
                    f.write('clear')

            elif command == 'get_rng_status':
                try:
                    with open(rng_errorfile, 'rb') as f:
                        status = f.read()
                    status = int.from_bytes(status, byteorder='little')
                except FileNotFoundError:
                    # rng2fpga writes this file every time it starts, and /tmp is
                    # cleared at boot, so its absence means the rng service has not
                    # run since this machine came up -- nothing is feeding the fpga.
                    # That is an error state rather than an unknown one, so report a
                    # non-zero status; 256 is outside the range of the one-byte flag
                    # rng2fpga writes, so it cannot be mistaken for one of its codes.
                    status = 256
                send_i(conn, int(status))
            
            elif command == 'get_pci_status':
                # An enumerated endpoint is not the same as a usable one: Ubuntu
                # ships an in-tree module also called xdma that binds nothing and
                # leaves no device node, so check for the node as well.
                # check_output would also raise here whenever grep matched
                # nothing, which took mon down instead of reporting 'missing'.
                pci = subprocess.run("lspci -d 10ee: | grep -qi xilinx",
                                     shell=True).returncode == 0
                node = Path('/dev/xdma0_user').exists()
                if pci and node:
                    sendc(conn, 'ok')
                elif not pci:
                    sendc(conn, 'no xilinx pci device')
                else:
                    sendc(conn, 'no /dev/xdma0_user (driver not bound)')
            
            elif command == 'get_fifo_status':
                status_ddr = ddr_status2()
                status_rng = rng_fifos_mon_v2()
                for i in range(4):
                    send_i(conn, status_ddr[i])
                send_i(conn, status_rng[1])
                send_i(conn, status_rng[5])
            
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
                status.append(subprocess.run("systemctl is-active hw.service", shell=True, capture_output=True).returncode)
                status.append(subprocess.run("systemctl is-active hws.service", shell=True, capture_output=True).returncode)
                status.append(subprocess.run("systemctl is-active gc.service", shell=True, capture_output=True).returncode)
                status.append(subprocess.run("systemctl is-active rng.service", shell=True, capture_output=True).returncode)
                for i in range(4):
                    send_i(conn, status[i])
            
            elif command == 'get_wrs_ip_status':
                # 0 == good, matching the returncode convention the client reads.
                # The address alone does not say the link is up -- an interface
                # keeps its configured address with the cable out -- so require
                # the carrier too.
                try:
                    with open('/sys/class/net/eth_wrs/carrier') as f:
                        carrier = f.read().strip() == '1'
                except OSError:
                    carrier = False
                has_ip = subprocess.run("ip -4 ad show eth_wrs | grep -q 192.168.10",
                                        shell=True).returncode == 0
                send_i(conn, 0 if (carrier and has_ip) else 1)

            elif command == 'get_qkd_ready':
                # The node idles until this exists; hws' `start` step raises it
                # and /tmp clears at boot, so it also says whether the pair has
                # been calibrated since the last power cycle.
                sendc(conn, 'up' if Path('/tmp/qkd_ready').exists() else 'absent')

            elif command == 'get_node_stats':
                try:
                    with open("/tmp/node_stats.csv", "r") as f:
                        for line in f:
                            pass
                        data = line.split(";")
                        key_length = int(data[0])
                        qber = float(data[1])
                        #print(key_length, qber)
                        send_i(conn, key_length)
                        send_d(conn, qber)
                except:
                    send_i(conn, 0)
                    send_d(conn, 0)





def main():
    
    # make sure /tmp/log/ existists
    Path("/tmp/log").mkdir(exist_ok=True)

    # get ip from config/network.json
    with open(networkfile, 'r') as f:
        network = json.load(f)

    host = network['ip']['alice']
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






