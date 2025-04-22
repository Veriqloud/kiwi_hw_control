import subprocess, os, sys, argparse
import time
import numpy as np
import datetime 
import mmap
import gen_seq, cal_lib

def write_to_dev(fd, offset, addr, array_of_u32):
    """ 
    fd           : file descriptor of the xdma file; elements of the file are bytes
    offset       : must be multiple of PAGESIZE, which we assume is 4096
    addr         : the address of the first element, with respect to offset; counting bytes
    array_of_u32 : an array of integers; four bytes per element
    """
    if ((offset % 4096) != 0):
        exit("offset is not a multiple of pagesize")
    mm = mmap.mmap(fd.fileno(), len(array_of_u32)*4 + 4096, offset=offset)
    current_addr = addr
    for value in array_of_u32:
        mm[current_addr:current_addr+4] = value.to_bytes(4, 'little')
        current_addr += 4
    #mm.flush()

def read_from_dev(fd, offset, addr, length):
    """ 
    fd     : file descriptor of the xdma file; elements of the file are bytes
    offset : must be multiple of PAGESIZE, which we assume is 4096
    addr   : the address of the first element, with respect to offset; counting bytes
    length : number of u32 integers you want to read
    """
    if ((offset % 4096) != 0):
        exit("offset is not a multiple of pagesize")
    mm = mmap.mmap(fd.fileno(), length*4 + 4096, offset=offset)
    array_of_u32 = []
    for i in range(addr//4, length+addr//4):
        array_of_u32.append(int.from_bytes(mm[i*4: (i+1)*4], 'little')) 
    return array_of_u32

# for testing create dev_fake with 
# dd if=/dev/urandom of=dev_fake bs=5MB count=1
def open_write_close(offset, addr, array_of_u32):
    dev_name = "dev_fake"
    #dev_name = "/dev/xdma0_user"
    fd = open(dev_name, 'r+b')
    write_to_dev(fd, offset, addr, array_of_u32)
    fd.close()

def open_read_close(offset, addr, length):
    dev_name = "dev_fake"
    #dev_name = "/dev/xdma0_user"
    fd = open(dev_name, 'r+b')
    r = read_from_dev(fd, offset, addr, length)
    fd.close()
    return r


def Write(base_add, value):
    str_base = str(base_add)
    str_value = str(value)
    # command ="../../tools/reg_rw /dev/xdma0_user "+ str_base + " w "+ str_value 
    command ="../dma_ip_drivers/XDMA/linux-kernel/tools/reg_rw /dev/xdma0_user "+ str_base + " w "+ str_value 
    #print(command)
    s = subprocess.check_call(command, shell = True)

def Read(base_add):
    str_base = str(base_add)
    # command ="../../tools/reg_rw /dev/xdma0_user "+ str_base + " w "+ "| grep  \"Read.*:\" | sed 's/Read.*: 0x\([a-z0-9]*\)/\\1/'" 
    command ="../dma_ip_drivers/XDMA/linux-kernel/tools/reg_rw /dev/xdma0_user "+ str_base + " w "+ "| grep  \"Read.*:\" | sed 's/Read.*: 0x\([a-z0-9]*\)/\\1/'" 
    #print(command)
    s = subprocess.check_output(command, shell = True)
    return s

def Write_stream(device,file, size, count):
    str_device = device
    str_file = file
    str_size = str(size)
    str_count = str(count)
    # command ="../../tools/dma_to_device -d "+ str_device + " -f "+ str_file + " -s "+ str_size + " -c " + str_count 
    command ="../dma_ip_drivers/XDMA/linux-kernel/tools/dma_to_device -d "+ str_device + " -f "+ str_file + " -s "+ str_size + " -c " + str_count 
    print(command)
    s = subprocess.check_call(command, shell = True)

def Read_stream(device, file, size, count):
    str_device = device
    str_file = file
    str_size = str(size)
    str_count = str(count)
    # command ="../../tools/dma_from_device -d "+ str_device + " -f "+ str_file + " -s "+ str_size + " -c " + str_count 
    command ="../dma_ip_drivers/XDMA/linux-kernel/tools/dma_from_device -d "+ str_device + " -f "+ str_file + " -s "+ str_size + " -c " + str_count 
    print(command)
    s = subprocess.check_call(command, shell = True)

#Global parameter of AXI QUAD SPI
SRR=0x40
SPICR=0x60
SPISR=0x64
SPI_DTR=0x68
SPI_DRR=0x6C
SPISSR=0x70
DGIER=0x1C
IPISR=0x20
IPIER=0x28
def Init_spi(base_add, offset, spi_mode):
    Add_SRR = base_add + offset + SRR #reset AXI QUAD SPI
    Write(Add_SRR, 0x0A)
    Add_CR = base_add + offset + SPICR #set AXI QUAD SPI Control register
    DATA_SPICR = 0x186 | spi_mode<<3 
    Write(Add_CR, DATA_SPICR) 
    Add_DGIER = base_add + offset + DGIER #Device Global Interrupt Enable Register
    Write(Add_DGIER, 0x80000000)
    Add_IPIER = base_add + offset + IPIER # IP Interrupt Enable Register
    Write(Add_IPIER, 0x04)

def Set_reg(spi_bus,device,*args):
    if (spi_bus == 1):
        BaseAdd = 0x00013000
        OffsetAdd = 0x00000000
        DATA_CS_DIS = 0x03
        if (device == 'tdc'):
            spi_mode = 0x02
            DATA_CS_EN = 0x02
        elif (device == 'jic'):
            spi_mode = 0x03
            DATA_CS_EN = 0x01
        else :
            exit("Wrong name of device on spi_bus1")
    elif (spi_bus == 2):
        BaseAdd = 0x00020000
        OffsetAdd = 0x00000000
        DATA_CS_DIS = 0x07
        if (device == 'ltc'):
            spi_mode = 0
            DATA_CS_EN = 0x03
        elif (device == 'fda'):
            spi_mode = 3
            DATA_CS_EN = 0x06
        elif (device == 'sda'):
            spi_mode = 1
            DATA_CS_EN = 0x05
        else:
            exit ("Wrong name of device on spi_bus2")
    else:
        exit("Wrong spi_bus")

    Add_Write = BaseAdd + OffsetAdd + SPI_DTR #Address of data transmit register
    Add_CS = BaseAdd + OffsetAdd + SPISSR #Chip select address
    Add_CR = BaseAdd + OffsetAdd + SPICR #Enable transer address
    Add_DRR = BaseAdd + OffsetAdd + SPI_DRR #Data receive on SPI
    Add_SR = BaseAdd + OffsetAdd + SPISR #Status register on SPI

    Init_spi(BaseAdd, OffsetAdd, spi_mode) #Init AXI Quad SPI
    
    for byte in args: 
        Write(Add_Write,byte) ## data

    Write(Add_CS, DATA_CS_EN) # Select slave
    Write(Add_CR, 0x86 | spi_mode<<3 ) # Enable transfer 
    Write(Add_CS, DATA_CS_DIS) #Reset chip select value
    Write(Add_CR, 0x1C6 | spi_mode<<3) #Disable transfer and fifo reset

def Get_reg(spi_bus,device,expect,*args):
    if (spi_bus == 1):
        BaseAdd = 0x00013000
        OffsetAdd = 0x00000000
        DATA_CS_DIS = 0x03
        if (device == 'tdc'):
            spi_mode = 0x02
            DATA_CS_EN = 0x02
        elif (device == 'jic'):
            spi_mode = 0x03
            DATA_CS_EN = 0x01
        else :
            exit("Wrong name of device on spi_bus1")
    elif (spi_bus == 2):
        BaseAdd = 0x00020000
        OffsetAdd = 0x00000000
        DATA_CS_DIS = 0x07
        if (device == 'ltc'):
            spi_mode = 0
            DATA_CS_EN = 0x03
        elif (device == 'fda'):
            spi_mode = 3
            DATA_CS_EN = 0x06
        elif (device == 'sda'):
            spi_mode = 1
            DATA_CS_EN = 0x05
        else:
            exit ("Wrong name of device on spi_bus2")
    else:
        exit("Wrong spi_bus")

    
    Add_Write = BaseAdd + OffsetAdd + SPI_DTR
    Add_CS = BaseAdd + OffsetAdd + SPISSR #Chip select address
    Add_CR = BaseAdd + OffsetAdd + SPICR #Enable transer address
    Add_DRR = BaseAdd + OffsetAdd + SPI_DRR #Data receive on SPI
    Add_SR = BaseAdd + OffsetAdd + SPISR #Status register on SPI

    Init_spi(BaseAdd, OffsetAdd, spi_mode) #Init AXI Quad SPI
    for byte in args:
        Write(Add_Write, byte)

    Write(Add_CS, DATA_CS_EN) # Select slave
    Write(Add_CR, 0x86 | spi_mode<<3) # Enable transfer
    Write(Add_CS, DATA_CS_DIS) #Reset chip select value
    Write(Add_CR, 0x186 | spi_mode<<3) #Disable transfer 
    str_base_drr = str(Add_DRR)
    str_base_sr = str(Add_SR)
    
    y_num = 25
    x_num = 0
    while (x_num != y_num):
        out_drr = Read(str_base_drr)
        out_sr = Read(str_base_sr)
        x_num = int(out_sr)
    readout_hex = format(int(out_drr.decode(),16),'#04x')
    if (readout_hex != expect):
        check = 'F'
    else:
        check = 'T'
    return (readout_hex, expect, check)

#-------------CLOCK CHIP FUNCTIONS----------------------------------------------
def Set_Ltc():
    reg_file = open('registers/ltc/Ltc6951Regs.txt','r')
    for l in reg_file.readlines():
        add, val = l.split(',')
        add_shifted = "0x{:02x}".format((int(add, base=16)<<1))
        Set_reg(2,'ltc', add_shifted, val)
    print("Set ltc configuration registers finished")
    reg_file.close()

def Sync_Ltc():
    Write(0x00012000, 0x0)
    Write(0x00012000, 0x1)
    #time.sleep(1)
    time.sleep(2)
    Write(0x00012000, 0x0)
    print("Output clocks are aligned")

def Get_Ltc_info():
    reg_file = open('registers/ltc/Ltc6951Expect.txt','r')
    array = []
    print("Monitoring ltc registers:(add, (readback, expected, T/F))")
    for l in reg_file.readlines():
        add, val = l.split(',')
        add_shifted = str(hex(int(add, base=16)<<1 |1)) 
        tup = Get_reg(2,'ltc',val.strip(),add_shifted,'0x00')
        print(add,tup)
    print("Monitoring ltc finished")
    reg_file.close()

def Get_Id():
    data_cs_en = 0x03
    id_add = '0x13'
    add_shifted = str(hex(int(id_add, base=16)<<1 |1)) 
    id_val = Get_reg(2,'ltc','0x11',add_shifted,'0x00')
    print("Id_Addr",id_add,"Ltc_id:",id_val)

def Config_Ltc():
    Set_Ltc()
    Get_Id()
    Get_Ltc_info()

###-------------DAC81408 FUNCTIONS----------------------------------

def Get_Sda_Id():
    id_add = '0x01'
    add_shifted = str(hex(1<<7 | int(id_add, base=16))) 
    #print(add_shifted)
    id_val_pre = Get_reg(2,'sda','0x60',add_shifted,'0','0')
    rev_val_pre= Get_reg(2,'sda','0x0a','0','0')
    id_val = Get_reg(2,'sda','0x60',add_shifted,'0','0')
    rev_val = Get_reg(2,'sda','0x0a','0','0')
    print
    print("Id and revision of sda:","id_addr:",id_add,"sda_id:",id_val,"sda_rev:",rev_val)

def Soft_Reset_Sda():
    trigger_reg_add = '0x0E'
    reserved_code = 0xA
    Set_reg(2,'sda',trigger_reg_add, '0x00',reserved_code)
    print('Soft reset sda finished')
    
def Set_Sda_Config():
    file = open('registers/sda/Dac81408_setting.txt','r')
    for l in file.readlines():
        addb, val1, val2 = l.split(',')
        Set_reg(2,'sda', addb, val1, val2) #Set all registers
    print("Set sda configuration registers finished")
    file.close()

def Get_Sda_Config():
    file = open('registers/sda/Dac81408_setting.txt','r')
    print("Monitoring sda readback configuration registers")
    for l in file.readlines():
        addb, val1, val2 = l.split(',')
        add_shifted = str(hex(1<<7 | int(addb, base=16))) #Start to readback value for monitoring
        val2_pre = Get_reg(2,'sda',val2,add_shifted,'0','0')
        val1_pre = Get_reg(2,'sda',val1,'0','0')
        val2 = Get_reg(2,'sda',val2.strip(),add_shifted,'0','0')
        val1 = Get_reg(2,'sda',val1,'0','0')
        print("reg_add",addb)
        print("reg_val2:",val2)
        print("reg_val1:",val1)
    print("Monitoring sda finished")
    file.close()

def Config_Sda():
    Soft_Reset_Sda()
    Set_Sda_Config()
    Get_Sda_Id()
    Get_Sda_Config()
# dedicate channel 4 for -10V to +10V to set am_bias
# other channels range from 0V to +5V to set attenuators and pol controller
# channel 7 is for vca, channel 0 to 3 is for pol controller
def Set_vol(channel, voltage):
    vz = float(voltage)
    if (channel == 4):
        data_vol = int(((vz + 10) * (1<<16)-1)/20)  
    elif (channel == 7):
        data_vol = int((vz * (1<<16)-1)/10)
    else:
        data_vol = int((vz * (1<<16)-1)/5)
    reg = [(20+channel, data_vol),]
    addb = 20 + channel
    val = data_vol
    addr_shift =format((addb&0xff),'#04x')
    val1 =format(((val>>8)&0xff),'#04x')
    val2 =format((val&0xff),'#04x')
    # print(addr_shift)
    # print(val1)
    # print(val2)
    Set_reg(2,'sda', addr_shift, val1, val2) #Set data register
    print("Channel",channel,"is set to", round(voltage,2), "V")

###-------------AD9152 FUNCTIONS -------------------------------------
## This function, write config for JESD to the FPGA registers
def WriteFPGA():
    #file = open("registers/fda/FastdacFPGA.txt","r")
    file = open("registers/fda/FastdacFPGA_204b.txt","r")
    for l in file.readlines():
        addr, val = l.split(',')
        ad_fpga_addr = str(hex((int(addr,base=16) + 0x10000)))
        Write(ad_fpga_addr, val)
        #print(ad_fpga_addr)
        #print(val)
    print("Set JESD configuration for FPGA finished")
    file.close()

def Write_Sequence_Dacs(rf_am):
    #Write dpram_max_addr port out 
    Base_Addr = 0x00030000
    Write(Base_Addr + 16, 0x0000a0a0) #sequence64
    #Write data to dpram_dac0 and dpram_dac1
    Base_seq0 = Base_Addr + 0x1000  #Addr_axi_sequencer + addr_dpram
    if (rf_am == 'off_am'):
        seq_list = gen_seq.seq_dac0_off(64,0) #dac0_off(cycle_num, shift_pm) # am: off, pm: seq64
    if (rf_am == 'off_pm'):
        seq_list = gen_seq.seq_dac1_off(2, [-0.95,0.95], 64,0,0) # am: double pulse, pm: 0
    elif (rf_am == 'sp'):
        # seq_list = gen_seq.seq_dacs_sp_10(64,0,0) # am: single pulse, pm: seq64
        seq_list = gen_seq.seq_dacs_sp(2, [-0.95,0.95], 64,0,0) # am: single pulse, pm: seq64
    elif (rf_am == 'dp'):
        # seq_list = gen_seq.seq_dacs_dp_10(64,0,0) # am: double pulse, pm: seq64
        # seq_list = gen_seq.seq_dacs_dp(2, [-0.95,0.95], 64,0,0,0) # am: double pulse, pm: seq64
        seq_list = gen_seq.seq_dacs_dp(2, [-0.95,0.95], 64,0,0,0) # am: double pulse, pm: seq64

    vals = []
    for ele in seq_list:
        vals.append(int(ele,0))

    fd = open("/dev/xdma0_user", 'r+b', buffering=0)
    write_to_dev(fd, Base_seq0, 0, vals)
    fd.close()
    print("Set sequence for drpam_dac0 and dpram_dac1 finished")


# def Write_Sequence_Params():
#     Base_Addr = 0x00030000
#     #Write dpram_max_addr port out
#     #[22:16]: max_addr_seq1
#     #[6:0]:   max_addr_seq0
#     Write(Base_Addr + 16, 0x0000a0a0) #sequence64
#     #Write dpram_rng_max_addr port out
#     #[14:0]: 0x4e20 = 20000
#     #Write(Base_Addr + 28, 0x4e20) #for 0.5ms distance
#     #dpram_rng_max_addr for sequence 16 qubit
#     Write(Base_Addr + 28, 0x0100) #for 256 values test ddr

# #Write samples to DAC0 (IDAC, signal for AM)
# def Write_Sequence(rf_am):
#     Base_seq0 = 0x00030000 + 0x1000  #Addr_axi_sequencer + addr_dpram
#     if (rf_am == 'off_am'):
#         file0 = open('data/fda/lyes_test/seq_dac0_off.txt','r') # am: off, pm: seq64
#     if (rf_am == 'off_pm'):
#         file0 = open('data/fda/lyes_test/seq_dac1_off.txt','r') # am: double pulse, pm: 0
#     elif (rf_am == 'sp'):
#         file0 = open('data/fda/lyes_test/seq_dacs_sp.txt','r') # am: single pulse, pm: seq64
#     elif (rf_am == 'dp'):
#         file0 = open('data/fda/lyes_test/seq_dacs_dp.txt','r') # am: double pulse, pm: seq64

#     counter = 0
#     for l in file0.readlines():
#         counter += 1
#         Base_seq = str(hex(int(Base_seq0) + (counter-1)*4))
#         Write(Base_seq, l)
#         #print(Base_seq)
#         #print(l)
#     print("Set sequence for DAC0 finished")
#     file0.close()

# def Write_Sequence_Rng():
    # Base_Addr = 0x00030000
    # #Write dpram_rng_max_addr port out
    # #[14:0]: 0x4e20 = 20000
    # #Write(Base_Addr + 28, 0x4e20) #for 0.5ms distance
    # #dpram_rng_max_addr for sequence 16 qubit
    # Write(Base_Addr + 28, 0x0100) #for 256 values test ddr
    # #Write data to rng_dpram
    # Base_seq0 = 0x00030000 + 0x2000  #Addr_axil_sequencer +   addr_dpram
    # file0 = open('data/fda/seqrng_gen/SeqRng_ddr0.txt','r') #Use this file for testing ddr
    # #file0 = open('data/fda/seqrng_gen/SeqRng.txt','r') #Use this file for 0.5ms distance
    # # counter = 0
    # # for l in file0.readlines():
    # #     counter += 1
    # #     Base_seq = str(hex(int(Base_seq0) + (counter-1)*4))
    # #     Write(Base_seq, l)
    # #     #print(Base_seq)
    # #     #print(l)
    # # print("Set rng sequence for DAC1 finished")
    # # file0.close()
def Write_Sequence_Rng():
    Base_Addr = 0x00030000
    Base_seq0 = 0x00030000 + 0x2000  #Addr_axil_sequencer +   addr_dpram
    dpram_max_addr = 8
    Write(Base_Addr + 28, hex(dpram_max_addr)) 
    list_rng_zero = gen_seq.seq_rng_zero(dpram_max_addr)
    
    vals = []
    for l in list_rng_zero:
        vals.append(int(l, 0))
    fd = open("/dev/xdma0_user", 'r+b', buffering=0)
    write_to_dev(fd, Base_seq0, 0, vals)
    fd.close()
    print("Initialie fake rng sequence equal 0 ")


#Write parameter of amplitude and delay for signal on DAC1 (QDAC, signal for PM)
#2's compliment in dac
#shift only apllies for mode 2|mode 3
#in mode 0, data comes from dpram_sequence, move samples in file -> shift (run test_sig.py ) 
def Write_Dac1_Shift(rng_mode, amp0, amp1, amp2, amp3, shift):
    Base_Addr = 0x00030000
    amp_list = [amp0,amp1,amp2,amp3]
    amp_out_list = []
    for amp in amp_list:
        if (amp >= 0):
            amp_hex = round(32767*amp)
        elif (amp < 0):
            amp_hex = 32768+32768+round(32767*amp)
        amp_out_list.append(amp_hex)
    shift_hex = hex(shift)
    up_offset = 0x4000
    zero_pos = 1
    params = (int(up_offset)<<16 | zero_pos<<4 | shift)
    division_sp = hex(1000)
    fastdac_amp1_hex = (amp_out_list[1]<<16 | amp_out_list[0])
    fastdac_amp2_hex = (amp_out_list[3]<<16 | amp_out_list[2])
    Write(Base_Addr + 8, fastdac_amp1_hex)
    Write(Base_Addr + 24, fastdac_amp2_hex)
    Write(Base_Addr + 4, params)
    Write(Base_Addr + 32, division_sp)

    #Write bit0 of slv_reg5 to choose RNG mode
    #1: Real rng from usb | 0: rng read from dpram
    #Write bit1 of slv_reg5 to choose dac1_sequence mode
    #1: random amplitude mode | 0: fix sequence mode
    #Write bit2 of slv_reg5 to choose feedback mode
    #1: feedback on | 0: feedback off
    #----------------------------------------------
    #Write slv_reg5:
    #0x0: Fix sequence for dac1, input to dpram
    #0x02: Random amplitude, with fake rng
    #0x03: Random amplitude, with true rng
    #0x06: Random amplitude, with fake rng, feedback on
    #0x07: Random amplitude, with true rng, feedback on
    Write(Base_Addr + 20, hex(rng_mode))
    #Trigger for switching domain
    Write(Base_Addr + 12,0x1)
    Write(Base_Addr + 12,0x0)

#Read back the FGPA registers configured for JESD
def ReadFPGA():
    file = open("registers/fda/FastdacFPGAstats.txt","r")
    for l in file.readlines():
        addr, val = l.split(',')
        ad_fpga_addr = str(hex((int(addr,base=16) + 0x10000)))
        readout = Read(ad_fpga_addr)
        #print(readout)
    file.close()

#reset jesd module
def En_reset_jesd():
    Write(0x00012000, 0x2)
    Write(0x00012000, 0x0)
    time.sleep(2)
    print("Reset FPGA JESD module")

# From Set_reg_powerup to Set_reg_seq2: Set all registers for AD9152 
def Set_reg_powerup():
    file = open('registers/fda/hop_regs/reg_powerup.txt','r')
    for l in file.readlines():
        addb1, addb2, val = l.split(',')
        Set_reg(2,'fda', addb1, addb2, val)
        #print(addb1)
        #print(addb2)
        #print(val)
    print("Set fda power registers finished")
    file.close()

def Set_reg_plls():
    file = open('registers/fda/hop_regs/reg_plls.txt','r')
    for l in file.readlines():
        addb1, addb2, val = l.split(',')
        Set_reg(2,'fda', addb1, addb2, val)
    print("Set fda serdes_pll registers finished")
    file.close()

def Set_reg_seq1():
    file = open('registers/fda/hop_regs/reg_seq1.txt','r')
    for l in file.readlines():
        addb1, addb2, val = l.split(',')
        Set_reg(2,'fda', addb1, addb2, val)
    print("Set fda dac_pll, transport and physical1 registers finished")
    file.close()
    
def Set_reg_seq2():
    file = open('registers/fda/hop_regs/reg_seq2.txt','r')
    for l in file.readlines():
        addb1, addb2, val = l.split(',')
        Set_reg(2,'fda', addb1, addb2, val)
    print("Set fda physical2 and data_link registers finished")
    file.close()

def Relink_Fda():
    file = open('registers/fda/hop_regs/reg_relink.txt','r')
    for l in file.readlines():
        addb1, addb2, val = l.split(',')
        Set_reg(2,'fda', addb1, addb2, val)
    file.close()

# Read back some registers of AD9152 to monitoring jesd status and latency
def Get_reg_monitor():
    array = []
    file = open('registers/fda/hop_regs/reg_monitor.txt','r')
    print("Monitoring pll locked, dyn_link_latency, and jesd link ")
    ret_arr = []
    for l in file.readlines():
        addb1, addb2, val = l.split(',')
        instr = str(hex(int(addb1, base=16)|0x80))     
        tup = Get_reg(2,'fda', val.strip(), instr, addb2, '0x00')
        ret_arr.append(tup)
        print(addb1,addb2,tup)
    print("Monitoring finished. If dyn_link_latency != 0x00 then run sda_init again")
    file.close()
    return ret_arr

#Readback ID of AD9152 for debug
def Get_Id_Fda():
    chip_type = Get_reg(2,'fda','0x04','0x80','0x03','0x00')
    id1 = Get_reg(2,'fda','0x52','0x80','0x04','0x00')
    id2 = Get_reg(2,'fda','0x91','0x80','0x05','0x00'   )
    revision = Get_reg(2,'fda','0x08','0x80','0x06','0x00')
    print("type: ",chip_type,"id: ", id1,id2,"revision: ", revision)

# def Set_Fda():
    #Write_Sequence()
    #WriteFPGAFunc()
    # WriteFPGA()
    # En_reset_jesd()
    # Set_reg_powerup()
    # Set_reg_plls()
    # Set_reg_seq1() #seq1 include power, serdespll, dacpll
    # Set_reg_seq2()

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
#Reset the ttl_gate module
def ttl_reset():
    Write(0x0001200c,0x01)
    Write(0x0001200c,0x00)
    time.sleep(2)
    #print("Reset TTL gate module")
#Generate the pulse for APD gate
#Input parameter: duty cycle, tune delay, fine delay, increase/decrease fine delay step
#Default: duty = 2, tune = 1, fine = 1000, inc = 1
#fine step 1000 ~1ns
#tune step 1 ~ 4ns
def calculate_delay(duty, tune, fine, inc):
    fine_clock_num = fine*16
    transfer = duty<<19|tune<<15|fine_clock_num<<1|inc
    transfer_bin = bin(transfer)
    transfer_hex = hex(transfer)
    #print(transfer_bin)
    #print(transfer_hex)
    return transfer_hex

def write_delay_master(duty, tune, fine, inc):
    Base_Add = 0x00015004 
    transfer = calculate_delay(duty, tune, fine, inc)
    Write(Base_Add,transfer)
    # print('delay 0,52ns = 125 taps')
    #result = Read(Base_Add)  #Read to check AXI
    #print(result)

def write_delay_slaves(fine1, inc1, fine2, inc2):
    Base_Add = 0x0001500c
    transfer = (fine2*16)<<17|inc2<<16|(fine1*16)<<1|inc1
    Write(Base_Add, hex(transfer))

def params_en():
    Base_Add = 0x0015008
    Write(Base_Add,0x00)
    Write(Base_Add,0x01)

def trigger_fine_master():
    Base_Add = 0x00015000
    Write(Base_Add, 0x0)
    Write(Base_Add, 0x1)
    time.sleep(0.02)
    Write(Base_Add, 0x0)
    print("Trigger master done")

def trigger_fine_slv1():
    Base_Add = 0x00015000
    Write(Base_Add + 16, 0x0)
    Write(Base_Add + 16, 0x1)
    time.sleep(0.02)
    Write(Base_Add + 16, 0x0)
    print("Trigger slave1 done")

def trigger_fine_slv2():
    Base_Add = 0x00015000
    Write(Base_Add + 20, 0x0)
    Write(Base_Add + 20, 0x1)
    time.sleep(0.02)
    Write(Base_Add + 20, 0x0)
    print("Trigger slave2 done")

def Gen_Gate():
    print("Generate Gate signal for APD")
    ttl_reset()
    write_delay_master(2,1,100,1)
    write_delay_slaves(100,1,100,1)
    params_en()
    # trigger only master and slv1/ all of them
    trigger_fine_master()
    # trigger_fine_slv1()
    # trigger_fine_slv2()
#-------------------------TDC AND JITTER CLEANER-----------------------

def Set_Si5319():
    reg_file = open('registers/jit_cleaner/Si5319_regs.txt','r')
    ins_set_addr = 0x00
    ins_write = 0x40
    for l in reg_file.readlines():
        add, val = l.split(',')
        Set_reg(1,'jic', ins_set_addr,add)
        Set_reg(1,'jic', ins_write,val)
    print("Set jic configuration registers finished")
    reg_file.close()

def Get_Si5319():
    reg_file = open('registers/jit_cleaner/Si5319_regs.txt','r')
    ins_set_addr = 0x00
    ins_read = 0x80
    print("Monitoring jic registers")
    for l in reg_file.readlines():
        add, val = l.split(',')
        Set_reg(1,'jic', ins_set_addr,add)
        ret_val = Get_reg(1,'jic',val.strip(), ins_read,'0')
        print(add,ret_val)
    print("Monitoring finished. It's normal the last reg is F")
    reg_file.close()

def Get_Id_Si5319():
    ins_set_addr = 0x00
    ins_read = 0x80
    Set_reg(1,'jic', ins_set_addr,'0x87')
    ret_val = Get_reg(1,'jic','0x32',ins_read,'0x00')
    print("Jitter cleaner Id:",ret_val)
    
def Config_Jic():
    Set_Si5319()
    Get_Id_Si5319()
    Get_Si5319()

def Set_AS6501():
    reg_file = open('registers/tdc/AS6501_regs.txt','r')
    #opc_write_config = 0x80
    for l in reg_file.readlines():
        add, val = l.split(',')
        Set_reg(1,'tdc', add, val ) 
    print("Set tdc configuration registers finished")
    reg_file.close()

def Get_AS6501():
    reg_file = open('registers/tdc/AS6501_regs.txt','r')
    opc_read_config = 0x40
    print("Montoring tdc registers")
    for l in reg_file.readlines():
        add, val = l.split(',')
        add_str = str(hex(int(add, base=16) & 0x1f | int(0x40)))
        ret_val = Get_reg(1,'tdc',val.strip(),add_str,'0x00' )
        print(add,ret_val)
    print("Monitoring finished")
    reg_file.close()

def Get_Id_AS6501():
    #opc_power = 0x30
    #opc_read_results = 0x60 #reg 8..31 results and status
    #opc_read_config = 0x40 # reg 0..17 configuration register
    ret_val_1 = Get_reg(1,'tdc','0x41','0x41','0x00')
    ret_val_2 = Get_reg(1,'tdc','0x41','0x43','0x00')
    print(ret_val_1)
    print(ret_val_2)
    
def Reg_Mngt_Tdc():
    #lrst active high, reset module process tdc frame and sdi
    #slv_reg[1] pull high to low in clk_rst_mngt
    Write(0x00012004,0x2)
    Write(0x00012004,0x0)
    BaseAddr = 0x00000000 # BaseAddr of TDC AXI-Slave
    #Disable TDC module
    Write(BaseAddr,0x00)
    #Write TDC module register
    Write(BaseAddr + 4,0x0e04) #14 stop_wise: 14bit, index_wise: 4bit
    Write(BaseAddr + 36,0x0) #reg_enable =0
    Write(BaseAddr + 36,0x1) #reg_enable = 1
    #Enable TDC module
    Write(BaseAddr,0x01)
    

def Get_TDC_Data(transferSize, transferCount, output_file):
    device_c2h = '/dev/xdma0_c2h_2'
    #Send command_histogram
    BaseAddr = 0x00000000
    Write(BaseAddr + 40,0x0)
    Write(BaseAddr + 40,0x1)
    #Read from stream
    Read_stream(device_c2h, output_file, transferSize, transferCount)

def Get_Stream(base_addr,device_c2h,output_file,count):
    #print(command)
    #Send command to fpga to reset fifo
    Write(base_addr,0x0)
    Write(base_addr,0x1)
    #time.sleep(1)
    #Read from stream
    command ="test_tdc/dma_from_device "+"-d "+ device_c2h +" -f "+ output_file+ " -c " + str(count) 
    s = subprocess.check_call(command, shell = True)

def Reset_Tdc():
    Write(0x00012004,0x01)
    Write(0x00012004,0x00)
    time.sleep(2)
    print("Reset TDC clock")

def Config_Tdc():
    Reg_Mngt_Tdc() #Setting fpga control registers for SM under lclk 
    Reset_Tdc() #Could be before or after Reg_Mngt_Tdc()
    Set_AS6501() #Setting registers of TDC chip
    Set_reg(1,'tdc', 0x18) #Start the tdc, setting register of TDC chip
    Get_AS6501() #Reading registers of TDC chip

def Stop_sim(fre_divider,start):
    pulse_stop = start + 13
    stop_pulse_sim = hex(int(pulse_stop<<16 | start<<8 | fre_divider))
    print(stop_pulse_sim)
    #Write Stop_sim limit parameter
    BaseAddr = 0x00000000
    Write(BaseAddr + 12,stop_pulse_sim) #from 10 to 26 period of 5ns 
    Write(BaseAddr + 36,0x0) #
    Write(BaseAddr + 36,0x4) #enable 

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

    
#-----------------------------TDC CALIBRATION-----------------------------------------------
#Set fpga registers for state machine under 200MHz
def Time_Calib_Reg(command,t0, gc_back, gate0, width0, gate1, width1):
    BaseAddr = 0x00000000
    Write(BaseAddr + 16,hex(int(width0<<24 | gate0))) #gate0
    Write(BaseAddr + 20,hex(int(width1<<24 | gate1))) #gate1
    Write(BaseAddr + 24,hex(int(t0))) #shift tdc time = 0
    Write(BaseAddr + 28,hex(int(gc_back))) #shift gc back = 0
    Write(BaseAddr + 32,hex(int(command))) #command = 1: raw | =2: with gate
    Write(BaseAddr + 36,0x0)
    Write(BaseAddr + 36,0x2)# turn bit[1] to high to enable register setting

def Time_Calib_Init():
    Config_Tdc() #Get digital data from TDC chip
    Reset_gc() #Reset global counter
    Start_gc() #Global counter start counting at the next PPS

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

def Gen_Sp(party, shift_am):
    # shift_am = 0
    if (party == 'alice'):
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
    elif (party == 'bob'):
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

        #Set APD in continuous mode
        subprocess.run("cd /home/vq-user/Aurea_API/OEM_API_Linux/Examples/Python && python Aurea.py --mode continuous && python Aurea.py --dt 100", shell = True)

        Time_Calib_Reg(1, 0, 0, 0, 0, 0, 0)
        #Get detection result
        Get_Stream(0x00000000+40,'/dev/xdma0_c2h_2','data/tdc/output_sp.bin',50000)
        command ="test_tdc/tdc_bin2txt data/tdc/output_sp.bin data/tdc/histogram_sp.txt"
        s = subprocess.check_call(command, shell = True)
        ref_time = np.loadtxt("data/tdc/histogram_sp.txt",usecols=1,unpack=True,dtype=np.int32)
        ref_time_arr = (ref_time*20%25000)/20
        #Find first peak of histogram
        first_peak = cal_lib.Find_First_Peak(ref_time_arr)
        print("First peak: ",first_peak)
        peak_target = np.array([625,689])
        # peak_target = np.array([0,64])
        # peak_target = np.array([500,664])
        # peak_target = np.array([375,539])
        shift_am_range = ((peak_target-first_peak)%625)/62.5
        print("shift_am_range", shift_am_range)
        # peak_target = 50
        # print("Target peak: ", peak_target)
        # shift_am_out = (round((peak_target-first_peak)/62.5))%10
        # shift_am_out = np.arange(np.ceil(shift_am_range[0]),np.floor(shift_am_range[1])+1,dtype=int)
        shift_am_out = int((np.ceil(shift_am_range[0]))%10)
        print("Shift for am: ",shift_am_out)
        return first_peak, shift_am_out

def Gen_Dp(party, shift_am, first_peak):
    # shift_am = 2
    if (party == 'alice'):
        Base_Addr = 0x00030000
        Write(Base_Addr + 16, 0x0000a0a0) #sequence64
        #Write data to dpram_dac0 and dpram_dac1
        Base_seq0 = Base_Addr + 0x1000  #Addr_axi_sequencer + addr_dpram
        #seq_list = gen_seq.seq_dacs_dp(2, [-0.95,0.95], 64,0,0,shift_am) # am: double pulse, pm: seq64
        seq_list = gen_seq.seq_dacs_dp(2, [-0.92,0.92], 64,0,0,shift_am) # am: double pulse, pm: seq64

        vals = []
        for ele in seq_list:
            vals.append(int(ele,0))

        fd = open("/dev/xdma0_user", 'r+b', buffering=0)
        write_to_dev(fd, Base_seq0, 0, vals)
        fd.close()
        print("Set sequence dp for dpram_dac0 and seq64 for dpram_dac1")
        Write_Dac1_Shift(2,0,0,0,0,0)
        print("Set mode 2 for fake rng")
    elif (party == 'bob'):
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

        #Set APD in continuous mode
        subprocess.run("cd /home/vq-user/Aurea_API/OEM_API_Linux/Examples/Python && python Aurea.py --mode continuous && python Aurea.py --dt 100 ", shell = True)

        Time_Calib_Reg(1, 0, 0, 0, 0, 0, 0)
        #Get detection result
        Get_Stream(0x00000000+40,'/dev/xdma0_c2h_2','data/tdc/output_dp.bin',50000)
        command ="test_tdc/tdc_bin2txt data/tdc/output_dp.bin data/tdc/histogram_dp.txt"
        s = subprocess.check_call(command, shell = True)

        #Generate gate signal
        print("Generate Gate signal for APD")
        # gate_initial = [105,355]
        gate_initial = [0,339]
        # gate_initial = [400,620]
        # delay_time = (((first_peak + 80) - gate_initial[1])%625)*20
        delay_time = ((first_peak + 0 + 625) - gate_initial[1])*20
        print("Estimate delay time : ", delay_time, "ps")
        tune_delay_val = int(np.floor(delay_time/4166))
        print("Tune delay: ", tune_delay_val)
        ttl_reset()
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
    if (party == 'alice'):
        Write_Dac1_Shift(2,0,0,0,0,0)
        print("Set phase of PM to zero")
    elif (party == 'bob'):
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
    if (party == 'alice'):
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
    elif (party == 'bob'):
        Write_Dac1_Shift(2,0,0,0,0,0)
        print("Set phase of PM to zero")
        print("Get detection result")
        Get_Stream(0x00000000+40,'/dev/xdma0_c2h_2','data/tdc/pm_a_shift_'+str(shift_pm+1)+'.bin',40000)
        command ="test_tdc/tdc_bin2txt data/tdc/pm_a_shift_"+str(shift_pm+1)+".bin data/tdc/pm_a_shift_"+str(shift_pm+1)+".txt"
        s = subprocess.check_call(command, shell = True)

def Find_Best_Shift(party):
    if party == 'alice':
        best_shift = cal_lib.Best_Shift(party)
    elif party == 'bob':
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
    if (party == 'alice'):
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
    elif (party == 'bob'):
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
        # En_reset_jesd()
        Config_Fda()
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


#-----------------------------DECOY SIGNAL----------------------------
#Reset from
def decoy_reset():
    Write(0x00012000 + 20,0x01)
    time.sleep(2)
    Write(0x00012000 + 20,0x00)
#input fake rng
def Test_Decoy():
    #dpram_rng_max_addr
    Write(0x00016000 + 28, 0x10)
    #Write data to rng_dpram
    Base_seq0 = 0x00016000 + 1024 
    rngseq0 = 0x00000000
    rngseq1 = 0x00000000
    Write(Base_seq0, rngseq0)
    Write(Base_seq0+4, rngseq1)
    #Write rng mode
    Write(0x00016000 + 12, 0x1)
    #enable regs values
    Write(0x00016000 , 0x0)
    Write(0x00016000 , 0x1)

def Test_pm_rng():
    #dpram_rng_max_addr
    Base_Addr = 0x00030000
    Write(Base_Addr + 28, 0x0008)
    #Write data to rng_dpram
    Base_seq0 = 0x00030000 + 0x2000  #Addr_axil_sequencer +   addr_dpram
    rngseq = 0x87654321
    Write(Base_seq0, rngseq)
    #Write amplitude
    Write_Dac1_Shift(0, 0, 0, 0, 0, 0)

#fine = 1000, inc = 1
#fine step 1000 ~1ns
#tune step 1 ~ 4ns
def de_calculate_delay(fine, inc):
    fine_clock_num = fine*16
    transfer = fine_clock_num<<1|inc
    transfer_bin = bin(transfer)
    transfer_hex = hex(transfer)
    return transfer_hex

def de_write_delay_master(tune, fine, inc):
    #Write tune delay
    Write(0x00016000 + 4, tune)
    #Write fine delay master 
    transfer = de_calculate_delay(fine, inc)
    Write(0x00016000 + 20,transfer)

def de_write_delay_slaves(fine1, inc1, fine2, inc2):
    Base_Add = 0x00016000 + 24
    transfer = (fine2*16)<<17|inc2<<16|(fine1*16)<<1|inc1
    Write(Base_Add, hex(transfer))

def de_params_en():
    #enable regs values
    Write(0x00016000 , 0x0)
    Write(0x00016000 , 0x1)

def de_trigger_fine_master():
    Base_Add = 0x00016000 + 8
    Write(Base_Add, 0x0)
    Write(Base_Add, 0x1)
    time.sleep(0.02)
    Write(Base_Add, 0x0)
    print("Trigger master done")

def de_trigger_fine_slv1():
    Base_Add = 0x00016000 + 8
    Write(Base_Add, 0x0)
    Write(Base_Add, 0x2)
    time.sleep(0.02)
    Write(Base_Add, 0x0)
    print("Trigger slave1 done")

def de_trigger_fine_slv2():
    Base_Add = 0x00016000 + 8
    Write(Base_Add, 0x0)
    Write(Base_Add, 0x4)
    time.sleep(0.02)
    Write(Base_Add, 0x0)
    print("Trigger slave2 done")

#------------------------------MAIN----------------------------------------------------------------------------------
def main():
    def alice(args):
        if args.init:
            Config_Ltc()
            Sync_Ltc()
            Write_Sequence_Dacs('off_am')
            Write_Sequence_Rng()
            Write_Dac1_Shift(2, 0, 0, 0, 0, 0)
            Config_Fda()
            #Config_Sda()
            #Set_vol(7, 0)
            #Set_vol(4, 1.2)
        elif args.gen_dp:
            Gen_Dp('alice', int(args.gen_dp[0]), int(args.gen_dp[1]))
        elif args.verify_shift_a is not None:
            shift_pm = int(args.verify_shift_a[0])
            Verify_Shift_A('alice',shift_pm,2)        
        elif args.verify_shift_b is not None:
            shift_pm = int(args.verify_shift_b[0])
            Verify_Shift_B('alice',shift_pm)
        elif args.find_delay_ab_mod32:
            Find_Opt_Delay_AB_mod32('alice')
        elif args.find_delay_ab:
            Find_Opt_Delay_AB('alice')
        elif args.ltc_init:
            Config_Ltc()
        elif args.sync_ltc:
            Sync_Ltc()
        elif args.fda_init:
            Config_Fda()
        elif args.shift is not None:
            rng_mode = int(args.shift[0])
            amp0 = float(args.shift[1])
            amp1 = float(args.shift[2])
            amp2 = float(args.shift[3])
            amp3 = float(args.shift[4])
            shift = int(args.shift[5])
            if (rng_mode > 20 or rng_mode <0):
                exit("wrong mode, should be in list[]")
            if (amp0>1 or amp0 <-1):
                exit("wrong amplitude, should be in range -1..1")
            if (amp1>1 or amp1 <-1):
                exit("wrong amplitude should be in range -1..1")
            if (amp2>1 or amp2 <-1):
                exit("wrong amplitude, should be in range -1..1")
            if (amp3>1 or amp3 <-1):
                exit("wrong amplitude should be in range -1..1")
            if (shift > 10 or shift <0):
                exit("shift is not in range")
            Write_Dac1_Shift(rng_mode, amp0, amp1, amp2, amp3, shift)
        elif args.sequence is not None:
            rf_am = args.sequence[0]
            Write_Sequence_Dacs(rf_am)
            Write_Sequence_Rng()
        elif args.sda_init:
            Config_Sda()
        elif args.am_bias is not None:
            chan = int(args.am_bias[0])
            vol = float(args.am_bias[1])
            if (chan != 4):
                exit("not the right channel for am_bias")
            if (vol>10 or vol <-10):
                exit ("voltage not in the good range")
            Set_vol(chan,vol)
        elif args.vca_bias is not None:
            chan = int(args.vca_bias[0])
            vol = float(args.vca_bias[1])
            if (chan != 7):
                exit("not the right channel for vca_bias")
            if (vol>6 or vol <0):
                exit ("voltage not in the good range")
            Set_vol(chan,vol)
        elif args.ddr_data_reg is not None:
            command = int(args.ddr_data_reg[0])
            current_gc = np.int64(args.ddr_data_reg[1])
            read_speed = int(args.ddr_data_reg[2])
            fiber_delay = int(args.ddr_data_reg[3])
            pair_mode = int(args.ddr_data_reg[4])
            Ddr_Data_Reg(command,current_gc,read_speed,fiber_delay,pair_mode)
        elif args.ddr_data_init:
            Ddr_Data_Init()
        elif args.get_gc:
            Ddr_Data_Init()
            Get_Gc()
        elif args.get_current_gc:
            Get_Current_Gc()
        elif args.read_angle:
            Read_Angle()
        elif args.angle:
            Angle()
        elif args.ddr_status:
            Ddr_Status()
        elif args.decoy:
            Test_Decoy()
        elif args.pm_rng:
            Test_pm_rng()
        elif args.decoy_rst:
            decoy_reset()
        elif args.de_para_master is not None:
            tune = int(args.de_para_master[0])
            fine = int(args.de_para_master[1])
            inc = int(args.de_para_master[2])
            if (tune>7 or tune <0):
                exit ("not the tune value in range")
            if (fine>2000 or fine <0):
                exit ("not the fine value in range")
            if (inc != 1 and inc != 0):
                exit ("not the choice for direction of shift")
            de_write_delay_master(tune,fine,inc)
        elif args.de_para_slaves is not None:
            fine1 = int(args.de_para_slaves[0])
            inc1 = int(args.de_para_slaves[1])
            fine2 = int(args.de_para_slaves[2])
            inc2 = int(args.de_para_slaves[3])
            if (fine1 >2000 or fine1 <0):
                exit ("not the fine value in range")
            if (inc1 != 1 and inc1 != 0):
                exit ("not the choice for direction of shift")
            if (fine2 >2000 or fine2 <0):
                exit ("not the fine value in range")
            if (inc2 != 1 and inc2 != 0):
                exit ("not the choice for direction of shift")
            de_write_delay_slaves(fine1,inc1, fine2, inc2)
        elif args.de_regs_en:
            de_params_en()
        elif args.de_add_delay_m:
            de_trigger_fine_master()
        elif args.de_add_delay_s1:
            de_trigger_fine_slv1()
        elif args.de_add_delay_s2:
            de_trigger_fine_slv2()




    def charlie(args):
        if (args.ltc_init):
            Config_Ltc()
        
    def bob(args):
        if args.init:
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
            Count_Mon()
            # Cont_Det()
        elif args.gen_dp:
            Gen_Dp('bob')
        # elif args.find_gate:
        #     Find_Gate()
        # elif args.find_shift:
        #     Find_Shift()
        elif args.verify_shift_b is not None:
            shift_pm = int(args.verify_shift_b[0])
            Verify_Shift_B('bob',shift_pm)
        elif args.verify_shift_a is not None:
            shift_pm = int(args.verify_shift_a[0])
            Verify_Shift_A('bob',shift_pm,2)
        elif args.find_delay_b:
            Find_Opt_Delay_B()
        elif args.find_delay_ab_mod32:
            Find_Opt_Delay_AB_mod32('bob')
        elif args.find_delay_ab:
            Find_Opt_Delay_AB('bob')
        elif args.ltc_init:
            Config_Ltc()
        elif (args.sync_ltc):
            Sync_Ltc()
        elif args.fda_init:
            Config_Fda()
        elif args.shift is not None:
            rng_mode = int(args.shift[0])
            amp0 = float(args.shift[1])
            amp1 = float(args.shift[2])
            amp2 = float(args.shift[3])
            amp3 = float(args.shift[4])
            shift = int(args.shift[5])
            if (rng_mode > 16 or rng_mode <0):
                exit("wrong mode, should be in list[]")
            if (amp0>1 or amp0 <-1):
                exit("wrong amplitude, should be in range -1..1")
            if (amp1>1 or amp1 <-1):
                exit("wrong amplitude should be in range -1..1")
            if (amp2>1 or amp2 <-1):
                exit("wrong amplitude, should be in range -1..1")
            if (amp3>1 or amp3 <-1):
                exit("wrong amplitude should be in range -1..1")
            if (shift > 10 or shift <0):
                exit("shift is not in range")
            Write_Dac1_Shift(rng_mode, amp0, amp1, amp2, amp3, shift)
        elif args.sequence is not None:
            rf_am = args.sequence[0]
            Write_Sequence_Dacs(rf_am)
            Write_Sequence_Rng()
        elif args.sda_init:
            Config_Sda()
        elif args.pol_bias is not None:
            chan = int(args.pol_bias[0])
            vol = float(args.pol_bias[1])
            if (chan > 3):
                exit("not the right channel for pol_bias")
            if (vol>5 or vol <0):
                exit ("voltage not in the good range")
            Set_vol(chan,vol)
        elif args.pol_ctl:
            Polarisation_Control()
        elif args.gen_gate:
            Gen_Gate()
        elif args.jic_init:
            Config_Jic()
        elif args.tdc_init:
            Config_Tdc()
        elif args.sim_stop_pulse is not None:
            fre_divider = int(args.sim_stop_pulse[0])
            if (fre_divider > 256 or fre_divider < 0):
                exit("not in range of [0..256]")
            pulse_start = int(args.sim_stop_pulse[1])
            if (pulse_start > 3986 or pulse_start < 0):
                exit("not in the range of [0..3986] steps")
            Stop_sim(fre_divider,pulse_start)
        elif args.time_calib_reg is not None:
            command = int(args.time_calib_reg[0])
            t0 = int(args.time_calib_reg[1])
            gc_back = int(args.time_calib_reg[2])
            gate0 = int(args.time_calib_reg[3])
            width0 = int(args.time_calib_reg[4])
            gate1 = int(args.time_calib_reg[5])
            width1 = int(args.time_calib_reg[6])
            Time_Calib_Reg(command, t0, gc_back, gate0, width0, gate1, width1)
        elif args.time_calib_init:
            Time_Calib_Init()
        elif args.cont_det:
            Cont_Det()
        elif args.gated_det:
            Gated_Det()
        elif args.mon_counts:
            Count_Mon()
        elif args.find_shift_old:
            Phase_Shift_Calib()
        elif args.test_phase:
            Phase_Drift_Test()
        elif args.feedback_phase:
            Feedback_Phase()
        elif args.gated_det_fd:
            Reset_gc()
            Start_gc()
            Gated_Det()
        elif args.ddr_data_reg is not None:
            command = int(args.ddr_data_reg[0])
            current_gc = np.int64(args.ddr_data_reg[1])
            read_speed = int(args.ddr_data_reg[2])
            fiber_delay = int(args.ddr_data_reg[3])
            pair_mode = int(args.ddr_data_reg[4])
            Ddr_Data_Reg(command,current_gc,read_speed,fiber_delay,pair_mode)
        elif args.ddr_data_init:
            Ddr_Data_Init()
        elif args.get_gc:
            Ddr_Data_Init()
            Get_Gc()
        elif args.get_current_gc:
            Get_Current_Gc()
        elif args.read_angle:
            Read_Angle()
        elif args.angle:
            Angle()
        elif args.ddr_status:
            Ddr_Status()
        elif args.ddr_debug:
            Ddr_Debug()

    def debug(args):
        if (args.ltc_init):
            Config_Ltc()
        elif args.para_master is not None:
            duty = int(args.para_master[0])
            tune = int(args.para_master[1])
            fine = int(args.para_master[2])
            inc = int(args.para_master[3])
            if (duty > 7 or duty <1):
                exit("not the duty in range ")
            if (tune>7 or tune <0):
                exit ("not the tune value in range")
            if (fine>2000 or fine <0):
                exit ("not the fine value in range")
            if (inc != 1 and inc != 0):
                exit ("not the choice for direction of shift")
            write_delay_master(duty,tune,fine,inc)
        elif args.para_slaves is not None:
            fine1 = int(args.para_slaves[0])
            inc1 = int(args.para_slaves[1])
            fine2 = int(args.para_slaves[2])
            inc2 = int(args.para_slaves[3])
            if (fine1 >2000 or fine1 <0):
                exit ("not the fine value in range")
            if (inc1 != 1 and inc1 != 0):
                exit ("not the choice for direction of shift")
            if (fine2 >2000 or fine2 <0):
                exit ("not the fine value in range")
            if (inc2 != 1 and inc2 != 0):
                exit ("not the choice for direction of shift")
            write_delay_slaves(fine1,inc1, fine2, inc2)
        elif args.regs_en:
            params_en()
        elif args.add_delay_m:
            trigger_fine_master()
        elif args.add_delay_s1:
            trigger_fine_slv1()
        elif args.add_delay_s2:
            trigger_fine_slv2()
        elif args.ttl_rst:
            ttl_reset()
        elif args.long_delay:
            Test_delay()


    #create top_level parser
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(required=True)

    #create parser for "alice" command
    parser_alice = subparsers.add_parser('alice')
    parser_alice.add_argument("--init",action="store_true",help="initialize Alice")
    parser_alice.add_argument("--gen_dp",nargs=2, metavar=('shift_am', 'first_peak'), help="generate double pulse")
    parser_alice.add_argument("--verify_shift_a",nargs=1,metavar=("shift_pm"),help="verify shift parameter of alice")
    parser_alice.add_argument("--verify_shift_b",nargs=1,metavar=("shift_pm"),help="verify shift parameter of bob")
    parser_alice.add_argument("--find_delay_ab_mod32",action="store_true",help="apply phase to find delay between Alice and Bob")
    parser_alice.add_argument("--find_delay_ab",action="store_true",help="apply phase to find delay between Alice and Bob")


    parser_alice.add_argument("--ltc_init",action="store_true",help="config ltc")
    parser_alice.add_argument("--sync_ltc",action="store_true", help="send sync trigger to fpga")
    parser_alice.add_argument("--fda_init",action="store_true", help="config fastdac")
    parser_alice.add_argument("--sequence",nargs=1,metavar=('rf_am'), help="rf_am str ['off_am','off_pm','sp','dp'];send samples to DAC0,DAC1 from files")
    parser_alice.add_argument("--shift",nargs=6,metavar=('rng_mode','amp0','amp1','amp2','amp3','shift'), help="rng_mode int [0:fix_seq;2:fake_rng_seq;3:true_rng_seq];amp* float [-1,1]; shift int [0,10] ")
    parser_alice.add_argument("--sda_init",action="store_true", help="slow_dac init")
    parser_alice.add_argument("--am_bias",nargs=2,metavar=('chan','vol'), help="chan int [4]; vol float [-10,10] V")
    parser_alice.add_argument("--vca_bias",nargs=2,metavar=('chan','vol'), help="chan int [7]; vol float [0,6] V")
    parser_alice.add_argument("--stretch_bias",nargs=2,metavar=('chan','vol'), help="chan int [3]; vol float [0,5] V")
    #check decoy signal
    parser_alice.add_argument("--decoy",action="store_true", help="check decoy signal")
    parser_alice.add_argument("--pm_rng",action="store_true", help="check pm rng")
    parser_alice.add_argument("--decoy_rst",action="store_true", help="reset decoy module")
    parser_alice.add_argument("--de_para_master",nargs=3,metavar=('tune','fine','inc'), help="tune int [0..7] ~4ns/step; fine int [0..512] 512 taps ~ 1.1ns ; inc int [inc[1]/dec[0]] ")
    parser_alice.add_argument("--de_para_slaves",nargs=4,metavar=('fine1','inc1','fine2','inc2'), help="fine* int [0..511] 511 taps ~ 1.1ns(the)/1.68ns(ex) ; inc* int [inc[1]/dec[0]] ")
    parser_alice.add_argument("--de_regs_en",action="store_true", help="save parameters to fpga regs ")
    parser_alice.add_argument("--de_add_delay_m",action="store_true", help="trigger delay master ")
    parser_alice.add_argument("--de_add_delay_s1",action="store_true", help="trigger delay slave1 ")
    parser_alice.add_argument("--de_add_delay_s2",action="store_true", help="trigger delay slave2 ")


    parser_alice.add_argument("--ddr_data_reg",nargs=5,metavar=('command','current_gc','read_speed','fiber_delay','pair_mode'), help="command int[1: get_gc | 2: get_current_gc | 3: read_angle | 4: stop_read]; current_gc int64; read_speed int [0..4000] control speed of reading gc_in_fifo; fiber_delay int [0..2^32]; pair_mode int 0|1")
    parser_alice.add_argument("--ddr_data_init",action="store_true", help="reset and start ddr_data module")
    parser_alice.add_argument("--get_gc",action="store_true", help="get gc from Bob and send back to fpga as a loop test")
    parser_alice.add_argument("--get_current_gc",action="store_true", help="get current value of gc")
    parser_alice.add_argument("--read_angle",action="store_true", help="start read out angle at current gc +++")
    parser_alice.add_argument("--angle",action="store_true", help="read out angle ")
    parser_alice.add_argument("--ddr_status",action="store_true", help="monitoring ddr_status")

    parser_alice.set_defaults(func=alice)


    #create parser for "charlie" command
    parser_charlie = subparsers.add_parser('charlie')
    parser_charlie.set_defaults(func=charlie)

    #create parser for "bob" command
    parser_bob = subparsers.add_parser('bob')
    parser_bob.add_argument("--init",action="store_true",help="initialize Bob")
    parser_bob.add_argument("--gen_dp",action="store_true",help="detection dp in continuous mode")
    # parser_bob.add_argument("--find_gate",action="store_true",help="find gate parameters")
    # parser_bob.add_argument("--find_shift",action="store_true",help="find phase shift parameter")
    parser_bob.add_argument("--verify_shift_b",nargs=1,metavar=("shift_pm"),help="verify shift parameter of bob")
    parser_bob.add_argument("--verify_shift_a",nargs=1,metavar=("shift_pm"),help="verify shift parameter of alice")
    parser_bob.add_argument("--find_delay_b",action="store_true",help="find fiber delay locally in Bob")
    parser_bob.add_argument("--find_delay_ab_mod32",action="store_true",help="find delay between Alice and Bob")
    parser_bob.add_argument("--find_delay_ab",action="store_true",help="find delay between Alice and Bob")


    parser_bob.add_argument("--ltc_init",action="store_true",help="config ltc")
    parser_bob.add_argument("--sync_ltc",action="store_true", help="send sync trigger to fpga")
    parser_bob.add_argument("--fda_init",action="store_true", help="config fastdac")
    parser_bob.add_argument("--sequence",nargs=1,metavar=('rf_am'), help="rf_am str ['off_am','off_pm','sp','dp'];send samples to DAC0,DAC1 from files")
    parser_bob.add_argument("--shift",nargs=6,metavar=('rng_mode','amp0','amp1','amp2','amp3','shift'), help="rng_mode int [0:fix_seq;2:fake_rng_seq;3:true_rng_seq];amp* float [-1,1]; shift int [0,10] ")
    parser_bob.add_argument("--sda_init",action="store_true", help="slow_dac init")
    parser_bob.add_argument("--pol_bias",nargs=2,metavar=('chan','vol'), help="chan int [0,1,2,3]; vol float [-10,10] V")
    parser_bob.add_argument("--pol_ctl",action="store_true", help="run polarisation control")
    parser_bob.add_argument("--gen_gate",action="store_true",help="generate gate signal for APD Aurea")

    parser_bob.add_argument("--jic_init",action="store_true", help="set registers jitter cleaner ")
    parser_bob.add_argument("--tdc_init",action="store_true", help="set registers tdc ")
    parser_bob.add_argument("--sim_stop_pulse",nargs=2,metavar=('fre_divider','pulse_start'), help="generate stop pulse for tdc, start at [0..3986] step, 1 step = 5ns, fre_divider int[1..250], stopa_fre = 200M/(800*fre_div), 5=50kHz, 250 = 1kHz")

    parser_bob.add_argument("--time_calib_reg",nargs=7,metavar=('command','t0','gc_back','gate0','width0','gate1','width1'), help="command int[1:raw|2:with gate];"
            "t0 int [0..625]: minus t0 | 32768 + [0..625]: plus t0;" 
            "gc_back int [10..12] gcs;"
            "gate* int [0..625] 20ps;"
            "width* int [0..100] 20ps")
    parser_bob.add_argument("--time_calib_init",action="store_true", help="Get time data ready")
    parser_bob.add_argument("--cont_det",action="store_true", help="find delay time of tdc arriving time refer to previous 80MHz edge")
    parser_bob.add_argument("--gated_det",action="store_true", help="apply gate after shift the time to verify histogram")
    parser_bob.add_argument("--mon_counts",action="store_true", help="monitor the number of counts")
    
    #Calibration Shift 
    parser_bob.add_argument("--find_shift_old",action="store_true", help="find shift parameter for PM signal")
    parser_bob.add_argument("--test_phase",action="store_true", help="shift phase and check click rate")
    parser_bob.add_argument("--feedback_phase",action="store_true", help="turn feedback on, inital phase qkd")
    parser_bob.add_argument("--find_delay",action="store_true", help="find optical delay between parties")
    parser_bob.add_argument("--gated_det_fd",action="store_true", help="find optical delay between parties")


    #Group of commands on ddr
    parser_bob.add_argument("--ddr_data_reg",nargs=5,metavar=('command','current_gc','read_speed','fiber_delay','pair_mode'), help="command int[1: get_gc | 2: get_current_gc | 3: read_angle | 4: stop_read]; current_gc int64; read_speed int [0..4000] control speed of reading gc_in_fifo; fiber_delay int [0..2^32]; pair_mode int 0|1")
    parser_bob.add_argument("--ddr_data_init",action="store_true", help="reset and start ddr_data module")
    parser_bob.add_argument("--get_gc",action="store_true", help="get gc from Bob and send back to fpga as a loop test")
    parser_bob.add_argument("--get_current_gc",action="store_true", help="get current value of gc")
    parser_bob.add_argument("--read_angle",action="store_true", help="start read out angle at current gc +++")
    parser_bob.add_argument("--angle",action="store_true", help="read out angle ")
    parser_bob.add_argument("--ddr_status",action="store_true", help="monitoring ddr_status")


    parser_bob.set_defaults(func=bob)

    #create parser for "debug" command
    parser_debug = subparsers.add_parser('debug')
    parser_debug.add_argument("--ltc_init",action="store_true",help="config ltc")
    parser_debug.set_defaults(func=debug)

    parser_debug.add_argument("--ttl_rst",action="store_true", help="reset ttl pulse ")
    parser_debug.add_argument("--para_master",nargs=4,metavar=('duty','tune','fine','inc'), help="duty int [0..3]; tune int [0..3] ~4ns/step; fine int [0..512] 512 taps ~ 1.1ns ; inc int [inc[1]/dec[0]] ")
    parser_debug.add_argument("--para_slaves",nargs=4,metavar=('fine1','inc1','fine2','inc2'), help="fine* int [0..511] 511 taps ~ 1.1ns(the)/1.68ns(ex) ; inc* int [inc[1]/dec[0]] ")
    parser_debug.add_argument("--regs_en",action="store_true", help="save parameters to fpga regs ")
    parser_debug.add_argument("--add_delay_m",action="store_true", help="trigger delay master ")
    parser_debug.add_argument("--add_delay_s1",action="store_true", help="trigger delay slave1 ")
    parser_debug.add_argument("--add_delay_s2",action="store_true", help="trigger delay slave2 ")
    parser_debug.add_argument("--long_delay",action="store_true", help="test distance of 0.5ms ")

    
    args = parser.parse_args()
    args.func(args)
if __name__ =="__main__":
    main()
