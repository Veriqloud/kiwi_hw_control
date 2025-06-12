#!/bin/python

import socket, json, time, struct, sys, datetime
#import numpy as np
import ctl_alice as ctl
from lib.fpga import get_tmp, save_tmp, update_tmp, update_default, get_default, Sync_Gc, wait_for_pps_ret
import lib.gen_seq as gen_seq
from termcolor import colored


####### convenient send and receive commands ########

# send command
def sendc(socket, command):
    b = command.encode()
    m = len(command).to_bytes(1, 'little')+b
    socket.sendall(m)

# receive command
def rcvc(socket):
    l = int.from_bytes(socket.recv(1), 'little')
    mr = socket.recv(l)
    while len(mr)<l:
        mr += socket.recv(l-len(mr))
    command = mr.decode().strip()
    return command

# send integer
def send_i(socket, value):
    m = struct.pack('i', value)
    socket.sendall(m)

# receive integer
def rcv_i(socket):
    m = socket.recv(4)
    value = struct.unpack('i', m)[0]
    return value

# receive long integer
def rcv_q(socket):
    m = socket.recv(8)
    value = struct.unpack('q', m)[0]
    return value

# send double
def send_d(socket, value):
    m = struct.pack('d', value)
    socket.sendall(m)

# receive double
def rcv_d(socket):
    m = socket.recv(8)
    value = struct.unpack('d', m)[0]
    return value





######### config files ###############

#qlinepath = '/home/vq-user/qline_clean/'
qlinepath = '../'

networkfile = qlinepath+'config/network.json'
connection_logfile = qlinepath+'log/ip_connections_to_hardware_system.log'
hardware_logfile = qlinepath+'log/hardware_system.log'

with open(networkfile, 'r') as f:
    network = json.load(f)


########## network ###############

# connect to Bob
host = network['ip']['bob']
port = int(network['port']['hws'])
bob = socket.socket()
bob.connect((host, port))

# Create TCP socket for listening for commands from admin
host = network['ip']['alice']
port = int(network['port']['hws'])
server_socket = socket.socket()
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_socket.bind((host, port))
server_socket.listen()

print(f"Server listening on {host}:{port}")


####### config functions ###########

def init():
    sendc(bob, 'init')
    ctl.init_all()
    sendc(bob, 'Alice init done')
    rcvc(bob)
            
def sync_gc():
    sendc(bob, 'sync_gc')
    wait_for_pps_ret()
    sendc(bob, 'go')
    Sync_Gc()

def find_vca(limit=3000):
    sendc(bob, 'find_vca')
    update_tmp('am_mode', 'double')
    main.Update_Dac()
    d = get_default()
    vca = d['vca']
    count = 0
    while  (count < limit) and (vca <= 4.8) :
        vca = round(vca + 0.2, 2)
        main.Set_Vca(round(vca, 2))
        time.sleep(0.1)
        sendc(bob, 'get counts')
        count = rcv_i(bob)

    if count >= limit:
       print(colored(f"Success, {vca}V / {count} cts \n", "green"))
    else:
       print(colored(f"Fail, {vca}V / {count} cts \n", "red"))
    update_tmp('vca_calib', vca)
    update_default('vca', vca-1)
    sendc(bob, 'done')


def find_am_bias(range_val=0.5):
    update_tmp('am_mode', 'off')
    main.Update_Dac()
    t = get_tmp()
    d = get_default()
    bias_default = d['am_bias']
    bias_default_1 = t['am_bias_2']
    t['am_mode'] = 'off'
    save_tmp(t)
    main.Update_Dac()
    counts = []
    main.Set_Am_Bias_2(0) 
    time.sleep(0.1)
    num_points = int(2 * range_val / 0.1) + 1
    prev_count = None
    increase_count = 0
    for i in range(num_points):
        main.Set_Am_Bias(bias_default - range_val + 0.1*i)
        sendc(bob, 'get counts')
        count = rcv_i(bob)
        counts.append(count)

        if prev_count is not None:
            if count > prev_count:
                increase_count += 1
            else:
                increase_count = 0
        if increase_count >= 3:
            break
        prev_count = count

    min_counts = min(counts)
    min_idx = counts.index(min_counts)
    print("Min count: ", min_counts , "index: ", min_idx,"\n")
    am_bias_opt = bias_default - range_val + 0.1*min_idx
    main.Set_Am_Bias(am_bias_opt)
    main.Set_Am_Bias_2(bias_default_1)
    sendc(bob, 'done')



def verify_am_bias():
    update_tmp('am_mode', 'off')
    ctl.Update_Dac()
    sendc(bob, 'get counts')
    count_off = rcv_u32()

    update_tmp('am_mode', 'double')
    ctl.Update_Dac()
    time.sleep(0.2)

    sendc(bob, 'get counts')
    count_double = rcv_i(bob)

    ratio = count_double / count_off
    if ratio >= 2:
       print(colored(f"Success: double/off  = {ratio:.2f} ({count_double}/{count_off}) \n", "green"))
       result = True
    else:
       print(colored(f"Fail: double/off = {ratio:.2f} ({count_double}/{count_off}) \n", "yellow"))
       result = False
    update_tmp('am_mode', 'off')
    ctl.Update_Dac()
    return result


def find_am2_bias():
    update_tmp('am_mode', 'double')
    main.Update_Dac()
    #t = get_tmp()
    d = get_default()
    bias_default = d['am_bias_2']
    #bias_default_1 = t['am_bias'] 
    #t['am_mode'] = 'off'
    #save_tmp(t)
    ctl.Update_Dac()
    counts = []
    #main.Set_Am_Bias(0) 
    time.sleep(0.2)
    for i in range(21):
        value = bias_default - 3 + 0.1 * i
        if value < 0:
           value = 0
        main.Set_Am_Bias_2(value)
       # main.Set_Am_Bias_2(bias_default -3 + 0.1*i)
        sendc('get counts')
        counts.append(rcv_u32())
    min_counts = min(counts)
    min_idx = counts.index(min_counts)
    print("Min count: ", min_counts , "index: ", min_idx)
    am_bias_opt = bias_default -3 + 0.1*min_idx
    ctl.Set_Am_Bias_2(max(0, round(am_bias_opt + 2, 2))) 
    #main.Set_Am_Bias(bias_default_1)

def pol_bob():
    rcvc(bob)

def ad():
    update_tmp('am_mode', 'off')
    ctl.Update_Dac()
    rcvc(bob)
    update_tmp('am_mode', 'double')
    ctl.Update_Dac()
    rcvc(bob)

def find_sp():
    #1.Send single pulse, am_shift 0
    update_tmp('am_shift', 0)
    update_tmp('am_mode', 'single')
    ctl.Update_Dac()
    #2. Receive am_shift value from Bob
    am_shift = rcv_i(bob)
    update_tmp('am_shift', am_shift)
    update_tmp('am_mode', 'single64')
    ctl.Update_Dac()
    coarse_shift = rcv_i(bob)

    am_shift = (am_shift + coarse_shift) % 640
    print("updating am_shift to", am_shift)
    update_tmp('am_shift', am_shift)
    ctl.Update_Dac()


def verify_gates():
    print(colored('verify_gates', 'cyan'))
    update_tmp('am_mode', 'off')
    ctl.Update_Dac()
    rcvc(bob)
    update_tmp('am_mode', 'double')
    ctl.Update_Dac()
    status = rcvc(bob)
    if status == "success":
        print(colored("Success: good gates found \n", "green"))
        result = True
    else:
        result = False
    return result


def fs_b():
    t = get_tmp()
    t['am_mode'] = 'double'
    t['pm_mode'] = 'off'
    save_tmp(t)
    ctl.Update_Dac()
    pm_shift = rcv_i(bob)
    if pm_shift != 1000:
            print(colored("Success: Shift_Bob found\n", "green"))
    else:
            print(colored("Fail: pm_shift_Bob is None\n", "red"))


def fs_a():
    t = get_tmp()
    t['am_mode'] = 'double'
    t['pm_mode'] = 'seq64'
    save_tmp(t)
    d = get_default()
    pm_shift_coarse = (d['pm_shift']//10) * 10
    for s in range(10):
        t['pm_shift'] = pm_shift_coarse + s
        save_tmp(t)
        ctl.Update_Dac()
        time.sleep(0.1)
        sendc(bob, 'download data')
        rcvc(bob)
    pm_shift = rcv_i(bob)
    if pm_shift != 1000:
        update_tmp('pm_shift', pm_shift_coarse + pm_shift)
        ctl.Update_Dac()
        print(colored("Success: Shift_Alice found\n", "green"))
    else:
        print(colored("Fail: pm_shift_Alice is None\n", "red"))


def fd_b():
    update_tmp('am_mode', 'double')
    update_tmp('pm_mode', 'fake_rng')
    update_tmp('insert_zeros', 'off')
    ctl.Write_To_Fake_Rng(gen_seq.seq_rng_zeros())
    ctl.Update_Dac()
    rcvc(bob)

def fd_b_long():
    update_tmp('am_mode', 'double')
    update_tmp('pm_mode', 'fake_rng')
    update_tmp('insert_zeros', 'off')
    ctl.Write_To_Fake_Rng(gen_seq.seq_rng_zeros())
    ctl.Update_Dac()
    rcvc(bob)

def fd_a():
    ctl.Write_To_Fake_Rng(gen_seq.seq_rng_single())
    update_tmp('pm_mode', 'fake_rng')
    update_tmp('am_mode', 'double')
    update_tmp('insert_zeros', 'off')
    ctl.Update_Dac()
    fiber_delay = rcv_i(bob)
    t = get_tmp()
    t['fiber_delay_mod'] = fiber_delay
    t['fiber_delay'] = (fiber_delay-1)%80 + t['fiber_delay_long']
    save_tmp(t)

def fd_a_long():
    t = get_tmp()
    t['pm_mode'] = 'fake_rng'
    t['am_mode'] = 'double'
    t['insert_zeros'] = 'off'
    save_tmp(t)
    ctl.Write_To_Fake_Rng(gen_seq.seq_rng_block1())
    ctl.Update_Dac()
    send_i(t['fiber_delay_mod'])
    fiber_delay_long = rcv_i()
    t = get_tmp()
    t['fiber_delay_long'] = fiber_delay_long
    t['fiber_delay'] = t['fiber_delay_mod'] + fiber_delay_long*80 
    t['decoy_delay'] = t['fiber_delay'] 
    save_tmp(t)


def fz_b():
    update_tmp('am_mode', 'double')
    update_tmp('pm_mode', 'fake_rng')
    update_tmp('insert_zeros', 'off')
    ctl.Write_To_Fake_Rng(gen_seq.seq_rng_zeros())
    ctl.Update_Dac()
    rcvc(bob)

def fz_a():
    t = get_tmp()
    t['pm_mode'] = 'fake_rng'
    t['insert_zeros'] = 'on'
    t['zero_pos'] = 0
    save_tmp(t)
    ctl.Write_To_Fake_Rng(gen_seq.seq_rng_all_one())
    ctl.Update_Dac()
    send_i(t['fiber_delay_mod'])
    zero_pos = rcv_i(bob)
    update_tmp('zero_pos', zero_pos)
    ctl.Update_Dac()


# for convencience
functionmap = {}
functionmap['init'] = init
functionmap['sync_gc'] = sync_gc
functionmap['find_vca'] = find_vca
functionmap['find_am_bias'] = find_am_bias
functionmap['verify_am_bias'] = verify_am_bias
functionmap['find_am2_bias'] = find_am2_bias
functionmap['verify_gates'] = verify_gates
functionmap['fs_b'] = fs_b
functionmap['fs_a'] = fs_a
functionmap['fd_b'] = fd_b
functionmap['fd_b_long'] = fd_b_long
functionmap['fd_a'] = fd_a
functionmap['fd_a_long'] = fd_a_long
functionmap['fz_a'] = fz_a
functionmap['fz_b'] = fz_b


while True:
    conn, addr = server_socket.accept()  # Accept incoming connection from admin
    print(f"Connected by {addr}")
    with open(connection_logfile, 'a') as f:
        f.write(f"{datetime.datetime.now()}\t{addr}\n")

    log = open(hardware_logfile, 'a')
    log.write(f"\n{datetime.datetime.now()}\t{addr}\n")

    try:
        while True:
            try:
                # Receive command from client
                command = rcvc(conn)
            except ConnectionResetError:
                print("Client connection was reset. Exiting loop.")
                break
            
            if command=='':
                break

            functionmap[command]()


    except KeyboardInterrupt:
        print("Server stopped by keyboard interrupt.")
    finally:
        try:
            conn.shutdown(socket.SHUT_RDWR)  # Properly shutdown connection
        except OSError:
            pass  # Ignore if connection is already closed
        conn.close()
        log.close()


#if __name__ == "__main__":
#    parser = argparse.ArgumentParser(description="Send command")
#    parser.add_argument("commands", nargs='+', help="Commands: init_all, find_gates, find_delays, verify_gates")
#    args = parser.parse_args()
#
#    global tmp_result
#    tmp_result = False
#
#    if 'init_all' in args.commands:
#        client_start(['init', 'sync_gc', 'find_max_vca_3000'], True)
#        for voltage in [0.3, 0.5, 1, 2]:
#            tmp_result = False
#            client_start([
#                f'find_am_bias_{voltage}',
#                'verify_am_bias'
#            ], False)
#
#            if tmp_result:
#                client_start(['find_am2_bias','pol_bob', 'find_max_vca_4000'], False)
#                break
#
#        if tmp_result == False:
#            print(colored('ERROR: AM bias calibration failed', 'red'))
#            sys.exit(1)
#
#    cmd_mapping = {
#        'find_gates': ['ad', 'find_sp', 'ad', 'verify_gates'],
#        'find_delays': [
#            'find_max_vca_4200', 'fs_b', 'fs_a',
#            'fd_b', 'fd_b_long', 'fd_a', 'fd_a_long',
#            'fz_b', 'fz_a'
#        ]
#    }
#
#    if 'find_gates' in args.commands:
#        max_global_attempts = 2
#        for global_attempt in range(max_global_attempts):
#            client_start(['ad', 'find_sp', 'ad'])
#
#            max_retries = 1
#            for attempt in range(max_retries):
#                tmp_result = False
#                client_start(['verify_gates'])
#                if tmp_result:
#                    break
#                print(colored(f"verify_gates failed retrying...", "yellow"))
#
#            if tmp_result:
#                break
#
#            print(colored(f"verify_gates failed after {max_retries} retries, restarting find_gate sequence...", "red"))
#
#        if not tmp_result:
#            print(colored("ERROR: verify_gates failed after all retries", "red"))
#            sys.exit(1)
#
#    if 'find_delays' in args.commands:
#        client_start(cmd_mapping['find_delays'])
#
#    known_groups = {'init_all', *cmd_mapping.keys()}
#    individual_cmds = [cmd for cmd in args.commands if cmd not in known_groups]
#
#    if individual_cmds:
#        client_start(individual_cmds)
