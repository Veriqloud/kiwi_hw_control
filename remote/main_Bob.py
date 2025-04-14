#!/bin/python

import subprocess, os, sys, argparse
import time
import numpy as np
import datetime 
import mmap
import lib.gen_seq as gen_seq
import lib.cal_lib as cal_lib
from lib.config_lib import *
from lib.Aurea import Aurea

def Ensure_Spd_Mode(mode):
    deadtime_cont = 20
    deadtime_gated = 15
    t = get_tmp()
    if mode=='continuous':
        if (t['spd_mode'] != 'continuous') or (t['spd_deadtime']!=deadtime_cont):
            aurea = Aurea()
            aurea.mode("continuous")
            aurea.deadtime(deadtime_cont)
            aurea.close()
            t['spd_mode'] = 'continuous'
            t['spd_deadtime'] = deadtime_cont
    elif mode=='gated':
        if (t['spd_mode'] != 'gated') or (t['spd_deadtime']!=deadtime_gated):
            aurea = Aurea()
            aurea.mode("gated")
            aurea.deadtime(deadtime_gated)
            aurea.close()
            t['spd_mode'] = 'gated'
            t['spd_deadtime'] = deadtime_gated
    else:
        exit("wrong mode")
    save_tmp(t)

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


def Update_Softgate():
    t = get_tmp()
    command = 1 if t['soft_gate']=='off' else 2
    g0 = t['soft_gate0']
    g1 = t['soft_gate1']
    w = t['soft_gatew']
    Time_Calib_Reg(command, t['t0'], 0, g0, w, g1, w)
            

def Update_Pol():
    t = get_tmp()
    p = [t['pol0'], t['pol1'], t['pol2'], t['pol3']]
    for ch,vol in enumerate(p):
        if (vol>5 or vol <0):
            exit ("voltage not in the good range")
        Set_vol(ch,vol)


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
    timestep = 3.383    # fine delay timestep in ps
    delay_au = round(delay/timestep)
    fine_max = 404      # corresponds to 1/3 of coarse delay
    coarse = delay_au // (fine_max*3)
    fine0_abs = delay_au % fine_max
    fine1_abs = int((delay_au%(fine_max*3)) >= fine_max) * fine_max
    fine2_abs = int((delay_au%(fine_max*3)) >= 2*fine_max) * fine_max


    fine0 = fine0_abs - t['gate_delayf0']
    direction0 = 1 if fine0 > 0 else 0

    fine1 = fine1_abs - t['gate_delayf1']
    direction1 = 1 if fine1 > 0 else 0
    
    fine2 = fine2_abs - t['gate_delayf2']
    direction2 = 1 if fine2 > 0 else 0

    write_delay_master(2,coarse, abs(fine0), direction0) 
    write_delay_slaves(abs(fine1), direction1, abs(fine2), direction2)

    params_en()
    trigger_fine_master()
    trigger_fine_slv1()
    trigger_fine_slv2()

    t['gate_delayf0'] = fine0_abs
    t['gate_delayf1'] = fine1_abs
    t['gate_delayf2'] = fine2_abs
    save_tmp(t)

    print("gate pulse delay set to", delay/1000, "sn")
    #print(coarse, fine0, fine1, fine2)
    #print(coarse, direction0, direction1, direction2)


def Find_Best_Shift(party):
    best_shift = cal_lib.Best_Shift(party)
    return best_shift

    
#---------------------------TDC CALIBRATION-----------------------------------------------

def Cont_Det(): 
    num_data = 2000
    Get_Stream(0x00000000+40,'/dev/xdma0_c2h_2','data/tdc/output_dp.bin',num_data)
    command ="test_tdc/tdc_bin2txt data/tdc/output_dp.bin data/tdc/histogram_dp.txt"
    s = subprocess.check_call(command, shell = True)

    time_gc = np.loadtxt("data/tdc/histogram_dp.txt",usecols=(1,2),unpack=True)
    int_time_gc = time_gc.astype(np.int64)
    duration = (max(int_time_gc[1])-min(int_time_gc[1]))*25
    click_rate = np.around(num_data/(duration*0.000000001),decimals=4)
    print("Number of count: ", str(len(int_time_gc[1])))
    print("Appro click rate: ", str(click_rate), "click/s")

def Download_Time(num_clicks, fileprefix="time"):
    print("downloading time tags into file", fileprefix+".txt")
    binfile = 'data/tdc/'+fileprefix+'.bin'
    txtfile = 'data/tdc/'+fileprefix+'.txt'
    Get_Stream(0x00000000+40,'/dev/xdma0_c2h_2',binfile, num_clicks)
    command ="test_tdc/tdc_bin2txt "+binfile+" "+txtfile
    s = subprocess.check_call(command, shell = True)


def Measure_Sp(num_clicks=20000):
    Ensure_Spd_Mode('continuous')
    Download_Time(num_clicks, fileprefix="histogram_sp")
    ref_time = np.loadtxt("data/tdc/histogram_sp.txt",usecols=1,unpack=True,dtype=np.int32)
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
    data = np.loadtxt('data/tdc/single64.txt', usecols=(2,4))
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
    Download_Time(num_clicks, "histogram_dp")



def Read_Count_InGates():
    BaseAddr = 0x00000000
    click0_count = Read(BaseAddr + 60)
    hex_click0_count = click0_count.decode('utf-8').strip()
    dec_click0_count = int(hex_click0_count, 16)
    click1_count = Read(BaseAddr + 56)
    hex_click1_count = click1_count.decode('utf-8').strip()
    dec_click1_count = int(hex_click1_count, 16)
    time.sleep(0.1)
    ingates_count = dec_click0_count + dec_click1_count
    return ingates_count

def Polarisation_Control():
    voltages = np.arange(1,3.5,0.5)
    bests = []
    for ch in range(4):
        c = []
        for v in voltages:
            Set_vol(ch,v)
            c.append(Read_Count_InGates())
        c = np.array(c)
        print(c)
        best = voltages[c.argmax()]
        bests.append(best)
        print("Best voltage on channel ", ch, "is", best)
        Set_vol(ch,best)

    bests2 = []
    for ch in range(4):
        voltages = np.arange(bests[ch]-0.2,bests[ch]+0.3,0.1)
        c = []
        for v in voltages:
            Set_vol(ch,v)
            c.append(Read_Count_InGates())
        c = np.array(c)
        print(c)
        best = voltages[c.argmax()]
        bests2.append(best)
        print("Best voltage on channel ", ch, "is", best)
        Set_vol(ch,best)

#-----------APPLY GATE--------------------------
#Apply the gate parameter to FPGA and take just the click inside the gate
#click rate is 50kHz, slower than rstidx(625kHz) -> use ref_time (reference to 5MHz) to define position
#in one 5MHz has 16 cycles of 80MHz (qclk cycle), 8 global counters
#clicks arrive at any qclk cycle, have to do modulo in FPGA
def Gated_Det():
    print("-----------------------------GATE INPUT----------------------")
    #Command_gate_aply set in Time_Calib_Reg
    Get_Stream(0x00000000+40,'/dev/xdma0_c2h_2','data/tdc/output_gated.bin',100000)
    command ="test_tdc/tdc_bin2txt data/tdc/output_gated.bin data/tdc/histogram_gated.txt"
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
            Get_Stream(0x00000000+40,'/dev/xdma0_c2h_2','data/tdc/clickout_'+str(10*j+i+1)+'.bin',5000) 
        Write_Dac1_Shift(2,0.125+j*0.125,-0.125+ j*0.125,0,0,0)

    for j in range(4):
        for i in range(10):
            command ="test_tdc/tdc_bin2txt data/tdc/clickout_"+str(10*j+i+1)+".bin data/tdc/click_data_"+str(10*j+i+1)+".txt"
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
    data = np.loadtxt("data/tdc/fd_b_single.txt",usecols=(2,3,4), dtype=np.int64)
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
    data = np.loadtxt("data/tdc/fd_b_single_long.txt",usecols=(2,3,4), dtype=np.int64)
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
    data = np.loadtxt("data/tdc/fz_b.txt",usecols=(2,3,4), dtype=np.int64)

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
    zeros_pos = (t['fiber_delay_mod'] -2 - peakpos) % 16
    print("zeros pos found:", zeros_pos) 
    return zeros_pos 

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
        print("zeros pos found:", 0) 
        return 0
    
    Download_Time(50000, 'fz_a')
    data = np.loadtxt("data/tdc/fz_a.txt",usecols=(2,3,4), dtype=np.int64)

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
    zeros_pos = (fiber_delay_mod - 0 - peakpos) % 16
    print("zeros pos found:", zeros_pos) 
    return int(zeros_pos )

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

    data = np.loadtxt("data/tdc/fd_a_single.txt",usecols=(2,3,4), dtype=np.int64)
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
    print("Fiber delay of Alice: ",index, " [q_bins]")
    return(int(index))

def Find_Opt_Delay_A_long(fiber_delay_mod):
    # generate a sequence of 64 angles where the first one stands out
    t = get_tmp()
    t['feedback'] = 'on'
    t['soft_gate'] = 'on'
    t['insert_zeros'] = 'off'
    save_tmp(t)
    Update_Softgate()
    Update_Dac()
    Write_To_Fake_Rng(gen_seq.seq_rng_zeros())

    Download_Time(200000, 'fd_a_single_long')
    data = np.loadtxt("data/tdc/fd_a_single_long.txt",usecols=(2,3,4), dtype=np.int64)
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

    index = np.argmax(np.abs(h))
    print("Fiber delay of Alice: ",index, " [64 q_bins]")
    return(int(index))

def Test_delay():
    Base_Addr = 0x00030000
    Write(Base_Addr + 28, 0x4e20) #for 0.5ms distance
    Base_seq0 = 0x00030000 + 0x2000  #Addr_axil_sequencer +   addr_dpram
    file0 = open('data/fda/seqrng_gen/SeqRng.txt','r') #Use this file for 0.5ms distance
    counter = 0
    for l in file0.readlines():
        counter += 1
        Base_seq = str(hex(int(Base_seq0) + (counter-1)*4))
        Write(Base_seq, l)
        #print(Base_seq)
        #print(l)
    print("Set rng sequence for DAC1 finished")
    file0.close()


def fall_edge(file_path, start_range=200, end_range=900):
    data = np.loadtxt(os.path.expanduser(file_path), usecols=1)
    bins = np.arange(0, 1251, 2) - 1
    hist, _ = np.histogram(data % 1250, bins=bins)
    index = bins[:-1] + 1
    mask = (index >= start_range) & (index <= end_range)
    index_filt = index[mask]
    amp_filt = hist[mask]
    lf = 724  # default
    for i in range(1, len(amp_filt)):
        if amp_filt[i] < amp_filt[i - 1]:
            lf = index_filt[i]
    return lf




#----------MONITORING REGISTERS-------------------
#Read back monitoring signal
def Count_Mon():
    print("-----------DISPLAY NUMBER OF COUNTS--------------")
    BaseAddr = 0x00000000
    while True:
        total, click0, click1 = get_counts()
        print(f"Total: {total}, Click0: {click0}, Click1: {click1}              ",flush=True)
        time.sleep(0.1)

def Count_Mon2():
    print("-----------DISPLAY NUMBER OF COUNTS--------------")
    while True:
        total = 0
        click0 = 0
        click1 = 0
        for i in range(10):
            ret = get_counts()
            click0 += ret[0]
            click1 += ret[1]
            total += ret[2]
            time.sleep(0.1)
        print(f"Total: {total}, Click0: {click0}, Click1: {click1}              ",flush=True)


def Read_Count():
    BaseAddr = 0x00000000
    total_count = Read(BaseAddr + 64)
    hex_total_count = total_count.decode('utf-8').strip()
    dec_total_count = int(hex_total_count, 16)
    print("Total count: ", dec_total_count)
    return dec_total_count



def Get_Current_Gc():
    #Command_enable
    Write(0x00001000+4,0x0)
    Write(0x00001000+4,0x1)
    time.sleep(1)
    #Readback registers
    gc_lsb = Read(0x00001000+60)
    gc_msb = Read(0x00001000+64)
    print(gc_lsb)
    print(gc_msb)

    current_gc = np.int64(int(gc_msb.decode('utf-8').strip(),16) << 32 | int(gc_lsb.decode('utf-8').strip(),16))

    print(hex(current_gc))
    print(current_gc/40e6, 's')
    return current_gc



#def Angle():
#    #Readback 
#    device_c2h = '/dev/xdma0_c2h_3'
#    output_file = 'data/ddr4/alpha.bin'
#    size = 16
#    count = 32
#    for i in range(1):
#    #while True:
#    #    Read_stream(device_c2h,output_file,size,count)
#        command ="test_tdc/dma_from_device "+"-d "+ device_c2h +" -f "+ output_file+ " -c " + str(count) 
#        s = subprocess.check_call(command, shell = True)
#        time.sleep(1)



def init_ltc():
    Config_Ltc()

def init_sync():
    Sync_Ltc()

def init_fda():
    Write_To_Fake_Rng(gen_seq.seq_rng_zeros())
    d = get_default()
    t = get_tmp()
    t['angle0'] = d['angle0']
    t['angle1'] = d['angle1']
    t['angle2'] = d['angle2']
    t['angle3'] = d['angle3']
    t['pm_shift'] = d['pm_shift']
    t['pm_mode'] = 'off'
    save_tmp(t)
    Update_Angles()
    Update_Dac()
    Config_Fda()



def init_sda():
    Config_Sda()

def init_jic():
    Config_Jic()

def init_tdc():
    d = get_default()
    t = get_tmp()
    t['gate_delay'] = d['gate_delay']
    t['soft_gate0'] = d['soft_gate0']
    t['soft_gate1'] = d['soft_gate1']
    t['soft_gatew'] = d['soft_gatew']
    t['t0'] = d['t0']
    t['spd_deadtime'] = d['deadtime_cont']
    save_tmp(t)
    Update_Softgate()
    Time_Calib_Init()
    aurea = Aurea()
    aurea.deadtime(t['spd_deadtime'])
    aurea.mode("continuous")
    aurea.close()

def init_ttl():
    ttl_reset()
    t = get_tmp()
    t['gate_delayf0'] = 0
    t['gate_delayf1'] = 0
    t['gate_delayf2'] = 0
    d = get_default()
    t['gate_delay'] = d['gate_delay']
    save_tmp(t)
    Gen_Gate()

def init_ddr():
    Ddr_Data_Init()

def init_apply_default():
    d = get_default()
    t = get_tmp()
    t['pm_shift'] = d['pm_shift']
    t['angle0'] = d['angle0']
    t['angle1'] = d['angle1']
    t['angle2'] = d['angle2']
    t['angle3'] = d['angle3']
    t['gate_delay'] = d['gate_delay']
    t['soft_gate0'] = d['soft_gate0']
    t['soft_gate1'] = d['soft_gate1']
    t['soft_gatew'] = d['soft_gatew']
    t['t0'] = d['t0']
    t['fiber_delay'] = d['fiber_delay']
    t['fiber_delay_mod'] = d['fiber_delay']%32
    t['zero_pos'] = d['zero_pos']
    save_tmp(t)
    Update_Dac()
    Update_Angles()
    Update_Softgate()
    Gen_Gate()



def init_rst_default():
    d = {}
    d['pm_shift'] = 320
    d['angle0'] = 0
    d['angle1'] = 0.18
    d['angle2'] = -0.18
    d['angle3'] = 0.36
    d['gate_delay'] = 6000
    d['soft_gate0'] = 20
    d['soft_gate1'] = 530
    d['soft_gatew'] = 60
    d['t0'] = 0
    d['deadtime_cont'] = 20
    d['deadtime_gated'] = 15
    d['fiber_delay_mod'] = 0
    d['fiber_delay'] = 0
    d['zero_pos'] = 0
    save_default(d)

def init_rst_tmp():
    t = {}
    t['pm_mode'] = 'seq64'
    t['pm_shift'] = 0
    t['feedback'] = 'off'
    t['insert_zeros'] = 'off'
    t['angle0'] = 0
    t['angle1'] = 0
    t['angle2'] = 0
    t['angle3'] = 0
    t['first_peak'] = 0
    t['gate_delayf0'] = 0
    t['gate_delayf1'] = 0
    t['gate_delayf2'] = 0
    t['spd_mode'] = 'continuous'
    t['spd_deadtime'] = 100
    t['spd_eff'] = 20
    t['pol0'] = 0
    t['pol1'] = 0
    t['pol2'] = 0
    t['pol3'] = 0
    t['gate_delay'] = 0
    t['soft_gate'] = 'off'
    t['soft_gate0'] = 0
    t['soft_gate1'] = 0
    t['soft_gatew'] = 0
    t['t0'] = 0
    t['fiber_delay_mod'] = 0
    t['fiber_delay'] = 0
    t['zero_pos'] = 0
    save_tmp(t)

def init_all():
    init_ltc()
    init_sync()
    init_fda()
    init_sda()
    init_jic()
    init_tdc()
    init_ttl()
    init_apply_default()




#------------------------------MAIN----------------------------------------------------------------------------------
def main():
    def init(args):
        if args.ltc:
            init_ltc()
        elif args.fda:
            init_fda()
        elif args.sync:
            init_sync()
        elif args.sda:
            init_sda()
        elif args.jic:
            init_jic()
        elif args.tdc:
            init_tdc()
        elif args.ttl:
            init_ttl()
        elif args.ddr:
            init_ddr()
        elif args.all:
            init_all()
        elif args.rst_default:
            init_rst_default()
        elif args.rst_tmp:
            init_rst_tmp()
        elif args.apply_default:
            init_apply_default()
    def set(args):
        if args.pm_mode:
            update_tmp('pm_mode', args.pm_mode)
            Update_Dac()
        elif args.fake_rng_seq:
            if args.fake_rng_seq == 'single':
                Write_To_Fake_Rng(gen_seq.seq_rng_single(args.pos))
                Update_Dac()
            elif args.fake_rng_seq == 'off':
                Write_To_Fake_Rng(gen_seq.seq_rng_zeros())
                Update_Dac()
            elif args.fake_rng_seq == 'random':
                Write_To_Fake_Rng(gen_seq.seq_rng_random())
                Update_Dac()
            elif args.fake_rng_seq == 'all_one':
                Write_To_Fake_Rng(gen_seq.seq_rng_all_one())
                Update_Dac()
            elif args.fake_rng_seq == 'block1':
                Write_To_Fake_Rng(gen_seq.seq_rng_block1())
                Update_Dac()

        elif args.pm_shift is not None:
            update_tmp('pm_shift', args.pm_shift)
            Update_Dac()
        elif args.feedback:
            update_tmp('feedback', args.feedback)
            Update_Dac()
            t = get_tmp()
            if t['soft_gate'] == 'off':
                print("WARNING: softgate filter is OFF. Feedback will not work")

        elif args.insert_zeros:
            update_tmp('insert_zeros', args.insert_zeros)
            Update_Dac()
        elif args.zero_pos is not None:
            update_tmp('zero_pos', args.zero_pos)
            Update_Dac()
        elif args.angles:
            t = get_tmp()
            t['angle0'] = args.angles[0]
            t['angle1'] = args.angles[1]
            t['angle2'] = args.angles[2]
            t['angle3'] = args.angles[3]
            save_tmp(t)
            Update_Angles()
        elif args.spd_mode:
            print("opening SPD...")
            aurea = Aurea()
            if args.spd_mode=="free":
                update_tmp('spd_mode', 'continuous')
                aurea.mode("continuous")
                aurea.close()
            elif args.spd_mode=="gated":
                update_tmp('spd_mode', 'gated')
                aurea.mode("gated")
                aurea.close()
        elif not (args.spd_deadtime==None):
            print("opening SPD...")
            aurea = Aurea()
            aurea.deadtime(args.spd_deadtime)
            aurea.close()
            update_tmp('spd_deadtime', args.spd_deadtime)
        elif not (args.spd_eff==None):
            print("opening SPD...")
            aurea = Aurea()
            aurea.effi(int(args.spd_eff))
            aurea.close()
            update_tmp('spd_eff', args.spd_eff)
        elif not (args.spd_delay==None):
            delay = args.spd_delay    # translate to ps
            update_tmp('gate_delay', delay)
            Gen_Gate()
        elif args.pol_bias is not None:
            t = get_tmp()
            t['pol0'] = args.pol_bias[0]
            t['pol1'] = args.pol_bias[1]
            t['pol2'] = args.pol_bias[2]
            t['pol3'] = args.pol_bias[3]
            save_tmp(t)
            Update_Pol()
        elif args.soft_gate_filter:
            update_tmp('soft_gate', args.soft_gate_filter)
            Update_Softgate()
        elif args.soft_gates:
            t = get_tmp()
            t['soft_gate0'] = args.soft_gates[0]
            t['soft_gate1'] = args.soft_gates[1]
            t['soft_gatew'] = args.soft_gates[2]
            save_tmp(t)
            Update_Softgate()

    def get(args):
        if args.counts:
            Count_Mon()
        if args.counts2:
            Count_Mon2()
        elif args.time:
            Download_Time(args.time)
        elif args.get_gc:
            #Ddr_Data_Init()
            Get_Current_Gc()
#        if args.angles:
#            Angle()





    def debug(args):
        if args.t0 is not None:
            #Time_Calib_Reg(1, args.t0, 0, 0, 0, 0, 0)
            Set_t0(args.t0)
        elif args.measure is not None:
            Measure_Sp(10000)


    #create top_level parser
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(required=True)

    parser_init = subparsers.add_parser('init')
    parser_set = subparsers.add_parser('set')
    parser_get = subparsers.add_parser('get')
    parser_debug = subparsers.add_parser('debug')

######### init ###########
    parser_init.add_argument("--all", action="store_true", 
                             help="init all devices and sync")
    parser_init.add_argument("--ltc", action="store_true", 
                             help="init clock chip ltc")
    parser_init.add_argument("--fda", action="store_true", 
                             help="init fast dac")
    parser_init.add_argument("--sda", action="store_true", 
                             help="init slow dac")
    parser_init.add_argument("--jic", action="store_true", 
                             help="init jitter cleaner for tdc")
    parser_init.add_argument("--tdc", action="store_true", 
                             help="init tdc")
    parser_init.add_argument("--sync", action="store_true", 
                             help="sync to PPS")
    parser_init.add_argument("--ttl", action="store_true", 
                             help="delay module for the SPD gate")
    parser_init.add_argument("--rst_default", action="store_true", 
                             help="reset default parameters in config/default.txt")
    parser_init.add_argument("--rst_tmp", action="store_true", 
                             help="reset tmp file in config/default.txt")
    parser_init.add_argument("--apply_default", action="store_true", 
                             help="apply values from config/default.txt")
    parser_init.add_argument("--ddr", action="store_true", 
                             help="init ddr data")


######### set ###########
#    parser_set.add_argument("--rng_mode", choices=['seq', 'fake_rng', 'true_rng'],
#                            help="fixed periodic sequece, fake rng or real rng")
    parser_set.add_argument("--fake_rng_seq", choices=['off', 'single', 'random', 'all_one', 'block1'],
                            help="set fake rng sequence")
    parser_set.add_argument("--feedback", choices=['on', 'off'], 
                            help="balance interferometer")
    parser_set.add_argument("--insert_zeros", choices=['on', 'off'], 
                            help="insert zeros into rng sequence for feedback")
    parser_set.add_argument("--zero_pos", type=int, 
                            help="insert zeros at this position for feedback")
    parser_set.add_argument("--spd_mode", choices=['free', 'gated'], 
                            help="free running or gated")
    parser_set.add_argument("--spd_delay", type=int, metavar="time",  
                            help="delay time in ps")
    parser_set.add_argument("--spd_deadtime", type=int, metavar="time",
                            help="dead time in us; recommended: 15us for gated; 50us for freerunning")
    parser_set.add_argument("--spd_eff", choices=['10', '20', '30'], 
                            help="detection efficiency in percent; strongly recommended: 20")
    parser_set.add_argument("--soft_gate_filter", choices=['off', 'on'], 
                            help="filter events through time gates")
    parser_set.add_argument("--soft_gates", nargs=3, type=int, 
                            metavar=['gate0 gate1 width'],
                            help="set gate positions and width")
    parser_set.add_argument("--pm_mode", choices=['seq64', 'seq64tight', 'fake_rng', 'true_rng', 'off'],
                            help="fixed periodic sequece, fake rng or real rng")
    
    parser_set.add_argument("--pol_bias",nargs=4, type=float, metavar="V",  help="float [0,5] V")
    
    parser_set.add_argument("--pos",type=int, default=0, help="peak position for single")
    


######### get  ###########
    parser_get.add_argument("--counts", action="store_true", 
                            help="get SPD counts")
    parser_get.add_argument("--counts2", action="store_true", 
                            help="get SPD counts averaged over 1s")
    parser_get.add_argument("--time", type=int, metavar="num_counts",
                            help="download timestamps of spd clicks")
    parser_get.add_argument("--get_gc", action="store_true",
                            help="get current global counter")
#    parser_get.add_argument("--angles", action="store_true",
#                            help="download the postprocessed angles")

    parser_set.add_argument("--angles", nargs=4, type=float, 
                            help="float [-1,1]")
    parser_set.add_argument("--pm_shift", type=int, metavar=("steps"), 
                            help="time shift signal for phase modulator in steps of 1.25ns")


######### debug ###########
    parser_debug.add_argument("--t0", type=int, 
                              help = "set t0")
    parser_debug.add_argument("--measure", action="store_true", 
                              help = "measure and find first peak")

    
    parser_init.set_defaults(func=init)
    parser_debug.set_defaults(func=debug)
    parser_set.set_defaults(func=set)
    parser_get.set_defaults(func=get)
    
    args = parser.parse_args()
    args.func(args)


if __name__ =="__main__":
    main()









