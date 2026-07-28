
#!/bin/python

import socket, json, time, os, struct, datetime, os
#import numpy as np
import ctl_bob as ctl
import lib.gen_seq as gen_seq

from lib.fpga import get_tmp, save_tmp, update_tmp, Set_t0, Sync_Gc, get_gc
from termcolor import colored

from pathlib import Path
import subprocess
import builtins


# Prefix every log line with a timestamp (see hws_alice.py). hws logs to
# ~/log/hws.log via systemd with no time information; shadowing the module-level
# `print` timestamps all existing calls without touching each one. Timestamps
# stay uncolored so the showlogs/logd ANSI parser renders the rest as before.
def print(*args, **kwargs):
    ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
    builtins.print(ts, *args, **kwargs)


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

def wait_for_node_idle(timeout=60):
    """Block until gc-bob raises /tmp/node_idle, i.e. the node has answered a
    HwNotReady poll with its DMA fds closed and gc is not streaming. Call this
    right after dropping /tmp/qkd_ready and before reconfiguring hardware
    (init), so calibration never resets the FPGA under a mid-session node.
    Returns True if the ack arrived, False on timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if os.path.isfile('/tmp/node_idle'):
            print(colored('node idle ack received (/tmp/node_idle); fifos released', 'green', force_color=True))
            return True
        time.sleep(0.5)
    print(colored(f'WARNING: timed out after {timeout}s waiting for /tmp/node_idle; proceeding anyway', 'red', force_color=True))
    return False

# --- physical SPD gate placement check -------------------------------------
#
# The gate slides over the two time-bin pulses, so click0 and click1 trade off
# as gate_delay moves. `ad` picks a position once at calibration; if it lands on
# a slope (or in the dip BETWEEN the two pulses) one channel is clipped, and no
# amount of soft-gate tuning can recover photons the physical gate already threw
# away -- adjust_soft_gates only slides a digital window INSIDE whatever the
# hardware gate passed. Recentring the physical gate on the flat top is what
# gives adjust_soft_gates usable range again.
#
# NOTE ON THE TEST: do NOT use a gradient/first-derivative test. A badly placed
# gate can sit in a local MINIMUM (qline1 sat at 11680 ps, in the dip between
# the two pulses), where the symmetric gradient is ~0 and a slope test reports
# "flat". Instead ask whether a materially BETTER position exists within +-
# GATE_PROBE_PS; that catches slopes and dips alike.
#
# NOTE ON THE OBJECTIVE: use click0+click1, NOT the click1/click0 ratio. The
# ratio looks tempting (measured against QBER over 1597 min it gave Pearson
# r = -0.715) but that only holds inside the normal operating range. Push the
# gate late and click0 collapses while click1 holds -- measured on qline1
# 2026-07-28: 12600 ps -> ratio 2.5, 13200 ps -> ratio 6.1 with click0 down to
# 335. Maximising the ratio therefore walks the gate until one detector channel
# is DEAD. The sum penalises clipping either channel. Validated against both a
# known-bad gate (2026-07-28 morning, +14.1% available at +-600 -> fires) and a
# known-good one (same day, +0.4% -> stays put); the ratio objective by contrast
# reported +19..+91% on a HEALTHY gate, i.e. it would move it for no reason.
#
# NOTE ON THE RANGE: gate delay does NOT wrap. Gen_Gate() programs an absolute
# delay line (one coarse + three fine stages, each with its own calibration
# offset from config/delayf.txt), so positions one optical period apart are
# physically DIFFERENT settings -- measured 2026-07-28: 12630 ps gives ratio
# 2.33-2.40 but 150 ps gives 1.97-2.05, and 12480 differs from 0 the same way.
# An earlier version of this code did `% GATE_PERIOD_PS` and silently teleported
# the gate. Clamp instead.
GATE_PERIOD_PS = 312 * 40    # optical period; ad() works in 312 bins of 40 ps
GATE_MIN_PS = 0              # both ends verified on qline1 hardware 2026-07-28
GATE_MAX_PS = 13280          # beyond ~12900 click0 starts dying; do not go higher
GATE_PROBE_PS = 600          # +- offset for the cheap 3-point probe (see validation)
GATE_PROBE_TOL = 0.08        # a neighbour must beat centre by >8% to count as "better"
GATE_SCAN_SPAN_PS = 800      # +- span of the recentring scan
GATE_SCAN_STEP_PS = 100      # step of the recentring scan
GATE_PLATEAU_BAND = 0.05     # points within 5% of the best sum form the plateau
GATE_SETTLE_S = 0.3          # enough: 0.3 s and 2.5 s agree within noise (measured)
GATE_MIN_COUNTS = 50         # below this (per counts_slow window) the read is noise


def _gate_apply(ps):
    """Move the physical gate to `ps` ps, clamped to the safe range.

    Clamped, never wrapped -- see the range note above.
    """
    ps = max(GATE_MIN_PS, min(GATE_MAX_PS, int(ps)))
    update_tmp('gate_delay', ps)
    ctl.Gen_Gate()
    return ps


def _gate_probe(ps):
    """Set the gate to `ps` and return (score, click0, click1).

    score = click0+click1, the number of usefully gated detections (see the
    objective note above).

    counts_slow() averages 10 reads over ~1 s via the mmap'd /dev/xdma0_user, so
    this never touches the exclusive /dev/xdma0_c2h_2 and cannot collide with a
    concurrent calibration the way a TDC histogram read would.
    """
    applied = _gate_apply(ps)
    time.sleep(GATE_SETTLE_S)
    total, click0, click1 = ctl.counts_slow()
    return click0 + click1, click0, click1


def gate_edge_check(recentre=True):
    """Test whether the physical SPD gate is badly placed; recentre if it is.

    THIS IS A GUARD, NOT AN OPTIMISER. It reliably gets the gate off a grossly
    bad spot, but click0+click1 is only a proxy for link quality and it can
    settle on a SECONDARY optimum. Replaying the real 2026-07-28 fault: from
    11680 ps (QBER 0.071, 10k bits/round) it moves to ~11180 (QBER ~0.038, ~43k)
    -- a 46% improvement, while the true best was ~12400 (QBER 0.025, ~72k),
    because the count sum peaks on the lower branch and QBER on the upper one.
    Finding the real optimum needs QBER per point (~100 s each), which is what a
    human doing a proper `ad`/full_init recalibration is for. Alice wraps this
    call in a live-QBER before/after check and undoes any move that regressed.

    Returns a short one-line status string (the hws wire protocol is length-
    prefixed with a single byte, so keep replies well under 255 chars).

    Cheap path (the common case) is 3 probe points, ~4 s, and changes nothing.
    Only if a materially better neighbour exists do we pay for the wider scan.
    The original position is restored on any failure or if the scan finds
    nothing better, so a bad measurement can never leave the gate parked
    somewhere worse than it started.
    """
    t = get_tmp()
    d0 = max(GATE_MIN_PS, min(GATE_MAX_PS, int(t['gate_delay'])))
    try:
        return _gate_edge_check(d0, recentre)
    except Exception:
        # Never leave the gate parked on a probe point because a read blew up.
        _gate_apply(d0)
        raise


def _gate_edge_check(d0, recentre):
    base, c0, c1 = _gate_probe(d0)
    if base < GATE_MIN_COUNTS:
        _gate_apply(d0)
        return f'skipped: too few counts ({c0}+{c1}) - laser/detector down?'

    lo, _, _ = _gate_probe(max(GATE_MIN_PS, d0 - GATE_PROBE_PS))
    hi, _, _ = _gate_probe(min(GATE_MAX_PS, d0 + GATE_PROBE_PS))
    best_neighbour = max(lo, hi)

    if best_neighbour <= base * (1 + GATE_PROBE_TOL):
        _gate_apply(d0)
        return (f'ok: gate centred at {d0} ps '
                f'(clicks {base:.0f}; -{GATE_PROBE_PS}:{lo:.0f} +{GATE_PROBE_PS}:{hi:.0f})')

    if not recentre:
        _gate_apply(d0)
        return (f'EDGE at {d0} ps: clicks {base:.0f} but neighbour {best_neighbour:.0f} '
                f'(recentre disabled)')

    # On a slope or in a dip -> scan the neighbourhood and move to the middle of
    # the flat top, which maximises drift margin (the point is to stop the gate
    # wandering back onto a slope, not merely to grab the best single sample).
    print(colored(f'gate at {d0} ps looks misplaced (clicks {base:.0f} vs neighbour '
                  f'{best_neighbour:.0f}); scanning', 'yellow', force_color=True))
    offsets = list(range(-GATE_SCAN_SPAN_PS, GATE_SCAN_SPAN_PS + 1, GATE_SCAN_STEP_PS))
    scan = []
    for off in offsets:
        ps = d0 + off
        if not (GATE_MIN_PS <= ps <= GATE_MAX_PS):
            continue
        r, _, _ = _gate_probe(ps)
        scan.append((ps, r, off))
        print(f'  gate {ps:5d} ps -> click0+click1 {r:.0f}')

    best_ps, best_r, _ = max(scan, key=lambda x: x[1])
    if best_r <= base * (1 + GATE_PROBE_TOL):
        _gate_apply(d0)
        return f'ok: no better gate within +-{GATE_SCAN_SPAN_PS} ps of {d0} (kept {d0})'

    # Contiguous run of near-best points containing the best one = the plateau.
    # Index into `scan` (not `offsets`): points outside the safe range are skipped,
    # so the two lists are not aligned.
    threshold = best_r * (1 - GATE_PLATEAU_BAND)
    bi = next(i for i, (ps, r, off) in enumerate(scan) if ps == best_ps)
    lo_i = bi
    while lo_i > 0 and scan[lo_i - 1][1] >= threshold:
        lo_i -= 1
    hi_i = bi
    while hi_i < len(scan) - 1 and scan[hi_i + 1][1] >= threshold:
        hi_i += 1

    centre_ps = (scan[lo_i][0] + scan[hi_i][0]) // 2
    new_ps = _gate_apply(centre_ps)
    width = scan[hi_i][0] - scan[lo_i][0] + GATE_SCAN_STEP_PS
    final_r, _, _ = _gate_probe(new_ps)
    return (f'MOVED gate {d0} -> {new_ps} ps (plateau {width} ps wide, '
            f'clicks {base:.0f} -> {final_r:.0f})')


def set_gate_delay(ps):
    """Apply an explicit gate delay. Used by Alice to revert a move that the
    live QBER did not actually confirm as an improvement."""
    return _gate_apply(ps)


print(f"Server listening on {host}:{port}")


while True:
    conn, addr = server_socket.accept()  # Accept incoming connection
    print(f"Connected by {addr}")
    with open(connection_logfile, 'a') as f:
        f.write(f"{datetime.datetime.now()}\t{addr}\n")


    def recv_exact(l):
        m = bytes(0)
        while len(m)<l:
            chunk = conn.recv(l - len(m))
            if not chunk:  # EOF: client closed the connection cleanly
                raise ConnectionResetError("client disconnected")
            m += chunk
        return m

    # send command
    def sendc(c):
        print(colored(c, 'blue', force_color=True))
        b = c.encode()
        m = len(c).to_bytes(1, 'little')+b
        conn.sendall(m)

    # receive command
    def rcvc():
        b0 = conn.recv(1)
        if not b0:  # EOF: client closed the connection cleanly (recv returns b'')
            raise ConnectionResetError("client disconnected")
        l = int.from_bytes(b0, 'little')
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


    def rcv_data():
        m = recv_exact(4)
        l = struct.unpack('i', m)[0]
        data = recv_exact(l)
        print(colored('received data', 'cyan', force_color=True))
        return data


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
                # Stop the node before reconfiguring the FPGA: drop the
                # QKD-ready flag (gc-bob answers the node's polls with
                # HwNotReady, the node closes its DMA fds), clear any stale
                # ack, then wait until gc-bob raises /tmp/node_idle.
                try:
                    os.remove('/tmp/qkd_ready')
                except FileNotFoundError:
                    pass
                try:
                    os.remove('/tmp/node_idle')   # force a fresh ack
                except FileNotFoundError:
                    pass
                wait_for_node_idle()
                ctl.init_hw()
                ctl.apply_config()
                rcvc()
                sendc('Alice and Bob init done')    
                print(colored('Alice and Bob init done \n', 'cyan', force_color=True))


            elif command == 'clean':
                ctl.clean_config()
            
            elif command == 'save':
                filename = rcvc()
                ctl.save_config(filename)
            
            elif command == 'load':
                filename = rcvc()
                if not os.path.isfile("/home/vq-user/config/calibration/"+filename):
                    sendc('error')
                else:
                    ctl.load_config(filename)
                    sendc('ok')


            elif command == 'sync_gc':
                rcvc()
                Sync_Gc()
                print(colored('sync_gc', 'cyan', force_color=True))
            
            elif command == 'compare_gc':
                gc = get_gc()
                send_d(gc)

            elif command == 'config_laser':
                print(colored('doing nothing', 'cyan', force_color=True))

            elif command == 'free_running':
                ctl.Ensure_Spd_Mode('continuous')
                update_tmp('soft_gate', 'off')
                ctl.Update_Softgate()
                sendc('ok')

            elif command == 'vca_per':
                print(colored('vca_per', 'cyan'))
                #ctl.Ensure_Spd_Mode('continuous')
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
                print(colored('adjust_am', 'cyan', force_color=True))
                t = get_tmp()
                t['pm_mode'] = 'true_rng'
                t['insert_zeros'] = 'on'
                t['feedback'] = 'on'
                t['soft_gate'] = 'on'
                save_tmp(t)
                ctl.Update_Softgate()
                ctl.Update_Dac()

                while rcvc() == 'get counts':
                    time.sleep(0.2)
                    count = ctl.counts_fast()[1] + ctl.counts_fast()[2]
                    send_i(count)
#                  values = []
#                  for _ in range(6):
#                    count = ctl.counts_fast()[1] + ctl.counts_fast()[2]
#                    values.append(count)
#                    time.sleep(0.1)
#                  avg_count = int(sum(values) / len(values))
#                  send_i(avg_count)



            elif command == 'adjust_am_qber':
                print(colored('adjust_am_qber', 'cyan', force_color=True))

                while rcvc() != 'done':
                    time.sleep(0.2)

            elif command == 'adjust_angles_a_qber':
                print(colored('adjust_angles_a_qber', 'cyan', force_color=True))

                while rcvc() != 'done':
                    time.sleep(0.2)

            elif command == 'adjust_angles_b_qber':
                print(colored('adjust_angles_b_qber', 'cyan', force_color=True))

                while True:
                    cmd = rcvc()

                    if cmd == 'get_angle1':
                        t = get_tmp()
                        send_d(t['angle1'])

                    elif cmd == 'set_angle1':
                        angle1 = rcv_d()

                        angle0 = 0.0
                        angle2 = -angle1
                        angle3 = 2 * angle1

                        update_tmp('angle0', angle0)
                        update_tmp('angle1', angle1)
                        update_tmp('angle2', angle2)
                        update_tmp('angle3', angle3)

                        ctl.Update_Dac()

                    elif cmd == 'done':
                        break

            elif command == 'find_vca':
                #print(colored('find_vca', 'cyan', force_color=True))
                #ctl.Ensure_Spd_Mode('continuous')
                while rcvc() == 'get counts':
                    count = ctl.counts_fast()[0]
                    send_i(count)


            elif command == 'find_am_bias':
                #print(colored('find_am_bias', 'cyan', force_color=True))
                while rcvc() == 'get counts':
                    time.sleep(0.2)
                    count = ctl.counts_fast()[0]
                    send_i(count)

            elif command == 'find_am2_bias':
                #print(colored('find_am_bias', 'cyan', force_color=True))
                while rcvc() == 'get counts':
                    time.sleep(0.2)
                    count = ctl.counts_fast()[0]
                    send_i(count)



            elif command == 'verify_am_bias':
                #print(colored('verify_am_bias', 'cyan', force_color=True))
                for i in range(2):
                    rcvc()
                    time.sleep(0.2)
                    count = ctl.counts_fast()[0]
                    send_i(count)


            elif command == 'verify_am2_bias':
                #print(colored('verify_am_bias', 'cyan', force_color=True))
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
                #update_tmp('t0', 10)
                ctl.Gen_Gate()
                ctl.Update_Softgate()
                ctl.Ensure_Spd_Mode('gated')
                time.sleep(0.2)
                ctl.Download_Time(10000, 'verify_gate_ad_0')
                file_off = HW_CONTROL+"data/tdc/verify_gate_ad_0.txt"

                lf = ctl.fall_edge(file_off)
                target = (70-lf) % 312
                target = (target - 10) % 312
                update_tmp('gate_delay', target*40)
                ctl.Gen_Gate()
                sendc('done')


            elif command == 'check_gate_edge':
                print(colored('check_gate_edge', 'cyan', force_color=True))
                try:
                    msg = gate_edge_check()
                except Exception as e:
                    msg = f'fail: gate check errored ({e})'
                    print(colored(msg, 'red', force_color=True))
                print(colored(msg, 'green', force_color=True))
                sendc(msg[:250])


            elif command == 'set_gate_delay':
                print(colored('set_gate_delay', 'cyan', force_color=True))
                ps = rcv_i()
                applied = set_gate_delay(ps)
                print(colored(f'gate delay set to {applied} ps', 'green', force_color=True))
                sendc(f'gate {applied}')


            elif command == 'find_sp':
                print(colored('find_sp', 'cyan', force_color=True))
                t = get_tmp()
                t['t0'] = 10 #to have some space to the left
                t['soft_gate'] = 'off'
                save_tmp(t)
                ctl.Update_Softgate()
                ctl.Gen_Gate()

                # detection single pulse at shift_am 0
                print("measure and search single peak")
                shift_am, t0  = ctl.Measure_Sp(20000)
                #Set_t0(10+t0)
                update_tmp('t0', 10+t0)
                #t = get_tmp()

                #update_tmp('gate_delay', (t['gate_delay']-t0*20) % 12500)
                ctl.Gen_Gate()
                
                # send back shift_am value to alice
                send_i(shift_am)

                # detect single64 pulse and send to Alice
                #update_tmp('soft_gate', 'on')
                #ctl.Update_Softgate()
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
                #maxtime = gate1 + width
                input_file = HW_CONTROL+'data/tdc/verify_gate_double.txt'
                input_file2 = HW_CONTROL+'data/tdc/verify_gate_off.txt'
                status, peak0_x, peak1_x = ctl.verify_gate_double(input_file, input_file2, gate0, gate1, width, binstep)
                print(status, peak0_x, peak1_x)
                #if status == "success":
                w0 = 30
                w1 = 30
                pic0 = max(int(round(peak0_x - (w0 / 2))), 0)
                pic1 = max(int(round(peak1_x - (w1 / 2))), 0)

                ctl.set_Softgate(pic0, pic1, w0, w1)
                t['soft_gate0'] = pic0
                t['soft_gate1'] = pic1
                t['w0'] = w0
                t['w1'] = w1
                save_tmp(t)
                ctl.Update_Softgate()

                pic = HW_CONTROL+"data/calib_res/gate_double.png"
                with open(pic, 'rb') as f:
                    data = f.read()
                send_data(data)
                sendc(status)


            elif command == 'fs_b':
                print(colored('fs_b', 'cyan', force_color=True))
                backup = ctl.backup_params_bob()
                ctl.Ensure_Spd_Mode('gated')
                t = get_tmp()
                t['pm_mode'] = 'seq64'
                t['feedback'] = 'off'
                t['soft_gate'] = 'on'
                save_tmp(t)
                ctl.Update_Softgate()
                pm_shift_coarse = (t['pm_shift']//10) * 10
                for s in range(10):
                    t['pm_shift'] = pm_shift_coarse + s
                    save_tmp(t)
                    ctl.Update_Dac()
                    ctl.Download_Time(10000, 'pm_b_shift_'+str(s))
                pm_shift, hp = ctl.Find_Best_Shift('bob')
               # hp = hp+0.005
                update_tmp('angle0', 0)
                update_tmp('angle1', hp)
                update_tmp('angle2', -hp)
                update_tmp('angle3', 2*hp)
                ctl.Update_Dac()

                if pm_shift is not None:
                   update_tmp('pm_shift', pm_shift_coarse + pm_shift)
                   ctl.Update_Dac()
                else:
                   pm_shift=1000
                ctl.restore_params_bob(backup)
                send_i(pm_shift)


           
            elif command == 'fs_a':
                print(colored('fs_a', 'cyan', force_color=True))
                backup = ctl.backup_params_bob()
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
                pm_shift, hp = ctl.Find_Best_Shift('alice')
                if pm_shift is None:
                   pm_shift = 1000
                ctl.restore_params_bob(backup)
                send_i(pm_shift)
               # hp = hp-0.002
                send_d(hp)


           
            elif command == 'fd_b':
                print(colored('fd_b', 'cyan', force_color=True))
                backup = ctl.backup_params_bob()
                ctl.Ensure_Spd_Mode('gated')
                fiber_delay = ctl.Find_Opt_Delay_B()
                response = 'Find delay bob done'
                t = get_tmp()
                t['fiber_delay_mod'] = fiber_delay
                t['fiber_delay'] = fiber_delay % 80 + t['fiber_delay_long']
                save_tmp(t)
                ctl.restore_params_bob(backup)
                sendc('ok')
            
            elif command == 'fd_b_long':
                print(colored('fd_b_long', 'cyan', force_color=True))
                backup = ctl.backup_params_bob()
                ctl.Ensure_Spd_Mode('gated')
                fiber_delay = ctl.Find_Opt_Delay_B_long()
                response = 'Find delay bob done'
                t = get_tmp()
                t['fiber_delay_long'] = fiber_delay
                t['fiber_delay'] = t['fiber_delay_mod']%80 + fiber_delay*80
                save_tmp(t)
                ctl.restore_params_bob(backup)
                sendc('ok')
            

            elif command == 'fd_a':
                print(colored('fd_a', 'cyan', force_color=True))
                backup = ctl.backup_params_bob()
                ctl.Ensure_Spd_Mode('gated')
                fiber_delay = ctl.Find_Opt_Delay_A()
                ctl.restore_params_bob(backup)
                send_i(fiber_delay)




            
            elif command == 'fd_a_long':
                print(colored('fd_a_long', 'cyan', force_color=True))
                backup = ctl.backup_params_bob()
                ctl.Ensure_Spd_Mode('gated')
                fiber_delay_mod = rcv_i()
                fiber_delay = ctl.Find_Opt_Delay_A_long(fiber_delay_mod)
                ctl.restore_params_bob(backup)
                send_i(fiber_delay)
            
            elif command == 'fz_b':
                print(colored('fz_b', 'cyan', force_color=True))
                backup = ctl.backup_params_bob()
                ctl.Ensure_Spd_Mode('gated')
                zero_pos = ctl.Find_Zero_Pos_B_new()
                update_tmp('zero_pos', zero_pos)
                ctl.Update_Dac()
                ctl.restore_params_bob(backup)
                sendc('ok')
            


            elif command == 'fz_a':
                print(colored('fz_a', 'cyan', force_color=True))
                backup = ctl.backup_params_bob()
                ctl.Ensure_Spd_Mode('gated')
                print("received command fz_a")
                t = get_tmp()
                t['pm_mode'] = 'fake_rng'
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
                ctl.restore_params_bob(backup)
                sendc('ok')





            elif command == 'adjust_soft_gates':
                backup = ctl.backup_params_bob()
                t = get_tmp()
                t['pm_mode'] = 'true_rng'
                t['insert_zeros'] = 'on'
                t['feedback'] = 'on'
                t['soft_gate'] = 'on'
                save_tmp(t)
                ctl.Update_Softgate()
                ctl.Update_Dac()
                g0 = t['soft_gate0']
                g1 = t['soft_gate1']
                w0 = 30
                w1 = 30

                best_g0 = g0
                best_g1 = g1
                best_w0 = w0
                best_w1 = w1
                best_count = -1

                for delta in [-6,-3, 0, 3,6]:
                    g0_test = max(0, g0 + delta)
                    ctl.set_Softgate(g0_test, g1, w0, w1)
                    time.sleep(0.2)
                    count = ctl.counts_fast()[2]
                    if count > best_count:
                        best_count = count
                        best_g0 = g0_test

                t['soft_gate0'] = best_g0
                save_tmp(t)
                ctl.set_Softgate(best_g0, g1, w0, w1)

                best_count = -1
                for delta in [-6,-3, 0, 3,6]:
                    g1_test = max(0, g1 + delta)
                    ctl.set_Softgate(best_g0, g1_test, w0, w1)
                    time.sleep(0.2)
                    count = ctl.counts_fast()[1]
                    if count > best_count:
                        best_count = count
                        best_g1 = g1_test

                t['soft_gate1'] = best_g1
                save_tmp(t)

                best_w0 = w0
                max_count_w0 = ctl.counts_fast()[2]
                for delta in [3, 6]:
                    w0_test = max(0, w0 + delta)
                    ctl.set_Softgate(best_g0, best_g1, w0_test, w1)
                    time.sleep(0.2)
                    counts = ctl.counts_fast()[2]
                    if counts - max_count_w0 >= 50:
                        best_w0 = w0_test
                        max_count_w0 = counts

                best_w1 = w1
                max_count_w1 = ctl.counts_fast()[1]
                for delta in [3, 6]:
                    w1_test = max(0, w1 + delta)
                    ctl.set_Softgate(best_g0, best_g1, best_w0, w1_test)
                    time.sleep(0.2)
                    counts = ctl.counts_fast()[1]
                    if counts - max_count_w1 >= 50:
                        best_w1 = w1_test
                        max_count_w1 = counts

                ctl.set_Softgate(best_g0, best_g1, best_w0, best_w1)
                time.sleep(0.2)
                counts = ctl.counts_fast()

                if counts[1] > counts[2]:
                    i = 1
                else:
                    i = 0

                if i == 1:
                    for delta in range(0, 16, 2):
                        w1_test = max(0, best_w1 - delta)
                        ctl.set_Softgate(best_g0, best_g1, best_w0, w1_test)
                        time.sleep(0.2)
                        counts = ctl.counts_fast()
                        if abs(counts[1] - counts[2]) <= 60 or counts[1] < counts[2]:
                            best_w1 = w1_test
                            break
                    else:
                        best_w1 = w1_test
                else:
                    for delta in range(0, 16, 2):
                        w0_test = max(0, best_w0 - delta)
                        ctl.set_Softgate(best_g0, best_g1, w0_test, best_w1)
                        time.sleep(0.2)
                        counts = ctl.counts_fast()
                        if abs(counts[2] - counts[1]) <= 60 or counts[2] < counts[1]:
                            best_w0 = w0_test
                            break
                    else:
                        best_w0 = w0_test

                t = get_tmp()
                t['soft_gate0'], t['soft_gate1'] = best_g0, best_g1
                t['w0'], t['w1'] = best_w0, best_w1
                save_tmp(t)

                ctl.set_Softgate(best_g0, best_g1, best_w0, best_w1)
                ctl.restore_params_bob(backup)
                sendc('done')















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

                g0, g1, w0, w1 = t['soft_gate0'], t['soft_gate1'], t['w0'], t['w1']

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







            elif command == 'adjust_angles_a':
                while rcvc() == 'get counts':
                    counts = ctl.counts_fast()
                    count = abs(counts[1] + counts[2])
                   # count = ctl.diff_counts()
                    send_i(count)

            elif command == 'adjust_angles_b':

                t = get_tmp()
                base_angle1 = t['angle1']
                best_angle1 = base_angle1
                max_diff = 0

                for delta in [-0.006,-0.003, 0, 0.003,0.006]:
                    angle1_test = base_angle1 + delta
                    angle0 = 0.0
                    angle1 = angle1_test
                    angle2 = -angle1_test
                    angle3 = 2 * angle1_test

                    update_tmp('angle0', angle0)
                    update_tmp('angle1', angle1)
                    update_tmp('angle2', angle2)
                    update_tmp('angle3', angle3)
                    ctl.Update_Dac()
                    time.sleep(0.4)
                    counts = ctl.counts_fast()
                    diff = abs(counts[1] + counts[2])

 #                   diff = ctl.diff_counts()   
                    if diff > max_diff:
                        min_diff = diff
                        best_angle1 = angle1_test


                angle0 = 0.0
                angle1 = best_angle1
                angle2 = -best_angle1
                angle3 = 2 * best_angle1

                update_tmp('angle0', round(angle0, 3))
                update_tmp('angle1', round(angle1, 3))
                update_tmp('angle2', round(angle2, 3))
                update_tmp('angle3', round(angle3, 3))
                ctl.Update_Dac()
                sendc('adjust_angles_b done')


            elif command == 'single_peak':
                print(colored('single_peak', 'cyan', force_color=True))

                t = get_tmp()
                soft_gate_init = t['soft_gate']
                spd_mode_init = t['spd_mode']

                update_tmp('soft_gate', 'off')
                ctl.Update_Softgate()
                ctl.Ensure_Spd_Mode('continuous')
                time.sleep(0.2)

                ctl.Download_Time(10000, 'single_peak')
                ctl.plot_single_peak()
                update_tmp('soft_gate', soft_gate_init)
                ctl.Update_Softgate()
                ctl.Ensure_Spd_Mode(spd_mode_init)

                sendc('done')




            elif command == 'start':
                print(colored('start', 'cyan', force_color=True))
                t = get_tmp()
                t['pm_mode'] = 'true_rng'
                t['insert_zeros'] = 'on'
                t['feedback'] = 'on'
                t['soft_gate'] = 'on'
                save_tmp(t)
                ctl.Update_Softgate()
                ctl.Update_Dac()
                # Calibration is done: raise the QKD-ready flag. gc-bob
                # answers the node's next poll with HwReady and the node
                # resumes sessions. /tmp clears on reboot, so a power-cycle
                # leaves the flag down until the next full_init.
                open('/tmp/qkd_ready', 'w').close()
                sendc('ok')

            elif not command:
                print("Client disconnected.")
                break  # Exit loop if the client closes the connection
        
            else:
                print(f"[hws_bob] error: received unknown command from Alice")


            clear_flag_calibrating()


    except KeyboardInterrupt:
        print("Server stopped by keyboard interrupt.")
    except ConnectionResetError:
        # Client went away (reset OR clean EOF) mid-command; close and re-accept
        # instead of spinning on empty reads / flooding the log.
        print("Client disconnected mid-command. Waiting for new connection.")
    finally:
        try:
            conn.shutdown(socket.SHUT_RDWR)  # Properly shutdown connection
        except OSError:
            pass  # Ignore if connection is already closed
        conn.close()


