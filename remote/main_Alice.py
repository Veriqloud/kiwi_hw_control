#!/bin/python

import subprocess, os, sys, argparse
import time
import numpy as np
import datetime 
import mmap
import lib.gen_seq as gen_seq
import lib.cal_lib as cal_lib
from lib.config_lib import *


def Set_Vca(voltage):
    if (voltage>5) or (voltage<0):
        print("Voltage out of range. Choose a value between 0 and 5")
        exit
    Set_vol(7, voltage)

def Set_Am_Bias(voltage):
    Set_vol(4, voltage)


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


#-------------------------GLOBAL COUNTER-------------------------------------------
def Reset_gc():
    Write(0x00000008,0x00) #Start_gc = 0
    Write(0x00012008,0x01)
    Write(0x00012008,0x00)
    time.sleep(2)
    print("Reset global counter......")

def Start_gc():
    BaseAddr = 0x00000000
    Write(BaseAddr + 8, 0x00000000)
    Write(BaseAddr + 8, 0x00000001)
    time.sleep(1)
    print("Global counter starts counting up from some pps")

    

def Gen_Sp(shift_am):
    # shift_am = 0
    Base_Addr = 0x00030000
    Write(Base_Addr + 16, 0x0000a0a0) #sequence64
    #Write data to dpram_dac0 and dpram_dac1
    Base_seq0 = Base_Addr + 0x1000  #Addr_axi_sequencer + addr_dpram
    seq_list = gen_seq.seq_dacs_sp(2, [-0.95,0.95], 64,0,shift_am) # am: double pulse, pm: seq64

    vals = []
    for ele in seq_list:
        vals.append(int(ele,0))

    fd = open("/dev/xdma0_user", 'r+b', buffering=0)
    write_to_dev(fd, Base_seq0, 0, vals)
    fd.close()
    print("Set sequence dp for dpram_dac0 and seq64 for dpram_dac1")
    Write_Dac1_Shift(2,0,0,0,0,0)
    print("Set mode 2 for fake rng")

def Gen_Dp(shift_am, qdistance):
    # shift_am = 2
    # qdistance = 0.08
    Base_Addr = 0x00030000
    Write(Base_Addr + 16, 0x0000a0a0) #sequence64
    #Write data to dpram_dac0 and dpram_dac1
    Base_seq0 = Base_Addr + 0x1000  #Addr_axi_sequencer + addr_dpram
    #seq_list = gen_seq.seq_dacs_dp(2, [-0.95,0.95], 64,0,0,shift_am) # am: double pulse, pm: seq64
    seq_list = gen_seq.seq_dacs_dp(2, [-1+qdistance,1-qdistance], 64,0,0,shift_am) # am: double pulse, pm: seq64

    vals = []
    for ele in seq_list:
        vals.append(int(ele,0))

    fd = open("/dev/xdma0_user", 'r+b', buffering=0)
    write_to_dev(fd, Base_seq0, 0, vals)
    fd.close()
    print("Set sequence dp for dpram_dac0 and seq64 for dpram_dac1")
    Write_Dac1_Shift(2,0,0,0,0,0)
    print("Set mode 2 for fake rng")

def Verify_Shift_B(party,shift_am):
    Write_Dac1_Shift(2,0,0,0,0,0)
    print("Set phase of PM to zero")


def Verify_Shift_A(party, shift_pm, shift_am):
    Base_Addr = 0x00030000
    Write(Base_Addr + 16, 0x0000a0a0) #sequence64
    # Write data to dpram_dac0 and dpram_dac1
    Base_seq0 = Base_Addr + 0x1000  #Addr_axi_sequencer + addr_dpram
    seq_list = gen_seq.seq_dacs_dp(2, [-0.95,0.95], 64,shift_pm,510,shift_am) # am: off, pm: seq64
    vals = []
    for ele in seq_list:
        vals.append(int(ele,0))
    fd = open("/dev/xdma0_user", 'r+b', buffering=0)
    write_to_dev(fd, Base_seq0, 0, vals)
    fd.close()
    Write_Dac1_Shift(0,0,0,0,0,0)
    print("Set seq64 for PM, sweep shift value ")

def Find_Best_Shift(party):
    best_shift = cal_lib.Best_Shift(party)
    return best_shift



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
    #dpram_rng_max_addr
    Base_Addr = 0x00030000
    Base_seq0 = 0x00030000 + 0x2000  #Addr_axil_sequencer +   addr_dpram
    Write(Base_Addr + 28, hex(dpram_max_addr))
    #Write data to rng_dpram
    list_rng = gen_seq.seq_rng_short(dpram_max_addr)
    vals = []
    for l in list_rng:
        vals.append(int(l, 0))
    fd = open("/dev/xdma0_user", 'r+b', buffering=0)
    write_to_dev(fd, Base_seq0, 0, vals)
    fd.close()
    #Write amplitue
    amp = np.array([0 ,0, 0.45, 0])
    Write_Dac1_Shift(2, amp[0], amp[1], amp[2], amp[3], shift_pm)
    #Reset jesd module
    # En_reset_jesd()
    Config_Fda()
    print("Apply phase in period of 32 gcs")

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

def init_ltc():
    Config_Ltc()

def init_fda():
    Config_Fda()
    Seq_Dacs_Off()
    Write_Sequence_Rng()
    d = get_default()
    Write_Angles(d['angle0'], d['angle1'], d['angle2'], d['angle3'])
    t = get_tmp()
    Write_Pm_Shift(t['pm_shift'])

def init_sync():
    Sync_Ltc()

def init_sda():
    Config_Sda()
    t = get_tmp()
    d = get_default()
    Set_Vca(d['vca'])
    Set_Am_Bias(t['am_bias'])

def init_rst_default():
    d = {}
    d['vca'] = 4
    d['qdistance'] = 0.08
    d['angle0'] = 0
    d['angle1'] = 0
    d['angle2'] = 0
    d['angle3'] = 0
    save_default(d)

def init_rst_tmp():
    t = {}
    t['am_pulse'] = 'off'
    t['am_shift'] = 0
    t['am_bias'] = 0
    t['pm_mode'] = 'seq64'
    t['pm_shift'] = 0
    save_tmp(t)

def init_all():
    init_ltc()
    init_sync()
    init_fda()
    init_sda()


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
        elif args.all:
            init_all()
        elif args.rst_default:
            init_rst_default()
        elif args.rst_tmp:
            init_rst_tmp()
    def set(args):
        if not(args.vca==None):
            Set_Vca(args.vca)
        elif not(args.am_bias == None):
            Set_Am_Bias(args.am_bias)
        elif not(args.qdistance==None):
            t = get_tmp()
            Gen_Dp(t['am_shift'], args.qdistance)
            t['qdistance'] = args.qdistance
            save_tmp(t)
        elif args.rng_mode:
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
        elif args.am_shift is not None:
            t = get_tmp()
            t['am_shift'] = args.am_shift
            save_tmp(t)
            if t['am_pulse']=='single':
                Gen_Sp(t['am_shift'])
            else:
                Gen_Dp(t['am_shift'], t['qdistance'])
        elif args.am_pulse:
            t = get_tmp()
            if args.am_pulse=='single':
                Gen_Sp(t['am_shift'])
                t['am_pulse'] = 'single'
                save_tmp(t)
            elif args.am_pulse=='double':
                Gen_Dp(t['am_shift'], t['qdistance'])
                t['am_pulse'] = 'double'
                save_tmp(t)
            elif args.am_pulse=='off':
                t['am_pulse'] = 'off'
                Write_Sequence_Dacs('off_am')
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



            


    #create top_level parser
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(required=True)

    parser_init = subparsers.add_parser('init')
    parser_set = subparsers.add_parser('set')

######### init ###########
    parser_init.add_argument("--all", action="store_true", 
                             help="init all devices and sync")
    parser_init.add_argument("--ltc", action="store_true", 
                             help="init clock chip ltc")
    parser_init.add_argument("--fda", action="store_true", 
                             help="init fast dac")
    parser_init.add_argument("--sda", action="store_true", 
                             help="init slow dac")
    parser_init.add_argument("--sync", action="store_true", 
                             help="sync to PPS")
    parser_init.add_argument("--rst_default", action="store_true", 
                             help="reset default parameters in config/default.txt")
    parser_init.add_argument("--rst_tmp", action="store_true", 
                             help="reset tmp file in config/default.txt")


######### set ###########
    parser_set.add_argument("--vca", type=float, metavar=("voltage"), 
                            help="voltage controlled attenuator; float [0,5] V")
    parser_set.add_argument("--am_bias", type=float, metavar=("voltage"), 
                            help="bias of amplitude modulator; float [-10,10] V")
    parser_set.add_argument("--am_pulse", choices=['off', 'single', 'double'],
                            help="send single pulse or double pulse")
    parser_set.add_argument("--am_shift", type=int, metavar=("steps"), 
                            help="time shift pulse generation in steps of 1.25ns")
    parser_set.add_argument("--qdistance", type=float, metavar="value", 
                            help="fine tune double pulse separation; float [0,0.5]; good value is 0.08")
    parser_set.add_argument("--rng_mode", choices=['seq', 'fake_rng', 'true_rng'],
                            help="fixed periodic sequece, fake rng or real rng")
    
    parser_set.add_argument("--feedback", choices=['on', 'off'], 
                            help="balance interferometer")

    #parser_alice.add_argument("--init",action="store_true",help="initialize Alice")





    parser_init.set_defaults(func=init)
    parser_set.set_defaults(func=set)

    args = parser.parse_args()
    args.func(args)


if __name__ =="__main__":
    main()
