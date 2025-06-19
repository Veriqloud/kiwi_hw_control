# always two bytes: opcode + addr and data

# opcodes
opc_power = 0x30        # power on reset
opc_init = 0x18         # initialize chip and start measurement
opc_write_config = 0x80 # address on the lowest bits
opc_read_config = 0x40
opc_read_result = 0x60


PIN_ENA_STOPA = 1
PIN_ENA_STOPB = 1
PIN_ENA_REFCLK = 1
PIN_ENA_LVDS_OUT = 1
PIN_ENA_RSTIDX = 1

cfg0 = PIN_ENA_STOPA + (PIN_ENA_STOPB<<2) +  (PIN_ENA_REFCLK<<4) + (PIN_ENA_LVDS_OUT<<5) + (PIN_ENA_RSTIDX<<7)

HIT_ENA_STOPA = 1 #switch channel on/off
HIT_ENA_STOPB = 0
CHANNEL_COMBINE = 0
HIGH_RESOLUTION = 1 #FIFO DEPTH is 16,8 or 4 ~ resolution off,2x or 4x

cfg1 =  HIT_ENA_STOPA + (HIT_ENA_STOPB<<2) + (CHANNEL_COMBINE<<4) + (HIGH_RESOLUTION<<6)

REF_INDEX_BITWIDTH = 0b010  # 0b111=12bit 0b100=16bit 0b101=24bit 0b010=4bit
STOP_DATA_BITWIDTH = 0b0   # 0b01=16bit=3ps@5MHzrefclk; 0b10=18bit 0b11=20bit 0b0=14bit
LVDS_DOUBLE_DATA_RATE = 0
COMMON_FIFO_READ = 0 #Both channels are independent
BLOCKWISE_FIFO_READ = 0 #Operate with standard fifo function

cfg2 = REF_INDEX_BITWIDTH + (STOP_DATA_BITWIDTH<<3) + (LVDS_DOUBLE_DATA_RATE<<5) + (COMMON_FIFO_READ<<6) + (BLOCKWISE_FIFO_READ<<7)

REFCLK_DIVISIONS = 10000   # 200000=1ps; 10000=20ps; @ 5MHz refclk

cfg3 = REFCLK_DIVISIONS & 0xff
cfg4 = (REFCLK_DIVISIONS>>8) & 0xff
cfg5 = (REFCLK_DIVISIONS>>16) & 0x0f

LVDS_TEST_PATTERN = 0   # LVDS outputs test pattern ref=15781034 res=699632

cfg6 = (0b110<<5) + (LVDS_TEST_PATTERN<<4)

LVDS_DATA_VALID_ADJUST = 1  # 0=-160ps 1=0ps 2=160ps 3=320ps

cfg7 = (1<<6) + (LVDS_DATA_VALID_ADJUST<<4) + (0b11)

# fixed values for reg 8..15
cfg8 =  0b10100001
cfg9 =  0b00010011
cfg10 = 0b0
cfg11 = 0b1010
cfg12 = 0b11001100
cfg13 = 0b11001100
cfg14 = 0b11110001
cfg15 = 0b01111101

CMOS_INPUT = 0  # LVDS voltage levels

cfg16 = CMOS_INPUT<<2


reg = [
        (0x00, cfg0),
        (0x01, cfg1),
        (0x02, cfg2),
        (0x03, cfg3),
        (0x04, cfg4),
        (0x05, cfg5),
        (0x06, cfg6),
        (0x07, cfg7),
        (0x08, cfg8),
        (0x09, cfg9),
        (0x0a, cfg10),
        (0x0b, cfg11),
        (0x0c, cfg12),
        (0x0d, cfg13),
        (0x0e, cfg14),
        (0x0f, cfg15),
        (0x10, cfg16),
        ]


f = open("AS6501_regs.txt","w")
f.write(format(0x30,'#04x') + ",") #power reset
f.write(format(0x00,'#04x')+"\n")
for e in reg:                      #config regs
    s = format(((0x80 + e[0])&0xFF),'#04x')
    f.write(str(s)+",")
    s = format(e[1],'#04x')
    f.write(str(s)+"\n")
#f.write(format(0x18,'#04x')+ ",") #Start measurement, reset but keep config regs
#f.write(format(0x00,'#04x')+"\n")
f.close()

# write full sequence to file
#f = open("reg_init.txt", "w")

# reset
#f.write(str(0x3000)+"\n")

# config
#for e in reg:
#    s = ((0x80 + e[0]) << 8) + e[1]
#    f.write(str(s)+"\n")
    
# start measurement. careful
#f.write(str(0x1800)+"\n")

#f.close()
