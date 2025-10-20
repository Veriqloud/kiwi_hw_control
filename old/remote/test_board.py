import main
import time
import numpy as np
import subprocess

#-----TEST CONDITIONS--------------------------------
#
# - Simulate click rate: 10kHz, position of click reference to TDC refclk is fix
# - Using DDR loop, gc is feedback to the same device
# - Using 0 delay (as no fiber)
# - Feedback 4096 gc and read same number of angles 

DPRAM_MAX_ADDR = 8
CLICK_FRE_DIV = 25 #fre_divider = 25 -> STOP pulse rate 10kHz
CLICK_POS_REF = 20
WORD_COUNT_GC = 4096
WORD_COUNT_ANGLE = 128 # = 4096/32


def Write_Sequence_Rng(FDA_RNG_DPRAM):
    print("Write test rng to dpram")
    Base_Addr = 0x00030000
    Base_seq0 = 0x00030000 + 0x2000  #Addr_axil_sequencer +   addr_dpram
    dpram_max_addr = DPRAM_MAX_ADDR
    main.Write(Base_Addr + 28, hex(dpram_max_addr))
    #list_rng_zero = gen_seq.seq_rng_zero(dpram_max_addr)
    list_rng_zero = FDA_RNG_DPRAM
    vals = []
    for l in list_rng_zero:
        vals.append(int(l, 0))
    fd = open("/dev/xdma0_user", 'r+b', buffering=0)
    main.write_to_dev(fd, Base_seq0, 0, vals)
    fd.close()

def Test_Decoy(DECOY_RNG_DPRAM):
    print("Write test rng to decoy dpram")
    #dpram_rng_max_addr
    main.Write(0x00016000 + 28, DPRAM_MAX_ADDR)
    #Write data to rng_dpram
    Base_seq0 = 0x00016000 + 1024
    #rngseq0 = 0x22222222
    rngseq0 = DECOY_RNG_DPRAM
    #rngseq1 = 0x22222222
    main.Write(Base_seq0, rngseq0)
    #main.Write(Base_seq0+4, rngseq1)
    #Write rng mode
    main.Write(0x00016000 + 12, 0x0)
    #enable regs values
    main.Write(0x00016000 , 0x0)
    main.Write(0x00016000 , 0x1)

def ddr_sequence():
    # Reset alpha fifo
    #main.Ddr_Data_Reg(command,current_gc,read_speed, fiber_delay, pair_mode, de_fiber_delay, de_pair_mode, ab_fiber_delay):
    print("Start ddr control sequence")
    main.Ddr_Data_Reg(4,0,100,0,1,0,1,0)
    # Setting ddr4 registers
    main.Ddr_Data_Reg(3,0,100,0,1,0,1,0)
    # Init ddr4
    main.Ddr_Data_Init()
    # Capture PPS
    while True:
        pps_ret = main.Read(0x00001000+48)
        pps_ret_int = np.int64(int(pps_ret.decode('utf-8').strip(),16))

        #print(pps_ret_int)
        if (pps_ret_int == 1):
            break
    time.sleep(0.02) #delay should be more than 10ms
    # Start to write 
    main.Write(0x00001000, 0x00)
    main.Write(0x00001000, 0x01)
    # time.sleep(1)
    # current_gc = main.Get_Current_Gc()
    # print('Bob current_gc: ',current_gc)
    # Command_enable -> Reset the fifo_gc_out
    main.Write(0x00001000+28,0x0)
    main.Write(0x00001000+28,0x1)
    # Command enable to save alpha
    main.Write(0x00001000+24,0x0)
    main.Write(0x00001000+24,0x1)
    # Declare devices
    data_gc = b'' #declare bytes object
    device_c2h = '/dev/xdma0_c2h_1'
    device_h2c = '/dev/xdma0_h2c_0'
    try:
        with open(device_c2h, 'rb') as f:
            with open(device_h2c, 'wb') as fw:
                #while True:
                for i in range(WORD_COUNT_GC):
                    data_gc = f.read(16)
                    #print(data_gc,flush=True)
                    if not data_gc:
                        print("No available data on stream")
                        break
                    #Write back to h2c device of Bob
                    bytes_written = fw.write(data_gc)
                    fw.flush()

    except FileNotFoundError:
        print(f"Device not found")
    except PermissionError:
        print(f"Permission to file is denied")
    except Exception as e:
        print(f"Error occurres: {e}")

def Angle():
    #Readback 
    print("Read angle from fifo")
    device_c2h = '/dev/xdma0_c2h_3'
    output_file = 'data/ddr4/alpha.bin'
    size = 16
    count = WORD_COUNT_ANGLE 
    for i in range(1):
    #while True:
    #    Read_stream(device_c2h,output_file,size,count)
        command ="test_tdc/dma_from_device "+"-d "+ device_c2h +" -f "+ output_file+ " -c " + str(count) 
        s = subprocess.check_call(command, shell = True)
        time.sleep(1)

    with open(output_file,'rb') as f:
        angle_print = f.read(16)
        angle_hex = [int(b) for b in format(int.from_bytes(angle_print, 'little'), '04x')]  
    print("Angle's sublist", angle_hex[:4])
    f.close()
    return angle_hex[0]

def test1():
    #Clock chip
    print("TEST1----------------------START CLOCKCHIP,SDA,FDA TEST-------------")
    print("*")
    main.Config_Ltc()
    main.Sync_Ltc()
    print("--------------------------------------------------------------------")
    print("*")
    #SDA
    main.Config_Sda()
    print("--------------------------------------------------------------------")
    print("*")
    print("Set voltage for output channels")
    for i in range(8):
        main.Set_vol(i,0)
        time.sleep(0.1)
        main.Set_vol(i,1)
    #main.Set_vol(channel,val)
    print("--------------------------------------------------------------------")
    print("*")
    #FDA
    main.Write_Sequence_Dacs('dp')
    FDA_RNG_DPRAM = ['0x00000000']
    Write_Sequence_Rng(FDA_RNG_DPRAM)
    main.Write_Dac1_Shift(2, 1, 1, 1, 1, 0)
    main.Config_Fda()

def test2():
    print("TEST2----------------------------START TTL GATE TEST----------------")
    print("*")
    main.ttl_reset()
    #main.write_delay_master(duty,tune,fine,inc)
    #main.write_delay_slaves(fine1,inc1, fine2, inc2)
    main.write_delay_master(2,0,100,1)
    main.write_delay_slaves(100,1,100,1)
    main.params_en()
    time.sleep(2)
    for i in range(4):
        main.trigger_fine_master()
        time.sleep(1)
    for i in range(4):
        main.trigger_fine_slv1()
        time.sleep(1)
    for i in range(4):
        main.trigger_fine_slv2()
        time.sleep(1)
    time.sleep(2)
    main.ttl_reset()
    
def test3():
    print("----------------------------START DECOY SIGNAL TEST-----------------")
    print("*")
    main.decoy_reset()
    DECOY_RNG_DPRAM = 0x22222222
    Test_Decoy(DECOY_RNG_DPRAM)
    #main.de_write_delay_master(tune,fine,inc)
    #main.de_write_delay_slaves(fine1,inc1, fine2, inc2)
    main.de_write_delay_master(0,100,1)
    main.de_write_delay_slaves(100,1,100,1)
    main.de_params_en()
    for i in range(4):
        main.de_trigger_fine_master()
        time.sleep(1)
    for i in range(4):
        main.de_trigger_fine_slv1()
        time.sleep(1)
    for i in range(4):
        main.de_trigger_fine_slv2()
        time.sleep(1)
    time.sleep(2)
    main.decoy_reset()

def test4():
    print("----------------------------START JIT CLEANER & TDC TEST------------")
    print("*")
    main.Config_Jic()
    print("--------------------------------------------------------------------")
    print("*")
    #main.Stop_sim(fre_divider,pulse_start)
    print("Generate simulates STOPA signal for TDC")
    main.Stop_sim(CLICK_FRE_DIV,CLICK_POS_REF) 
    print("--------------------------------------------------------------------")
    print("*")
    main.Time_Calib_Reg(1, 0, 0, 0, 625, 0, 625)
    main.Time_Calib_Init()
    print("--------------------------------------------------------------------")
    print("*")
    return_count = main.Count_Sta()

def test5():
    print("----------------------------START DDR TEST--------------------------")
    print("*")
    FDA_RNG_DPRAM_ARR =[['0xffffffff'],['0xaaaaaaaa'],['0x55555555'],['0x00000000']]
    DECOY_RNG_DPRAM_ARR = [0x00000000, 0x11111111, 0x22222222, 0x33333333]
    angle_matrix = []
    for i in range(4):
        row = []
        for j in range(4):
            Write_Sequence_Rng(FDA_RNG_DPRAM_ARR[i])
            Test_Decoy(DECOY_RNG_DPRAM_ARR[j])
            ddr_sequence()
            return_angle = Angle()
            row.append(return_angle)
            print("--------------------------------------------------------------------")
            print("*")
        angle_matrix.append(row)
    print("Angle matrix", angle_matrix)
    Exp_matrix = [[3, 3, 7, 7], [2, 2, 6, 6], [1, 1, 5, 5], [0, 0, 4, 4]]
    print("Expect Angle matrix", Exp_matrix)

def test6():
    FDA_RNG_DPRAM_ARR =['0x00c00000']
    DECOY_RNG_DPRAM_ARR = 0x00000000
    Write_Sequence_Rng(FDA_RNG_DPRAM_ARR)
    Test_Decoy(DECOY_RNG_DPRAM_ARR)
    ddr_sequence()
    return_angle = Angle()
    print(return_angle)

test1()
test2()
test3()
test4()
test5()
#test6()
