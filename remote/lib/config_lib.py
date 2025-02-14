import subprocess, time, mmap

import lib.gen_seq as gen_seq

def save_default(data):
    """
    data : dictionary to be saved to config/tmp.txt
    """
    with open("config/default.txt", 'w') as f:
        f.write("# tab separated\n")
        for i in data.items():
            f.write(i[0]+"\t"+str(i[1])+"\n")

def get_default():
    """
    return : dictionary from config/default.txt
    """
    d = {}
    floatlist = ['vca', 'am_bias', 'qdistance', 
                 'angle0', 'angle1', 'angle2', 'angle3']
    with open("config/default.txt") as f:
        lines = f.readlines()
        for l in lines[1:]:
            s = l[:-1].split("\t")
            key = s[0]
            value = s[1]
            if key in floatlist:
                d[key] = float(value) 
            else:
                d[key] = int(value) 
    return d

def save_tmp(data):
    """
    data : dictionary to be saved to config/tmp.txt
    """
    with open("config/tmp.txt", 'w') as f:
        for i in data.items():
            f.write(i[0]+"\t"+str(i[1])+"\n")

def get_tmp():
    """
    return : dictionary from config/tmp.txt
    """
    t = {}
    floatlist = ['qdistance', 'pol0', 'pol1', 'pol2', 'pol3', 'vca', 'am_bias',
                 'angle0', 'angle1', 'angle2', 'angle3']
    strlist = ['spd_mode', 'am_mode', 'pm_mode', 'feedback', 'soft_gate']
    with open("config/tmp.txt") as f:
        lines = f.readlines()
        for l in lines:
            s = l[:-1].split("\t")
            key = s[0]
            value = s[1]
            if key in floatlist:
                t[key] = float(value) 
            elif key in strlist:
                t[key] = value
            else:
                t[key] = int(value) 
    return t

def update_tmp(key, element):
    t = get_tmp()
    t[key] = element
    save_tmp(t)

def update_default(key, element):
    d = get_default()
    d[key] = element
    save_default(d)

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


## write seq listst to dac for dpram operation
def Write_To_Dac(seqlist_dac0, seqlist_dac1):
    Base_Addr = 0x00030000
    Write(Base_Addr + 16, 0x0000a0a0) #sequence64
    #Write data to dpram_dac0 and dpram_dac1
    Base_seq0 = Base_Addr + 0x1000  #Addr_axi_sequencer + addr_dpram
    seqlist = seqlist_dac1*2**16 + seqlist_dac0
    fd = open("/dev/xdma0_user", 'r+b', buffering=0)
    write_to_dev(fd, Base_seq0, 0, seqlist.tolist())
    fd.close()



#def Seq_Dacs_Off():
#    #Write dpram_max_addr port out 
#    Base_Addr = 0x00030000
#    Write(Base_Addr + 16, 0x0000a0a0) #sequence64
#    #Write data to dpram_dac0 and dpram_dac1
#    Base_seq0 = Base_Addr + 0x1000  #Addr_axi_sequencer + addr_dpram
#    seq_list = gen_seq.seq_dacs_off() 
#
#    vals = []
#    for ele in seq_list:
#        vals.append(int(ele,0))
#
#    fd = open("/dev/xdma0_user", 'r+b', buffering=0)
#    write_to_dev(fd, Base_seq0, 0, vals)
#    fd.close()


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
    print("Initialize fake rng sequence equal 0 ")


#Write parameter of amplitude and delay for signal on DAC1 (QDAC, signal for PM)
#2's compliment in dac
#shift only apllies for mode 2|mode 3
#in mode 0, data comes from dpram_sequence, move samples in file -> shift (run test_sig.py ) 
#def Write_Dac1_Shift(rng_mode, amp0, amp1, amp2, amp3, shift):
#    Base_Addr = 0x00030000
#    amp_list = [amp0,amp1,amp2,amp3]
#    amp_out_list = []
#    for amp in amp_list:
#        if (amp >= 0):
#            amp_hex = round(32767*amp)
#        elif (amp < 0):
#            amp_hex = 32768+32768+round(32767*amp)
#        amp_out_list.append(amp_hex)
#    shift_hex = hex(shift)
#    up_offset = 0x4000
#    shift_hex_up_offset = (int(up_offset)<<16 | shift)
#    division_sp = hex(1000)
#    fastdac_amp1_hex = (amp_out_list[1]<<16 | amp_out_list[0])
#    fastdac_amp2_hex = (amp_out_list[3]<<16 | amp_out_list[2])
#    Write(Base_Addr + 8, fastdac_amp1_hex)
#    Write(Base_Addr + 24, fastdac_amp2_hex)
#    Write(Base_Addr + 4, shift_hex_up_offset)
#    Write(Base_Addr + 32, division_sp)
#
#    #Write bit0 of slv_reg5 to choose RNG mode
#    #1: Real rng from usb | 0: rng read from dpram
#    #Write bit1 of slv_reg5 to choose dac1_sequence mode
#    #1: random amplitude mode | 0: fix sequence mode
#    #Write bit2 of slv_reg5 to choose feedback mode
#    #1: feedback on | 0: feedback off
#    #----------------------------------------------
#    #Write slv_reg5:
#    #0x0: Fix sequence for dac1, input to dpram
#    #0x02: Random amplitude, with fake rng
#    #0x03: Random amplitude, with true rng
#    #0x06: Random amplitude, with fake rng, feedback on
#    #0x07: Random amplitude, with true rng, feedback on
#    Write(Base_Addr + 20, hex(rng_mode))
#    #Trigger for switching domain
#    Write(Base_Addr + 12,0x1)
#    Write(Base_Addr + 12,0x0)

def Write_Pm_Mode(mode='seq64', feedback='off'):
    Base_Addr = 0x00030000
    if feedback=='off':
        fb = 0
    else:
        fb = 4
    if mode=='seq64':
        Write(Base_Addr + 20, hex(0))
    elif mode=='fake_rng':
        Write(Base_Addr + 20, hex(2+fb))
    elif mode=='true_rng':
        Write(Base_Addr + 20, hex(3+fb))
    else:
        print("wrong sequence argument")
        exit()
    #Trigger for switching domain
    Write(Base_Addr + 12,0x1)
    Write(Base_Addr + 12,0x0)
    update_tmp('pm_mode', mode)

def Write_Pm_Shift(shift):
    Base_Addr = 0x00030000
    shift_hex = hex(shift)
    up_offset = 0x4000
    shift_hex_up_offset = (int(up_offset)<<16 | shift)
    division_sp = hex(1000)
    Write(Base_Addr + 4, shift_hex_up_offset)
    Write(Base_Addr + 32, division_sp)
    #Trigger for switching domain
    Write(Base_Addr + 12,0x1)
    Write(Base_Addr + 12,0x0)
    print("pm_shift written: ", shift)


def Write_Angles(a0, a1, a2, a3):
    Base_Addr = 0x00030000
    amp_list = [a0,a1,a2,a3]
    amp_out_list = []
    for amp in amp_list:
        if (amp >= 0):
            amp_hex = round(32767*amp)
        elif (amp < 0):
            amp_hex = 32768+32768+round(32767*amp)
        amp_out_list.append(amp_hex)
    fastdac_amp1_hex = (amp_out_list[1]<<16 | amp_out_list[0])
    fastdac_amp2_hex = (amp_out_list[3]<<16 | amp_out_list[2])
    Write(Base_Addr + 8, fastdac_amp1_hex)
    Write(Base_Addr + 24, fastdac_amp2_hex)
    #Trigger for switching domain
    Write(Base_Addr + 12,0x1)
    Write(Base_Addr + 12,0x0)
    print("angles written: ", a0, a1, a2, a3)

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
    #print("Trigger master done")

def trigger_fine_slv1():
    Base_Add = 0x00015000
    Write(Base_Add + 16, 0x0)
    Write(Base_Add + 16, 0x1)
    time.sleep(0.02)
    Write(Base_Add + 16, 0x0)
    #print("Trigger slave1 done")

def trigger_fine_slv2():
    Base_Add = 0x00015000
    Write(Base_Add + 20, 0x0)
    Write(Base_Add + 20, 0x1)
    time.sleep(0.02)
    Write(Base_Add + 20, 0x0)
    #print("Trigger slave2 done")



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
    command = "test_tdc/dma_from_device "+"-d "+ device_c2h +" -f "+ output_file+ " -c " + str(count) 
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


#---------------------------TDC CALIBRATION-----------------------------------------------
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

def Soft_Gate_Filter(state):
    if state=="on":
        command = 2
    elif state=="off":
        command = 1
    else:
        exit("wrong argument to Soft_Gate_Finter()")
    BaseAddr = 0x00000000
    Write(BaseAddr + 32,hex(int(command))) #command = 1: raw | =2: with gate
    Write(BaseAddr + 36,0x0)
    Write(BaseAddr + 36,0x2)# turn bit[1] to high to enable register setting

def Set_t0(t0):
    BaseAddr = 0x00000000
    Write(BaseAddr + 24,hex(int(t0))) #shift tdc time = 0
    Write(BaseAddr + 36,0x0)
    Write(BaseAddr + 36,0x2)# turn bit[1] to high to enable register setting

def Write_Soft_Gates(gate0, width0, gate1, width1):
    BaseAddr = 0x00000000
    Write(BaseAddr + 16,hex(int(width0<<24 | gate0))) #gate0
    Write(BaseAddr + 20,hex(int(width1<<24 | gate1))) #gate1
    Write(BaseAddr + 36,0x0)
    Write(BaseAddr + 36,0x2)# turn bit[1] to high to enable register setting

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

def Time_Calib_Init():
    Config_Tdc() #Get digital data from TDC chip
    Reset_gc() #Reset global counter
    Start_gc() #Global counter start counting at the next PPS

#def Write_Seqlist_old(seqlist):
#    Base_Addr = 0x00030000
#    Write(Base_Addr + 16, 0x0000a0a0) #sequence64
#    #Write data to dpram_dac0 and dpram_dac1
#    Base_seq0 = Base_Addr + 0x1000  #Addr_axi_sequencer + addr_dpram
#    vals = []
#    for ele in seq_list:
#        vals.append(int(ele,0))
#    fd = open("/dev/xdma0_user", 'r+b', buffering=0)
#    write_to_dev(fd, Base_seq0, 0, vals)
#    fd.close()
