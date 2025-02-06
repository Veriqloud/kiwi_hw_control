#!/bin/python

import subprocess, os, sys, argparse
import time
import numpy as np
import datetime 
import mmap
import gen_seq, cal_lib
from lib.config_lib import *
from lib.Aurea import Aurea




def Config_Fda():
    WriteFPGA()
    En_reset_jesd()
    Set_reg_powerup()
    Set_reg_plls()
    Set_reg_seq1() #seq1 include power, serdespll, dacpll
    Set_reg_seq2()
    Get_Id_Fda()
    ret_regs = Get_reg_monitor()
    while (ret_regs[2][2] == 'F'):
        En_reset_jesd()
        Set_reg_powerup()
        Set_reg_plls()
        Set_reg_seq1() #seq1 include power, serdespll, dacpll
        Set_reg_seq2()
        ret_regs = Get_reg_monitor()

#-------------------------PULSE GATE APD-------------------------------

def Gen_Gate(delay):
    timestep = 3.383    # fine delay timestep in ps
    delay_au = round(delay/timestep)
    fine_max = 404      # corresponds to 1/3 of coarse delay
    coarse = delay_au // (fine_max*3)
    fine0_abs = delay_au % fine_max
    fine1_abs = int((delay_au%(fine_max*3)) >= fine_max) * fine_max
    fine2_abs = int((delay_au%(fine_max*3)) >= 2*fine_max) * fine_max

    t = get_tmp()

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

    print(coarse, fine0, fine1, fine2)
    print(coarse, direction0, direction1, direction2)



    
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
    binfile = 'data/tdc/'+fileprefix+'.bin'
    txtfile = 'data/tdc/'+fileprefix+'.txt'
    Get_Stream(0x00000000+40,'/dev/xdma0_c2h_2',binfile, num_clicks)
    command ="test_tdc/tdc_bin2txt "+binfile+" "+txtfile
    s = subprocess.check_call(command, shell = True)

def Seq64():
    Base_Addr = 0x00030000
    Write(Base_Addr + 16, 0x0000a0a0) #sequence64
    #Write data to dpram_dac0 and dpram_dac1
    Base_seq0 = Base_Addr + 0x1000  #Addr_axi_sequencer + addr_dpram
    seq_list = gen_seq.seq_dac0_off(64,0) # am: off, pm: seq64

    vals = []
    for ele in seq_list:
        vals.append(int(ele,0))

    fd = open("/dev/xdma0_user", 'r+b', buffering=0)
    write_to_dev(fd, Base_seq0, 0, vals)
    fd.close()
    print("Set sequence off_am for dpram_dac0 and seq64 for dpram_dac1")

def Measure_Sp(num_clicks):
    Seq64()

    #Time_Calib_Reg(1, 0, 0, 0, 0, 0, 0)
    #Get detection result
    Download_Time(num_clicks, fileprefix="histogram_sp")

    ref_time = np.loadtxt("data/tdc/histogram_sp.txt",usecols=1,unpack=True,dtype=np.int32)
    ref_time_arr = (ref_time*20%25000)/20
    #Find first peak of histogram
    first_peak = cal_lib.Find_First_Peak(ref_time_arr)
    print("First peak: ",first_peak)
    peak_target = 40
    shift_am = ((peak_target-first_peak)%625)/62.5
    print("shift_am", shift_am)
    shift_am_out = int((shift_am-0.5)%10)
    t0 = (peak_target - first_peak - shift_am_out*62.5) % 625
    print("Shift for am: ",shift_am_out)
    print("Shift for t0: ",t0)
    return first_peak, shift_am_out

def Gen_Dp(first_peak):
    Seq64()

    Time_Calib_Reg(1, 0, 0, 0, 0, 0, 0)

    #Get detection result
    Download_Time(50000, fileprefix="histogram_dp")

    #Generate gate signal
    print("Generate Gate signal for APD")
    # gate_initial = [105,355]
    gate_initial = [0,339]
    # delay_time = (((first_peak + 80) - gate_initial[1])%625)*20
    delay_time = ((first_peak + 80 + 625) - gate_initial[1])*20
    print("Estimate delay time : ", delay_time, "ps")
    tune_delay_val = int(np.floor(delay_time/4166))
    print("Tune delay: ", tune_delay_val)
    ttl_reset()
    write_delay_master(2,tune_delay_val,50,1) #tap = 50 -> delay = 0.166ns
    write_delay_slaves(50,1,50,1)
    params_en()
    total_fine_delay = delay_time%4166
    fine_step = int(total_fine_delay/160) #fixing tap = 50
    print("Estimate fine step: ",fine_step)
    if (fine_step <= 9):
        for i in range(fine_step):
            trigger_fine_master()
    else:
        if (fine_step <= 18):
            for i in range(9):
                trigger_fine_master()
                # time.sleep(1)
            for i in range(fine_step - 9):
                trigger_fine_slv1()
                # time.sleep(1)
        else:
            if (fine_step <= 27):
                for i in range(9):
                    trigger_fine_master()
                    # time.sleep(1)
                    trigger_fine_slv1()
                    # time.sleep(1)
                for i in range(fine_step-18):
                    trigger_fine_slv2()
                    # time.sleep(1)
            else:
                for i in range(9):
                    trigger_fine_master()
                    # time.sleep(1)
                    trigger_fine_slv1()
                    # time.sleep(1)
                    trigger_fine_slv2()
                    # time.sleep(1)                                

    #APD switch to gated mode
    subprocess.run("cd /home/vq-user/Aurea_API/OEM_API_Linux/Examples/Python && python Aurea.py --mode gated && python Aurea.py --dt 10 && python Aurea.py --eff 20 ", shell = True)

    Get_Stream(0x00000000+40,'/dev/xdma0_c2h_2','data/tdc/output_gate_apd.bin',50000)
    command ="test_tdc/tdc_bin2txt data/tdc/output_gate_apd.bin data/tdc/histogram_gate_apd.txt"
    s = subprocess.check_call(command, shell = True)

    #Find_Gate
    ref_time = np.loadtxt("data/tdc/histogram_gate_apd.txt",usecols=1,unpack=True,dtype=np.int32)
    ref_time_arr = (ref_time*20%12500)/20
    #Generate bin counts and bin edges
    counts,bins_edges = np.histogram(ref_time_arr,bins=625)
    gw = 60
    print("first peak return: ", first_peak)
    gate1_start = int((first_peak - 5)%625)
    gate0_start = int((gate1_start - 110)%625)
    print(f"gate0_start : {gate0_start}")
    print(f"gate1_start : {gate1_start}")
    #Set gate parameter
    Time_Calib_Reg(2, 0, 0, gate0_start, gw, gate1_start, gw)
    #Get detection result
    print("OUTPUT GATED DETECTION")
    Get_Stream(0x00000000+40,'/dev/xdma0_c2h_2','data/tdc/output_gated.bin',100000)
    command ="test_tdc/tdc_bin2txt data/tdc/output_gated.bin data/tdc/histogram_gated.txt"
    s = subprocess.check_call(command, shell = True)

def Verify_Shift_B(party,shift_am):
    Base_Addr = 0x00030000
    Write(Base_Addr + 16, 0x0000a0a0) #sequence64
    #Write data to dpram_dac0 and dpram_dac1
    Base_seq0 = Base_Addr + 0x1000  #Addr_axi_sequencer + addr_dpram
    for i in range(10):
        seq_list = gen_seq.seq_dacs_dp(2,[-0.95,0.95],64,i,320,shift_am) # am: off, pm: seq64
        vals = []
        for ele in seq_list:
            vals.append(int(ele,0))
        fd = open("/dev/xdma0_user", 'r+b', buffering=0)
        write_to_dev(fd, Base_seq0, 0, vals)
        fd.close()
        Write_Dac1_Shift(0,0,0,0,0,0)
        # print("Set seq64 for PM, shift value from find_shift")
        print("Get detection result")
        Get_Stream(0x00000000+40,'/dev/xdma0_c2h_2','data/tdc/pm_b_shift_'+str(i+1)+'.bin',40000)
        # command ="test_tdc/tdc_bin2txt data/tdc/output_gated.bin data/tdc/histogram_gated.txt"
        # s = subprocess.check_call(command, shell = True)
    for i in range(10):
        command ="test_tdc/tdc_bin2txt data/tdc/pm_b_shift_"+str(i+1)+".bin data/tdc/pm_b_shift_"+str(i+1)+".txt"
        s = subprocess.check_call(command, shell = True)


def Verify_Shift_A(party, shift_pm, shift_am):
    Write_Dac1_Shift(2,0,0,0,0,0)
    print("Set phase of PM to zero")
    print("Get detection result")
    Get_Stream(0x00000000+40,'/dev/xdma0_c2h_2','data/tdc/pm_a_shift_'+str(shift_pm+1)+'.bin',40000)
    command ="test_tdc/tdc_bin2txt data/tdc/pm_a_shift_"+str(shift_pm+1)+".bin data/tdc/pm_a_shift_"+str(shift_pm+1)+".txt"
    s = subprocess.check_call(command, shell = True)

def Find_Best_Shift(party):
    best_shift = cal_lib.Best_Shift(party)
    return best_shift

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


def Phase_Drift_Test():
    #dpram_rng_max_addr
    Base_Addr = 0x00030000
    Write(Base_Addr + 28, 0x4e20)
    #Write_Dac1_shift
    for j in range(33):
        Write_Dac1_Shift(2,-1+j*0.0625,-1+j*0.0625,0 ,0,0)
        Get_Stream(0x00000000+40,'/dev/xdma0_c2h_2','data/tdc/testphase_'+str(j+1)+'.bin',640) 

    for i in range(33):
        command ="test_tdc/tdc_bin2txt data/tdc/testphase_"+str(i+1)+".bin data/tdc/testphase_"+str(i+1)+".txt"
        s = subprocess.check_call(command, shell = True)


def Feedback_Phase():
    #dpram_rng_max_addr
    Base_Addr = 0x00030000
    Write(Base_Addr + 28, 0x0008)
    #Write data to rng_dpram
    Base_seq0 = 0x00030000 + 0x2000  #Addr_axil_sequencer +   addr_dpram
    rngseq = 0x1b1b1b1b
    Write(Base_seq0, rngseq)
    #Write amplitude
    #amp = np.array([-0.5,-0.2, 0.2, 0.5])
    amp = np.array([0.2, 0.2, 0.2, 0.2])
    Write_Dac1_Shift(14, amp[0], amp[1], amp[2], amp[3], 8)

def Find_Opt_Delay_AB_mod32(party,shift_pm):
    dpram_max_addr = 32
    Write_Dac1_Shift(6, 0, 0, 0, 0, shift_pm)
    time.sleep(5)
    Get_Stream(0x00000000+40,'/dev/xdma0_c2h_2','data/tdc/output_gated.bin',250000)
    command ="test_tdc/tdc_bin2txt data/tdc/output_gated.bin data/tdc/histogram_gated.txt"
    s = subprocess.check_call(command, shell = True)
    #Process to get delay val
    int_click_gated = np.loadtxt("data/tdc/histogram_gated.txt",usecols=(2,3,4),unpack=True, dtype=np.int64)

    seq = dpram_max_addr*2  #[q_bins]
    times_ref_click0 = []
    times_ref_click1 = []
    for i in range(len(int_click_gated[1])):
        if (int_click_gated[1][i] == 0):
            if (int_click_gated[2][i] == 0):
                gc_q = (int_click_gated[0][i]%(seq/2))*2
            elif(int_click_gated[2][i] == 1):
                gc_q = (int_click_gated[0][i]%(seq/2))*2 + 1
            times_ref_click0.append(gc_q)
        elif (int_click_gated[1][i] == 1):
            if (int_click_gated[2][i] == 0):
                gc_q = (int_click_gated[0][i]%(seq/2))*2
            elif(int_click_gated[2][i] == 1):
                gc_q = (int_click_gated[0][i]%(seq/2))*2 + 1
            times_ref_click1.append(gc_q)

    n0, bins0 = np.histogram(times_ref_click0, seq)
    n1, bins1 = np.histogram(times_ref_click1, seq)
    index = np.argmax(np.abs(n1-n0))
    print("Fiber Delay Alice-Bob in mode 32-gcs period: ",index, " [q_bins]")
    return int(index)

def Find_Opt_Delay_AB(party,shift_pm,delay_mod):
    dpram_max_addr = 4000
    non_zero_addr = 32
    # start_position = 64 - 44  #40 q_bins returned from mod32
    start_position = 64 - delay_mod
    # dpram_max_addr = 4000
    #with 100km, doesn't work with write to dev() function, maybe need to offset
    # non_zero_addr = 80
    if (party == 'alice'):
        Base_Addr = 0x00030000
        Base_seq0 = 0x00030000 + 0x2000  #Addr_axil_sequencer +   addr_dpram
        Write(Base_Addr + 28, hex(dpram_max_addr))
        #Write data to rng_dpram
        # list_rng = gen_seq.seq_rng_long(dpram_max_addr,non_zero_addr)
        list_rng = gen_seq.seq_rng_fd(dpram_max_addr,start_position)
        vals = []
        for l in list_rng:
            vals.append(int(l, 0))
        fd = open("/dev/xdma0_user", 'r+b', buffering=0)
        write_to_dev(fd, Base_seq0, 0, vals)
        fd.close()
        # file0 = open('data/fda/seqrng_gen/SeqRng.txt','r') #Use this file for 0.5ms distance
        # counter = 0
        # for l in file0.readlines():
        #     counter += 1
        #     Base_seq = str(hex(int(Base_seq0) + (counter-1)*4))
        #     Write(Base_seq, l)
        #     #print(Base_seq)
        #     #print(l)
        # print("Set rng sequence for DAC1 finished")
        # file0.close()

        #Write amplitude
        amp = np.array([0 ,0, 0.45, 0])
        Write_Dac1_Shift(2, amp[0], amp[1], amp[2], amp[3], shift_pm)
        #Reset jesd module
        En_reset_jesd()
        # Config_Fda()
        print("Apply phase for long distance mode")
        # Config_Fda()

        #Write amplitude
    if (party == 'bob'):
        Write_Dac1_Shift(6, 0, 0, 0, 0, shift_pm)
        time.sleep(10)
        Get_Stream(0x00000000+40,'/dev/xdma0_c2h_2','data/tdc/output_gated.bin',500000)
        command ="test_tdc/tdc_bin2txt data/tdc/output_gated.bin data/tdc/histogram_gated.txt"
        s = subprocess.check_call(command, shell = True)

        #Process to get delay val
        int_click_gated = np.loadtxt("data/tdc/histogram_gated.txt",usecols=(2,3,4),unpack=True, dtype=np.int64)

        seq = dpram_max_addr*2  #[q_bins]
        times_ref_click0 = []
        times_ref_click1 = []
        for i in range(len(int_click_gated[1])):
            if (int_click_gated[1][i] == 0):
                if (int_click_gated[2][i] == 0):
                    gc_q = (int_click_gated[0][i]%(seq/2))*2
                elif(int_click_gated[2][i] == 1):
                    gc_q = (int_click_gated[0][i]%(seq/2))*2 + 1
                times_ref_click0.append(gc_q)
            elif (int_click_gated[1][i] == 1):
                if (int_click_gated[2][i] == 0):
                    gc_q = (int_click_gated[0][i]%(seq/2))*2
                elif(int_click_gated[2][i] == 1):
                    gc_q = (int_click_gated[0][i]%(seq/2))*2 + 1
                times_ref_click1.append(gc_q)

        n0, bins0 = np.histogram(times_ref_click0, int(dpram_max_addr/non_zero_addr))
        n1, bins1 = np.histogram(times_ref_click1, int(dpram_max_addr/non_zero_addr))
        index = np.argmax(np.abs(n1-n0))
        index_arr = np.abs(n1-n0)
        print("Fiber Delay Alice-Bob : ",index, "[index] = ",index*non_zero_addr*2 ," [q_bins]")

def Find_Opt_Delay_A(shift_pm):
    # Write_Dac1_Shift(6, 0, 0, 0, 0, shift_pm)
    # Write_Dac1_Shift(2, 0, 0, 0, 0, shift_pm)
    Write_Dac1_Shift(2, 0, 0, 0, 0, 0)
    subprocess.run("cd /home/vq-user/Aurea_API/OEM_API_Linux/Examples/Python && python Aurea.py --mode continuous && python Aurea.py --dt 100 ", shell = True)
    Time_Calib_Reg(1, 0, 0, 0, 0, 0, 0)

    time.sleep(2)
    Get_Stream(0x00000000+40,'/dev/xdma0_c2h_2','data/tdc/output_fd.bin',20000)
    command ="test_tdc/tdc_bin2txt data/tdc/output_fd.bin data/tdc/histogram_fd.txt"
    s = subprocess.check_call(command, shell = True)

    #Process to get delay val
    int_click_gated = np.loadtxt("data/tdc/histogram_fd.txt",usecols=(2,3,4),unpack=True, dtype=np.int64)
    print("Get detection result")
    # seq = dpram_max_addr*2  #[q_bins]
    # times_ref_click0 = []
    # times_ref_click1 = []
    # for i in range(len(int_click_gated[1])):
    #     if (int_click_gated[1][i] == 0):
    #         if (int_click_gated[2][i] == 0):
    #             gc_q = (int_click_gated[0][i]%(seq/2))*2
    #         elif(int_click_gated[2][i] == 1):
    #             gc_q = (int_click_gated[0][i]%(seq/2))*2 + 1
    #         times_ref_click0.append(gc_q)
    #     elif (int_click_gated[1][i] == 1):
    #         if (int_click_gated[2][i] == 0):
    #             gc_q = (int_click_gated[0][i]%(seq/2))*2
    #         elif(int_click_gated[2][i] == 1):
    #             gc_q = (int_click_gated[0][i]%(seq/2))*2 + 1
    #         times_ref_click1.append(gc_q)

    # n0, bins0 = np.histogram(times_ref_click0, int(dpram_max_addr/non_zero_addr))
    # n1, bins1 = np.histogram(times_ref_click1, int(dpram_max_addr/non_zero_addr))
    # index = np.argmax(np.abs(n1-n0))
    # index_arr = np.abs(n1-n0)
    # print("Fiber Delay Alice-Bob : ",index, "[index] = ",index*non_zero_addr*2 ," [q_bins]")


def Find_Opt_Delay_B(shift_pm):
    #dpram_rng_max_addr
    Base_Addr = 0x00030000
    Base_seq0 = 0x00030000 + 0x2000  #Addr_axil_sequencer +   addr_dpram
    dpram_max_addr = 32
    Write(Base_Addr + 28, hex(dpram_max_addr))
    #Write data to rng_dpram
    list_rng = gen_seq.seq_rng_short(dpram_max_addr)
    vals = []
    for l in list_rng:
        vals.append(int(l, 0))
    fd = open("/dev/xdma0_user", 'r+b', buffering=0)
    write_to_dev(fd, Base_seq0, 0, vals)
    fd.close()
    #Write amplitude
    amp = np.array([0,0, 0.45, 0])
    Write_Dac1_Shift(6, amp[0], amp[1], amp[2], amp[3], shift_pm)
    #Reset jesd module
    # WriteFPGA()
    En_reset_jesd()
    # Config_Fda()
    # Config_Fda()
    print("Apply phase in period of 32 gcs")
    time.sleep(3)
    #Get detection result
    Get_Stream(0x00000000+40,'/dev/xdma0_c2h_2','data/tdc/output_gated.bin',150000)
    command ="test_tdc/tdc_bin2txt data/tdc/output_gated.bin data/tdc/histogram_gated.txt"
    s = subprocess.check_call(command, shell = True)
    #Process to get delay val
    int_click_gated = np.loadtxt("data/tdc/histogram_gated.txt",usecols=(2,3,4),unpack=True, dtype=np.int64)

    seq = dpram_max_addr*2  #[q_bins]
    times_ref_click0 = []
    times_ref_click1 = []
    for i in range(len(int_click_gated[1])):
        if (int_click_gated[1][i] == 0):
            if (int_click_gated[2][i] == 0):
                gc_q = (int_click_gated[0][i]%(dpram_max_addr))*2
            elif(int_click_gated[2][i] == 1):
                gc_q = (int_click_gated[0][i]%(dpram_max_addr))*2 + 1
            times_ref_click0.append(gc_q)
        elif (int_click_gated[1][i] == 1):
            if (int_click_gated[2][i] == 0):
                gc_q = (int_click_gated[0][i]%(seq/2))*2
            elif(int_click_gated[2][i] == 1):
                gc_q = (int_click_gated[0][i]%(seq/2))*2 + 1
            times_ref_click1.append(gc_q)


    n0, bins0 = np.histogram(times_ref_click0, seq)
    n1, bins1 = np.histogram(times_ref_click1, seq)
    # bin_center0 = (bins0[:-1] + bins0[1:])/2
    # bin_center1 = (bins1[:-1] + bins1[1:])/2

    index = np.argmax(np.abs(n1-n0))
    print("Fiber delay of Bob: ",index, " [q_bins]")

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


#----------MONITORING REGISTERS-------------------
#Read back monitoring signal
def Count_Mon():
    print("-----------DISPLAY NUMBER OF COUNTS--------------")
    BaseAddr = 0x00000000
    #Write(BaseAddr + 32, 0x4)
    #for i in range (20):
    while True:
        total_count = Read(BaseAddr + 64)
        hex_total_count = total_count.decode('utf-8').strip()
        dec_total_count = int(hex_total_count, 16)
        #print(f"Total count: {dec_total_count}",end ='\r', flush=True)
        click0_count = Read(BaseAddr + 60)
        hex_click0_count = click0_count.decode('utf-8').strip()
        dec_click0_count = int(hex_click0_count, 16)
        #print(f"Click0 count: {dec_click0_count}",end ='\r', flush=True)
        click1_count = Read(BaseAddr + 56)
        hex_click1_count = click1_count.decode('utf-8').strip()
        dec_click1_count = int(hex_click1_count, 16)
        time.sleep(0.1)
        print(f"Total: {dec_total_count}, Click0: {dec_click0_count}, Click1: {dec_click1_count}               ",flush=True)

def Read_Count():
    BaseAddr = 0x00000000
    total_count = Read(BaseAddr + 64)
    hex_total_count = total_count.decode('utf-8').strip()
    dec_total_count = int(hex_total_count, 16)
    print("Total count: ", dec_total_count)
    return dec_total_count

#------------------------------DDR4 TESTING-----------------------------------
# Testing AXIS write and read DDR4 through AXI Virtual FIFO
# threshold define speed of reading gc_in_fifo
# 199999 for 1kHz click rate
def Ddr_Data_Reg(command,current_gc,read_speed, fiber_delay, pair_mode):
    #set_command_gc, slv_reg2[3]=1
    #Write(0x00001000+8,0x8)
    #Set_command
    Write(0x00001000+8,hex(int(command)))
    #Write dq_gc_start
    dq_gc_start = np.int64(current_gc) #+s
    print(hex(dq_gc_start)) 
    gc_lsb = dq_gc_start & 0xffffffff
    #print(hex(gc_lsb))
    gc_msb = (dq_gc_start & 0xffff00000000)>>32
    #print(hex(gc_msb))
    #Write dq_gc_start
    threshold_full = 4000 #optinal for debug
    Write(0x00001000+16,hex(gc_lsb))
    Write(0x00001000+20,hex(gc_msb))
    Write(0x00001000+32,hex(read_speed))
    Write(0x00001000+36,hex(threshold_full))
    Write(0x00001000+40,hex(fiber_delay))
    Write(0x00001000+24,hex(pair_mode<<1))
    #Enable register setting
    Write(0x00001000+12,0x0)
    Write(0x00001000+12,0x1)

def Ddr_Data_Init():
    #Reset module
    Write(0x00001000, 0x00) #Start write ddr = 0
    Write(0x00012000 + 16,0x00)
    #time.sleep(0.1)
    Write(0x00012000 + 16,0x01)
    time.sleep(1)
    print("Reset ddr data module")

#Test Get_Gc() in python
def Get_Gc():
    #Start to write 
    Write(0x00001000, 0x00) 
    Write(0x00001000, 0x01) 
    #Command_enable -> Reset the fifo_gc_out
    Write(0x00001000+28,0x0)
    Write(0x00001000+28,0x1)
    #----------------------------------
    #Command enable to save alpha
    Write(0x00001000+24,0x0)
    Write(0x00001000+24,0x1)

    device_c2h = '/dev/xdma0_c2h_0'
    count = 16
    data = b'' #declare bytes object
    
    try:
        with open(device_c2h, 'rb') as f:
            while True:
                data = f.read(count)
                if not data:
                    print("No available data on stream")
                    break
                print(f"Read {len(data)} bytes: {data.hex()}")
    except FileNotFoundError:
        print(f"Device not found")    
    except PermissionError:
        print(f"Permission to file is denied")
    except Exception as e:
        print(f"Error occurres: {e}")

# def Get_Gc():
#     device_c2h = '/dev/xdma0_c2h_0'
#     fileout = 'data/ddr4/gc_out.bin'
#     device_h2c = '/dev/xdma0_h2c_0'
#     count = 64
#     #Start to write 
#     Write(0x00001000, 0x00) 
#     Write(0x00001000, 0x01) 
#     #Command_enable -> Reset the fifo_gc_out
#     Write(0x00001000+28,0x0)
#     Write(0x00001000+28,0x1)
#     #----------------------------------
#     #Command enable to save alpha
#     Write(0x00001000+24,0x0)
#     Write(0x00001000+24,0x1)
#     #----------------------------------
#     #Read from fifo_gc_out and push back to fifo_gc_in
#     try:
#         command ="test_tdc/dma_loop "+"-d "+ device_c2h +" -f "+ device_h2c+ " -c " + str(count) 
#         s = subprocess.check_call(command, shell = True)
#     except subprocess.CalledProcessError as e:
#         print("Exit get_gc process")
#         sys.exit(e.returncode)

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
    print(current_gc)
    return current_gc


def Read_Angle():
    current_gc = Get_Current_Gc()
    Ddr_Data_Reg(3,current_gc + 40000000, 199999)
    #Command enable
    Write(0x00001000+24,0x0)
    Write(0x00001000+24,0x1)
    time.sleep(2)
    device_c2h = '/dev/xdma0_c2h_3'
    output_file = 'data/ddr4/alpha.bin'
    size = 16
    count = 16 #1s, the rate is 1k, 2bits in 1ms -> 128bits in 64ms 
    for i in range(1):
        command ="test_tdc/dma_from_device "+"-d "+ device_c2h +" -f "+ output_file+ " -c " + str(count) 
        s = subprocess.check_call(command, shell = True)
        time.sleep(1)

def Angle():
    #Readback 
    device_c2h = '/dev/xdma0_c2h_3'
    output_file = 'data/ddr4/alpha.bin'
    size = 16
    count = 32
    for i in range(1):
    #while True:
    #    Read_stream(device_c2h,output_file,size,count)
        command ="test_tdc/dma_from_device "+"-d "+ device_c2h +" -f "+ output_file+ " -c " + str(count) 
        s = subprocess.check_call(command, shell = True)
        time.sleep(1)

def Ddr_Status():
    while True:
        ddr_fifos_status = Read(0x00001000 + 52)
        fifos_status = Read(0x00001000 + 56)
        hex_ddr_fifos_status = ddr_fifos_status.decode('utf-8').strip()
        hex_fifos_status = fifos_status.decode('utf-8').strip()
        vfifo_idle = (int(hex_ddr_fifos_status,16) & 0x180)>>7
        vfifo_empty = (int(hex_ddr_fifos_status,16) & 0x60)>>5
        vfifo_full = (int(hex_ddr_fifos_status,16) & 0x18)>>3
        gc_out_full = (int(hex_ddr_fifos_status,16) & 0x4)>>2
        gc_in_empty = (int(hex_ddr_fifos_status,16) & 0x2)>>1
        alpha_out_full = int(hex_ddr_fifos_status,16) & 0x1

        gc_out_empty = (int(hex_fifos_status,16) & 0x4)>>2
        gc_in_full = (int(hex_fifos_status,16) & 0x2)>>1
        alpha_out_empty = int(hex_fifos_status,16) & 0x1
        current_time = datetime.datetime.now()
        print(f"Time: {current_time} VF: {vfifo_full} VE: {vfifo_empty}, VI: {vfifo_idle} | gc_out_f,e: {gc_out_full},{gc_out_empty} | gc_in_f,e: {gc_in_full},{gc_in_empty} | alpha_out_f,e: {alpha_out_full},{alpha_out_empty}", flush=True)
        #print("Time: {current_time}  VF: {vfifo_full}, VE: {vfifo_empty}, VI: {vfifo_idle} | gc_out_f,e: {gc_out_full}, {gc_out_empty} | gc_in_f,e: {gc_in_full}, {gc_in_empty} | alpha_out_f,e: {alpha_out_full}, {alpha_out_empty}                                                                      " ,end ='\r', flush=True)
        time.sleep(0.1)



#------------------------------MAIN----------------------------------------------------------------------------------
def main():
    def init(args):
        if args.ltc:
            Config_Ltc()
        elif args.fda:
            Config_Fda()
        elif args.sync:
            Sync_Ltc()
        elif args.sda:
            Config_Sda()
            d = get_default()
        elif args.fda:
            Config_Fda()
        elif args.jic:
            Config_Jic()
        elif args.tdc:
            Time_Calib_Reg(1, 0, 0, 0, 0, 0, 0)
            Time_Calib_Init()
        elif args.ttl:
            ttl_reset()
            t = get_tmp()
            t['gate_delayf0'] = 0
            t['gate_delayf1'] = 0
            t['gate_delayf2'] = 0
            save_tmp(t)
        elif args.all:
            Config_Ltc()
            Sync_Ltc()
            Write_Sequence_Dacs('dp')
            Write_Sequence_Rng()
            Write_Dac1_Shift(2, 0, 0, 0, 0, 0)
            Config_Fda()
            Config_Sda()
            Config_Jic()
            Time_Calib_Reg(1, 0, 0, 0, 0, 0, 0)
            Time_Calib_Init()
            ttl_reset()
            Gen_Gate(0)
            t = get_tmp()
            t['gate_delayf0'] = 0
            t['gate_delayf1'] = 0
            t['gate_delayf2'] = 0
            save_tmp(t)
    def set(args):
        if args.rng_mode:
            angles = np.loadtxt("config/angles.txt", dtype=float)
            d = get_default()
            if args.rng_mode=='seq':
                mode = 0
            elif args.rng_mode=='fake_rng':
                mode = 2
            elif args.rng_mode=='true_rng':
                mode = 3
            t = get_tmp()
            Write_Dac1_Shift(mode+(t['feedback']<<2), angles[0], angles[1], angles[2], angles[3], d['shift'])
            t['rng_mode'] = mode
            save_tmp(t)
        elif args.feedback:
            angles = np.loadtxt("config/angles.txt", dtype=float)
            d = get_default()
            t = get_tmp()
            if args.feedback=="on":
                feedback = 1
            elif args.feedback=="off":
                feedback = 0
            Write_Dac1_Shift(t['rng_mode']+(feedback<<2), angles[0], angles[1], angles[2], angles[3], d['shift'])
            t['feedback'] = feedback
            save_tmp(t)
        elif args.spd_mode:
            print("opening SPD...")
            aurea = Aurea()
            if args.spd_mode=="free":
                aurea.mode("continuous")
            elif args.spd_mode=="gated":
                d = get_default()
                aurea.mode("gated")
                Gen_Gate(d['gate_delay'])
        elif not (args.spd_deadtime==None):
            print("opening SPD...")
            aurea = Aurea()
            aurea.deadtime(args.spd_deadtime)
        elif not (args.spd_eff==None):
            print("opening SPD...")
            aurea = Aurea()
            aurea.effi(int(args.spd_eff))
        elif not (args.spd_delay==None):
            delay = int(args.spd_delay*1000)    # translate to ps
            Gen_Gate(delay)
            d = get_default()
            d['gate_delay'] = delay
            save_default(d)
            print("gate pulse delay set to", delay/1000, "sn")
        elif args.pol_bias is not None:
            for ch,vol in enumerate(args.pol_bias):
                if (vol>5 or vol <0):
                    exit ("voltage not in the good range")
                Set_vol(ch,vol)
    def get(args):
        if args.counts:
            Count_Mon()
        elif args.time:
            Download_Time(args.time)





    def debug(args):
        if args.reset_defaults:
            d = {}
            d['gate_delay'] = 0
            save_default(d)
        elif args.reset_tmp:
            t = {}
            t['rng_mode'] = 0
            t['feedback'] = 0
            t['first_peak'] = 20
            t['gate_delayf0'] = 0
            t['gate_delayf1'] = 0
            t['gate_delayf2'] = 0
            t['first_peak'] = 0
            t['t0'] = 0
            save_tmp(t)
        elif args.t0 is not None:
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


######### set ###########
    parser_set.add_argument("--rng_mode", choices=['seq', 'fake_rng', 'true_rng'],
                            help="fixed periodic sequece, fake rng or real rng")
    parser_set.add_argument("--feedback", choices=['on', 'off'], 
                            help="balance interferometer")
    parser_set.add_argument("--spd_mode", choices=['free', 'gated'], 
                            help="free running or gated")
    parser_set.add_argument("--spd_delay", type=float, metavar="time",  
                            help="delay time in ns [range..]")
    parser_set.add_argument("--spd_deadtime", type=float, metavar="time",
                            help="dead time in us; recommended: 15us for gated; 50us for freerunning")
    parser_set.add_argument("--spd_eff", choices=['10', '20', '30'], 
                            help="detection efficiency in percent; strongly recommended: 20")

    
    parser_set.add_argument("--pol_bias",nargs=4, type=float, metavar="V",  help="float [0,5] V")
    
    parser_get.add_argument("--counts", action="store_true", 
                            help="get SPD counts")
    parser_get.add_argument("--time", type=int, metavar="num_counts",
                            help="download timestamps of spd clicks")


######### debug ###########
    parser_debug.add_argument("--reset_defaults", action="store_true", 
                              help="reset values stored in config/default.txt")
    parser_debug.add_argument("--reset_tmp", action="store_true", 
                              help="reset values stored in config/tmp.txt")
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









