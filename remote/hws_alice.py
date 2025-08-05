#!/bin/python

import socket, json, time, struct, sys, datetime
#import numpy as np
import ctl_alice as ctl
from lib.fpga import get_tmp, save_tmp, update_tmp, update_default, get_default, Sync_Gc, wait_for_pps_ret, get_gc
import lib.gen_seq as gen_seq
from termcolor import colored
import numpy as np

####### convenient send and receive commands ########

def recv_exact(socket, l):
    m = bytes(0)
    while len(m)<l:
        m += socket.recv(l - len(m))
    return m
    

# send command
def sendc(socket, command):
    print(colored(command, 'blue', force_color=True))
    b = command.encode()
    m = len(command).to_bytes(1, 'little')+b
    socket.sendall(m)

# receive command
def rcvc(socket):
    l = int.from_bytes(socket.recv(1), 'little')
    mr = recv_exact(socket, l)
    command = mr.decode().strip()
    print(colored(command, 'cyan', force_color=True))
    return command

# send integer
def send_i(socket, value):
    print(colored(value, 'blue', force_color=True))
    m = struct.pack('i', value)
    socket.sendall(m)

# receive integer
def rcv_i(socket):
    m = recv_exact(socket, 4)
    value = struct.unpack('i', m)[0]
    print(colored(value, 'cyan', force_color=True))
    return value

# receive long integer
def rcv_q(socket):
    m = recv_exact(socket, 8)
    value = struct.unpack('q', m)[0]
    print(colored(value, 'cyan', force_color=True))
    return value

# send double
def send_d(socket, value):
    print(colored(value, 'blue', force_color=True))
    m = struct.pack('d', value)
    socket.sendall(m)

# receive double
def rcv_d(socket):
    m = recv_exact(socket, 8)
    value = struct.unpack('d', m)[0]
    print(colored(value, 'cyan', force_color=True))
    return value

# send binary data
def send_data(socket, data):
    print(colored('sending data', 'blue', force_color=True))
    l = len(data)
    m = struct.pack('i', l) + data
    socket.sendall(m)

def rcv_data(socket):
    m = recv_exact(socket, 4)
    l = struct.unpack('i', m)[0]
    m = bytes(0)
    while len(m)<l:
        m += socket.recv(l - len(m))
    print(colored('received data', 'blue', force_color=True))
    return m







######### config files ###############

#qlinepath = '/home/vq-user/qline/'
qlinepath = '../'

networkfile = qlinepath+'config/network.json'
connection_logfile = qlinepath+'log/ip_connections_to_hardware_system.log'

with open(networkfile, 'r') as f:
    network = json.load(f)


########## network ###############

# connect to Bob
host = network['ip']['bob_wrs']
port = int(network['port']['hws'])
bob = socket.socket()

try_connect = True
print('trying to connect to Bob...')
while try_connect:
    try:
        bob.connect((host, port))
        try_connect = False
    except ConnectionRefusedError:
        time.sleep(1)
        continue
    except:
        exit('could not connect to Bob')


# Create TCP socket for listening for commands from admin
host = network['ip']['alice']
port = int(network['port']['hws'])
server_socket = socket.socket()
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_socket.bind((host, port))
server_socket.listen()

print(f"Server listening on {host}:{port}")



####### config functions ###########

def init(conn):
    sendc(bob, 'init')
    ctl.init_all()
    sendc(bob, 'Alice init done')
    rcvc(bob)
    sendc(conn, 'init done')
            
def sync_gc(conn):
    sendc(bob, 'sync_gc')
    wait_for_pps_ret()
    sendc(bob, 'go')
    Sync_Gc()
    sendc(conn, 'sync_gc done')

def compare_gc(conn):
    sendc(bob, 'compare_gc')
    gc = get_gc()
    gc_bob = rcv_d(bob)
    diff = gc - gc_bob
    difftime = diff/80e6
    sendc(conn, f'gc difference: {diff} ({difftime} s)')


def qdistance(conn):
    sendc(bob, 'qdistance')
    best_q = 0.0
    max_count = 0
    prev_q = 0
    prev_count = 0
    high_th = 300
    low_th = 150

    for qd in np.arange(0.0, 1.01, 0.1):
        update_tmp('qdistance', qd)
        ctl.Update_Dac()
        time.sleep(0.2)
        sendc(bob, 'get counts')
        diff_count = rcv_i(bob)
        print(f"qdistance={qd:.2f} -> counts={diff_count}")
        if diff_count > max_count:
            max_count = diff_count
            best_q = qd
        if (prev_count > high_th or max_count > high_th) and diff_count < low_th:
            break
        prev_q = qd
        prev_count = diff_count

    refined_q = best_q
    max_count = 0
    start = max(0.0, best_q - 0.075)
    end = min(1.0, best_q + 0.075)

    for qd in np.arange(start, end, 0.025):
        update_tmp('qdistance', qd)
        ctl.Update_Dac()
        time.sleep(0.2)
        sendc(bob, 'get counts')
        diff_count = rcv_i(bob)
        print(f"[refined] qdistance={qd:.3f} -> counts={diff_count}")
        if diff_count > max_count:
            max_count = diff_count
            refined_q = qd

    update_tmp('qdistance', refined_q)
    update_default('qdistance', refined_q)
    ctl.Update_Dac()
    msg = colored(f"{refined_q:.3f} / {max_count} counts", "green")
    print(msg)
    sendc(bob, 'done')
    sendc(conn, 'qdistance done')




def vca_per(conn, per=70):
    sendc(bob, 'vca_per')
    update_tmp('am_mode', 'double')
    ctl.Update_Dac()
    d = get_default()
    vca = d['vca']
    bias_1 = d['am_bias']
    bias_2 = d['am_bias_2']
    if per==70 :
       ctl.Set_Am_Bias(bias_1 + 0.3)
       ctl.Set_Am_Bias_2(bias_2 + 0.3)
    count = 0
    ctl.Set_Vca(5)
    time.sleep(0.2)
    sendc(bob, 'get counts')
    max_count=rcv_i(bob)
    limit=max_count*(per/100)
    while  (count < limit) and (vca <= 4.8) :
        vca = round(vca + 0.2, 2)
        ctl.Set_Vca(round(vca, 2))
        time.sleep(0.2)
        sendc(bob, 'get counts')
        count = rcv_i(bob)
        print(count)

    if count >= limit:
        m = colored(f"success, {vca}V / {count} cts \n", "green")
        print(m)

    else:
        m = colored(f"fail, {vca}V / {count} cts \n", "red")
        print(m)
    update_tmp('vca_calib', vca)
    update_default('vca', max(vca-1, 0))
    ctl.Set_Am_Bias(bias_1)
    ctl.Set_Am_Bias_2(bias_2)
    sendc(bob, 'done')
    sendc(conn, 'vca_per '+m)




def find_vca(conn, limit=3000):
    sendc(bob, 'find_vca')
    update_tmp('am_mode', 'double')
    ctl.Update_Dac()
    d = get_default()
    vca = d['vca']
    bias_1 = d['am_bias']
    bias_2 = d['am_bias_2']
    if limit==3000 :
       ctl.Set_Am_Bias(bias_1 + 0.3)
       ctl.Set_Am_Bias_2(bias_2 + 0.3)
    count = 0
    while  (count < limit) and (vca <= 4.8) :
        vca = round(vca + 0.2, 2)
        ctl.Set_Vca(round(vca, 2))
        time.sleep(0.2)
        sendc(bob, 'get counts')
        count = rcv_i(bob)
        print(count)

    if count >= limit:
        m = colored(f"success, {vca}V / {count} cts \n", "green", force_color=True)
        print(m)

    else:
        m = colored(f"fail, {vca}V / {count} cts \n", "red", force_color=True)
        print(m)
    update_tmp('vca_calib', vca)
    update_default('vca', max(vca-1, 0))
    ctl.Set_Am_Bias(bias_1)
    ctl.Set_Am_Bias_2(bias_2)
    sendc(bob, 'done')
    sendc(conn, 'find_vca '+m)


def find_am_bias(conn, range_val=0.5, sendresult=True):
    sendc(bob, 'find_am_bias')
    update_tmp('am_mode', 'off')
    ctl.Update_Dac()
    t = get_tmp()
    d = get_default()
    bias_default = d['am_bias']
    bias_default_1 = t['am_bias_2']
    t['am_mode'] = 'off'
    save_tmp(t)
    ctl.Update_Dac()
    counts = []
    ctl.Set_Am_Bias_2(0) 
    #time.sleep(0.1)
    num_points = int(2 * range_val / 0.1) + 1
    prev_count = None
    increase_count = 0
    for i in range(num_points):
        ctl.Set_Am_Bias(bias_default - range_val + 0.1*i)
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
    ctl.Set_Am_Bias(am_bias_opt)
    ctl.Set_Am_Bias_2(bias_default_1)
    sendc(bob, 'done')
    if sendresult:
        sendc(conn, 'find_am_bias done')


def verify_am_bias(conn, sendresult=True):
    sendc(bob, 'verify_am_bias')
    update_tmp('am_mode', 'off')
    ctl.Update_Dac()
    time.sleep(0.2)
    sendc(bob, 'get counts')
    count_off = rcv_i(bob)

    update_tmp('am_mode', 'double')
    t = get_tmp()
    bias = t['am_bias']
    bias2=bias+2
    ctl.Set_Am_Bias(bias2)
    ctl.Update_Dac()
    time.sleep(0.2)

    sendc(bob, 'get counts')
    count_double = rcv_i(bob)
    ctl.Set_Am_Bias(bias)
    time.sleep(0.2)

    ratio = count_double / count_off
    if ratio >= 1.8:
        m = colored(f"success: double/off  = {ratio:.2f} ({count_double}/{count_off}) \n", "green", force_color=True)
        print(m)
        result = True
    else:
        m = colored(f"fail double/off = {ratio:.2f} ({count_double}/{count_off}) \n", "yellow", force_color=True)
        print(m)
        result = False
    update_tmp('am_mode', 'off')
    ctl.Update_Dac()
    if sendresult:
        sendc(conn, 'verify_am_bias '+m)
    return result, count_double, count_off

def loop_find_am_bias(conn):
    for voltage in [0.3, 0.5, 1, 2 , 6]:
        find_am_bias(conn, voltage, sendresult=False)
        result, count_double, count_off = verify_am_bias(conn, sendresult=False)
        if result:
            break
    ratio = count_double / count_off
    if result == False:
        m = colored(f"fail double/off = {ratio:.2f} ({count_double}/{count_off}) \n", "yellow", force_color=True)
    else:
        m = colored(f"success: double/off  = {ratio:.2f} ({count_double}/{count_off}) \n", "green", force_color=True)
        t = get_tmp()
        update_default('am_bias',t['am_bias'])
    print(m)
    sendc(conn, 'loop_find_am_bias '+m)

def loop_find_gates(conn):
    for global_attempt in range(2):
        ad(conn, sendresult=False)
        find_sp(conn, sendresult=False)
        ad(conn, sendresult=False)

        max_retries = 1
        for attempt in range(max_retries):
            result, pic = verify_gates(conn, sendresult=False)
            if result:
                send_data(conn, pic)
                m = colored("success: good gates found \n", "green", force_color=True)
                sendc(conn, 'loop_find_gates '+m)
                return 
            print(colored(f"verify_gates failed retrying...", "yellow", force_color=True))

        print(colored(f"verify_gates failed after {max_retries} retries, restarting find_gate sequence...", "red", force_color=True))

    send_data(conn, pic)
    m = colored(f"verify_gates failed", "red", force_color=True)
    sendc(conn, 'loop_find_gates '+m)


def find_am2_bias(conn):
    sendc(bob, 'find_am2_bias')
    update_tmp('am_mode', 'double')
    ctl.Update_Dac()
    #t = get_tmp()
    d = get_default()
    bias_default = d['am_bias_2']
    #bias_default_1 = t['am_bias'] 
    #t['am_mode'] = 'off'
    #save_tmp(t)
    ctl.Update_Dac()
    counts = []
    #ctl.Set_Am_Bias(0) 
    time.sleep(0.2)
    for i in range(21):
        value = bias_default - 3 + 0.1 * i
        if value < 0:
           value = 0
        ctl.Set_Am_Bias_2(value)
       # ctl.Set_Am_Bias_2(bias_default -3 + 0.1*i)
        sendc(bob, 'get counts')
        counts.append(rcv_i(bob))
    min_counts = min(counts)
    min_idx = counts.index(min_counts)
    print("Min count: ", min_counts , "index: ", min_idx)
    am_bias_opt = bias_default -3 + 0.1*min_idx
    ctl.Set_Am_Bias_2(max(0, round(am_bias_opt + 2, 2))) 
    #ctl.Set_Am_Bias(bias_default_1)
    sendc(conn, 'find_am_bias done. '+f"min count: {min_counts}, index: {min_idx}")

def pol_bob(conn):
    sendc(bob, 'pol_bob')
    rcvc(bob)
    sendc(conn, 'pol_bob done')



def ad(conn, sendresult=True):
    sendc(bob, 'ad')
    update_tmp('am_mode', 'off')
    ctl.Update_Dac()
    rcvc(bob)
    update_tmp('am_mode', 'double')
    ctl.Update_Dac()
    time.sleep(0.2)
    #rcvc(bob)
    if sendresult:
        sendc(conn, 'ad done')

def find_sp(conn, sendresult=True):
    sendc(bob, 'find_sp')
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
    if sendresult:
        sendc(conn, 'find_sp done')


def verify_gates(conn, sendresult=True):
    sendc(bob, 'verify_gates')
    print(colored('verify_gates', 'cyan', force_color=True))
    update_tmp('am_mode', 'off')
    ctl.Update_Dac()
    rcvc(bob)
    update_tmp('am_mode', 'double')
    ctl.Update_Dac()
    pic = rcv_data(bob)
    status = rcvc(bob)
    if status == "success":
        m = colored("success: good gates found \n", "green", force_color=True)
        print(m)
        result = True
    else:
        m = colored("fail: bad gates \n", "red", force_color=True)
        print(m)
        result = False
    if sendresult:
        send_data(conn, pic)
        sendc(conn, 'verify_gates '+m)
    return result, pic


def fs_b(conn):
    sendc(bob, 'fs_b')
    t = get_tmp()
    t['am_mode'] = 'double'
    t['pm_mode'] = 'off'
    save_tmp(t)
    ctl.Update_Dac()
    pm_shift = rcv_i(bob)
    if pm_shift != 1000:
        m = colored("Success: Shift_Bob found\n", "green", force_color=True)
        print(m)
    else:
        m = colored("Fail: pm_shift_Bob is None\n", "red", force_color=True)
        print(m)
    sendc(conn, 'fs_b '+m)


def fs_a(conn):
    sendc(bob, 'fs_a')
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
        m = colored("success: Shift_Alice found\n", "green", force_color=True)
        print(m)
    else:
        m = colored("fail: pm_shift_Alice is None\n", "red", force_color=True)
        print(m)
    sendc(conn, 'fs_a '+m)


def fd_b(conn):
    sendc(bob, 'fd_b')
    update_tmp('am_mode', 'double')
    update_tmp('pm_mode', 'fake_rng')
    update_tmp('insert_zeros', 'off')
    ctl.Write_To_Fake_Rng(gen_seq.seq_rng_zeros())
    ctl.Update_Dac()
    rcvc(bob)
    sendc(conn, 'fd_b done')

def fd_b_long(conn):
    sendc(bob, 'fd_b_long')
    update_tmp('am_mode', 'double')
    update_tmp('pm_mode', 'fake_rng')
    update_tmp('insert_zeros', 'off')
    ctl.Write_To_Fake_Rng(gen_seq.seq_rng_zeros())
    ctl.Update_Dac()
    rcvc(bob)
    sendc(conn, 'fd_b_long done')

def fd_a(conn):
    sendc(bob, 'fd_a')
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
    sendc(conn, 'fd_a done')

def fd_a_long(conn):
    sendc(bob, 'fd_a_long')
    t = get_tmp()
    t['pm_mode'] = 'fake_rng'
    t['am_mode'] = 'double'
    t['insert_zeros'] = 'off'
    save_tmp(t)
    ctl.Write_To_Fake_Rng(gen_seq.seq_rng_block1())
    ctl.Update_Dac()
    send_i(bob, t['fiber_delay_mod'])
    fiber_delay_long = rcv_i(bob)
    t = get_tmp()
    t['fiber_delay_long'] = fiber_delay_long
    t['fiber_delay'] = t['fiber_delay_mod'] + fiber_delay_long*80 
    t['decoy_delay'] = t['fiber_delay'] 
    save_tmp(t)
    sendc(conn, 'fd_a_long done')


def fz_b(conn):
    sendc(bob, 'fz_b')
    update_tmp('am_mode', 'double')
    update_tmp('pm_mode', 'fake_rng')
    update_tmp('insert_zeros', 'off')
    ctl.Write_To_Fake_Rng(gen_seq.seq_rng_zeros())
    ctl.Update_Dac()
    rcvc(bob)
    update_tmp('insert_zeros', 'on')
    ctl.Write_To_Fake_Rng(gen_seq.seq_rng_zeros())
    ctl.Update_Dac()
    sendc(conn, 'fz_b done')





def fz_a(conn):
    sendc(bob, 'fz_a')
    d = get_default()
    t = get_tmp()
    t['pm_mode'] = 'fake_rng'
    t['insert_zeros'] = 'on'
    t['zero_pos'] = d['zero_pos']
    save_tmp(t)
    ctl.Write_To_Fake_Rng(gen_seq.seq_rng_all_one())
    ctl.Update_Dac()

    t = get_tmp()
    initial_zero_pos = t['zero_pos']

    sendc(bob, 'get ratio')
    ratio = rcv_d(bob)
    if ratio > 3:
        zero_pos = initial_zero_pos
        print(f"Initial zero_pos {initial_zero_pos} is good, ratio={ratio:.2f}")
    else:
        max_ratio = ratio
        best_zero_pos = initial_zero_pos
        for zp in range(16):
            t['zero_pos'] = zp
            save_tmp(t)
            ctl.Update_Dac()
            time.sleep(0.2)
            sendc(bob, 'get ratio')
            ratio = rcv_d(bob)

            if ratio > 3:
                zero_pos = zp
                break

            if ratio > max_ratio:
                max_ratio = ratio
                best_zero_pos = zp
            else:
                zero_pos = best_zero_pos
    sendc(bob, 'ok')
    update_tmp('zero_pos', zero_pos)
    update_default('zero_pos', zero_pos)
    ctl.Update_Dac()
    rcvc(bob)
    sendc(conn, 'fz_a done')

def start(conn):
    sendc(bob, 'start')
    t = get_tmp()
    t['pm_mode'] = 'true_rng'
    t['insert_zeros'] = 'on'
    save_tmp(t)
    ctl.Update_Dac()
    rcvc(bob)
    sendc(conn, 'start done')







# for convencience
functionmap = {}
functionmap['init'] = init
functionmap['sync_gc'] = sync_gc
functionmap['compare_gc'] = compare_gc
functionmap['vca_per'] = vca_per
functionmap['qdistance'] = qdistance
functionmap['find_vca'] = find_vca
functionmap['find_am_bias'] = find_am_bias
functionmap['verify_am_bias'] = verify_am_bias
functionmap['loop_find_am_bias'] = loop_find_am_bias
functionmap['loop_find_gates'] = loop_find_gates
functionmap['find_am2_bias'] = find_am2_bias
functionmap['pol_bob'] = pol_bob
functionmap['ad'] = ad
functionmap['find_sp'] = find_sp
functionmap['verify_gates'] = verify_gates
functionmap['fs_b'] = fs_b
functionmap['fs_a'] = fs_a
functionmap['fd_b'] = fd_b
functionmap['fd_b_long'] = fd_b_long
functionmap['fd_a'] = fd_a
functionmap['fd_a_long'] = fd_a_long
functionmap['fz_a'] = fz_a
functionmap['fz_b'] = fz_b
functionmap['start'] = start


while True:
    conn, addr = server_socket.accept()  # Accept incoming connection from admin
    print(f"Connected by {addr}")
    with open(connection_logfile, 'a') as f:
        f.write(f"{datetime.datetime.now()}\t{addr}\n")

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

            print(colored(command+' ...\n', 'blue', force_color=True))
            if command.startswith('find_vca_'):
                limit = int(command.split('_')[-1])
                print('command: ', command)
                functionmap['find_vca'](conn, limit)
            elif command.startswith('vca_per_'):
                per = int(command.split('_')[-1])
                print('command: ', command)
                functionmap['vca_per'](conn, per)

            else:
                try:
                    functionmap[command](conn)
                except:
                    print(colored('unkown command or error in function'+command, 'red', force_color=True))
                    sendc(conn, colored('unknown command or error in function'+command, 'red', force_color=True))
                    continue

            print(colored('... '+command+' done \n', 'blue', force_color=True))


    except KeyboardInterrupt:
        print("Server stopped by keyboard interrupt.")
    finally:
        try:
            conn.shutdown(socket.SHUT_RDWR)  # Properly shutdown connection
        except OSError:
            pass  # Ignore if connection is already closed
        conn.close()


