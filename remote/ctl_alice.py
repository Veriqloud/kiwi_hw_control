#!/bin/python

#import argparse
import os
import time
import numpy as np
#import datetime 
#import mmap
import lib.gen_seq as gen_seq
from lib.fpga import *


LOG_FILE = os.path.expanduser("~/bin/qber_total.log")




def read_data_qber():
    try:
        with open(LOG_FILE, 'r') as f:
            lines = f.readlines()
        for line in reversed(lines):
            line = line.strip()
            if not line or line.startswith("val41"):
                continue
            parts = line.split(',')
            if len(parts) < 3:
                continue
            try:
                v41 = float(parts[0])
                v14 = float(parts[1])
                qber = float(parts[2])
                return [v41, v14, qber]
            except:
                continue
    except Exception as e:
        print(f"[ERROR] Reading QBER data: {e}")
    return None


#################### Config_laser #####################
from math import exp
from lib.laser.koheron_control import Controller


def read_laser_coeffs(filepath):
    coeffs = {}
    try:
        with open(filepath, 'r') as f:
            for line in f:
                parts = line.split()
                if len(parts) == 2:
                    key, val = parts
                    coeffs[key] = float(val)
    except FileNotFoundError:
        print(f"File not found: {filepath}")
    except Exception as e:
        print(f"Error reading laser coefficients: {e}")
    return coeffs


def calc_steinhart_resistance(A, B, C, TempC):
    try:
        T = TempC + 273.15  # Convert °C to Kelvin
        x = (1 / C) * (A - 1 / T)
        y = ((B / (3 * C)) ** 3 + (x / 2) ** 2) ** 0.5
        R = exp((y - (x / 2)) ** (1 / 3.0) - (y + (x / 2)) ** (1 / 3.0))
        return R
    except Exception as e:
        print(f"Error computing resistance: {e}")
        return None


def read_rtact_from_laser(port="/dev/ttylaser"):
    try:
        ctl = Controller(port=port)
        rtact = ctl.get("rtact")
        return float(rtact)
    except Exception as e:
        print(f"Error reading rtact: {e}")
        return None


def write_laser_config(Rset,Ilaser,  port="/dev/ttylaser"):
    """
    Write the laser configuration using Rset as rtset.
    """
    try:
        ctl = Controller(port=port)

        config = {
            "ldelay": 1000.0,
            "lason": 1,
            "ilaser": int(Ilaser),
            "ilmax": 400.0,
            "rtset": int(Rset),   # Pass the calculated resistance
            "tecon": 1,
            "pgain": 10.0,
            "igain": 0.4,
            "dgain": 0.0,
            "tilim": 0.5,
            "vtmin": -1,
            "vtmax": 1,
            "tprot": 1,
            "vldauto": 1
        }

        for param in config:
            ctl.set(param, config[param])

        # Optional: automatically save the configuration
        ctl.set("save")

        return True  # success

    except Exception as e:
        print(f"Error writing laser config: {e}")
        return False


#######################################################


def update_vca():
    t = get_tmp()
    voltage=t['vca']
    if (voltage>5) or (voltage<0):
        print("Voltage out of range. Choose a value between 0 and 5")
        exit()
    Set_vol(7, voltage)

def update_bias():
    t = get_tmp()
    am=t['am_bias']
    am2=t['am2_bias']
    Set_vol(5, am)
    if (am2>10) or (am2<0):
        print("Voltage out of range. Choose a value between 0 and 10")
        exit()
    Set_vol(4, am2)

def Set_Vca(voltage):
    t = get_tmp()
    vcai=t['vca']
    vcao=voltage
    if (voltage>5) or (voltage<0):
        print("Voltage out of range. Choose a value between 0 and 5")
        exit()

    if (vcao - vcai) > -0.6:
        Set_vol(7, vcao)
        update_tmp('vca', vcao)
        return

    step=10
    delta = (vcao - vcai) / step

    for i in range(1, step + 1):
        v = vcai + delta * i
        Set_vol(7, v)
        time.sleep(0.05)
    update_tmp('vca', vcao)
    update_tmp('vca', voltage)




def Set_Am_Bias(voltage):
    Set_vol(5, voltage)
    update_tmp('am_bias', voltage)

def Set_Am2_Bias(voltage):
    if (voltage>10) or (voltage<0):
        print("Voltage out of range. Choose a value between 0 and 10")
        exit()
    Set_vol(4, voltage)
    update_tmp('am2_bias', voltage)


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


def gen_decoy():
    # read delay from tmp.txt
    # calculate and update corse and fine delays
    t = get_tmp()
    delay = t['decoy_delay']


    timestep = 3.383    # fine delay timestep in ps
    delay_au = round(delay/timestep)
    fine_max = 404      # corresponds to 1/3 of coarse delay
    coarse = delay_au // (fine_max*3)
    fine0_abs = delay_au % fine_max
    fine1_abs = int((delay_au%(fine_max*3)) >= fine_max) * fine_max
    fine2_abs = int((delay_au%(fine_max*3)) >= 2*fine_max) * fine_max

    with open(HW_CONTROL+"config/decoy_delayf.txt", 'r+') as f:
        df0 = int(f.readline())
        df1 = int(f.readline())
        df2 = int(f.readline())

        fine0 = fine0_abs - df0
        direction0 = 1 if fine0 > 0 else 0

        fine1 = fine1_abs - df1
        direction1 = 1 if fine1 > 0 else 0
        
        fine2 = fine2_abs - df2
        direction2 = 1 if fine2 > 0 else 0

        de_write_delay_master(coarse, abs(fine0), direction0) 
        write_delay_slaves(abs(fine1), direction1, abs(fine2), direction2)

        de_params_en()
        de_trigger_fine_master()
        de_trigger_fine_slv1()
        de_trigger_fine_slv2()

        f.seek(0)

        f.write(str(fine0_abs)+'\n')
        f.write(str(fine1_abs)+'\n')
        f.write(str(fine2_abs)+'\n')

    print("decoy pulse delay set to", delay/1000, "sn")
    print(coarse, fine0, fine1, fine2)
    print(coarse, direction0, direction1, direction2)

    
    
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
    #Write_To_Fake_Rng(gen_seq.seq_rng_zeros())
    #d = get_default()
    #t = get_tmp()
    #t['angle0'] = d['angle0']
    #t['angle1'] = d['angle1']
    #t['angle2'] = d['angle2']
    #t['angle3'] = d['angle3']
    #t['am_shift'] = d['am_shift']
    #t['pm_shift'] = d['pm_shift']
    #t['am_mode'] = 'off'
    #t['pm_mode'] = 'off'
    #t['qdistance'] = d['qdistance']
    #save_tmp(t)
    #Update_Angles()
    #Update_Dac()
    Config_Fda()

def init_sda():
    Config_Sda()
    for i in range(8):
     Set_vol(i, 0)
    #d = get_default()
    #Set_Vca(d['vca'])
    #Set_Am_Bias(d['am_bias'])
    #Set_Am_Bias_2(d['am_bias_2'])

def init_decoy():
    decoy_reset()
    with open(HW_CONTROL+'config/decoy_delayf.txt', 'w') as f:
        f.write('0\n0\n0\n')
    gen_decoy()

def init_hw():
    init_ltc()
    init_sync()
    init_fda()
    init_sda()
    init_decoy()

def apply_config():
    Update_Dac()
    Update_Angles()
    update_vca()
    update_bias()
    gen_decoy()

def rst_config():
    t = {}
    t['am_mode'] = 'off'
    t['am2_mode'] = 'off'
    t['am_shift'] = 0
    t['pm_mode'] = 'off'
    t['pm_shift'] = 0
    t['vca'] = 2
    t['vca_calib'] = 0
    t['am_bias'] = 0
    t['am2_bias'] = 2
    t['am2_bias_min'] = 0
    t['angle0'] = 0
    t['angle1'] = 0.18
    t['angle2'] = -0.18
    t['angle3'] = 0.36
    t['qdistance'] = 0.095
    t['fiber_delay_mod'] = 0
    t['fiber_delay'] = 0
    t['fiber_delay_long'] = 0
    t['zero_pos'] = 0
    t['insert_zeros'] = 'off'
    t['decoy_delay'] = 0
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





