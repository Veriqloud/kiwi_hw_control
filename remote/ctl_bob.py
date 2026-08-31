#!/bin/python

#import subprocess, os, sys, argparse
import os, time
import numpy as np
#import datetime 
import mmap
import lib.gen_seq as gen_seq
import lib.cal as cal_lib
import lib.timing as timing
import lib.sysconst as sysconst
from lib.fpga import *
from lib.aurea.Aurea import Aurea
from scipy.optimize import curve_fit
import matplotlib.pyplot as plt

HW_CONTROL = '/home/vq-user/hw_control/'
LOG = '/home/vq-user/log/calibration/'


def backup_params_bob():
    t = get_tmp()
    backup = {
        'pm_mode': t['pm_mode'],
        'feedback': t['feedback'],
        'soft_gate': t['soft_gate'],
        'insert_zeros': t['insert_zeros']
    }
    return backup

def restore_params_bob(backup):
    t = get_tmp()
    t['pm_mode'] = backup['pm_mode']
    t['feedback'] = backup['feedback']
    t['soft_gate'] = backup['soft_gate']
    t['insert_zeros'] = backup['insert_zeros']
    save_tmp(t)
    Update_Softgate()
    Update_Dac()

def update_spd():
    t = get_tmp()
    aurea = Aurea()
    aurea.mode(t['spd_mode'])
    if (t['spd_mode'] == 'continuous'):
        aurea.deadtime(t['deadtime_cont'])
    else:
        aurea.deadtime(t['deadtime_gated'])
    aurea.close()


def Ensure_Spd_Mode(mode):
    t = get_tmp()
    if mode=='continuous':
        if (t['spd_mode'] != 'continuous'):
            aurea = Aurea()
            aurea.mode("continuous")
            aurea.deadtime(t['deadtime_cont'])
            time.sleep(0.5)
            aurea.close()
            t['spd_mode'] = 'continuous'
    elif mode=='gated':
        if (t['spd_mode'] != 'gated'):
            aurea = Aurea()
            aurea.mode("gated")
            aurea.deadtime(t['deadtime_gated'])
            time.sleep(0.5)
            aurea.close()
            t['spd_mode'] = 'gated'
    else:
        exit("wrong mode")
    save_tmp(t)

def get_spd_temp():
    aurea = Aurea()
    temp = aurea.temp()
    aurea.close()
    return temp

def Update_Dac():
    # update from tmp.txt
    # Generate sequences for dac0 and dac1 and write to device.
    # Update am_shift and pm_shift
    t = get_tmp()
    dac0 = gen_seq.dac0_off(64)

    if t['pm_mode'] == 'off':
        Write_Pm_Mode('fake_rng', t['feedback'])
        Write_Angles(0,0,0,0)
        dac1 = gen_seq.dac1_sample(np.zeros(64), t['pm_shift'])
    elif t['pm_mode'] == 'seq64':
        Write_Pm_Mode('seq64', t['feedback'])
        dac1 = gen_seq.dac1_sample(gen_seq.lin_seq_2(), t['pm_shift'])
    elif t['pm_mode'] == 'seq64tight':
        Write_Pm_Mode('seq64', t['feedback'])
        dac1 = gen_seq.dac1_sample_tight(gen_seq.lin_seq_2(), t['pm_shift'])
    elif t['pm_mode'] == 'fake_rng':
        Write_Pm_Mode('fake_rng', t['feedback'], t['insert_zeros'])
        Write_Angles(t['angle0'], t['angle1'], t['angle2'], t['angle3'])
        dac1 = gen_seq.dac1_sample(np.zeros(64), 0)
    elif t['pm_mode'] == 'true_rng':
        Write_Pm_Mode('true_rng', t['feedback'], t['insert_zeros'])
        Write_Angles(t['angle0'], t['angle1'], t['angle2'], t['angle3'])
        dac1 = gen_seq.dac1_sample(np.zeros(64), 0)
    
    Write_To_Dac(dac0, dac1)
    Write_Pm_Shift(t['pm_shift']%10, t['zero_pos'])
    print("Dac", t['pm_mode'], t['pm_shift'], t['feedback'], t['insert_zeros'])

def Update_Angles():
    t = get_tmp()
    Write_Angles(t['angle0'], t['angle1'], t['angle2'], t['angle3'])





def set_Softgate(g0, g1, w0, w1):
    t = get_tmp()
    command = 1 if t['soft_gate']=='off' else 2
    g0, g1, w0, w1 = max(0, g0), max(0, g1), max(0, w0), max(0, w1)
    Time_Calib_Reg(command, t['t0'], 0, g0, w0, g1, w1)





def Update_Softgate():
    t = get_tmp()
    command = 1 if t['soft_gate']=='off' else 2
    g0 = t['soft_gate0']
    g1 = t['soft_gate1']
    w = t['soft_gatew']
    w0 = t['w0']
    w1 = t['w1']
    Time_Calib_Reg(command, t['t0'], 0, g0, w0, g1, w1)
            

def Set_Pol(ch, vol):
    if ch>3:
        exit ("wrong channel in Set_Pol")
    if (vol<0) or (vol>5):
        exit ("wrong voltage in Set_Pol")
    Set_vol(ch,round(vol,2))

def Update_Pol():
    t = get_tmp()
    p = [t['pol0'], t['pol1'], t['pol2'], t['pol3']]
    for ch,vol in enumerate(p):
        Set_Pol(ch,round(vol,2))

#def Optimize_Pos():
#    t = get_tmp()
#    p = [t['pol0'], t['pol1'], t['pol2'], t['pol3']]
#    diff = np.zeros(4)
#    counts = np.zeros(4)
#    for ch in range(4):
#        Set_Pol(ch, p[ch] - 0.2)
#        time.sleep(0.2)
#        c1 = get_counts()
#        Set_Pol(ch, p[ch] + 0.2)
#        time.sleep(0.2)
#        c2 = get_counts()
#        diff[ch] = (c1-c2)
#        counts[ch] = (c1+c2)/2
#    snr = diff / np.sqrt(counts)
#    print(snr)



def Config_Fda():
    WriteFPGA()
    En_reset_jesd()
    Set_reg_powerup()
    Set_reg_plls()
    Set_reg_seq1() #seq1 include power, serdespll, dacpll
    Set_reg_seq2()
    Get_Id_Fda()
    check = Get_reg_monitor()
    while not check[2]:
        En_reset_jesd()
        Set_reg_powerup()
        Set_reg_plls()
        Set_reg_seq1() #seq1 include power, serdespll, dacpll
        Set_reg_seq2()
        check = Get_reg_monitor()

#-------------------------PULSE GATE APD-------------------------------

def Gen_Gate():
    # generate gate pulse for SPD
    # read delay from tmp.txt
    # calculate and update corse and fine delays
    t = get_tmp()
    delay = t['gate_delay']
    Set_t0(t['t0'])

    # Width of the electrical pulse that gates the APD, in 1.0417 ns pattern
    # slots. The Aurea OEM API has no gate-width call at all, so this is the
    # only width control there is. `.get` with a default keeps both keys
    # optional: tmp.txt needs no line until one is set, and get_tmp()
    # int()-parses them correctly when it is. 8 slots is 8.33 ns.
    width = t.get('gate_duty', 8)
    # Extra pattern offset, in slots, on top of the coarse position carried by
    # gate_delay. This is what walks the gate in 1.0417 ns steps; the coarse
    # field alone moves in fours.
    offset = t.get('gate_offset', 0)

    timestep = 3.383    # fine delay timestep in ps
    delay_au = round(delay/timestep)
    fine_max = 404      # corresponds to 1/3 of coarse delay
    coarse = delay_au // (fine_max*3)
    fine0_abs = delay_au % fine_max
    fine1_abs = int((delay_au%(fine_max*3)) >= fine_max) * fine_max
    fine2_abs = int((delay_au%(fine_max*3)) >= 2*fine_max) * fine_max

    with open(HW_CONTROL+"config/delayf.txt", 'r+') as f:
        df0 = int(f.readline())
        df1 = int(f.readline())
        df2 = int(f.readline())

        fine0 = fine0_abs - df0
        direction0 = 1 if fine0 > 0 else 0

        fine1 = fine1_abs - df1
        direction1 = 1 if fine1 > 0 else 0
        
        fine2 = fine2_abs - df2
        direction2 = 1 if fine2 > 0 else 0

        # slv_reg1[22:15] -- the old duty_val/delay_val pair -- is not read by
        # this bitstream. Gate width and coarse position come from the pattern
        # register; write_delay_master still carries the ODELAY fine delay,
        # which is unchanged.
        pattern = gate_pattern(width, 4*coarse + offset)
        write_gate_pattern(pattern)
        write_delay_master(0, 0, abs(fine0), direction0)
        write_delay_slaves(abs(fine1), direction1, abs(fine2), direction2)

        params_en()
        trigger_fine_master()
        trigger_fine_slv1()
        trigger_fine_slv2()

        f.seek(0)

        f.write(str(fine0_abs)+'\n')
        f.write(str(fine1_abs)+'\n')
        f.write(str(fine2_abs)+'\n')

    print("gate pulse delay set to", delay/1000, "ns, width", width,
          "slots, pattern", format(pattern, '#05x'))
    print(coarse, fine0, fine1, fine2)
    print(coarse, direction0, direction1, direction2)


def Find_Best_Shift(party):
    if party == 'alice':
       gc_comp = cal_lib.find_best_gc_comp('alice') 
    else:
       gc_comp = cal_lib.find_best_gc_comp('bob')
    best_shift = cal_lib.Best_Shift(party,gc_comp)
    half_period = cal_lib.plot_shift(party, best_shift, gc_comp)
    return best_shift, half_period
    
#---------------------------TDC CALIBRATION-----------------------------------------------

def Cont_Det(): 
    num_data = 2000
    Get_Stream(0x00000000+40,'/dev/xdma0_c2h_2',HW_CONTROL+'data/tdc/output_dp.bin',num_data)
    command =HW_CONTROL+'lib/test_tdc/tdc_bin2txt data/tdc/output_dp.bin '+HW_CONTROL+'data/tdc/histogram_dp.txt'
    s = subprocess.check_call(command, shell = True)

    time_gc = np.loadtxt(HW_CONTROL+"data/tdc/histogram_dp.txt",usecols=(1,2),unpack=True)
    int_time_gc = time_gc.astype(np.int64)
    duration = (max(int_time_gc[1])-min(int_time_gc[1]))*25
    click_rate = np.around(num_data/(duration*0.000000001),decimals=4)
    print("Number of count: ", str(len(int_time_gc[1])))
    print("Appro click rate: ", str(click_rate), "click/s")

def Download_Time(num_clicks, fileprefix="time"):
    print("downloading time tags into file", fileprefix+".txt")
    binfile = HW_CONTROL+'data/tdc/'+fileprefix+'.bin'
    txtfile = HW_CONTROL+'data/tdc/'+fileprefix+'.txt'
    Get_Stream(0x00000000+40,'/dev/xdma0_c2h_2',binfile, num_clicks)
    command =HW_CONTROL+"lib/test_tdc/tdc_bin2txt "+binfile+" "+txtfile
    s = subprocess.check_call(command, shell = True)


def Measure_Sp(num_clicks=20000):
    Ensure_Spd_Mode('continuous')
    Download_Time(num_clicks, fileprefix="histogram_sp")
    ref_time = np.loadtxt(HW_CONTROL+"data/tdc/histogram_sp.txt",usecols=1,unpack=True,dtype=np.int32)
    ref_time_arr = ref_time%1250
    #Find first peak of histogram
    first_peak = cal_lib.Find_First_Peak(ref_time_arr)
    print("First peak: ",first_peak)
    peak_target = 40
    # corse shift using AM (steps are periode/10, i.e. 1.25ns)
    shift_am = ((peak_target-first_peak)%625)/62.5
    print("shift_am", shift_am)
    shift_am_out = int(shift_am)%10
    # fine shift using t0 (t0 is added to the timestamps)
    t0 = round((peak_target - first_peak - shift_am_out*62.5) % 625)
    print("Suggested am_shift: ",shift_am_out)
    print("Suggested t0: ",t0)
    return shift_am_out, t0

def Measure_Sp64(num_clicks=20000):
    Ensure_Spd_Mode('gated')
    Download_Time(num_clicks, fileprefix='single64')
    data = np.loadtxt(HW_CONTROL+'data/tdc/single64.txt', usecols=(2,4))
    #gc = (data[:,0]%32)*2 + data[:,1]
    gc = (data[:,0]*2 + data[:,1]) % 64
    h, b = np.histogram(gc, bins=np.arange(65))
    print(h.argmax())
    coarse_shift = (1 - h.argmax()) % 64
    coarse_shift = coarse_shift*10
    print("Suggested coarse am_shift: ", coarse_shift)
    return int(coarse_shift)


def Verify_Gates(num_clicks=20000):
    Ensure_Spd_Mode('gated')
    t = get_tmp()
    t['pm_mode'] = 'seq64'
    t['feedack'] = 'off'
    save_tmp(t)
    Update_Dac()
    time.sleep(0.1)
    Download_Time(num_clicks, "histogram_dp")



#def Read_Count_InGates():
#    BaseAddr = 0x00000000
#    click0_count = Read(BaseAddr + 60)
#    hex_click0_count = click0_count.decode('utf-8').strip()
#    dec_click0_count = int(hex_click0_count, 16)
#    click1_count = Read(BaseAddr + 56)
#    hex_click1_count = click1_count.decode('utf-8').strip()
#    dec_click1_count = int(hex_click1_count, 16)
#    time.sleep(0.1)
#    ingates_count = dec_click0_count + dec_click1_count
#    return ingates_count

def Polarisation_Control():
    voltages = np.arange(1,3.5,0.5)
    bests = []
    for ch in range(4):
        c = []
        for v in voltages:
            Set_vol(ch,v)
            time.sleep(0.2)
            c.append(get_counts()[0])
        c = np.array(c)
        print(c)
        best = voltages[c.argmax()]
        bests.append(best)
        print("Best voltage on channel ", ch, "is", best)
        Set_vol(ch,round(best, 2))
        time.sleep(0.2)

    t = get_tmp()
    bests2 = []
    for ch in range(4):
        voltages = np.arange(bests[ch]-0.2,bests[ch]+0.2,0.1)
        c = []
        for v in voltages:
            Set_vol(ch,v)
            time.sleep(0.2)
            c.append(get_counts()[0])
        c = np.array(c)
        print(c)
        best = voltages[c.argmax()]
        bests2.append(best)
        print("Best voltage on channel ", ch, "is", best)
        t['pol'+str(ch)] = round(best, 2)
        Set_vol(ch,round(best, 2))
    save_tmp(t)

#-----------APPLY GATE--------------------------
#Apply the gate parameter to FPGA and take just the click inside the gate
#click rate is 50kHz, slower than rstidx(625kHz) -> use ref_time (reference to 5MHz) to define position
#in one 5MHz has 16 cycles of 80MHz (qclk cycle), 8 global counters
#clicks arrive at any qclk cycle, have to do modulo in FPGA
def Gated_Det():
    print("-----------------------------GATE INPUT----------------------")
    #Command_gate_aply set in Time_Calib_Reg
    Get_Stream(0x00000000+40,'/dev/xdma0_c2h_2',HW_CONTROL+'data/tdc/output_gated.bin',100000)
    command =HW_CONTROL+'test_tdc/tdc_bin2txt data/tdc/output_gated.bin '+HW_CONTROL+'data/tdc/histogram_gated.txt'
    s = subprocess.check_call(command, shell = True)

#Sweep the phase and the shift parameter, 4 phase*10shift -> value of shift
def Phase_Shift_Calib():
    #dpram_rng_max_addr
    Base_Addr = 0x00030000
    Write(Base_Addr + 28, 0x0008)
    #Write data to rng_dpram
    Base_seq0 = 0x00030000 + 0x2000  #Addr_axil_sequencer +   addr_dpram
    rngseq = 0x11111112
    Write(Base_seq0, rngseq)
    #Write_Dac1_shift
    for j in range(4):
        for i in range(10):
            Write_Dac1_Shift(2,0.125+j*0.125,-0.125+j*0.125,0 ,0,i)
            Get_Stream(0x00000000+40,'/dev/xdma0_c2h_2',HW_CONTROL+'data/tdc/clickout_'+str(10*j+i+1)+'.bin',5000) 
        Write_Dac1_Shift(2,0.125+j*0.125,-0.125+ j*0.125,0,0,0)

    for j in range(4):
        for i in range(10):
            command =HW_CONTROL+'test_tdc/tdc_bin2txt '+HW_CONTROL+'data/tdc/clickout_'+str(10*j+i+1)+".bin data/tdc/click_data_"+str(10*j+i+1)+".txt"
            s = subprocess.check_call(command, shell = True)


def Find_Opt_Delay_B():
    # generate a sequence of 64 angles where the first one stands out
    Write_To_Fake_Rng(gen_seq.seq_rng_single())
    t = get_tmp()
    t['pm_mode'] = 'fake_rng'
    t['feedback'] = 'on'
    t['soft_gate'] = 'on'
    t['insert_zeros'] = 'off'
    save_tmp(t)
    Update_Softgate()
    Update_Dac()

    Download_Time(50000, 'fd_b_single')
    data = np.loadtxt(HW_CONTROL+"data/tdc/fd_b_single.txt",usecols=(2,3,4), dtype=np.int64)
    gc = data[:,0] 
    r = data[:,1]
    q_pos = data[:,2]

    #gc0 = (gc[r==0]%40)*2 + q_pos[r==0] 
    #gc1 = (gc[r==1]%40)*2 + q_pos[r==1] 
    gc0 = (gc[r==0]*2 + q_pos[r==0])%80
    gc1 = (gc[r==1]*2 + q_pos[r==1])%80 

    bins = np.arange(81)
    h0, b = np.histogram(gc0, bins=bins)
    h1, b = np.histogram(gc1, bins=bins)

    h = h0-h1
    m = h.mean()
    h = h-m

    index = np.argmax(np.abs(h))
    np.savetxt(LOG+'fd_b.txt', np.abs(h))
    print("Fiber delay of Bob: ",index, " [q_bins]")
    return(int(index))

def Find_Opt_Delay_B_long():
    Write_To_Fake_Rng(gen_seq.seq_rng_block1())
    t = get_tmp()
    t['pm_mode'] = 'fake_rng'
    t['feedback'] = 'on'
    t['soft_gate'] = 'on'
    t['insert_zeros'] = 'off'
    save_tmp(t)
    Update_Softgate()
    Update_Dac()

    Download_Time(200000, 'fd_b_single_long')
    data = np.loadtxt(HW_CONTROL+"data/tdc/fd_b_single_long.txt",usecols=(2,3,4), dtype=np.int64)
    gc = data[:,0] 
    r = data[:,1]
    q_pos = data[:,2]
    
    #gc0 = (gc[r==0]*2 + q_pos[r==0] - t['fiber_delay_mod']) % (80*400)
    #gc1 = (gc[r==1]*2 + q_pos[r==1] - t['fiber_delay_mod']) % (80*400)
    gc0 = (gc[r==0]*2 + q_pos[r==0] - t['fiber_delay_mod']) % (80*400)
    gc1 = (gc[r==1]*2 + q_pos[r==1] - t['fiber_delay_mod']) % (80*400)

    bins = np.arange(0,80*401,80)
    h0, b = np.histogram(gc0, bins=bins)
    h1, b = np.histogram(gc1, bins=bins)

    h = h0-h1
    m = h.mean()
    h = h-m

    index = np.argmax(np.abs(h))
    np.savetxt(LOG+'fd_b_long.txt', np.abs(h))
    print("Fiber delay of Bob: ",index, " [64 q_bins]")
    return(int(index*64))

def Find_Zero_Pos_B():
    t = get_tmp()
    t['pm_mode'] = 'fake_rng'
    t['feedback'] = 'on'
    t['soft_gate'] = 'on'
    t['insert_zeros'] = 'on'
    t['zero_pos'] = 0
    save_tmp(t)
    Write_To_Fake_Rng(gen_seq.seq_rng_all_one())
    Update_Softgate()
    Update_Dac()
    time.sleep(0.5)
    counts = get_counts()
    if min(counts[1], counts[2])/counts[0] < 0.25:
        print("zeros pos found:", 0) 
        return 0
    
    Download_Time(50000, 'fz_b')
    data = np.loadtxt(HW_CONTROL+"data/tdc/fz_b.txt",usecols=(2,3,4), dtype=np.int64)

    gc = data[:,0] 
    r = data[:,1]
    q_pos = data[:,2]
    #gc0 = (gc[r==0]%32)*2 + q_pos[r==0] 
    #gc1 = (gc[r==1]%32)*2 + q_pos[r==1] 
    gc0 = (gc[r==0]*2 + q_pos[r==0])%64 
    gc1 = (gc[r==1]*2 + q_pos[r==1])%64 
    bins = np.arange(65)
    h0, b = np.histogram(gc0, bins=bins)
    h1, b = np.histogram(gc1, bins=bins)
    h = abs(h0-h1)
    peakpos = np.argmax(h) 
    zeros_pos = (t['fiber_delay_mod'] - 2 - peakpos) % 16
    print("zeros pos found:", zeros_pos) 
    return zeros_pos 


def Find_Zero_Pos_B_new():
    t = get_tmp()
    t['pm_mode'] = 'fake_rng'
    t['feedback'] = 'on'
    t['soft_gate'] = 'on'
    t['insert_zeros'] = 'on'
    save_tmp(t)

    Write_To_Fake_Rng(gen_seq.seq_rng_all_one())
    Update_Softgate()

    initial_zero_pos = t['zero_pos']
    save_tmp(t)
    Update_Dac()
    time.sleep(0.3)

    counts = get_counts()
    c1 = counts[1]
    c2 = counts[2]

    if c1 == 0 or c2 == 0:
        ratio = 0
    else:
        ratio = max(c1 / c2, c2 / c1)

    if ratio > 3:
        print(f"Initial zero_pos {initial_zero_pos} is good, ratio={ratio:.2f}")
        return initial_zero_pos

    max_ratio = ratio
    best_zero_pos = initial_zero_pos

    for zp in range(16):
        t['zero_pos'] = zp
        save_tmp(t)
        Update_Dac()
        time.sleep(0.3)

        counts = get_counts()
        c1 = counts[1]
        c2 = counts[2]

        if c1 == 0 or c2 == 0:
            ratio = 0
        else:
            ratio = max(c1 / c2, c2 / c1)

        if ratio > 3:
            print(f"Found zero_pos {zp} with good ratio={ratio:.2f}")
            return zp

        if ratio > max_ratio:
            max_ratio = ratio
            best_zero_pos = zp

    print(f"Best zero_pos found after full scan: {best_zero_pos}, ratio={max_ratio:.2f}")
    return best_zero_pos



def Find_Zero_Pos_A(fiber_delay_mod):
    t = get_tmp()
    t['feedback'] = 'on'
    t['soft_gate'] = 'on'
    t['insert_zeros'] = 'off'
    save_tmp(t)
    Write_To_Fake_Rng(gen_seq.seq_rng_zeros())
    Update_Softgate()
    Update_Dac()
    time.sleep(0.5)
    counts = get_counts()
    if min(counts[1], counts[2])/counts[0] < 0.25:
        print("Zeros pos found:", 0) 
        return 0
    
    Download_Time(50000, 'fz_a')
    data = np.loadtxt(HW_CONTROL+"data/tdc/fz_a.txt",usecols=(2,3,4), dtype=np.int64)

    gc = data[:,0] 
    r = data[:,1]
    q_pos = data[:,2]
    #gc0 = (gc[r==0]%32)*2 + q_pos[r==0] 
    #gc1 = (gc[r==1]%32)*2 + q_pos[r==1] 
    gc0 = (gc[r==0]*2 + q_pos[r==0])%64 
    gc1 = (gc[r==1]*2 + q_pos[r==1])%64 
    bins = np.arange(65)
    h0, b = np.histogram(gc0, bins=bins)
    h1, b = np.histogram(gc1, bins=bins)
    h = abs(h0-h1)
    peakpos = np.argmax(h) 
    zeros_pos = (fiber_delay_mod - 1 - peakpos) % 16
    print("zeros pos found:", zeros_pos) 
    return int(zeros_pos )


def calculate_ratio():
    counts = get_counts()
    c1 = counts[1]
    c2 = counts[2]
    if c1 == 0 or c2 == 0:
        return 0
    return max(c1 / c2, c2 / c1)



def diff_counts():
    max_diff = 0
    last_significant_diff_time = time.time()
    start_time = time.time()

    while time.time() - start_time < 15:
        counts = get_counts()
        c1 = counts[1]
        c2 = counts[2]
        diff = abs(c1 - c2)

        if diff > max_diff:
            if diff - max_diff > 20:
                last_significant_diff_time = time.time()
            max_diff = diff

        if time.time() - last_significant_diff_time > 3:
            break


    return max_diff





#def Check_Zeros_Pos():
#    t = get_tmp()
#    t['pm_mode'] = 'fake_rng'
#    t['feedback'] = 'on'
#    t['soft_gate'] = 'on'
#    t['insert_zeros'] = 'on'
#    t['zero_pos'] = 8
#    time.sleep(1)
#    save_tmp(t)
#    Update_Softgate()
#    Update_Dac()
#    
#    Write_To_Fake_Rng(gen_seq.seq_rng_all_one())
#    Download_Time(50000, 'fz_b_check')
#    data = np.loadtxt("data/tdc/fz_b_check.txt",usecols=(2,3,4), dtype=np.int64)

def Find_Opt_Delay_A():
    # generate a sequence of 64 angles where the first one stands out
    t = get_tmp()
    t['pm_mode'] = 'fake_rng'
    t['feedback'] = 'on'
    t['soft_gate'] = 'on'
    t['insert_zeros'] = 'off'
    save_tmp(t)
    Update_Softgate()
    Update_Dac()
    Write_To_Fake_Rng(gen_seq.seq_rng_zeros())

    #Get detection result
    Download_Time(50000, 'fd_a_single')
    #Process to get delay val

    data = np.loadtxt(HW_CONTROL+"data/tdc/fd_a_single.txt",usecols=(2,3,4), dtype=np.int64)
    gc = data[:,0] 
    r = data[:,1]
    q_pos = data[:,2]

    #gc0 = (gc[r==0]%40)*2 + q_pos[r==0] 
    #gc1 = (gc[r==1]%40)*2 + q_pos[r==1] 
    gc0 = (gc[r==0]*2 + q_pos[r==0])%80 
    gc1 = (gc[r==1]*2 + q_pos[r==1])%80 

    bins = np.arange(81)
    h0, b = np.histogram(gc0, bins=bins)
    h1, b = np.histogram(gc1, bins=bins)

    h = h0-h1
    m = h.mean()
    h = h-m

    index = np.argmax(np.abs(h))
    np.savetxt(LOG+'fd_a.txt', np.abs(h))
    print("Fiber delay of Alice: ",index, " [q_bins]")
    return(int(index))

def Find_Opt_Delay_A_long(fiber_delay_mod):
    # generate a sequence of 64 angles where the first one stands out
    t = get_tmp()
    t['pm_mode'] = 'fake_rng'
    t['feedback'] = 'on'
    t['soft_gate'] = 'on'
    t['insert_zeros'] = 'off'
    save_tmp(t)
    Update_Softgate()
    Update_Dac()
    Write_To_Fake_Rng(gen_seq.seq_rng_zeros())

    Download_Time(200000, 'fd_a_single_long')
    data = np.loadtxt(HW_CONTROL+"data/tdc/fd_a_single_long.txt",usecols=(2,3,4), dtype=np.int64)
    gc = data[:,0] 
    r = data[:,1]
    q_pos = data[:,2]

    #gc0 = (gc[r==0]*2 + q_pos[r==0] - fiber_delay_mod) % (80*400)
    #gc1 = (gc[r==1]*2 + q_pos[r==1] - fiber_delay_mod) % (80*400)
    gc0 = (gc[r==0]*2 + q_pos[r==0] - fiber_delay_mod) % (80*400)
    gc1 = (gc[r==1]*2 + q_pos[r==1] - fiber_delay_mod) % (80*400)

    bins = np.arange(0,80*401,80)
    h0, b = np.histogram(gc0, bins=bins)
    h1, b = np.histogram(gc1, bins=bins)

    h = h0-h1
    m = h.mean()
    h = h-m

    np.savetxt(LOG+'fd_a_long.txt', np.abs(h))
    index = np.argmax(np.abs(h))
    print("Fiber delay of Alice: ",index, " [64 q_bins]")
    return(int(index))

def Test_delay():
    Base_Addr = 0x00030000
    Write(Base_Addr + 28, 0x4e20) #for 0.5ms distance
    Base_seq0 = 0x00030000 + 0x2000  #Addr_axil_sequencer +   addr_dpram
    file0 = open(HW_CONTROL+'data/fda/seqrng_gen/SeqRng.txt','r') #Use this file for 0.5ms distance
    counter = 0
    for l in file0.readlines():
        counter += 1
        Base_seq = str(hex(int(Base_seq0) + (counter-1)*4))
        Write(Base_seq, l)
        #print(Base_seq)
        #print(l)
    print("Set rng sequence for DAC1 finished")
    file0.close()


#def fall_edge(file_path, start_range=200, end_range=900):
#    data = np.loadtxt(os.path.expanduser(file_path), usecols=1)
#    bins = np.arange(0, 1251, 2) - 1
#    hist, _ = np.histogram(data % 1250, bins=bins)
#    index = bins[:-1] + 1
#    mask = (index >= start_range) & (index <= end_range)
#    index_filt = index[mask]
#    amp_filt = hist[mask]
#    lf = 724  # default
#    for i in range(1, len(amp_filt)):
#        if amp_filt[i] < amp_filt[i - 1]:
#            lf = index_filt[i]
#    return lf

def fall_edge(file_path):
    data = np.loadtxt(os.path.expanduser(file_path), usecols=1)
    # ignore the first 2000 clicks (because it seems that there are leftovers)
    data = data[2000:]
    bins = np.arange(0, 624, 2) 
    hist, _ = np.histogram(data % 624, bins=bins)

    data_for_save = np.zeros((len(hist), 2), dtype=int)
    data_for_save[:,0] = hist

    # take columns with at least 10 clicks
    hist = hist//10
    # delete zero points in front of rising edge
    for i in range(len(hist)-1):
        if hist[i] == 0:
            if hist[i+1:i+10].any() > 0:
                hist[i] = 1
    zeros = hist == 0
    # get the first zero point
    d = zeros[1:]*1 - zeros[:-1]*1
    pos = np.where(d == 1)[0][0]

    data_for_save[pos,1] = 1
    np.savetxt(LOG+'fall_edge.txt', data_for_save, fmt='%d')
    return pos

#    index = bins[:-1] + 1
#    #mask = (index >= start_range) & (index <= end_range)
#    index_filt = index[mask]
#    amp_filt = hist[mask]
#    lf = 724  # default
#    for i in range(1, len(amp_filt)):
#        if amp_filt[i] < amp_filt[i - 1]:
#            lf = index_filt[i]
#    return lf


def Scan_Gate(coarse_step=400, fine_step=100, num_clicks=10000, verbose=True):
    """Sweep the physical SPD gate over a full period and keep the best position.

    `ad` aligns the gate window to a fixed place in the timing frame and leaves
    it there, so whichever comb peaks happen to fall inside are the ones that get
    gated -- and they need not be the strong ones. This looks instead at what the
    gate actually captures.

    Scored as (count rate) x (fraction of the histogram sitting in peaks).
    Download_Time collects a FIXED number of clicks, so its histogram gives the
    shape but says nothing about the level; the level has to come from the
    counters. Use the unwindowed `total`: click0/click1 count only inside the
    soft_gate0/soft_gate1 windows and read zero whenever the gate moves away from
    them, whatever `soft_gate` is set to, which makes them useless for a scan.

    num_clicks stays at 10000: `dma_from_device -c` rejects smaller requests
    (exit 128), and every other call site in the tree uses 10000 or more.

    Returns (best_delay_ps, rate, peak_fraction).
    """
    t = get_tmp()
    entry_delay = t['gate_delay']
    entry_soft = t['soft_gate']
    update_tmp('soft_gate', 'off')
    Update_Softgate()
    Ensure_Spd_Mode('gated')

    def score_at(delay):
        update_tmp('gate_delay', int(delay) % 12500)
        Gen_Gate()
        time.sleep(0.3)
        rate = float(np.mean([get_counts()[0] for _ in range(3)]))
        Download_Time(num_clicks, 'scan_gate')
        data = np.loadtxt(HW_CONTROL + 'data/tdc/scan_gate.txt', usecols=1) % 625
        h, _ = np.histogram(data, bins=np.arange(0, 625, 2))
        # The pedestal has to be measured INSIDE the open window. Gated, most of
        # the period is hard zero, so a median over the whole histogram is 0 and
        # every occupied bin then counts as peak -- the fraction saturates at 1.0
        # and the score degenerates into the raw rate.
        openbins = h[h > 0]
        base = float(np.median(openbins)) if openbins.size else 0.0
        thr = base + 4 * np.sqrt(max(base, 1.0))
        frac = float(np.clip(h - base, 0, None)[h > thr].sum() / max(h.sum(), 1))
        return rate * frac, rate, frac

    best = None
    try:
        for d in range(0, 12500, coarse_step):
            s, rate, frac = score_at(d)
            if verbose:
                print(f"  scan_gate coarse {d:>6} ps -> rate {rate:7.0f} "
                      f"peak_frac {frac:5.3f} score {s:8.0f}")
            if best is None or s > best[0]:
                best = (s, d, rate, frac)

        centre = best[1]
        for d in range(centre - coarse_step, centre + coarse_step + 1, fine_step):
            s, rate, frac = score_at(d)
            if verbose:
                print(f"  scan_gate fine   {d % 12500:>6} ps -> rate {rate:7.0f} "
                      f"peak_frac {frac:5.3f} score {s:8.0f}")
            if s > best[0]:
                best = (s, d % 12500, rate, frac)
    except Exception:
        # leave the gate where it was rather than half-scanned
        update_tmp('gate_delay', entry_delay)
        Gen_Gate()
        update_tmp('soft_gate', entry_soft)
        Update_Softgate()
        raise

    update_tmp('gate_delay', int(best[1]))
    Gen_Gate()
    update_tmp('soft_gate', entry_soft)
    Update_Softgate()
    time.sleep(0.2)
    return int(best[1]), best[2], best[3]


def verify_gate_double(input_file, input_file2, gate0, gate1, width, binstep=2):
    if width == 0:
        width = 30
    raw1 = np.loadtxt(input_file, usecols=1) % 625
    data1 = raw1

    raw2 = np.loadtxt(input_file2, usecols=1) % 625
    data2 = raw2

    bins = np.arange(0, 625) - 1
    h1, _ = np.histogram(data1, bins=bins)
    h2, _ = np.histogram(data2, bins=bins)
    centers = bins[:-1] + binstep / 2

    idx0 = np.where((centers >= gate0) & (centers < gate0 + width))[0]
    idx1 = np.where((centers >= gate1) & (centers < gate1 + width))[0]

    bg0_range = np.where((centers >= gate0 - width) & (centers < gate0 + 2 * width))[0]
    bg0_mask = np.setdiff1d(bg0_range, idx0)
    background_max0 = h1[bg0_mask].max() if bg0_mask.size else 0

    bg1_range = np.where((centers >= gate1 - width) & (centers < gate1 + 2 * width))[0]
    bg1_mask = np.setdiff1d(bg1_range, idx1)
    background_max1 = h1[bg1_mask].max() if bg1_mask.size else 0

    peak0 = h1[idx0].max() if idx0.size else 0
    peak1 = h1[idx1].max() if idx1.size else 0

    peak0_local_index = np.argmax(h1[idx0]) if idx0.size else None
    peak1_local_index = np.argmax(h1[idx1]) if idx1.size else None

    peak0_x = centers[idx0[peak0_local_index]] if idx0.size else None
    peak1_x = centers[idx1[peak1_local_index]] if idx1.size else None

    print(f'peak0 = {peak0} at x = {peak0_x}, background0 = {background_max0}')
    print(f'peak1 = {peak1} at x = {peak1_x}, background1 = {background_max1}')
    # === PLOT  ===
    plt.figure()
    plt.plot(centers, h2, label=os.path.basename('off'), color='blue', linestyle='--')
    plt.plot(centers, h1, label=os.path.basename('double'), color='red')
    plt.axvline(peak0_x - width/2, color='orange', linestyle='--', label='Gate0')
    plt.axvline(peak0_x + width/2, color='orange', linestyle='--')
    plt.axvline(peak1_x - width/2, color='purple', linestyle='--', label='Gate1')
    plt.axvline(peak1_x + width/2, color='purple', linestyle='--')
    plt.ylim(0)
    plt.xlim(0)
    plt.xlabel("Time bin (ns)")
    plt.ylabel("Counts")
    plt.legend()
    os.makedirs(HW_CONTROL+"data/calib_res", exist_ok=True)
    plt.savefig(HW_CONTROL+"data/calib_res/gate_double.png", dpi=300)
    plt.close()

    if peak0 > (background_max0 + 20) and peak1 > (background_max1 + 20):
        status = "success"
    elif (peak0 - (background_max0 + 20)) > 200 or (peak1 - (background_max1 + 20)) > 200:
        status = "success"
    else:
        status = "fail"

    if status == "fail":

        idx0_fallback = np.where((centers >= 0) & (centers <= 150))[0]
        idx1_fallback = np.where((centers >= 450) & (centers <= 623))[0]

        peak0 = h1[idx0_fallback].max() if idx0_fallback.size else 0
        peak1 = h1[idx1_fallback].max() if idx1_fallback.size else 0

        peak0_local_index = np.argmax(h1[idx0_fallback]) if idx0_fallback.size else None
        peak1_local_index = np.argmax(h1[idx1_fallback]) if idx1_fallback.size else None

        peak0_x = centers[idx0_fallback[peak0_local_index]] if idx0_fallback.size else None
        peak1_x = centers[idx1_fallback[peak1_local_index]] if idx1_fallback.size else None
   
    return status, peak0_x, peak1_x















#-------------------------FIND GATES------------------------------------------
#
# Gate placement computed from the single-pulse histogram instead of searched
# for.  One pulse per 25 ns frame arrives four times -- p0, p0+t1, p0+t2,
# p0+t1+t2 -- because Bob's unbalanced Mach-Zehnder splits it t1 apart and its
# two complementary output ports are recombined onto the one detector through
# the 2 m delay t2.  Those two numbers fix everything downstream:
#
#   t1  the separation Alice's pulse pair must have for the comb to merge, so
#       qdistance follows from it in closed form (lib/timing.qdistance_for_arm)
#   t2  the separation of the two interfering peaks, hence how wide the APD
#       gate has to open and where the two soft gates go
#   p0  where the comb sits in the timing frame, hence am_shift, t0 and
#       gate_delay
#
# t1, t2 and the APD constants are properties of the hardware, not of the
# tuning, so they are measured once and kept in config/system_constants.json
# (lib/sysconst); a later run reads them back and only re-locates p0.
#
# Everything here works in the frame the link actually runs in -- gated.  The
# free-running detector timestamps the same photon several ns earlier or later
# than the gated one, which is measured here as `mode_offset` and is large
# enough to put a gate on the wrong peak if it is ignored.

FG_CLICKS = 20000           # clicks per analysis histogram
FG_CLICKS_SWEEP = 10000     # clicks per step of the gate-width sweep
FG_SKIP = 2000              # leading clicks to drop; the first ones are stale
FG_MIN_RATE = 150           # counts/0.1 s: below this Download_Time stalls
FG_MIN_RATE_SWEEP = 40      # a narrow gate passes little; just download slower
FG_BINW = 2                 # units per histogram bin (40 ps)
FG_TARGET = 60              # where the first gated peak is put, in units
FG_GATE_WIDTHS = (6, 7, 8, 9, 10)   # gate widths to characterise, in slots
FG_OPEN_GATE = 12           # slots: all ones, the gate never closes
FG_SOFT_W = 30              # soft gate width in units, as elsewhere in the tree
FG_MIN_RATIO = 2.0          # in-window double/off below which gates are not good
FG_MAX_FIT = 5.0            # units: comb fit worse than this is a placement failure
FG_PLACED_TOL = 15          # units: how far the gated peak may sit from the target
# Units of clearance a soft window keeps from a gate edge. `support` finds the
# window by thresholding the pedestal, which reads a few units wide at each
# shoulder, so a measured clearance is optimistic by about that much -- and the
# shoulder is where detection efficiency is poor anyway. 10 units (200 ps)
# covers the bias and keeps the light off the slope.
FG_EDGE_SLACK = 10
FG_CENTRE_TOL = 5           # units: window-centre error worth correcting
FG_CENTRE_TRIES = 3         # attempts at centring the gate on the two ports
# Which peak the target refers to. Stored with the prediction residual, since a
# residual measured against a different choice of reference peak is meaningless.
FG_CONVENTION = 'portA_first'


class Link:
    """The Alice end of find_gates, as the three calls the routine needs.

    hws_bob defines sendc/rcvc/send_data as closures over the accepted socket,
    so the routine cannot import them; it gets them passed in instead and the
    whole exchange stays readable here rather than in the dispatch chain.
    """

    def __init__(self, sendc, rcvc, send_data):
        self._sendc = sendc
        self._rcvc = rcvc
        self._send_data = send_data

    def ask(self, request):
        """Tell Alice to do something and wait for her acknowledgement."""
        self._sendc(request)
        return self._rcvc()

    def report(self, text):
        self.ask('report ' + text[:200])

    def finish(self, status, picture=b''):
        """End the exchange: the verdict, then the diagnostic plot.

        The verdict goes first and the plot always follows, so Alice can read
        both unconditionally -- a failure that produced no plot still sends an
        empty one rather than leaving her blocked on a read that never comes.
        """
        self._sendc('done ' + status[:200])
        self._send_data(picture or b'')


def Fg_Rate(n=3):
    return float(np.mean([get_counts()[0] for _ in range(n)]))


def Fg_Histogram(num_clicks, prefix, frame, binw=FG_BINW, min_rate=FG_MIN_RATE):
    """Fold `num_clicks` fresh time tags into one `frame`.

    Refuses instead of hanging when there is too little light: Download_Time
    shells out to `dma_from_device -c`, which waits for its full count and
    never returns if the clicks do not arrive -- and the stray reader it leaves
    behind survives a restart of hw.service and blocks every later read.
    """
    rate = Fg_Rate()
    if rate < min_rate:
        raise RuntimeError(
            f"only {rate:.0f} counts/0.1 s -- too few for a {num_clicks} click "
            f"download, which would stall. Check the laser, vca, am_bias and "
            f"that the APD gate is open.")
    Download_Time(num_clicks, prefix)
    t = np.loadtxt(HW_CONTROL + 'data/tdc/' + prefix + '.txt', usecols=1)
    if len(t) > FG_SKIP * 2:
        t = t[FG_SKIP:]
    return timing.fold(t, frame, binw), rate


def Fg_Set_Gate(delay_ps, width_slots):
    """Put the APD gate at `delay_ps` with a `width_slots` wide pattern."""
    update_tmp('gate_delay', int(round(delay_ps)) % 12500)
    update_tmp('gate_duty', int(width_slots))
    update_tmp('gate_offset', 0)
    Gen_Gate()
    time.sleep(0.3)


def Fg_Measure_Window(h, binw=FG_BINW):
    """Where the APD gate window is and how wide it opens, from one histogram.

    Gated, the histogram is hard zero outside the window and carries the
    pedestal inside it, so the pedestal maps the window directly -- no CW light
    and no am_bias excursion off the null, which would have to be undone again.

    Returns None when the histogram is not gated at all (nothing reads zero),
    which is what a 12-slot all-ones pattern looks like.
    """
    # Filter Alice's pulses out first: they sit inside the window and are many
    # times taller than the pedestal that maps it, so every width taken against
    # the raw histogram would measure a pulse instead of the gate.
    prof = timing.pedestal_profile(h)
    sup = timing.support(prof, binw)
    if sup is None:
        return None
    start, width = sup
    n = len(prof)
    lo = int(round(start / binw))
    inside = np.array([prof[(lo + i) % n] for i in range(int(round(width / binw)))])
    peak = float(inside.max()) if inside.size else 0.0
    if peak <= 0:
        return None
    # Half-height width, not the full support: the gate profile is a sharp hump
    # rather than a plateau, and this is the width over which a pulse is still
    # detected with useful efficiency.
    half = float((inside > 0.5 * peak).sum()) * binw
    # Centroid rather than the middle of the support, which the soft shoulders
    # of the hump would bias.
    idx = np.arange(len(inside))
    centre = (start + float((idx * inside).sum() / inside.sum()) * binw + binw / 2.0)
    return {
        'start': float(start),
        'support': float(width),
        'half': half,
        'top_hat': float(inside.sum() / peak * binw),
        'centre': float(centre % (n * binw)),
    }


def Fg_Peaks(h, nmax=4, binw=FG_BINW):
    peaks, base = timing.find_peaks(h, binw=binw, nmax=nmax)
    return peaks, base


def Fg_Gate_Table(const, widths=FG_GATE_WIDTHS, delay_ps=None):
    """Measure what window each gate width opens, and record it.

    Runs with whatever light is present -- the pedestal is the probe -- so it
    needs no cooperation from Alice, and the result is a property of the board
    that later runs read back instead of repeating.
    """
    t = get_tmp()
    delay_ps = t['gate_delay'] if delay_ps is None else delay_ps
    measured = {}
    for w in widths:
        Fg_Set_Gate(delay_ps, w)
        try:
            h, rate = Fg_Histogram(FG_CLICKS_SWEEP, 'fg_gate', timing.PERIOD,
                                  min_rate=FG_MIN_RATE_SWEEP)
        except RuntimeError as e:
            print(f"  gate {w:>2} slots: {e}")
            continue
        win = Fg_Measure_Window(h)
        if win is None:
            print(f"  gate {w:>2} slots: not gated (window covers the period)")
            continue
        measured[w] = win
        # The decision is taken on the support -- the full extent over which the
        # gate passes anything. It is the only one of the three that rises
        # monotonically with the pattern width when measured against the
        # pedestal; the half-height width of a hump that is part gate profile
        # and part afterpulse decay does not, and reading a width off it picked
        # gates by noise.
        sysconst.put_gate_window(const, w, win['support'], half=win['half'],
                                 top_hat=win['top_hat'], rate=rate)
        print(f"  gate {w:>2} slots: passes {win['support'] * timing.UNIT_PS / 1000:5.2f} ns, "
              f"half height {win['half'] * timing.UNIT_PS / 1000:5.2f} ns, "
              f"top hat {win['top_hat'] * timing.UNIT_PS / 1000:5.2f} ns, "
              f"rate {rate:.0f}")
    return measured


def Fg_Centre_At_Zero(width_slots, probe_delay_ps=0):
    """Where the gate window sits when gate_delay and t0 are both zero.

    One measurement turns gate placement into arithmetic: the window centre
    moves with gate_delay one-for-one, and t0 shifts every time tag, so putting
    the window at unit C is

        gate_delay = ((C - t0 - centre_at_zero) mod 625) * 20 ps

    which replaces `ad`, whose falling-edge target was fixed in the timing frame
    and took whichever comb peaks happened to fall inside it.
    """
    t = get_tmp()
    Fg_Set_Gate(probe_delay_ps, width_slots)
    h, _ = Fg_Histogram(FG_CLICKS_SWEEP, 'fg_centre', timing.PERIOD)
    win = Fg_Measure_Window(h)
    if win is None:
        raise RuntimeError(f"the {width_slots} slot gate does not close the "
                           f"period, so its centre cannot be located")
    centre0 = (win['centre'] - t['t0'] - probe_delay_ps / timing.UNIT_PS) % timing.PERIOD
    return centre0, win


def Fg_Gate_Delay(centre_units, t0, centre_at_zero):
    """gate_delay in ps that puts the window centre at `centre_units`."""
    return ((centre_units - t0 - centre_at_zero) % timing.PERIOD) * timing.UNIT_PS


def Fg_Gate_Clearance(h, ports, soft_w):
    """Where the APD gate window sits, and how close its edges come to the light.

    Returns (window, clearance), `clearance` being the units between each port's
    soft window and the nearer edge of the physical gate -- negative when that
    edge cuts into it. None when the histogram is not gated at all, which is
    what an all-ones pattern looks like.

    The window comes from the support, which over-reads each shoulder by a few
    units, so clearance is an optimistic bound; FG_EDGE_SLACK is what covers it.

    The latency between Alice's dac0 and the TTL gate pattern is not the same
    after every power cycle, so this is measured with the width that will be
    used rather than predicted from the centre_at_zero probe.
    """
    win = Fg_Measure_Window(h)
    if win is None:
        return None
    start, width = win['start'], win['support']
    clear = []
    for p in ports:
        into = (p - start) % timing.PERIOD
        clear.append(min(into, width - into) - soft_w / 2.0)
    return win, clear


def Fg_Emission_Slots(am_mode, am_shift, qdistance, am_edge):
    """Rising dac0 crossings of `am_mode`, in slots -- where Alice's light leaves.

    Read off the generated codes rather than hard-coded, so a change to the edge
    shapes or to qdistance is picked up automatically.  The single and double
    patterns put their edges at different places inside their periods, and that
    difference is exactly what lets a measurement made on the single pulse place
    the double-pulse comb.
    """
    if am_mode == 'single':
        codes = gen_seq.dac0_single(64, am_shift, am_edge)
    elif am_mode == 'double':
        codes = gen_seq.dac0_double(64, qdistance, am_shift)
    else:
        raise ValueError(f"no emission geometry for am_mode {am_mode!r}")
    return timing.rising_crossings(codes)


def Fg_Refine_Window(h_double, h_off, nominal, soft_w, reach=None, step=2):
    """Slide one soft gate onto the light, within half a window of where the
    geometry put it.

    The geometry places the window on the peak's centroid, which is the right
    thing to derive but not quite where the counts are: the carved peak rises
    fast and decays slowly, so a window centred on its centroid clips the
    leading edge and buys tail instead -- worth 25% of the signal on the first
    port as measured on system1.

    Maximises the excess over the am-off reference rather than the raw counts,
    so the window is drawn to the light the modulator adds rather than to
    whatever leaks through anyway. The reach is bounded to half a window: this
    trims a placement, it cannot wander onto the neighbouring comb peak.
    """
    reach = soft_w // 2 if reach is None else reach
    scale = (h_double.sum() / max(h_off.sum(), 1.0)) if h_off is not None else 0.0

    def excess(start):
        got = Fg_Window_Sum(h_double, start, soft_w)
        if h_off is None:
            return got
        return got - Fg_Window_Sum(h_off, start, soft_w) * scale

    best = max(range(int(nominal) - reach, int(nominal) + reach + 1, step),
               key=excess)
    return best % timing.PERIOD, excess(best), excess(int(nominal))


def Fg_Choose_Gate_Width(candidates, centre_units, starts, t0, centre0_ref,
                        ref_slots, soft_w):
    """Pick the gate width that actually captures both peaks best.

    Which width is right cannot be read off the measured window: the support
    over-counts the edges, where detection efficiency is poor, and the
    half-height and top-hat widths of a profile that is part gate and part
    afterpulse decay do not even rise monotonically with the pattern.  So the
    width is narrowed to the candidates the measured geometry allows and then
    decided by what each one collects in the two windows -- scored on the weaker
    of the two, since a gate is only as good as the port it captures least.

    The window centre is not re-measured per candidate: gate_pattern extends the
    run of bits forwards from the offset, so widening it moves the centre by
    exactly half the added width.
    """
    best = None
    for w in candidates:
        centre0 = centre0_ref + timing.gate_centre_shift(w, ref_slots)
        Fg_Set_Gate(Fg_Gate_Delay(centre_units, t0, centre0), w)
        try:
            h, rate = Fg_Histogram(FG_CLICKS_SWEEP, 'fg_width', timing.PERIOD,
                                   min_rate=FG_MIN_RATE_SWEEP)
        except RuntimeError as e:
            print(f"  gate {w:>2} slots: {e}")
            continue
        base = timing.baseline(h)
        nbins = int(round(soft_w / FG_BINW))
        excess = [Fg_Window_Sum(h, g, soft_w) - base * nbins for g in starts]
        score = min(excess)
        print(f"  gate {w:>2} slots: captures {excess[0]:6.0f} and {excess[1]:6.0f} "
              f"above pedestal, rate {rate:.0f}")
        if best is None or score > best[0]:
            best = (score, w, centre0)
    if best is None:
        raise RuntimeError("no gate width produced a usable histogram")
    return best[1], best[2]


def Fg_Plot(h_single, sol, h_double, h_off, gates, path):
    """Two panels: what was measured, and where the gates ended up."""
    fig, (ax0, ax1) = plt.subplots(2, 1, figsize=(11, 7))

    x = (np.arange(len(h_single)) + 0.5) * FG_BINW * timing.UNIT_PS / 1000.0
    ax0.plot(x, h_single, color='black', lw=0.8)
    for name, off, colour in (('p0', 0, 'grey'), ('p0+t1', sol['t1'], 'tab:blue'),
                              ('p0+t2', sol['t2'], 'tab:green'),
                              ('p0+t1+t2', sol['t1'] + sol['t2'], 'tab:red')):
        pos = ((sol['p0'] + off) % timing.SP_FRAME) * timing.UNIT_PS / 1000.0
        ax0.axvline(pos, color=colour, ls='--', lw=1)
        ax0.annotate(name, (pos, ax0.get_ylim()[1]), color=colour,
                     fontsize=8, rotation=90, va='top')
    ax0.set_title(f"single pulse, free running: t1 = {sol['t1_ns']:.3f} ns, "
                  f"t2 = {sol['t2_ns']:.3f} ns, residual {sol['residual_ns']:.3f} ns")
    ax0.set_xlabel('ns in the 25 ns single-pulse frame')
    ax0.set_ylabel('counts')
    ax0.set_ylim(0)

    if h_double is not None:
        x = (np.arange(len(h_double)) + 0.5) * FG_BINW * timing.UNIT_PS / 1000.0
        if h_off is not None:
            ax1.plot(x, h_off, color='tab:blue', ls='--', lw=0.8, label='am off')
        ax1.plot(x, h_double, color='tab:red', lw=0.9, label='am double')
        for i, (g, w) in enumerate(gates):
            ax1.axvspan(g * timing.UNIT_PS / 1000.0,
                        (g + w) * timing.UNIT_PS / 1000.0,
                        color='orange' if i == 0 else 'purple', alpha=0.25,
                        label=f'soft gate {i}')
        ax1.legend(fontsize=8)
        ax1.set_title('double pulse, gated, with the placed soft gates')
        ax1.set_xlabel('ns in the 12.5 ns period')
        ax1.set_ylabel('counts')
        ax1.set_ylim(0)

    fig.tight_layout()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fig.savefig(path, dpi=140)
    plt.close(fig)


def Fg_Window_Sum(h, start, width, binw=FG_BINW):
    n = len(h)
    lo = int(round(start / binw))
    return float(sum(h[(lo + i) % n] for i in range(int(round(width / binw)))))


def Find_Gates(link, force=False):
    """Place both gates from the single-pulse geometry, and verify the result.

    `link` talks to Alice; `force` re-measures the hardware constants instead of
    reading them back.  Returns (status, message).
    """
    const = sysconst.load()
    laser = link.ask('laser')
    t = get_tmp()
    entry = {'soft_gate': t['soft_gate'], 'spd_mode': t['spd_mode'],
             'gate_delay': t['gate_delay'], 'gate_duty': t.get('gate_duty', 8),
             't0': t['t0']}
    update_tmp('soft_gate', 'off')
    Update_Softgate()
    try:
        return _find_gates(link, const, laser, entry, force)
    finally:
        # Whatever went wrong, do not leave the link filtering on windows that
        # were never placed -- a half-finished run would otherwise look like a
        # working gate with almost no counts.
        update_tmp('soft_gate', entry['soft_gate'])
        Update_Softgate()


def _find_gates(link, const, laser, entry, force):
    # ------------------------------------------- geometry, in the gated frame --
    # Measured gated, with the pattern held all-ones so the gate never closes.
    # The link runs gated, and the detector timestamps a gated photon several ns
    # away from a free-running one, so measuring the geometry free-running and
    # applying it gated puts every gate on the wrong peak.  All-ones also keeps
    # all four arrivals visible, which a real gate does not: it opens under 5 ns
    # of the 12.5 ns period, and with only two arrivals showing, p0 cannot be
    # told from p0+t2.
    link.ask('am single')
    link.ask('am_shift 0')
    Ensure_Spd_Mode('gated')
    Fg_Set_Gate(entry['gate_delay'], FG_OPEN_GATE)
    h_gate, rate_g = Fg_Histogram(FG_CLICKS, 'fg_single_gated', timing.SP_FRAME)
    peaks_g, base_g = Fg_Peaks(h_gate)
    if len(peaks_g) != 4:
        raise RuntimeError(
            f"the single-pulse histogram has {len(peaks_g)} peaks, not 4 "
            f"(rate {rate_g:.0f}/0.1 s, pedestal {base_g:.0f}). A flat histogram "
            f"here is an am_bias off the null far more often than it is a gate "
            f"problem -- sweep it in am_mode off and re-null before retrying.")
    sol = timing.solve_single_pulse([p['pos'] for p in peaks_g])
    complaints = timing.check_single_pulse(sol)
    if complaints:
        raise RuntimeError('single-pulse geometry does not hold: ' +
                           '; '.join(complaints))
    t1, t2 = sol['t1'], sol['t2']
    print(f"gated: p0 {sol['p0']:.1f} units, t1 {sol['t1_ns']:.3f} ns, "
          f"t2 {sol['t2_ns']:.3f} ns, residual {sol['residual_ns']:.3f} ns")
    link.report(f"t1 {sol['t1_ns']:.3f} ns, t2 {sol['t2_ns']:.3f} ns")

    qdistance, separation = timing.qdistance_for_arm(t1)
    first, second, forward, arc = timing.gate_pair(t1, t2)
    sysconst.put_interferometer(const, laser, t1, t2, sol['residual'],
                                qdistance, separation)

    # ------------------------------------ free running, for the APD constant --
    # Not used for placement -- only to record how far the free-running detector
    # timestamps the same photon from the gated one.  Bounded to half a peak
    # spacing, because beyond that the two histograms cannot say which arrival
    # matches which and the answer would be a multiple of t1 rather than a delay.
    Ensure_Spd_Mode('continuous')
    h_cont, _ = Fg_Histogram(FG_CLICKS, 'fg_single_cont', timing.SP_FRAME)
    peaks_c, _ = Fg_Peaks(h_cont)
    mode_offset = None
    if len(peaks_c) == 4:
        sol_c = timing.solve_single_pulse([p['pos'] for p in peaks_c])
        if not timing.check_single_pulse(sol_c):
            d = (sol['p0'] - sol_c['p0']) % timing.SP_FRAME
            mode_offset = d - timing.SP_FRAME if d > timing.SP_FRAME / 2 else d
    if mode_offset is None:
        link.report('free-running histogram unusable; apd mode offset not updated')
    else:
        print(f"free running to gated offset "
              f"{mode_offset * timing.UNIT_PS / 1000:+.3f} ns")
        link.report(f"apd mode offset {mode_offset * timing.UNIT_PS / 1000:+.3f} ns")
    Ensure_Spd_Mode('gated')

    # ------------------------------------------------- coarse 64-frame shift --
    link.ask('am single64')
    coarse = Measure_Sp64()

    # --------------------------------------------- put the comb on the target --
    # Where Alice's light leaves differs between the single and double patterns,
    # so the measurement is carried across through the two patterns' own rising
    # edges rather than assumed equal; whatever that misses by is measured below
    # and kept, so the next run predicts instead of correcting.
    am_edge = link.ask('am_edge').strip()
    c_single = Fg_Emission_Slots('single', 0, qdistance, am_edge)[0]
    c_double = Fg_Emission_Slots('double', 0, qdistance, am_edge)[0]
    delay = (sol['p0'] - c_single * timing.SLOT - entry['t0']) % timing.PERIOD
    seq = sysconst.get_sequence(const, laser)
    usable = (seq and seq.get('am_edge') == am_edge
              and seq.get('convention') == FG_CONVENTION)
    residual = seq['residual_units'] if usable else 0.0
    x0 = (c_double * timing.SLOT + delay + first + residual) % timing.PERIOD
    am_shift, t0 = timing.shift_for_target(x0, FG_TARGET)
    print(f"predicted first gated peak at {x0:.1f} units -> am_shift {am_shift}, t0 {t0}")

    update_tmp('t0', t0)
    Gen_Gate()
    link.ask(f'qdistance {qdistance:.6f}')
    link.ask(f'am_shift {(am_shift + coarse) % 640}')
    link.ask('am double')

    offsets, weights = timing.comb_offsets(t1, t2)
    for attempt in range(5):
        h_comb, _ = Fg_Histogram(FG_CLICKS, 'fg_comb', timing.PERIOD)
        peaks_d, _ = Fg_Peaks(h_comb, nmax=None)
        if not peaks_d:
            raise RuntimeError("no peaks in the double-pulse histogram")
        # The comb has been shifted to put its first interfering peak on the
        # target, so that is where the origin should be -- but only once the
        # single-to-double emission offset is known, which it is not on the very
        # first run of a system. A prior that is wrong by more than half a comb
        # spacing pulls the fit onto its neighbour, which is worse than none, so
        # the first look of a first run goes without one and the loop below
        # converges instead.
        trust_prior = attempt > 0 or usable
        origin, score, margin = timing.comb_origin(
            [(p['pos'], p['area']) for p in peaks_d], offsets, weights,
            prior=(FG_TARGET - first) % timing.PERIOD if trust_prior else None)
        got = (origin + first) % timing.PERIOD
        error = (FG_TARGET - got + timing.PERIOD / 2) % timing.PERIOD - timing.PERIOD / 2
        print(f"comb origin {origin:.1f} (fit {score:.1f} units, margin "
              f"{margin:.1f}), first gated peak at {got:.1f}, "
              f"{-error * timing.UNIT_PS / 1000:+.3f} ns from the target")
        residual_new = residual - error
        # Split the correction the same way the placement was: whole slots are
        # Alice's am_shift, the remainder is t0 on this side.
        slots = int(round(error / timing.SLOT))
        t0 = int(round(t0 + error - slots * timing.SLOT)) % timing.PERIOD
        update_tmp('t0', t0)
        Gen_Gate()
        if slots == 0:
            break
        # More than half a slot out: the whole-slot part has to move too, which
        # means telling Alice and looking again rather than trimming t0.
        am_shift = (am_shift + slots) % timing.SLOTS_PER_PERIOD
        link.ask(f'am_shift {(am_shift + coarse) % 640}')
        residual = residual_new
    else:
        raise RuntimeError("the comb will not settle on the target position")
    sysconst.put_sequence(const, laser, residual_new, am_edge, FG_CONVENTION)

    # ------------------------------------------------- close the gate onto it --
    table = sysconst.window_per_slot(const)
    if force or not table:
        print("measuring what each gate width opens")
        Fg_Gate_Table(const)
        table = sysconst.window_per_slot(const)
    # The APD gate spans the short arc between the two ports -- it is periodic,
    # so it does not care that they belong to different sides of the period.
    candidates = timing.gate_slot_candidates(arc, table)
    print(f"gate widths that can hold a {arc * timing.UNIT_PS / 1000:.2f} ns "
          f"arc: {candidates}")

    # Narrow the windows if the ports come closer together than the standard
    # width, so the two never overlap -- overlapping windows count the same
    # clicks into both channels and look like a placement failure.
    soft_w = int(min(FG_SOFT_W, max(8, arc - 4)))
    if soft_w < FG_SOFT_W:
        link.report(f"the two ports are only {arc * timing.UNIT_PS / 1000:.2f} ns "
                    f"apart, so the soft gates are narrowed to "
                    f"{soft_w * timing.UNIT_PS / 1000:.2f} ns")
    if not timing.gate_target_fits(FG_TARGET, forward, soft_w):
        raise RuntimeError(
            f"port B trails port A by {forward * timing.UNIT_PS / 1000:.2f} ns, "
            f"which does not leave room for both windows in one period at "
            f"target {FG_TARGET}. Both must share a period or the two clicks "
            f"carry different double-pulse indices.")

    t0_now = get_tmp()['t0']
    starts = (FG_TARGET - soft_w / 2.0, FG_TARGET + forward - soft_w / 2.0)
    # Centre of the short arc, measured forward from port B through the period
    # boundary to port A -- so the gate straddles the wrap, which the pattern
    # register handles.
    centre = (FG_TARGET + forward + arc / 2.0) % timing.PERIOD
    centre0_ref, _ = Fg_Centre_At_Zero(candidates[0])
    width_slots, _ = Fg_Choose_Gate_Width(
        candidates, centre, starts, t0_now, centre0_ref, candidates[0], soft_w)

    # ------------------------------------ close the loop on the real latency --
    # The delay between Alice's dac0 and the TTL gate pattern is not the same
    # after every power cycle, and centre_at_zero was probed at a different
    # width, so where the window actually lands is measured with the width that
    # will be used and corrected until both ports sit clear of both edges. This
    # is the job `ad` used to do, closed on the pulses themselves rather than on
    # a fixed falling edge in the timing frame.
    ports = (float(FG_TARGET), float((FG_TARGET + forward) % timing.PERIOD))
    clear = [float('nan'), float('nan')]
    edge_note = None
    for attempt in range(FG_CENTRE_TRIES):
        centre0 = centre0_ref + timing.gate_centre_shift(width_slots, candidates[0])
        Fg_Set_Gate(Fg_Gate_Delay(centre, t0_now, centre0), width_slots)
        got = None
        try:
            h_edge, _ = Fg_Histogram(FG_CLICKS_SWEEP, 'fg_gate_edge',
                                     timing.PERIOD, min_rate=FG_MIN_RATE_SWEEP)
            got = Fg_Gate_Clearance(h_edge, ports, soft_w)
        except RuntimeError as e:
            edge_note = f"gate edges not checked ({e})"
            break
        if got is None:
            edge_note = ("the gate does not close the period, so its edges "
                         "cannot be checked")
            break
        win, clear = got
        err = ((centre - win['centre'] + timing.PERIOD / 2) % timing.PERIOD
               - timing.PERIOD / 2)
        print(f"  gate {width_slots} slots: window {win['support']:.0f} units "
              f"wide at {win['start']:.0f}, centre {err:+.1f} units off target, "
              f"port clearance {clear[0]:+.0f}/{clear[1]:+.0f} units")
        if abs(err) > FG_CENTRE_TOL:
            # Correct the measured latency itself, not gate_delay, so the value
            # stored for the next run is the one the hardware just showed.
            d = get_tmp()['gate_delay'] / timing.UNIT_PS
            centre0_ref = ((win['centre'] - t0_now - d) % timing.PERIOD
                           - timing.gate_centre_shift(width_slots,
                                                      candidates[0])) % timing.PERIOD
            edge_note = f"gate centre was {err:+.1f} units off; corrected"
            continue
        if min(clear) < FG_EDGE_SLACK:
            # Centred as well as it can be and still tight: the only remaining
            # move is a wider pattern.
            wider = [w for w in candidates if w > width_slots]
            if not wider:
                edge_note = (f"the widest usable gate ({width_slots} slots) still "
                             f"comes within {min(clear):+.0f} units of a port")
                break
            edge_note = (f"{width_slots} slots leaves only {min(clear):+.0f} units "
                         f"of clearance; widening to {wider[0]}")
            print('  ' + edge_note)
            width_slots = wider[0]
            continue
        edge_note = None
        break
    else:
        edge_note = edge_note or "the gate would not centre on the two ports"
    # Carry the last correction to the hardware unconditionally: the loop can
    # end on a `continue` that has updated centre0_ref without re-setting the
    # gate, and the stored constants must describe the gate that is actually on.
    centre0 = centre0_ref + timing.gate_centre_shift(width_slots, candidates[0])
    Fg_Set_Gate(Fg_Gate_Delay(centre, t0_now, centre0), width_slots)
    if edge_note:
        print('  ' + edge_note)
        link.report(edge_note)
    sysconst.put_apd(const, centre_at_zero_units=round(centre0_ref, 2),
                     centre_ref_slots=candidates[0],
                     gate_slot_ps=round(timing.GATE_SLOT * timing.UNIT_PS, 2),
                     edge_clearance_units=[round(c, 1) for c in clear],
                     **({'mode_offset_units': round(mode_offset, 2)}
                        if mode_offset is not None else {}))
    sysconst.save(const)

    # ------------------------------------------------------------- verify -----
    h_double, rate_double = Fg_Histogram(FG_CLICKS, 'fg_double', timing.PERIOD)
    link.ask('am off')
    rate_off = Fg_Rate()
    try:
        # Fewer clicks and a lower floor than the signal histograms: a well
        # nulled modulator passes so little here that the reference cannot be
        # collected at all, and refusing to place gates because the extinction
        # is *good* would be the wrong way round.
        h_off, _ = Fg_Histogram(FG_CLICKS_SWEEP, 'fg_off', timing.PERIOD,
                                min_rate=FG_MIN_RATE_SWEEP)
    except RuntimeError as e:
        print(f"am-off reference not collectable ({e}); "
              f"falling back to the count rates")
        h_off = None
    link.ask('am double')

    nominal = starts
    gates = [Fg_Refine_Window(h_double, h_off, n, soft_w) for n in nominal]
    g0, g1 = gates[0][0], gates[1][0]
    for i, (g, got, was) in enumerate(gates):
        print(f"soft gate {i}: {int(nominal[i])} -> {g} units, "
              f"signal {was:.0f} -> {got:.0f} ({got / max(was, 1) - 1:+.0%})")
    set_Softgate(g0, g1, soft_w, soft_w)
    t = get_tmp()
    t['soft_gate0'], t['soft_gate1'] = g0, g1
    t['w0'], t['w1'] = soft_w, soft_w
    save_tmp(t)

    # How far the light in each window stands above the modulator's leakage.
    #
    # Both histograms hold a fixed number of clicks, not a fixed time, so a ratio
    # of their window sums compares only *shape* -- it says how much more of its
    # light double mode puts in the window, and silently discards the fact that
    # carving raises the rate three-fold in the first place. The quantity that
    # matters is counts per second in the window, so the shape ratio is
    # multiplied back by the rate ratio.
    rate_ratio = rate_double / rate_off if rate_off > 0 else float('inf')
    shape = [float('nan'), float('nan')]
    if h_off is not None:
        td, to = max(h_double.sum(), 1.0), max(h_off.sum(), 1.0)
        shape = []
        for g in (g0, g1):
            d = Fg_Window_Sum(h_double, g, soft_w) / td
            o = Fg_Window_Sum(h_off, g, soft_w) / to
            shape.append(d / o if o > 0 else float('inf'))
        ratios = [sh * rate_ratio for sh in shape]
        how = 'in-window signal/leakage'
    else:
        ratios = [rate_ratio, rate_ratio]
        how = 'count rate ratio only (am-off histogram not collectable)'
    # The pair decides, not the weaker half: the two ports are complementary, so
    # the phase Alice and Bob happen to sit at moves light from one to the other
    # while their sum stays put. Balancing them is what adjust_soft_gates and the
    # phase-shift steps do, later and deliberately.
    pair = sum(ratios) / 2.0
    print(f"{how}: {ratios[0]:.2f} and {ratios[1]:.2f}, pair {pair:.2f} "
          f"(shape {shape[0]:.2f}/{shape[1]:.2f}, rates {rate_double:.0f} vs "
          f"{rate_off:.0f} counts/0.1 s)")

    # End-to-end check on the histogram the verdict is taken from, with the final
    # t0 and the real gate in place -- not on the wide-open measurement that the
    # placement was computed from.
    peaks_v, _ = Fg_Peaks(h_double, nmax=None)
    landed = min(((p['pos'] - FG_TARGET + timing.PERIOD / 2) % timing.PERIOD
                  - timing.PERIOD / 2 for p in peaks_v), key=abs) if peaks_v else None

    Fg_Plot(h_gate, sol, h_double, h_off, [(g0, soft_w), (g1, soft_w)],
            HW_CONTROL + 'data/calib_res/find_gates.png')

    # Two separate questions, reported separately. Whether the gates are on the
    # peaks is what this routine controls, and the comb fit answers it to a few
    # tens of ps. Whether the peaks stand above the modulator's leakage is a
    # property of the am null and the optics, and reporting a drifted null as
    # "bad gates" is what sent the old path hunting for a placement that was
    # never the problem.
    placed = (score <= FG_MAX_FIT and landed is not None
              and abs(landed) <= FG_PLACED_TOL)
    contrast = pair >= FG_MIN_RATIO
    # Whether the TTL gate cuts into the light is a third, separate question.
    # Short of the slack is only worth saying; an edge actually inside a soft
    # window means those counts are being clipped by the gate, not measured.
    uncut = not any(c < 0 for c in clear if c == c)
    msg = (f"t1 {sol['t1_ns']:.3f} ns, t2 {sol['t2_ns']:.3f} ns, "
           f"qdistance {qdistance:.4f}, gate {width_slots} slots, "
           f"clearance {clear[0]:+.0f}/{clear[1]:+.0f} units, "
           f"soft gates {g0}/{g1}, signal/leakage {ratios[0]:.2f}/{ratios[1]:.2f}"
           f" (pair {pair:.2f}), rates {rate_double:.0f}/{rate_off:.0f}")
    if not uncut:
        msg = (f"the TTL gate cuts into the light "
               f"({clear[0]:+.0f}/{clear[1]:+.0f} units of clearance): " + msg)
    elif not placed:
        off = ('no peak found' if landed is None
               else f"{abs(landed) * timing.UNIT_PS / 1000:.2f} ns off target")
        msg = f"gates not placed (comb fit {score:.1f} units, {off}): " + msg
    elif not contrast:
        msg = (f"gates placed on the peaks, but the light in them stands only "
               f"{pair:.2f}x above the modulator's leakage -- re-null am_bias "
               f"and repeat: " + msg)
    ok = placed and contrast and uncut

    sysconst.put_last_run(
        const, status='success' if ok else 'fail', laser=laser,
        t1_ns=round(sol['t1_ns'], 4), t2_ns=round(sol['t2_ns'], 4),
        qdistance=round(qdistance, 4), gate_slots=int(width_slots),
        soft_gate0=int(g0), soft_gate1=int(g1), soft_w=int(soft_w),
        forward_ns=round(forward * timing.UNIT_PS / 1000.0, 4),
        arc_ns=round(arc * timing.UNIT_PS / 1000.0, 4),
        signal_leakage=[round(r, 2) for r in ratios],
        shape=[round(x, 2) for x in shape],
        rate_double=round(rate_double), rate_off=round(rate_off),
        comb_fit_units=round(score, 2),
        placed_offset_ns=(None if landed is None
                          else round(landed * timing.UNIT_PS / 1000.0, 4)),
        t0=int(get_tmp()['t0']))
    sysconst.save(const)
    # The verdict is the in-window ratio against the am-off reference, which is
    # the comparison verify_gate_double loaded and then never used: its test was
    # peak > background + 20 on the double trace alone, so a feature no bigger
    # than it is with the modulator off passed as a gated peak.
    return ('success' if ok else 'fail'), msg


def plot_single_peak():
    names = [HW_CONTROL + 'data/tdc/single_peak.txt']
    hist = []
    bins = np.arange(0, 1251, 2) - 1

    for name in names:
        t = np.loadtxt(name, usecols=1)
        t = t % 1250
        h, _ = np.histogram(t, bins=bins)
        hist.append(h)

    plt.figure(figsize=(10,5))
    for h in hist:
        plt.plot(bins[:-1]+1, h, color='red')

    plt.axvline(625, color='black')

    plt.ylim(0)
    plt.xlabel('Time bins')
    plt.ylabel('Counts')
    plt.title('Single Peak Measurement')
    plt.grid(True)

    pic = HW_CONTROL + 'data/calib_res/single_peak.png'
    plt.savefig(pic)
    plt.close()

#----------MONITORING REGISTERS-------------------
#Read back monitoring signal
#def Count_Mon():
#    print("-----------DISPLAY NUMBER OF COUNTS--------------")
#    BaseAddr = 0x00000000
#    while True:
#        total, click0, click1 = get_counts()
#        print(f"Total: {total}, Click0: {click0}, Click1: {click1}              ",flush=True)
#        time.sleep(0.1)
#
#def Count_Mon2():
#    print("-----------DISPLAY NUMBER OF COUNTS--------------")
#    while True:
#        total = 0
#        click0 = 0
#        click1 = 0
#        for i in range(10):
#            ret = get_counts()
#            click0 += ret[0]
#            click1 += ret[1]
#            total += ret[2]
#            time.sleep(0.1)
#        print(f"Total: {total}, Click0: {click0}, Click1: {click1}              ",flush=True)

def counts_single():
    return(request_counts())

def counts_fast():
    return(get_counts())

def counts_slow():
    total = 0
    click0 = 0
    click1 = 0
    for i in range(10):
        ret = get_counts()
        total += ret[0]
        click0 += ret[1]
        click1 += ret[2]
        time.sleep(0.1)
    return(total, click0, click1)


#def Read_Count():
#    BaseAddr = 0x00000000
#    total_count = Read(BaseAddr + 64)
#    hex_total_count = total_count.decode('utf-8').strip()
#    dec_total_count = int(hex_total_count, 16)
#    #print("Total count: ", dec_total_count)
#    return dec_total_count



#def Get_Current_Gc():
#    #Command_enable
#    Write(0x00001000+4,0x0)
#    Write(0x00001000+4,0x1)
#    time.sleep(0.01)
#    #Readback registers
#    gc_lsb = Read(0x00001000+60)
#    gc_msb = Read(0x00001000+64)
#    print(gc_lsb)
#    print(gc_msb)
#
#    current_gc = np.int64(int(gc_msb.decode('utf-8').strip(),16) << 32 | int(gc_lsb.decode('utf-8').strip(),16))
#
#    print(hex(current_gc))
#    print(current_gc/40e6, 's')
#    return current_gc






def init_ltc():
    Config_Ltc()

def init_sync():
    Sync_Ltc()

def init_fda():
    #Write_To_Fake_Rng(gen_seq.seq_rng_zeros())
    #d = get_default()
    #t = get_tmp()
    #t['angle0'] = d['angle0']
    #t['angle1'] = d['angle1']
    #t['angle2'] = d['angle2']
    #t['angle3'] = d['angle3']
    #t['pm_shift'] = d['pm_shift']
    #t['pm_mode'] = 'off'
    #save_tmp(t)
    #Update_Angles()
    #Update_Dac()
    Config_Fda()



def init_sda():
    Config_Sda()
    for i in range(8):
     Set_vol(i, 0)
    # Set_vol drives the DAC directly and bypasses Set_Pol, which records what
    # was written, so tmp.txt has to be squared with the zeroed channels here:
    # 0-3 are pol0-pol3.
    t = get_tmp()
    for ch in range(4):
        t['pol'+str(ch)] = 0
    save_tmp(t)

def init_jic():
    Config_Jic()

def init_tdc():
    #d = get_default()
    #t = get_tmp()
    #t['gate_delay'] = d['gate_delay']
    #t['soft_gate0'] = d['soft_gate0']
    #t['soft_gate1'] = d['soft_gate1']
    #t['soft_gatew'] = d['soft_gatew']
    #t['t0'] = d['t0']
    #t['spd_deadtime'] = d['deadtime_cont']
    #save_tmp(t)
    #Update_Softgate()
    Time_Calib_Init()
    #aurea = Aurea()
    #aurea.deadtime(t['spd_deadtime'])
    #aurea.mode("continuous")
    #aurea.close()

def init_ttl():
    ttl_reset()
    with open(HW_CONTROL+'config/delayf.txt', 'w') as f:
        f.write('0\n0\n0\n')
    Gen_Gate()

def init_ddr():
    Ddr_Data_Init()




def init_dpram():
    write(0x00030000, 28, 16000)
    write(0x00030000, [12, 12], [0x1, 0x0])
    write(0x00030000, 16, 0x0000a0a0)
    write(0x00030000, [4, 32, 12, 12], [943718451, 1000, 1, 0])
    write(0x00030000, [8, 24, 12, 12], [4089445888, 4240797368, 1, 0])



def set_basis_p0(p):
    # probability of the basis-choice true rng emitting 0; only effective in true_rng mode
    if (p < 0) or (p > 1):
        print("basis p0 out of range. Choose a value between 0 and 1")
        return
    write_basis_p0(min(round(p * P0_SCALE), P0_SCALE - 1))
    rng_reset()
    update_tmp('basis_p0', p)

def init_rng_p0():
    # program the biased-rng thresholds (tunable-p0 bitstreams); they reset to 0
    # on FPGA reconfiguration, which would make the true rng emit all-ones.
    # Bob's bitstream also carries the (unused) decoy rng block; give it a sane
    # threshold too so its fifo monitor flags stay meaningful.
    t = get_tmp()
    write_basis_p0(min(round(t.get('basis_p0', 0.5) * P0_SCALE), P0_SCALE - 1))
    write_decoy_p0(P0_SCALE // 2)

def init_hw():
    init_ltc()
    init_sync()
    init_dpram()
    init_fda()
    init_sda()
    init_jic()
    init_tdc()
    init_ttl()
    init_rng_p0()
    rng_reset()

def apply_config():
    Update_Dac()
    Update_Angles()
    Update_Softgate()
    #init_tdc()
    #init_ttl()
    Gen_Gate()
    update_spd()

def rst_config():
    t = {}
    t['angle0'] = 0
    t['angle1'] = 0.18
    t['angle2'] = -0.18
    t['angle3'] = 0.36
    t['pm_mode'] = 'off'
    t['pm_shift'] = 0
    t['feedback'] = 'off'
    t['first_peak'] = 0
    t['spd_mode'] = 'continuous'
    t['spd_eff'] = 20
    t['deadtime_cont'] = 20
    t['deadtime_gated'] = 15
    t['pol0'] = 2.5
    t['pol1'] = 2.5
    t['pol2'] = 2.5
    t['pol3'] = 2.5
    t['gate_delay'] = 6000
    t['soft_gate'] = 'off'
    t['soft_gate0'] = 28
    t['soft_gate1'] = 542
    t['soft_gatew'] = 40
    t['w1'] = 40
    t['w0'] = 40
    t['t0'] = 0
    t['fiber_delay_mod'] = 0
    t['fiber_delay_long'] = 0
    t['fiber_delay'] = 0
    t['insert_zeros'] = 'off'
    t['zero_pos'] = 0
    save_tmp(t)

def clean_config():
    rst_config()
    apply_config()

def save_config(filename):
    t = get_tmp()
    save_calibrated(t, filename)

def load_config(filename):
    c = get_calibrated(filename)
    save_tmp(c)
    init_hw()
    apply_config()











