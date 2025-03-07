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
        exit()
    Set_vol(7, voltage)
    update_tmp('vca', voltage)

def Set_Am_Bias(voltage):
    Set_vol(4, voltage)
    update_tmp('am_bias', voltage)


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
        Write_Pm_Mode('fake_rng')
        dac1 = gen_seq.dac1_sample(np.zeros(64), 0)
    elif t['pm_mode'] == 'true_rng':
        Write_Pm_Mode('true_rng')
        dac1 = gen_seq.dac1_sample(np.zeros(64), 0)
    
    Write_To_Dac(dac0, dac1)
    Write_Pm_Shift(t['pm_shift']%10)
    print("Dac", t['am_mode'], t['pm_mode'], t['am_shift'], t['pm_shift'])
    

def Update_Angles():
    t = get_tmp()
    Write_Angles(t['angle0'], t['angle1'], t['angle2'], t['angle3'])













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






#------------------------------MAIN----------------------------------------------------------------------------------

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
    d = get_default()
    Set_Vca(d['vca'])
    Set_Am_Bias(d['am_bias'])

def init_apply_default():
    d = get_default()
    t = get_tmp()
    t['vca'] = d['vca'] 
    t['qdistance'] = d['qdistance']
    t['am_bias'] = d['am_bias']
    t['am_shift'] = d['am_shift']
    t['pm_shift'] = d['pm_shift']
    t['angle0'] = d['angle0']
    t['angle1'] = d['angle1']
    t['angle2'] = d['angle2']
    t['angle3'] = d['angle3']
    t['fiber_delay'] = d['fiber_delay']
    t['fiber_delay_mod'] = d['fiber_delay']%32
    t['zero_pos'] = d['zero_pos']
    save_tmp(t)
    Set_Vca(t['vca'])
    Update_Dac()
    Update_Angles()

def init_rst_default():
    d = {}
    d['vca'] = 2
    d['qdistance'] = 0.08
    d['am_bias'] = 0
    d['am_shift'] = 514
    d['pm_shift'] = 514
    d['angle0'] = -0.3
    d['angle1'] = 0
    d['angle2'] = 0.3
    d['angle3'] = 0.6
    d['fiber_delay'] = 0
    d['zero_pos'] = 0
    save_default(d)

def init_rst_tmp():
    t = {}
    t['am_mode'] = 'off'
    t['am_shift'] = 0
    t['pm_mode'] = 'seq64'
    t['pm_shift'] = 0
    t['vca'] = 0
    t['am_bias'] = 0
    t['angle0'] = 0
    t['angle1'] = 0
    t['angle2'] = 0
    t['angle3'] = 0
    t['qdistance'] = 0
    t['fiber_delay_mod'] = 0
    t['fiber_delay'] = 0
    t['zero_pos'] = 0

    save_tmp(t)

#def init_ddr():
#    Ddr_Data_Init()

def init_all():
    init_ltc()
    init_sync()
    init_fda()
    init_sda()
    init_apply_default()


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
#        elif args.ddr:
#            init_ddr()
        elif args.all:
            init_all()
        elif args.rst_default:
            init_rst_default()
        elif args.rst_tmp:
            init_rst_tmp()
        elif args.apply_default:
            init_apply_default()
    def set(args):
        if args.vca is not None:
            Set_Vca(args.vca)
        elif args.am_bias is not None:
            Set_Am_Bias(args.am_bias)
        elif args.qdistance is not None:
            update_tmp('qdistance', args.qdistance)
            Update_Dac()
        elif args.pm_mode:
            update_tmp('pm_mode', args.pm_mode)
            Update_Dac()
        elif args.pm_shift is not None:
            update_tmp('pm_shift', args.pm_shift)
            Update_Dac()
        elif args.am_shift is not None:
            update_tmp('am_shift', args.am_shift)
            Update_Dac()
        elif args.am_mode:
            update_tmp('am_mode', args.am_mode)
            Update_Dac()
        elif args.angles:
            t = get_tmp()
            t['angle0'] = args.angles[0]
            t['angle1'] = args.angles[1]
            t['angle2'] = args.angles[2]
            t['angle3'] = args.angles[3]
            save_tmp(t)
            Update_Angles()
    def get(args):
        if args.get_gc:
            #Ddr_Data_Init()
            Get_Current_Gc()
        if args.ddr_status:
            Ddr_Status()
#        if args.angles:
#            Angle()



            


    #create top_level parser
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(required=True)

    parser_init = subparsers.add_parser('init')
    parser_set = subparsers.add_parser('set')
    parser_get = subparsers.add_parser('get')

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
    parser_init.add_argument("--apply_default", action="store_true", 
                             help="apply values from config/default.txt")
#    parser_init.add_argument("--ddr", action="store_true", 
#                             help="init ddr data")


    parser_set.add_argument("--vca", type=float, metavar=("voltage"), 
                            help="voltage controlled attenuator; float [0,5] V")
    parser_set.add_argument("--am_bias", type=float, metavar=("voltage"), 
                            help="bias of amplitude modulator; float [-10,10] V")
    parser_set.add_argument("--am_mode", choices=['off', 'single', 'double', 'single64'],
                            help="send single pulse at 40MHz or double pulse at 80MHz or single64 at 80MHz/64")
    parser_set.add_argument("--am_shift", type=int, metavar=("steps"), 
                            help="time shift pulse generation in steps of 1.25ns")
    parser_set.add_argument("--pm_shift", type=int, metavar=("steps"), 
                            help="time shift signal for phase modulator in steps of 1.25ns")
    parser_set.add_argument("--qdistance", type=float, metavar="value", 
                            help="fine tune double pulse separation; float [0,0.5]; good value is 0.08")
    parser_set.add_argument("--pm_mode", choices=['seq64', 'seq64tight', 'fake_rng', 'true_rng', 'off'],
                            help="fixed periodic sequece, fake rng or real rng")
    parser_set.add_argument("--angles", nargs=4, type=float,
                            help="float [-1,1]")
    

    parser_get.add_argument("--get_gc", action="store_true",
                            help="get current global counter")
    parser_get.add_argument("--ddr_status", action="store_true",
                            help="print ddr status")
#    parser_get.add_argument("--angles", action="store_true",
#                            help="download the postprocessed angles")
    
    #parser_alice.add_argument("--init",action="store_true",help="initialize Alice")





    parser_init.set_defaults(func=init)
    parser_set.set_defaults(func=set)
    parser_get.set_defaults(func=get)

    args = parser.parse_args()
    args.func(args)


if __name__ =="__main__":
    main()
