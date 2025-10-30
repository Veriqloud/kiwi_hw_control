#!/bin/python

import socket, json, time, os, struct, datetime
#import numpy as np
import ctl_bob as ctl
import lib.gen_seq as gen_seq

from lib.fpga import get_tmp, save_tmp, update_tmp, update_default, Set_t0, get_default, Sync_Gc, get_gc
from termcolor import colored

from pathlib import Path


HW_CONTROL = '/home/vq-user/hw_control/'

qlinepath = '../'

networkfile = qlinepath+'config/network.json'
connection_logfile = '/tmp/log/ip_connections_to_hardware_system.log'

# make sure /tmp/log/ existists
Path("/tmp/log").mkdir(exist_ok=True)


# get ip from config/network.json
with open(networkfile, 'r') as f:
    network = json.load(f)

# Server configuration
host = network['ip']['bob_wrs']
port = int(network['port']['hws'])


# Create TCP socket
server_socket = socket.socket()
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_socket.bind((host, port))
server_socket.listen()


def set_flag_calibrating():
    with open('/tmp/calibrating.txt', 'w') as f:
        f.write('calibrating')

def clear_flag_calibrating():
    with open('/tmp/calibrating.txt', 'w') as f:
        f.write('not calibrating')

print(f"Server listening on {host}:{port}")


while True:
    conn, addr = server_socket.accept()  # Accept incoming connection
    print(f"Connected by {addr}")
    with open(connection_logfile, 'a') as f:
        f.write(f"{datetime.datetime.now()}\t{addr}\n")


    def recv_exact(l):
        m = bytes(0)
        while len(m)<l:
            m += conn.recv(l - len(m))
        return m

    # send command
    def sendc(c):
        print(colored(c, 'blue', force_color=True))
        b = c.encode()
        m = len(c).to_bytes(1, 'little')+b
        conn.sendall(m)

    # receive command
    def rcvc():
        l = int.from_bytes(conn.recv(1), 'little')
        mr = recv_exact(l)
        command = mr.decode().strip()
        print(colored(command, 'cyan', force_color=True))
        return command
    
    # send integer
    def send_i(value):
        print(colored(value, 'blue', force_color=True))
        m = struct.pack('i', value)
        conn.sendall(m)
    
    # send long integer
    def send_q(value):
        print(colored(value, 'blue', force_color=True))
        m = struct.pack('q', value)
        conn.sendall(m)

    # receive integer
    def rcv_i():
        m = recv_exact(4)
        value = struct.unpack('i', m)[0]
        print(colored(value, 'cyan', force_color=True))
        return value

    # send double
    def send_d(value):
        print(colored(value, 'blue', force_color=True))
        m = struct.pack('d', value)
        conn.sendall(m)

    # receive double
    def rcv_d():
        m = recv_exact(8)
        value = struct.unpack('d', m)[0]
        print(colored(value, 'cyan', force_color=True))
        return value
    
    # send binary data
    def send_data(data):
        print(colored('sending data', 'blue', force_color=True))
        l = len(data)
        print(l)
        m = struct.pack('i', l) + data 
        conn.sendall(m)

    try:
        while True:
            try:
                # Receive command from client
                command = rcvc()
                set_flag_calibrating()
            except ConnectionResetError:
                print("Client connection was reset. Exiting loop.")
                break


            if command == 'init':
                ctl.init_all()
                rcvc()
                sendc('Alice and Bob init done')    
                print(colored('Alice and Bob init done \n', 'cyan', force_color=True))


            elif command == 'sync_gc':
                rcvc()
                Sync_Gc()
                print(colored('sync_gc', 'cyan', force_color=True))
            
            elif command == 'compare_gc':
                gc = get_gc()
                send_d(gc)


            elif command == 'vca_per':
                print(colored('vca_per', 'cyan'))
                ctl.Ensure_Spd_Mode('continuous')
                while rcvc() == 'get counts':
                    count = ctl.counts_fast()[0]
                    send_i(count)

            elif command == 'qdistance':
                print(colored('qdistance', 'cyan'))
                ctl.Ensure_Spd_Mode('continuous')
                while rcvc() == 'get counts':
                    count = ctl.diff_counts()
                    send_i(count)


            elif command == 'adjust_am':
 #               rcvc()
 #               print(colored('AM adjusted', 'cyan', force_color=True))
               print(colored('doing nothing', 'cyan', force_color=True))
#               rcvc()

            elif command == 'adjust_angles_a':
               print(colored('doing nothing', 'cyan', force_color=True))


            elif command == 'find_vca':
                print(colored('find_vca', 'cyan', force_color=True))
                ctl.Ensure_Spd_Mode('continuous')
                while rcvc() == 'get counts':
                    count = ctl.counts_fast()[0]
                    send_i(count)


            elif command == 'find_am_bias':
                print(colored('find_am_bias', 'cyan', force_color=True))
                while rcvc() == 'get counts':
                    time.sleep(0.2)
                    count = ctl.counts_fast()[0]
                    send_i(count)

            elif command == 'find_am2_bias':
                print(colored('find_am_bias_2', 'cyan', force_color=True))
                for i in range(21):
                    rcvc()
                    time.sleep(0.2)
                    count = ctl.counts_fast()[0]
                    send_i(count)




            elif command == 'verify_am_bias':
                print(colored('verify_am_bias', 'cyan', force_color=True))
                for i in range(2):
                    rcvc()
                    time.sleep(0.2)
                    count = ctl.counts_fast()[0]
                    send_i(count)



            elif command == 'pol_bob':
                    print(colored('pol_bob', 'cyan', force_color=True))
                    ctl.Polarisation_Control()
                    sendc('done')


            elif command == 'ad':
                print(colored('ad', 'cyan', force_color=True))
                update_tmp('soft_gate', 'off')
                update_tmp('gate_delay', 0)
                ctl.Gen_Gate()
                ctl.Update_Softgate()
                ctl.Ensure_Spd_Mode('gated')
                time.sleep(0.2)
                ctl.Download_Time(10000, 'verify_gate_ad_0')
                file_off = HW_CONTROL+"data/tdc/verify_gate_ad_0.txt"

                #max_iter = 2
                #iter_count = 0
                    

                lf = ctl.fall_edge(file_off)
                target = (65-lf) % 312
                update_tmp('gate_delay', target*40)
                ctl.Gen_Gate()
                sendc('done')

                #while True:
                #    lf = ctl.fall_edge(file_off, 200, 900)
               ##     print("Last falling edge off between 200 and 900:", lf)

                #    if abs(lf - 725) <= 2 or iter_count >= max_iter:
                #        break

                #    d = get_tmp()
                #    tmp_delay0=d['gate_delay0']
                ##    print("gate_delay0 =", tmp_delay0)
                #    tmp_delay=d['gate_delay']
                # #   print("tmp_delay =", tmp_delay)
                #    if lf > 725:
                #        ad = tmp_delay - ((lf - 725) * 20)
                #    else:
                #        ad = tmp_delay + ((725 - lf) * 20)

                #    ad = abs(ad)
                #    ad = 5000 if ad > 12500 else ad

                #    update_tmp('gate_delay', ad)
                #    update_tmp('gate_delay0', ad)
                #    ctl.Gen_Gate()
                #    iter_count += 1
                #    ctl.Download_Time(10000, 'verify_gate_ad_'+str(iter_count))
                #    file_off = HW_CONTROL+"data/tdc/verify_gate_ad_"+str(iter_count)+".txt"
                #sendc('done')
                #ctl.Ensure_Spd_Mode('continuous')
                #sendc('ok')
                #time.sleep(0.2)


            elif command == 'find_sp':
                print(colored('find_sp', 'cyan', force_color=True))
                t = get_tmp()
                t['t0'] = 10 #to have some space to the left
                t['soft_gate'] = 'off'
                save_tmp(t)
                ctl.Update_Softgate()

                # detection single pulse at shift_am 0
                print("measure and search single peak")
                shift_am, t0  = ctl.Measure_Sp(20000)
                Set_t0(10+t0)
                update_tmp('t0', 10+t0)
                d = get_tmp()
                update_tmp('gate_delay', (d['gate_delay0']-t0*20) % 12500)
                ctl.Gen_Gate()
                
                # send back shift_am value to alice
                send_i(shift_am)

                # detect single64 pulse and send to Alice
                update_tmp('soft_gate', 'on')
                ctl.Update_Softgate()
                print("measure sp64")
                coarse_shift = ctl.Measure_Sp64()
                send_i(coarse_shift)



            elif command == 'verify_gates':
                print(colored('verify_gates', 'cyan', force_color=True))
                update_tmp('soft_gate', 'off')
                ctl.Update_Softgate()
                ctl.Ensure_Spd_Mode('gated')
                time.sleep(0.2)
                ctl.Download_Time(10000, 'verify_gate_off')
                sendc("gates off done")
                ctl.Download_Time(10000, 'verify_gate_double')                
                t = get_tmp()
                gate0=t['soft_gate0']
                gate1=t['soft_gate1']
                width=t['soft_gatew']
                binstep = 2
                maxtime = gate1 + width
                input_file = HW_CONTROL+'data/tdc/verify_gate_double.txt'
                input_file2 = HW_CONTROL+'data/tdc/verify_gate_off.txt'
                status = ctl.verify_gate_double(input_file,input_file2, gate0, gate1, width, binstep, maxtime)
                pic = HW_CONTROL+"data/calib_res/gate_double.png"
                with open(pic, 'rb') as f:
                    data = f.read()
                send_data(data)
                sendc(status)


            elif command == 'fs_b':
                print(colored('fs_b', 'cyan', force_color=True))
                ctl.Ensure_Spd_Mode('gated')
                t = get_tmp()
                t['pm_mode'] = 'seq64'
                t['feedback'] = 'off'
                t['soft_gate'] = 'on'
                save_tmp(t)
                ctl.Update_Softgate()
                d = get_default()
                pm_shift_coarse = (d['pm_shift']//10) * 10
                for s in range(10):
                    t['pm_shift'] = pm_shift_coarse + s
                    save_tmp(t)
                    ctl.Update_Dac()
                    ctl.Download_Time(10000, 'pm_b_shift_'+str(s))
                pm_shift = ctl.Find_Best_Shift('bob')
                if pm_shift is not None:
                   update_tmp('pm_shift', pm_shift_coarse + pm_shift)
                   ctl.Update_Dac()
                else:
                   pm_shift=1000
                send_i(pm_shift)

           
            elif command == 'fs_a':
                print(colored('fs_a', 'cyan', force_color=True))
                ctl.Ensure_Spd_Mode('gated')
                t = get_tmp()
                t['pm_mode'] = 'off'
                t['feedback'] = 'off'
                t['soft_gate'] = 'on'
                save_tmp(t)
                ctl.Update_Softgate()
                ctl.Update_Dac()
                for s in range(10):
                    rcvc()
                    ctl.Download_Time(10000, 'pm_a_shift_'+str(s))
                    sendc("ok")
                pm_shift = ctl.Find_Best_Shift('alice')
                if pm_shift is None:
                   pm_shift = 1000
                send_i(pm_shift)



           
            elif command == 'fd_b':
                print(colored('fd_b', 'cyan', force_color=True))
                ctl.Ensure_Spd_Mode('gated')
                fiber_delay = ctl.Find_Opt_Delay_B()
                response = 'Find delay bob done'
                t = get_tmp()
                t['fiber_delay_mod'] = fiber_delay
                t['fiber_delay'] = fiber_delay % 80 + t['fiber_delay_long']
                save_tmp(t)
                sendc('ok')
            
            elif command == 'fd_b_long':
                print(colored('fd_b_long', 'cyan', force_color=True))
                ctl.Ensure_Spd_Mode('gated')
                fiber_delay = ctl.Find_Opt_Delay_B_long()
                response = 'Find delay bob done'
                t = get_tmp()
                t['fiber_delay_long'] = fiber_delay
                t['fiber_delay'] = t['fiber_delay_mod']%80 + fiber_delay*80
                save_tmp(t)
                sendc('ok')
            
            elif command == 'fd_a':
                print(colored('fd_a', 'cyan', force_color=True))
                ctl.Ensure_Spd_Mode('gated')
                fiber_delay = ctl.Find_Opt_Delay_A()
                send_i(fiber_delay)
            
            elif command == 'fd_a_long':
                print(colored('fd_a_long', 'cyan', force_color=True))
                ctl.Ensure_Spd_Mode('gated')
                fiber_delay_mod = rcv_i()
                fiber_delay = ctl.Find_Opt_Delay_A_long(fiber_delay_mod)
                send_i(fiber_delay)
            
            elif command == 'fz_b':
                print(colored('fz_b', 'cyan', force_color=True))
                ctl.Ensure_Spd_Mode('gated')
                zero_pos = ctl.Find_Zero_Pos_B_new()
                update_tmp('zero_pos', zero_pos)
                update_default('zero_pos', zero_pos)
                ctl.Update_Dac()
                sendc('ok')
            
            elif command == 'fz_a':
                print(colored('fz_a', 'cyan', force_color=True))
                ctl.Ensure_Spd_Mode('gated')
                print("received command fz_a")
                t = get_tmp()
                t['feedback'] = 'on'
                t['soft_gate'] = 'on'
                t['insert_zeros'] = 'off'
                save_tmp(t)
                ctl.Write_To_Fake_Rng(gen_seq.seq_rng_zeros())
                ctl.Update_Softgate()
                ctl.Update_Dac()
                time.sleep(0.3)

                while rcvc() == 'get ratio':
                      ratio = ctl.calculate_ratio()
                      send_d(ratio)

                update_tmp('insert_zeros', 'on')
                ctl.Update_Dac()
                sendc('ok')




            elif command == 'adjust_soft_gates':
                t = get_tmp()
                g0, g1, w0, w1 = t['soft_gate0'], t['soft_gate1'], t['w0'], t['w1']
                best_g0, best_g1, best_w0, best_w1 = g0, g1, w0, w1
                lowest_qber = None

                #  gate 0
                for delta in [-3, 0, 3]:
                    g0_test = max(0, g0 + delta)
                    t['soft_gate0'] = g0_test
                    save_tmp(t)
                    ctl.set_Softgate(g0_test, g1, w0, w1)
                    sendc('get_qber')
                    qber = rcv_d()
                    print(f" g0={g0_test}, g1={g1}, w0={w0}, w1={w1}, QBER={qber}")
                    if lowest_qber is None or qber < lowest_qber:
                        lowest_qber, best_g0 = qber, g0_test

                t['soft_gate0'] = best_g0
                save_tmp(t)
                ctl.set_Softgate(best_g0, g1, w0, w1)

                #  gate 1
                for delta in [-3, 0, 3]:
                    g1_test = max(0, g1 + delta)
                    t['soft_gate1'] = g1_test
                    save_tmp(t)
                    ctl.set_Softgate(best_g0, g1_test, w0, w1)
                    sendc('get_qber')
                    qber = rcv_d()
                    print(f" g0={best_g0}, g1={g1_test}, w0={w0}, w1={w1}, QBER={qber}")
                    if qber < lowest_qber:
                        lowest_qber, best_g1 = qber, g1_test

                t['soft_gate1'] = best_g1
                save_tmp(t)
                ctl.set_Softgate(best_g0, best_g1, w0, w1)

                #  w0
                for delta in [-3, 0, 3]:
                    w0_test = max(25, w0 + delta)
                    t['w0'] = w0_test
                    save_tmp(t)
                    ctl.set_Softgate(best_g0, best_g1, w0_test, w1)
                    sendc('get_qber')
                    qber = rcv_d()
                    print(f" g0={best_g0}, g1={best_g1}, w0={w0_test}, w1={w1}, QBER={qber}")
                    if qber < lowest_qber:
                        lowest_qber, best_w0 = qber, w0_test

                t['w0'] = best_w0
                save_tmp(t)
                ctl.set_Softgate(best_g0, best_g1, best_w0, w1)

                #  w1
                for delta in [-3, 0, 3]:
                    w1_test = max(25, w1 + delta)
                    t['w1'] = w1_test
                    save_tmp(t)
                    ctl.set_Softgate(best_g0, best_g1, best_w0, w1_test)
                    sendc('get_qber')
                    qber = rcv_d()
                    print(f" g0={best_g0}, g1={best_g1}, w0={best_w0}, w1={w1_test}, QBER={qber}")
                    if qber < lowest_qber:
                        lowest_qber, best_w1 = qber, w1_test

                t['w1'] = best_w1
                save_tmp(t)
                ctl.set_Softgate(best_g0, best_g1, best_w0, best_w1)

                sendc('ok')






            elif command == 'set_soft_gates':
                t = get_tmp()
#                t['pm_mode'] = 'fake_rng'
#                t['feedback'] = 'on'
#                t['soft_gate'] = 'on'
#                t['insert_zeros'] = 'off'
                save_tmp(t)
                ctl.Write_To_Fake_Rng(gen_seq.seq_rng_random())
                ctl.Update_Softgate()
                ctl.Update_Dac()
                time.sleep(0.3)

                d = get_default()
                g0, g1, w0, w1 = d['soft_gate0'], d['soft_gate1'], d['w0'], d['w1']

                print(f"Initial values: g0={g0}, g1={g1}, w0={w0}, w1={w1}")

                best_g0, best_g1, best_w0, best_w1 = g0, g1, w0, w1
                max_count = 0

                print("Step 1: optimizing g0")
                for delta in range(-10, 11, 3):
                    g0_test = max(0, g0 + delta)
                    ctl.set_Softgate(g0_test, g1, w0, w1)
                    time.sleep(0.2)
                    count = ctl.counts_fast()[1]
                    print(f"   g0={g0_test}, count1={count}")
                    if count > max_count:
                        max_count = count
                        best_g0 = g0_test

                print(f"Best g0={best_g0}, max_count={max_count}")

                max_count = 0
                print("Step 2: optimizing g1")
                for delta in range(-10, 11, 3):
                    g1_test = max(0, g1 + delta)
                    ctl.set_Softgate(best_g0, g1_test, w0, w1)
                    time.sleep(0.2)
                    count = ctl.counts_fast()[2]
                    print(f"   g1={g1_test}, count2={count}")
                    if count > max_count:
                        max_count = count
                        best_g1 = g1_test

                print(f"Best g1={best_g1}, max_count={max_count}")

                counts = ctl.counts_fast()
                print(f"Step 3: initial counts: c1={counts[1]}, c2={counts[2]}")

                if counts[1] > counts[2]:
                    i = 0
                else:
                    i = 1
                print(f"Decision: adjust w{i}")

                for delta in range(0, 11, 2):
                    if i == 1:
                        w1_test = max(0, w1 - delta)
                        ctl.set_Softgate(best_g0, best_g1, best_w0, w1_test)
                        time.sleep(0.2)
                        counts = ctl.counts_fast()
                        print(f"   w1={w1_test}, c1={counts[1]}, c2={counts[2]}")
                        if abs(counts[1] - counts[2]) <= 50:
                            best_w1 = w1_test
                            print(f"Best w1={best_w1}")
                            break
                    else:
                        w0_test = max(0, w0 - delta)
                        ctl.set_Softgate(best_g0, best_g1, w0_test, best_w1)
                        time.sleep(0.2)
                        counts = ctl.counts_fast()
                        print(f"   w0={w0_test}, c1={counts[1]}, c2={counts[2]}")
                        if abs(counts[1] - counts[2]) <= 50:
                            best_w0 = w0_test
                            print(f"Best w0={best_w0}")
                            break

                t = get_tmp()
                t['soft_gate0'], t['soft_gate1'] = best_g0, best_g1
                t['w0'], t['w1'] = best_w0, best_w1
                save_tmp(t)

                ctl.set_Softgate(best_g0, best_g1, best_w0, best_w1)
                print(f"Final values: g0={best_g0}, g1={best_g1}, w0={best_w0}, w1={best_w1}")
                sendc('set_soft_gates_done')







            elif command == 'set_angles_a':
                t = get_tmp()
                t['feedback'] = 'on'
                t['soft_gate'] = 'on'
                t['insert_zeros'] = 'off'
                save_tmp(t)
                ctl.Write_To_Fake_Rng(gen_seq.seq_rng_zeros())
                ctl.Update_Softgate()
                ctl.Update_Dac()
                time.sleep(0.3)

                ctl.Ensure_Spd_Mode('continuous')
                while rcvc() == 'get counts':
                    count = ctl.diff_counts()
                    send_i(count)



            elif command == 'start':
                print(colored('start', 'cyan', force_color=True))
                t['pm_mode'] = 'true_rng'
                t['insert_zeros'] = 'on'
                t['feedback'] = 'on'
                save_tmp(t)
                ctl.Update_Dac()
                sendc('ok')

            elif not command:
                print("Client disconnected.")
                break  # Exit loop if the client closes the connection
        
            clear_flag_calibrating()


    except KeyboardInterrupt:
        print("Server stopped by keyboard interrupt.")
    finally:
        try:
            conn.shutdown(socket.SHUT_RDWR)  # Properly shutdown connection
        except OSError:
            pass  # Ignore if connection is already closed
        conn.close()


