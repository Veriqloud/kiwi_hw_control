#!/bin/python

#import argparse
import os
import time
import numpy as np
#import datetime 
#import mmap
import lib.gen_seq as gen_seq
from lib.fpga import *


def Set_Vca(voltage):
    if (voltage>5) or (voltage<0):
        print("Voltage out of range. Choose a value between 0 and 5")
        exit()
    Set_vol(7, voltage)
    update_tmp('vca', voltage)

def Set_Am_Bias(voltage):
    Set_vol(5, voltage)
    update_tmp('am_bias', voltage)

def Set_Am_Bias_2(voltage):
    if (voltage>10) or (voltage<0):
        print("Voltage out of range. Choose a value between 0 and 10")
        exit()
    Set_vol(4, voltage)
    update_tmp('am_bias_2', voltage)


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



    
    
def Update_Dac():
    # update from tmp.txt
    # Generate sequences for dac0 and dac1 and write to device.
    # Update am_shift and pm_shift
    t = get_tmp()
    if t['am_mode'] == 'off':
        dac0 = gen_seq.dac0_off(64)
    elif t['am_mode'] == 'single':
        dac0 = gen_seq.dac0_single(64, t['am_shift'])
    elif t['am_mode'] == 'double':
        dac0 = gen_seq.dac0_double(64, t['qdistance'], t['am_shift'])
    elif t['am_mode'] == 'single64':
        dac0 = gen_seq.dac0_single_single(64, t['am_shift'])

    if t['pm_mode'] == 'off':
        Write_Pm_Mode('seq64')
        dac1 = gen_seq.dac1_sample(np.zeros(64), t['pm_shift'])
    elif t['pm_mode'] == 'seq64':
        Write_Pm_Mode('seq64')
        dac1 = gen_seq.dac1_sample(gen_seq.lin_seq_2(), t['pm_shift'])
    elif t['pm_mode'] == 'seq64tight':
        Write_Pm_Mode('seq64')
        dac1 = gen_seq.dac1_sample_tight(gen_seq.lin_seq_2(), t['pm_shift'])
    elif t['pm_mode'] == 'fake_rng':
        Write_Pm_Mode('fake_rng', insert_zeros=t['insert_zeros'])
        Write_Angles(t['angle0'], t['angle1'], t['angle2'], t['angle3'])
        dac1 = gen_seq.dac1_sample(np.zeros(64), 0)
    elif t['pm_mode'] == 'true_rng':
        Write_Pm_Mode('true_rng', insert_zeros=t['insert_zeros'])
        Write_Angles(t['angle0'], t['angle1'], t['angle2'], t['angle3'])
        dac1 = gen_seq.dac1_sample(np.zeros(64), 0)
    
    Write_To_Dac(dac0, dac1)
    Write_Pm_Shift(t['pm_shift']%10, t['zero_pos'])
    #print("Dac", t['am_mode'], t['pm_mode'], t['am_shift'], t['pm_shift'], t['insert_zeros'])
    

def Update_Angles():
    t = get_tmp()
    Write_Angles(t['angle0'], t['angle1'], t['angle2'], t['angle3'])


def Update_Decoy():
    t = get_tmp()
    decoy_state(t['am2_mode'])


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
#    print(hex(current_gc))
#    print(current_gc/40e6, 's')
#    return current_gc







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
    t['am_shift'] = d['am_shift']
    t['pm_shift'] = d['pm_shift']
    t['am_mode'] = 'off'
    t['pm_mode'] = 'off'
    t['qdistance'] = d['qdistance']
    save_tmp(t)
    Update_Angles()
    Update_Dac()
    Config_Fda()

def init_sda():
    Config_Sda()
    for i in range(8):
     Set_vol(i, 0)
    d = get_default()
    Set_Vca(d['vca'])
    Set_Am_Bias(d['am_bias'])
    Set_Am_Bias_2(d['am_bias_2'])

def init_apply_default():
    default_file = HW_CONTROL+'config/default.txt'
    if os.path.exists(default_file):
        return
    d = get_default()
    t = get_tmp()
    t['vca'] = d['vca'] 
    t['qdistance'] = d['qdistance']
    t['am_bias'] = d['am_bias']
    t['am_bias_2'] = d['am_bias_2']
    t['am_shift'] = d['am_shift']
    t['pm_shift'] = d['pm_shift']
    t['angle0'] = d['angle0']
    t['angle1'] = d['angle1']
    t['angle2'] = d['angle2']
    t['angle3'] = d['angle3']
    t['fiber_delay'] = d['fiber_delay']
    t['fiber_delay_long'] = d['fiber_delay_long']
    t['fiber_delay_mod'] = d['fiber_delay']%32
    t['decoy_delay'] = d['decoy_delay']
    t['zero_pos'] = d['zero_pos']
    save_tmp(t)
    Set_Vca(t['vca'])
    Update_Dac()
    Update_Angles()

def init_rst_default():
    default_file = HW_CONTROL+'config/default.txt'
    if os.path.exists(default_file):
        return
    d = {}
    d['vca'] = 2
    d['qdistance'] = 0.095
    d['am_bias'] = -0.8
    d['am_bias_2'] = 6
    d['am_shift'] = 514
    d['pm_shift'] = 514
    d['angle0'] = 0
    d['angle1'] = 0.18
    d['angle2'] = -0.18
    d['angle3'] = 0.36
    d['fiber_delay'] = 0
    d['fiber_delay_long'] = 0
    d['decoy_delay'] = 0
    d['zero_pos'] = 0
    save_default(d)

def init_rst_tmp():
    tmp_file = HW_CONTROL+'config/tmp.txt'
    if os.path.exists(tmp_file):
        return
    t = {}
    t['am_mode'] = 'off'
    t['am2_mode'] = 'off'
    t['am_shift'] = 0
    t['pm_mode'] = 'off'
    t['pm_shift'] = 0
    t['vca'] = 0
    t['vca_calib'] = 0
    t['am_bias'] = 0
    t['am_bias_2'] = 0
    t['angle0'] = 0
    t['angle1'] = 0
    t['angle2'] = 0
    t['angle3'] = 0
    t['qdistance'] = 0
    t['fiber_delay_mod'] = 0
    t['fiber_delay'] = 0
    t['fiber_delay_long'] = 0
    t['decoy_delay'] = 0
    t['zero_pos'] = 0
    t['insert_zeros'] = 'off'
    save_tmp(t)

#def init_ddr():
#    Ddr_Data_Init()

def init_all():
    init_ltc()
    init_sync()
    init_fda()
    init_sda()
    decoy_reset()
    init_rst_tmp()
    init_rst_default()
    init_apply_default()


