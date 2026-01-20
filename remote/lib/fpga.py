import subprocess, time, mmap, numpy as np, os

import hw_control.lib.gen_seq as gen_seq

HW_CONTROL = '/home/vq-user/hw_control/'
HW_CONFIG = '/home/vq-user/config/'

#def save_default(data):
#    """
#    data : dictionary to be saved to config/tmp.txt
#    """
#    with open(HW_CONTROL+"config/default.txt", 'w') as f:
#        f.write("# tab separated\n")
#        for i in data.items():
#            f.write(i[0]+"\t"+str(i[1])+"\n")

#def get_default():
#    """
#    return : dictionary from config/default.txt
#    """
#    d = {}
#    floatlist = ['vca', 'am_bias','am2_bias', 'qdistance', 
#                 'angle0', 'angle1', 'angle2', 'angle3']
#    with open(HW_CONTROL+"config/default.txt") as f:
#        lines = f.readlines()
#        for l in lines[1:]:
#            s = l[:-1].split("\t")
#            key = s[0]
#            value = s[1]
#            if key in floatlist:
#                d[key] = float(value) 
#            else:
#                d[key] = int(value) 
#    return d

def save_tmp(data):
    """
    data : dictionary to be saved to config/tmp.txt
    """
    with open(HW_CONTROL+"config/tmp.txt", 'w') as f:
        for i in data.items():
            f.write(i[0]+"\t"+str(i[1])+"\n")

def get_tmp():
    """
    return : dictionary from config/tmp.txt
    """
    t = {}
    floatlist = ['qdistance', 'pol0', 'pol1', 'pol2', 'pol3', 'vca', 'am_bias','am2_bias',  'am2_bias_min', 'angle0', 'angle1', 'angle2', 'angle3', 'vca_calib']
    strlist = ['spd_mode', 'am_mode', 'pm_mode', 'feedback', 'soft_gate', 'insert_zeros', 'am2_mode']
    with open(HW_CONTROL+"config/tmp.txt") as f:
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

def save_calibrated(data, filename):
    """
    data : dictionary to be saved to /home/vq-user/config/calibration/filename
    """
    fullpath = "/home/vq-user/config/calibration/"+filename
    os.makedirs(os.path.dirname(fullpath), exist_ok=True)
    with open(fullpath, 'w') as f:
        for i in data.items():
            f.write(i[0]+"\t"+str(i[1])+"\n")

def get_calibrated(filename):
    """
    return : dictionary from /home/vq-user/config/filename
    """
    t = {}
    floatlist = ['qdistance', 'pol0', 'pol1', 'pol2', 'pol3', 'vca', 'am_bias','am2_bias',  'am2_bias_min', 'angle0', 'angle1', 'angle2', 'angle3', 'vca_calib']
    strlist = ['spd_mode', 'am_mode', 'pm_mode', 'feedback', 'soft_gate', 'insert_zeros', 'am2_mode']
    with open("/home/vq-user/config/calibration/"+filename) as f:
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

#def update_default(key, element):
#    d = get_default()
#    d[key] = element
#    save_default(d)

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
    mm.close()

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
    #mm.flush()
    array_of_u32 = []
    for i in range(addr//4, length+addr//4):
        array_of_u32.append(int.from_bytes(mm[i*4: (i+1)*4], 'little')) 
    #mm.flush()
    mm.close()
    return array_of_u32

def write(offset, addr, value):
    """
    offset : must be multiple of PAGESIZE, which we assume is 4096
    addr   : int or array of ints; with respect to offset; counting bytes
    value  : int or array of ints
    """
    if (np.array(addr)>4092).any():
        exit("addr cannot be larger than 4092")
    if (type(addr) == int) and (type(value)==int):
        with open("/dev/xdma0_user", 'r+b', buffering=0) as fd:
            with mmap.mmap(fd.fileno(), 4096, offset=offset) as mm:
                mm[addr:addr+4] = value.to_bytes(4, 'little')
    else:
        if len(addr) != len(value):
            exit("length of addr and value do not match")
        with open("/dev/xdma0_user", 'r+b', buffering=0) as fd:
            with mmap.mmap(fd.fileno(), 4096, offset=offset) as mm:
                for a,v in zip(addr, value):
                    mm[a:a+4] = v.to_bytes(4, 'little')

def read(offset, addr):
    """
    offset : must be multiple of PAGESIZE, which we assume is 4096
    addr   : int or array of ints; with respect to offset; counting bytes
    """
    if (np.array(addr)>4092).any():
        exit("addr cannot be larger than 4092")
    if type(addr) == int:
        with open("/dev/xdma0_user", 'r+b', buffering=0) as fd:
            with mmap.mmap(fd.fileno(), 4096, offset=offset) as mm:
                return int.from_bytes(mm[addr:addr+4], 'little') 
    else:
        value = []
        with open("/dev/xdma0_user", 'r+b', buffering=0) as fd:
            with mmap.mmap(fd.fileno(), 4096, offset=offset) as mm:
                for a in addr:
                    value.append(int.from_bytes(mm[a:a+4], 'little'))
        return value
                    

def get_counts():
    addr = 56
    with open("/dev/xdma0_user", 'r+b', buffering=0) as fd:
        with mmap.mmap(fd.fileno(), 0x1000, offset=0) as mm:
            click0 = int.from_bytes(mm[addr:addr+4], 'little')
            click1 = int.from_bytes(mm[addr+4:addr+8], 'little')
            total = int.from_bytes(mm[addr+8:addr+12], 'little')
    return total, click0, click1

def request_counts():
    addr_start = 32
    addr_data = 44
    with open("/dev/xdma0_user", 'r+b', buffering=0) as fd:
        with mmap.mmap(fd.fileno(), 0x1000, offset=0) as mm:
            # start
            mm[addr_start] = 0x0
            mm[addr_start] = 0x8
            time.sleep(0.101)
            # read data
            total = int.from_bytes(mm[addr_data:addr_data+4], 'little')
            click1 = int.from_bytes(mm[addr_data+4:addr_data+8], 'little')
            click0 = int.from_bytes(mm[addr_data+8:addr_data+12], 'little')
    return total, click0, click1




#def Write_stream(device,file, size, count):
#    str_device = device
#    str_file = file
#    str_size = str(size)
#    str_count = str(count)
#    # command ="../../tools/dma_to_device -d "+ str_device + " -f "+ str_file + " -s "+ str_size + " -c " + str_count 
#    command ="/home/vq-user/qline/dma_ip_drivers/XDMA/linux-kernel/tools/dma_to_device -d "+ str_device + " -f "+ str_file + " -s "+ str_size + " -c " + str_count 
#    print(command)
#    s = subprocess.check_call(command, shell = True)
#
#def Read_stream(device, file, size, count):
#    str_device = device
#    str_file = file
#    str_size = str(size)
#    str_count = str(count)
#    # command ="../../tools/dma_from_device -d "+ str_device + " -f "+ str_file + " -s "+ str_size + " -c " + str_count 
#    command ="/home/vq-user/qline/dma_ip_drivers/XDMA/linux-kernel/tools/dma_from_device -d "+ str_device + " -f "+ str_file + " -s "+ str_size + " -c " + str_count 
#    print(command)
#    s = subprocess.check_call(command, shell = True)



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


def Get_reg_new(spi_bus,device,*args):
    if (spi_bus == 1):
        BaseAdd = 0x00013000
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

    with open("/dev/xdma0_user", 'r+b', buffering=0) as fd:
        with mmap.mmap(fd.fileno(), 4096, offset=BaseAdd) as mm:

            # reset spi
            mm[SRR] = 0x0A    #reset AXI QUAD SPI
            time.sleep(0.003)
            mm[SPICR:SPICR+4] = (0x186 | spi_mode<<3).to_bytes(4,'little')  #set AXI QUAD SPI Control register
            mm[DGIER:DGIER+4] = (0x80000000).to_bytes(4,'little') #Device Global Interrupt Enable Register
            mm[IPIER:IPIER+4] = (0x04).to_bytes(4,'little')    # IP Interrupt Enable Register

            mm[SPISSR] = DATA_CS_EN
            mm[SPICR] = 0x86 | spi_mode<<3      # Enable transfer

            # write bytes to fifo
            for value in args:
                mm[SPI_DTR] = value
            
            output = []
            for i in range(len(args)):
                # wait for rx fifo to have data 
                while mm[SPISR] & 1 == 1:
                    continue
                output.append(mm[SPI_DRR])
            
            ## read while not empty
            #while mm[SPISR] & 1 == 0:
            
            mm[SPISSR] = DATA_CS_DIS
            mm[SPICR:SPICR+4] = (0x186 | spi_mode<<3).to_bytes(4,'little') # Disable transfer
            #print([hex(i) for i in output])

    return output
    




def Set_Ltc():
    reg_file = open(HW_CONFIG+'registers/ltc/Ltc6951Regs.txt','r')
    for l in reg_file.readlines():
        add, val = l.split(',')
        add_shifted = int(add, base=16)<<1
        ret = Get_reg_new(2,'ltc', add_shifted, int(val, base=16))
    print("Set ltc configuration registers finished")
    reg_file.close()

def Sync_Ltc():
    #Reset sync counter
    write(0x12000, 24, 1)
    write(0x12000, 24, 0)
    time.sleep(0.1)
    #Send sync trigger
    write(0x12000, [0, 0], [0, 1])
    time.sleep(1.2)
    write(0x12000, 0, 0)
    print("Output clocks are aligned")

def Get_Ltc_info():
    reg_file = open(HW_CONFIG+'registers/ltc/Ltc6951Expect.txt','r')
    array = []
    print("Monitoring ltc registers")
    print("addr\texp\tret\tmatch")
    for l in reg_file.readlines():
        add, val = l.split(',')
        add = int(add, 16)
        val = int(val, 16)
        add_shifted = (add<<1) | 1
        ret = Get_reg_new(2,'ltc',add_shifted,0)[1]
        print(str(add)+"\t"+hex(val)+"\t"+hex(ret)+"\t"+str(val==ret))
    print("Monitoring ltc finished")
    reg_file.close()

def get_ltc_info(verbose=False):
    data = np.loadtxt(HW_CONFIG+'registers/ltc/Ltc6951Expect.txt', delimiter=',', converters=lambda s: int(s, 16), dtype=int)
    add = data[:,0]
    expect = data[:,1]
    l = len(add)
    got = np.zeros(l, dtype=int)
    for i in range(l):
        add_shifted = (add[i]<<1) | 1
        got[i] = Get_reg_new(2,'ltc',add_shifted,0)[1]
    if verbose:
        output = np.zeros((l,3), dtype=int)
        output[:,0] = add
        output[:,1] = expect
        output[:,2] = got
        return output
    else:
        return (got==expect).all()


def Get_Id():
    id_add = 0x13
    add_shifted = (id_add <<1) | 1 
    id_val = Get_reg_new(2,'ltc',add_shifted,0)[1]
    print("Id_Addr",hex(id_add),"Ltc_id:",hex(id_val))

    

def Config_Ltc():
    Set_Ltc()
    Get_Id()
    Get_Ltc_info()


def Get_Sda_Id():
    add = (1<<7) | 1
    id_val_pre = Get_reg_new(2,'sda',add, 0, 0)
    ret = Get_reg_new(2,'sda',0 , 0, 0)
    retadd = ret[0]
    deviceid = (ret[1]<<8 | ret[2]) << 2
    print("checking id of Sda: (expected value 0x298)")
    print(hex(retadd), hex(deviceid))

def Soft_Reset_Sda():
    trigger_reg_add = 0x0E
    reserved_code = 0xA
    Get_reg_new(2,'sda',trigger_reg_add, 0,reserved_code)
    print('Soft reset sda finished')
    
def Set_Sda_Config():
    file = open(HW_CONFIG+'registers/sda/Dac81408_setting.txt','r')
    for l in file.readlines():
        addb, val1, val2 = l.split(',')
        Get_reg_new(2,'sda', int(addb, 16), int(val1, 16), int(val2, 16)) #Set all registers
    print("Set sda configuration registers finished")
    file.close()


def Get_Sda_Config():
    file = open(HW_CONFIG+'registers/sda/Dac81408_Expect.txt','r')
    print("Monitoring sda readback configuration registers")
    print("addr\texp\tret\tmatch")
    for l in file.readlines():
        addb, val1, val2 = l.split(',')
        val = int(val1,16)<<8 | int(val2,16)
        add_shifted = 1<<7 | int(addb, base=16) #Start to readback value for monitoring
        val2_pre = Get_reg_new(2,'sda',add_shifted,0,0)
        ret = Get_reg_new(2,'sda',0,0,0)
        ret = ret[1]<<8 | ret[2]
        print(addb+"\t"+hex(val)+"\t"+hex(ret)+"\t"+str(val==ret))
        #print("reg_val1:",val1)
    print("Monitoring sda finished")
    file.close()

def get_sda_info(verbose=False):
    data = np.loadtxt(HW_CONFIG+'registers/sda/Dac81408_setting.txt', delimiter=',', converters=lambda s: int(s, 16), dtype=int)
    add = data[:,0]
    expect = data[:,1]<<8 | data[:,2]
    l = len(add)
    got = np.zeros(l, dtype=int)
    for i in range(l):
        add_shifted = 1<<7 | add[i] #Start to readback value for monitoring
        val2_pre = Get_reg_new(2,'sda',add_shifted,0,0)
        ret = Get_reg_new(2,'sda',0,0,0)
        got[i] = ret[1]<<8 | ret[2]
    if verbose:
        output = np.zeros((l,3), dtype=int)
        output[:,0] = add
        output[:,1] = expect
        output[:,2] = got
        return output
    else:
        # ignore addr 4 and addr 0xb because
        # they don't match even though the device seems
        # to be working normally
        got[2] = expect[2]
        got[8] = expect[8]
        return (got==expect).all()


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
    if channel in [4, 5]:
        data_vol = int(((vz + 10) * (1<<16)-1)/20)  
    elif (channel == 7 ):
        data_vol = int((vz * (1<<16)-1)/10)
    else:
        data_vol = int((vz * (1<<16)-1)/5)
    reg = [(20+channel, data_vol),]
    addb = 20 + channel
    val = data_vol
    addr_shift =addb&0xff
    val1 =(val>>8)&0xff
    val2 =val&0xff
    # print(addr_shift)
    # print(val1)
    # print(val2)
    Get_reg_new(2,'sda', addr_shift, val1, val2) #Set data register
    print("Channel",channel,"is set to", round(voltage,2), "V")


def WriteFPGA():
    #file = open("registers/fda/FastdacFPGA.txt","r")
    file = open(HW_CONFIG+"registers/fda/FastdacFPGA_204b.txt","r")
    with open("/dev/xdma0_user", 'r+b', buffering=0) as fd:
        with mmap.mmap(fd.fileno(), 4096, offset=0x10000) as mm:
            for l in file.readlines():
                addr, val = l.split(',')
                addr = int(addr,16)
                val = int(val,16)
                mm[addr:addr+4] = val.to_bytes(4,'little')
    print("Set JESD configuration for FPGA finished")
    file.close()


## write seq listst to dac for dpram operation
def Write_To_Dac(seqlist_dac0, seqlist_dac1):
    Base_Addr = 0x00030000
    write(Base_Addr, 16, 0x0000a0a0) #sequence64
    #Write data to dpram_dac0 and dpram_dac1
    Base_seq0 = Base_Addr + 0x1000  #Addr_axi_sequencer + addr_dpram
    seqlist = seqlist_dac1*2**16 + seqlist_dac0
    fd = open("/dev/xdma0_user", 'r+b', buffering=0)
    write_to_dev(fd, Base_seq0, 0, seqlist.tolist())
    fd.close()





def Write_To_Fake_Rng(seqlist):
    Base_Addr = 0x00030000
    Base_seq0 = 0x00030000 + 0x2000  #Addr_axil_sequencer +   addr_dpram
    dpram_max_addr = len(seqlist)*8     # memory is for 4 bit values 
    write(Base_Addr, 28, dpram_max_addr) 
    fd = open("/dev/xdma0_user", 'r+b', buffering=0)
    write_to_dev(fd, Base_seq0, 0, seqlist.tolist())
    fd.close()



def Write_Pm_Mode(mode='seq64', feedback='off', insert_zeros='off'):
    Base_Addr = 0x00030000
    if feedback=='off':
        fb = 0
    else:
        fb = 4
    if insert_zeros=='off':
        iz = 0
    else:
        iz = 8
    if mode=='seq64':
        write(Base_Addr, 20, 0)
    elif mode=='fake_rng':
        write(Base_Addr, 20, 2+fb+iz)
    elif mode=='true_rng':
        write(Base_Addr, 20, 3+fb+iz)
    else:
        print("wrong sequence argument")
        exit()
    #Trigger for switching domain
    write(Base_Addr, [12, 12],[0x1, 0x0])
    #update_tmp('pm_mode', mode)

def Write_Pm_Shift(shift, zero_pos):
    Base_Addr = 0x00030000
    lim = 18000
    up_offset = round(0.8*lim)
    shift_hex_up_offset = (up_offset<<16 | zero_pos<<4 | shift)
    division_sp = 1000
    # last two are the trigger for switching domain
    addr = [4, 32, 12, 12]
    value = [shift_hex_up_offset, division_sp, 1, 0]
    write(Base_Addr, addr, value)


def Write_Angles(a0, a1, a2, a3):
    amp_max = 18000
    f = 18000/32768
    Base_Addr = 0x00030000
    amp_list = [a0*f,a1*f,a2*f,a3*f]
    amp_out_list = []
    for amp in amp_list:
        if (amp >= 0):
            amp_hex = round(32767*amp)
        elif (amp < 0):
            amp_hex = 32768+32768+round(32767*amp)
        amp_out_list.append(amp_hex)
    fastdac_amp1_hex = (amp_out_list[1]<<16 | amp_out_list[0])
    fastdac_amp2_hex = (amp_out_list[3]<<16 | amp_out_list[2])
    addr = [8, 24, 12, 12]
    value = [fastdac_amp1_hex, fastdac_amp2_hex, 1, 0]
    #last two are the trigger for switching domain
    write(Base_Addr, addr, value)

def did_reboot():
    # check the first 204b reg
    ret = read(0x10000, 34)
    if ret == 0:
        return True
    else:
        return False

def print_angles():
    # check the first 204b reg
    ret = read(0x30000, [8,24])
    print(ret)

#Read back the FGPA registers configured for JESD
def ReadFPGA():
    file = open(HW_CONFIG+"registers/fda/FastdacFPGAstats.txt","r")
    for l in file.readlines():
        addr, val = l.split(',')
        ad_fpga_addr = (int(addr,base=16) + 0x10000)
        offset = ad_fpga_addr // 0x1000
        a = ad_fpga_addr % 0x1000
        readout = read(offset, a)
        print(readout)
    file.close()

#reset jesd module
def En_reset_jesd():
    with open("/dev/xdma0_user", 'r+b', buffering=0) as fd:
        with mmap.mmap(fd.fileno(), 4096, offset=0x12000) as mm:
            mm[0] = 0x2
            mm[0] = 0x0
    time.sleep(1.2)
    print("Reset FPGA JESD module")

# From Set_reg_powerup to Set_reg_seq2: Set all registers for AD9152 
def Set_reg_powerup():
    file = open(HW_CONFIG+'registers/fda/hop_regs/reg_powerup.txt','r')
    for l in file.readlines():
        addb1, addb2, val = l.split(',')
        addr1 = int(addb1,16)
        addr2 = int(addb2,16)
        val = int(val,16)
        Get_reg_new(2,'fda', addr1, addr2, val)
    time.sleep(0.1)
    print("Set fda power registers finished")
    file.close()

def Set_reg_plls():
    file = open(HW_CONFIG+'registers/fda/hop_regs/reg_plls.txt','r')
    for l in file.readlines():
        addb1, addb2, val = l.split(',')
        addr1 = int(addb1,16)
        addr2 = int(addb2,16)
        val = int(val,16)
        Get_reg_new(2,'fda', addr1, addr2, val)
    time.sleep(0.01)
    print("Set fda serdes_pll registers finished")
    file.close()

def Set_reg_seq1():
    file = open(HW_CONFIG+'registers/fda/hop_regs/reg_seq1.txt','r')
    for l in file.readlines():
        addb1, addb2, val = l.split(',')
        addr1 = int(addb1,16)
        addr2 = int(addb2,16)
        val = int(val,16)
        Get_reg_new(2,'fda', addr1, addr2, val)
    print("Set fda dac_pll, transport and physical1 registers finished")
    file.close()
    
def Set_reg_seq2():
    file = open(HW_CONFIG+'registers/fda/hop_regs/reg_seq2.txt','r')
    for l in file.readlines():
        addb1, addb2, val = l.split(',')
        addr1 = int(addb1,16)
        addr2 = int(addb2,16)
        val = int(val,16)
        Get_reg_new(2,'fda', addr1, addr2, val)
    print("Set fda physical2 and data_link registers finished")
    file.close()

def Relink_Fda():
    file = open(HW_CONFIG+'registers/fda/hop_regs/reg_relink.txt','r')
    for l in file.readlines():
        addb1, addb2, val = l.split(',')
        Get_reg_new(2,'fda', int(addb1), int(addb2), int(val))
    file.close()


def Get_reg_monitor():
    array = []
    file = open(HW_CONFIG+'registers/fda/hop_regs/reg_monitor.txt','r')
    print("Monitoring pll locked, dyn_link_latency, and jesd link ")
    check = []
    print("addb1\taddb2\texp\tret\tcomp")
    for l in file.readlines():
        addb1, addb2, val = l.split(',')
        instr = int(addb1, base=16)|0x80
        addb2 = int(addb2, 16)
        val = int(val, 16)
        ret = Get_reg_new(2,'fda', instr, addb2, 0)[-1]
        check.append(val==ret)
        print(addb1+"\t"+hex(addb2)+"\t"+hex(val)+"\t"+hex(ret)+"\t"+str(check[-1]))
    print("Monitoring finished. If dyn_link_latency != 0x00 then run sda_init again")
    file.close()
    return check

def get_fda_info(verbose=False):
    data = np.loadtxt(HW_CONFIG+'registers/fda/hop_regs/reg_monitor.txt', delimiter=',', converters=lambda s: int(s, 16), dtype=int)
    addb1 = data[:,0]
    addb2 = data[:,1]
    expect = data[:,2]
    l = len(addb1)
    got = np.zeros(l, dtype=int)
    for i in range(l):
        instr = addb1[i] | 0x80
        got[i] = Get_reg_new(2,'fda', instr, addb2[i], 0)[-1]
    if verbose:
        output = np.zeros((l,3), dtype=int)
        output[:,0] = addb1<<8 | addb2
        output[:,1] = expect
        output[:,2] = got
        return output
    else:
        return (got==expect).all()


def Get_Id_Fda():
    val_name = ['chip', 'id1', 'id2', 'rev']
    addr1 = [0x80, 0x80, 0x80, 0x80]
    addr2 = [0x03, 0x04, 0x05, 0x06]
    val_exp = [0x04, 0x52, 0x91, 0x08]
    print("meaning\texp\tret\tcomp")
    for i in range(len(val_name)):
        val_ret = Get_reg_new(2,'fda',addr1[i],addr2[i],0)[-1]
        print(val_name[i]+"\t"+hex(val_exp[i])+"\t"+hex(val_ret)+"\t"+str(val_exp[i]==val_ret))








#-------------------------PULSE GATE APD-------------------------------
#Reset the ttl_gate module
def ttl_reset():
    write(0x12000, [0xc, 0xc], [1, 0])
    time.sleep(0.2)

#Generate the pulse for APD gate
#Input parameter: duty cycle, tune delay, fine delay, increase/decrease fine delay step
#Default: duty = 2, tune = 1, fine = 1000, inc = 1
#fine step 1000 ~1ns
#tune step 1 ~ 4ns
def calculate_delay(duty, tune, fine, inc):
    fine_clock_num = fine*16
    transfer = duty<<19|tune<<15|fine_clock_num<<1|inc
    return transfer

def write_delay_master(duty, tune, fine, inc):
    transfer = calculate_delay(duty, tune, fine, inc)
    write(0x15000, 4, transfer)

def write_delay_slaves(fine1, inc1, fine2, inc2):
    transfer = (fine2*16)<<17|inc2<<16|(fine1*16)<<1|inc1
    write(0x15000, 0xc, transfer)

def params_en():
    write(0x15000, [0x8, 0x8], [0,1])

def trigger_fine_master():
    write(0x15000, [0, 0], [0,1])
    time.sleep(0.02)
    write(0x15000, 0, 0)

def trigger_fine_slv1():
    write(0x15000, [16, 16], [0,1])
    time.sleep(0.02)
    write(0x15000, 16, 0)

def trigger_fine_slv2():
    write(0x15000, [20, 20], [0,1])
    time.sleep(0.02)
    write(0x15000, 20, 0)



#--------------------------decoy state---------------------------------


def decoy_reset():
    write(0x12000, 20, 1)
    time.sleep(0.1)
    write(0x12000, 20, 0)

#input fake rng
def decoy_state(mode):
    #dpram_rng_max_addr
    write(0x16000, 28, 0x10)
    #Write data to rng_dpram
    Base_seq0 = 0x00016000
    true_rng = 0
    print("mode: ", mode)
    if mode=='single':
        rngseq0 = 0x1
        rngseq1 = 0x0
    elif mode=='off':
        rngseq0 = 0x0
        rngseq1 = 0x0
    elif mode=='true_rng':
        rngseq0 = 0x0
        rngseq1 = 0x0
        true_rng = 1
    elif mode=='fake_rng':
        # 0x33333333 = all high
        # 0x11111111 = every second high
        # 0x22222222 = every second high
        rngseq0 = 0x11111111
        rngseq1 = 0x11111111
    else:
        exit("wrong decoy state string")
    write(Base_seq0, [1024,1028], [rngseq0, rngseq1])
    #Write rng mode
    write(0x16000, [12, 0, 0], [true_rng, 0, 1])
    #last two are for enable regs values

#---------decoy delay------------------

def de_calculate_delay(fine, inc):
    fine_clock_num = fine*16
    transfer = fine_clock_num<<1|inc
    return transfer

def de_write_delay_master(tune, fine, inc):
    #Write tune delay
    write(0x16000, 4, tune)
    #Write fine delay master 
    transfer = de_calculate_delay(fine, inc)
    write(0x16000, 20,transfer)

def de_write_delay_slaves(fine1, inc1, fine2, inc2):
    transfer = (fine2*16)<<17|inc2<<16|(fine1*16)<<1|inc1
    write(0x16000, 24, transfer)

def de_params_en():
    write(0x16000, [0, 0], [0,1])

def de_trigger_fine_master():
    write(0x16000, [8, 8], [0,1])
    time.sleep(0.02)
    write(0x16000, 8, 0)

def de_trigger_fine_slv1():
    write(0x16000, [8, 8], [0,2])
    time.sleep(0.02)
    write(0x16000, 8, 0)

def de_trigger_fine_slv2():
    write(0x16000, [8, 8], [0,4])
    time.sleep(0.02)
    write(0x16000, 8, 0)


#-------------------------TDC AND JITTER CLEANER-----------------------

def Set_Si5319():
    reg_file = open(HW_CONFIG+'registers/jit_cleaner/Si5319_regs.txt','r')
    ins_set_addr = 0x00
    ins_write = 0x40
    for l in reg_file.readlines():
        add, val = l.split(',')
        add = int(add, 16)
        val = int(val, 16)
        Get_reg_new(1,'jic', ins_set_addr,add)
        Get_reg_new(1,'jic', ins_write,val)
    print("Set jic configuration registers finished")
    reg_file.close()

def Get_Si5319():
    reg_file = open(HW_CONFIG+'registers/jit_cleaner/Si5319_regs.txt','r')
    ins_set_addr = 0x00
    ins_read = 0x80
    print("Monitoring jic registers")
    print("addr\texp\tret\tmatch")
    for l in reg_file.readlines():
        add, val = l.split(',')
        add = int(add, 16)
        val = int(val, 16)
        Get_reg_new(1,'jic', ins_set_addr,add)
        ret = Get_reg_new(1,'jic', ins_read,0)[-1]
        print(hex(add)+"\t"+hex(val)+"\t"+hex(ret)+"\t"+str(val==ret))
    print("Monitoring finished. It's normal the last reg is F")
    reg_file.close()

def get_jic_info():
    reg_file = open(HW_CONFIG+'registers/jit_cleaner/Si5319_regs.txt','r')
    ins_set_addr = 0x00
    ins_read = 0x80
    check = []
    for l in reg_file.readlines():
        add, val = l.split(',')
        add = int(add, 16)
        val = int(val, 16)
        Get_reg_new(1,'jic', ins_set_addr,add)
        ret = Get_reg_new(1,'jic', ins_read,0)[-1]
        check.append(val==ret)
    reg_file.close()
    # return true if all regs ok
    return np.array(check[:-1]).all()

def Get_Id_Si5319():
    ins_set_addr = 0x00
    ins_read = 0x80
    Get_reg_new(1,'jic', ins_set_addr,0x87)
    ret_val = Get_reg_new(1,'jic',ins_read,0)[-1]
    print("Jitter cleaner Id:",hex(ret_val), "(expected 0x32)")
    
def Config_Jic():
    Set_Si5319()
    Get_Id_Si5319()
    Get_Si5319()

def Set_AS6501():
    reg_file = open(HW_CONFIG+'registers/tdc/AS6501_regs.txt','r')
    #opc_write_config = 0x80
    for l in reg_file.readlines():
        add, val = l.split(',')
        add = int(add, 16)
        val = int(val, 16)
        Get_reg_new(1,'tdc', add, val ) 
    print("Set tdc configuration registers finished")
    reg_file.close()

def Get_AS6501():
    reg_file = open(HW_CONFIG+'registers/tdc/AS6501_regs.txt','r')
    opc_read_config = 0x40
    print("Montoring tdc registers")
    print("addr\texp\tret\tmatch")
    for l in reg_file.readlines():
        add, val = l.split(',')
        add = int(add, 16)
        val = int(val, 16)
        addmod = add & 0x1f | 0x40
        ret = Get_reg_new(1, 'tdc', addmod, 0)[-1]
        print(hex(add)+"\t"+hex(val)+"\t"+hex(ret)+"\t"+str(val==ret))
    print("Monitoring finished")
    reg_file.close()

def get_tdc_info():
    reg_file = open(HW_CONFIG+'registers/tdc/AS6501_regs.txt','r')
    opc_read_config = 0x40
    check = []
    for l in reg_file.readlines():
        add, val = l.split(',')
        add = int(add, 16)
        val = int(val, 16)
        addmod = add & 0x1f | 0x40
        ret = Get_reg_new(1, 'tdc', addmod, 0)[-1]
        check.append(ret==val)
    reg_file.close()
    return np.array(check).all()

def Get_Id_AS6501():
    #opc_power = 0x30
    #opc_read_results = 0x60 #reg 8..31 results and status
    #opc_read_config = 0x40 # reg 0..17 configuration register
    ret1 = Get_reg_new(1,'tdc',0x41,0)[-1]
    ret2 = Get_reg_new(1,'tdc',0x43,0)[-1]
    print("id: ", hex(ret1), "(exp 0x41)", hex(ret2), "(exp 0x10)")
    
def Reg_Mngt_Tdc():
    #lrst active high, reset module process tdc frame and sdi
    #slv_reg[1] pull high to low in clk_rst_mngt
    write(0x12000, [4,4], [2,0])
    BaseAddr = 0x0 # BaseAddr of TDC AXI-Slave
    #Disable TDC module and
    #Write TDC module register and
    #Enable TDC module
    write(BaseAddr, [0, 4, 36, 36, 0], [0, 0x0e04, 0, 1, 1])
    

#def Get_TDC_Data(transferSize, transferCount, output_file):
#    device_c2h = '/dev/xdma0_c2h_2'
#    #Send command_histogram
#    BaseAddr = 0
#    write(BaseAddr, [40, 40], [0, 1])
#    #Read from stream
#    Read_stream(device_c2h, output_file, transferSize, transferCount)

def Get_Stream(base_addr,device_c2h,output_file,count):
    #print(command)
    #Send command to fpga to reset fifo
    offset = (base_addr//0x1000)<<12
    addr = base_addr % 0x1000
    write(offset, [addr, addr], [0, 1])
    #time.sleep(1)
    #Read from stream
    command = HW_CONTROL+"lib/test_tdc/dma_from_device "+"-d "+ device_c2h +" -f "+ output_file+ " -c " + str(count) 
    s = subprocess.check_call(command, shell = True)

def get_arrival_time(device_c2h, count):
    #Send command to fpga to reset fifo
    write(0, [40, 40], [0, 1])
    time = np.zeros(count, dtype=int)
    with open(device_c2h, 'rb') as f:
        for i in range(count):
            data = f.read(16)
            time[i] = int(data[0]) + ((int(data[1]) & 0x3f) << 8)
    return time


def Reset_Tdc():
    write(0x12000, [4, 4],[1,0])
    time.sleep(1.2)
    print("Reset TDC clock")

def Config_Tdc():
    Reg_Mngt_Tdc() #Setting fpga control registers for SM under lclk 
    Reset_Tdc() #Could be before or after Reg_Mngt_Tdc()
    Set_AS6501() #Setting registers of TDC chip
    Get_reg_new(1,'tdc', 0x18) #Start the tdc, setting register of TDC chip
    Get_AS6501() #Reading registers of TDC chip

def Stop_sim(fre_divider,start):
    pulse_stop = start + 13
    stop_pulse_sim = hex(int(pulse_stop<<16 | start<<8 | fre_divider))
    print(stop_pulse_sim)
    #Write Stop_sim limit parameter
    BaseAddr = 0
    write(BaseAddr, [12, 36, 36], [stop_pulse_sim, 0, 4]) #from 10 to 26 period of 5ns 


#---------------------------TDC CALIBRATION-----------------------------------------------
#Set fpga registers for state machine under 200MHz
def Time_Calib_Reg(command,t0, gc_back, gate0, width0, gate1, width1):
    BaseAddr = 0
    addr = [16, 20, 24, 28, 32, 36, 36]
    value = [
            width0<<24 | gate0, 
            width1<<24 | gate1,
            t0,
            gc_back,
            command,
            0,
            2]
    write(BaseAddr, addr, value) #gate0

def Soft_Gate_Filter(state):
    if state=="on":
        command = 2
    elif state=="off":
        command = 1
    else:
        exit("wrong argument to Soft_Gate_Finter()")
    BaseAddr = 0
    write(BaseAddr, [32, 36, 36], [command, 0, 2]) #command = 1: raw | =2: with gate

def Set_t0(t0):
    BaseAddr = 0
    # turn bit[1] to high to enable register setting
    write(BaseAddr, [24, 36, 36], [t0, 0, 2]) #shift tdc time = 0

def Write_Soft_Gates(gate0, width0, gate1, width1):
    BaseAddr = 0
    write(BaseAddr, [16, 20, 36, 36], width0<<24 | gate0, width1<<24 | gate1, 0, 2) #gate0

#-------------------------GLOBAL COUNTER-------------------------------------------
def wait_for_pps_ret():
    # wait for pps return 
    while True:
        pps_ret = read(0x00001000, 48)
        time.sleep(0.05)
        #pps_ret_int = int(pps_ret.decode('utf-8').strip(),16)

        #print(pps_ret_int)
        if (pps_ret == 1):
            break
    return 0

def sync():
    #Start to write 
    write(0x1000, [0, 0], [0, 1]) 

    #Command_enable -> Reset the fifo_gc_out
    write(0x1000, [28, 28], [0, 1])
    
    #Command enable to save alpha
    write(0x1000, [24, 24], [0, 1])


def Reset_gc():
    write(0, 8, 0) #Start_gc = 0
    write(0x12000, [8, 8], [1, 0])
    time.sleep(1.2)
    print("Reset global counter......")

def Start_gc():
    BaseAddr = 0
    write(BaseAddr, [8, 8], [0, 1])
    time.sleep(1.2)
    print("Global counter starts counting up from some pps")

def Sync_Gc():
    write(0, 8, 0) #Start_gc = 0
    write(0x12000, [8, 8], [1, 0])
    write(0, [8, 8], [0, 1])
    time.sleep(1.2)

def get_gc():
    write(0x1000, [4,4], [0,1])
    time.sleep(0.01)
    data = read(0x1000, [60, 64])
    current_gc = (data[1] << 32) | (data[0])
    return current_gc

def Time_Calib_Init():
    Config_Tdc() #Get digital data from TDC chip
    Reset_gc() #Reset global counter
    Start_gc() #Global counter start counting at the next PPS




#----------------- DDR -----------------

# Testing AXIS write and read DDR4 through AXI Virtual FIFO
# threshold define speed of reading gc_in_fifo
# 199999 for 1kHz click rate
def Ddr_Data_Reg(command,current_gc,read_speed, gc_delay, delay_ab = 0):
    fiber_delay = (gc_delay+1)//2
    pair_mode = (gc_delay+1)%2
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
    Write(0x00001000+44,hex(delay_ab))
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


def Ddr_Status():
    ddr_fifos_status = read(0x1000, 52)
    print(ddr_fifos_status)
    fifos_status = read(0x1000, 56)
    #hex_ddr_fifos_status = ddr_fifos_status.decode('utf-8').strip()
    #hex_fifos_status = fifos_status.decode('utf-8').strip()
    vfifo_idle = (ddr_fifos_status & 0x180)>>7
    vfifo_empty = (ddr_fifos_status & 0x60)>>5
    vfifo_full = (ddr_fifos_status & 0x18)>>3
    gc_out_full = (ddr_fifos_status & 0x4)>>2
    gc_in_empty = (ddr_fifos_status & 0x2)>>1
    alpha_out_full = ddr_fifos_status & 0x1

    gc_out_empty = (fifos_status & 0x4)>>2
    gc_in_full = (fifos_status & 0x2)>>1
    alpha_out_empty = fifos_status & 0x1
    #current_time = datetime.datetime.now()
    #print(f"Time: {current_time} VF: {vfifo_full} VE: {vfifo_empty}, VI: {vfifo_idle} | gc_out_f,e: {gc_out_full},{gc_out_empty} | gc_in_f,e: {gc_in_full},{gc_in_empty} | alpha_out_f,e: {alpha_out_full},{alpha_out_empty}", flush=True)
    s = f'VF: {vfifo_full} VE: {vfifo_empty}, VI: {vfifo_idle} | gc_out_f,e: {gc_out_full},{gc_out_empty} | gc_in_f,e: {gc_in_full},{gc_in_empty} | alpha_out_f,e: {alpha_out_full},{alpha_out_empty}'
    #print("Time: {current_time}  VF: {vfifo_full}, VE: {vfifo_empty}, VI: {vfifo_idle} | gc_out_f,e: {gc_out_full}, {gc_out_empty} | gc_in_f,e: {gc_in_full}, {gc_in_empty} | alpha_out_f,e: {alpha_out_full}, {alpha_out_empty}                                                                      " ,end ='\r', flush=True)
    return s

def ddr_status2():
    ddr_fifos_status = read(0x1000, 52)
    fifos_status = read(0x1000, 56)
    vfifo_idle = (ddr_fifos_status & 0x180)>>7
    vfifo_empty = (ddr_fifos_status & 0x60)>>5
    vfifo_full = (ddr_fifos_status & 0x18)>>3
    gc_out_full = (ddr_fifos_status & 0x4)>>2
    gc_in_empty = (ddr_fifos_status & 0x2)>>1
    alpha_out_full = ddr_fifos_status & 0x1

    gc_out_empty = (fifos_status & 0x4)>>2
    gc_in_full = (fifos_status & 0x2)>>1
    alpha_out_empty = fifos_status & 0x1
    return vfifo_full, gc_out_full, gc_in_full, alpha_out_full



def Angle(num, save=False):
    fs = open('/dev/xdma0_c2h_3', 'rb')

    angles = []
    # stream word is 128bit==64angles
    for i in range(num//64):
        print(i)
        data = fs.read(16)
        if not data:
            print("No available data on stream")
            break
        for b in data:
            v = int(b)
            angles.extend([
                v&0b11, 
                (v&0b1100)>>2, 
                (v&0b110000)>>4, 
                (v&0b11000000)>>6])
            
    fs.close()
    if save:
        np.savetxt('data/ddr4/alpha.txt', np.array(angles), fmt="%d")
        print("angles saved in data/ddr4/alpha.txt")

    return np.array(angles)
































