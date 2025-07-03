
# The values are taken from spi_ad9152_gh_mode4.c

# For reading need to add 0x0800 to the address. 



power_up = [
        (0x000, 0xBD),   #Soft reset
        (0x000,0x3C), #Deassert reset, set 4-wire SPI.
        ]
# needs 4ms sleep after power_up


power_up2 = [
        (0x011, 0x00), # power up DACs, CLKs
        (0x080,0x04),   # Disable dutycycle correction
        (0x081,0x04),  # Power up the SYSREF± receiver, disable hysteresis
        (0x1CD,0xD8),  # Band gap configuration.
        ]

serdes_pll = [
        (0x284,0x62), #default 
        (0x285,0xC9), #default
        (0x286,0xE),  #default
        (0x287,0x12), #default
        (0x28A,0x2B),  # SERDES PLL x, Table 36, SERDESPLL VCO >7.15GHz
        #(0x28A,0x7B),
        (0x28B,0x0),  
        (0x290,0x89), 
        (0x291,0x4c),  # SERDES PLL x
        #(0x291,0x49),  # SERDES PLL x
        (0x294,0x24), 
        (0x296,0x03),  # SERDES PLL x
        #(0x296,0x02),  # SERDES PLL x
        (0x297,0xD),  
        (0x299,0x2),  
        (0x29A,0x8E), 
        (0x29C,0x2A), 
        (0x29F,0x7E), 
        (0x2A0,0x6),  
        ]
    
dac_pll = [
        (0x08D,0x7B),
        (0x1B0,0x0), 
        (0x1B9,0x24),
        (0x1BC,0xD), 
        (0x1BE,0x2), 
        (0x1BF,0x8E),
        (0x1C0,0x2A),
        (0x1C4,0x7E),
        (0x1C1,0x2C),
        ]
    
dac_pll_optional = [
        (0x08B,0x01), #LOdivMode
        (0x08C,0x02), #RefDivMode
        (0x085,0x10), #Bcount
        (0x1B6,0x49), #LookupVals, Table 73 DAC VCO < 6.84GHz
        (0x1B5,0xC7), #Table 73
        (0x1BB,0x1a), #Table 73
        (0x1B4,0x78), #Optimal DAC PLL VCO settings
        (0x1C5,0x08), #Table 73
        (0x08A,0x12), #Optimal DAC PLL VCO settings
        (0x087,0x62), #Optimal DAC PLL VCO settings
        (0x088,0xC9), #Optimal DAC PLL VCO settings
        (0x089,0x0E), #Optimal DAC PLL VCO settings
        (0x083,0x10), #Enable DAC PLL
        ]
# sleep 10ms after that
    


digital_data_path = [
        #(0x112, 0x02),           #Interpolation mode, only mode 9 & 10, QDAC down
        (0x112, 0x01), #no interpolation in mode 4
        (0x111, 0xb0), # enable inverse sinc function and digitall gain bit 5, phase adjust bit 4
        (0x047, 0x00),  # coarse delay adjust 
        (0x11C,0x00), # phase adjust
        (0x11D,0x00), # phase adjust
        (0x110, 0x80),  # bit 7: DataFmt 0 = two compliment , 1 = offset binary
        #inv sinc function introduces loss 6.8dB, need to compensate by enable digital gain
        (0x13C,0xff),# gaincode of IDAC[7:0]
        (0x13D,0x0f),#gaincode of IDAC[11:8]
        (0x13E,0xff),# gaincode of QDAC[7:0] 
        (0x13F,0x0f),#gaincode of QDAC[11:8]
        #Offset compensate
        #(0x135,0x00), #Enable dc offset
        #(0x136,0xff),
        #(0x137,0x0f),
        #(0x13A,0x08),
        ]

val_450 = 0x1f
val_451 = 0x07
val_452 = 0x00
val_453 = 0x03
val_454 = 0x00
val_455 = 0x1F
val_456 = 0x01
val_457 = 0x0F
val_458 = 0x2F
val_459 = 0x20
val_45a = 0x80
#val_sum = val_450 + val_451 + val_452 + val_453 + val_454 + val_455 + val_456 + val_457 + val_458 + val_459 + val_45a
#print("checksum: ", hex(val_sum & 0xff))

BID = 7
CF = 0
CS = 0
DID = 31
F= 0
HD = 1
JESDV = 1
K = 31
L = 3
LID = 0
M = 1
N = 15
NP = 15
PHADJ = 0
S = 0
SCR = 0
SUBCLASSV = 1
val_sum = BID + CF + CS + DID + F + HD + JESDV + K + L + LID + M + N + NP + PHADJ + S + SCR + SUBCLASSV
print("checksum: ", hex(val_sum & 0xff))

transport_layer = [
        (0x200,0x00), #Power up the interface
        (0x201,0x00), #Unused lane, mode 4 uses 4 lanes
        (0x300,0x00), #CheckSumMode (attention: gets overwritten later)
    
        (0x450, val_450), #DID
        (0x451, val_451), #BID
        (0x452, val_452), #LID
        (0x453, val_453), #Scrambling 0 + L − 1
        (0x454, val_454), #F
        (0x455, val_455), #K
        (0x456, val_456), #M: coverter per link
        (0x457, val_457), #N
        (0x458, val_458), #Subclass 0 +Np
        (0x459, val_459), #JESDVer + S
        (0x45A, val_45a), #HD + CF
    
        (0x45D, val_sum & 0xff), # Lane0checksum
        (0x46C,0x0F), # Deskew lanes
        (0x476,0x01), # F
        (0x47D,0x0F), # Enable lanes. 
        ]

physical_layer1 = [
        (0x2A7, 0x01), # Autotune PHY setting
        (0x314, 0x01), # SERDES SPI configuration
        #(0x230, 0x09), # Set up the CDR
        (0x230,0x29), # lane rate is 8Gb/s
        (0x206, 0x00), # Reset the CDR

    ]
# sleep 1ms after physical_layer1

physical_layer2 = [
        (0x206, 0x01), # Release CDR reset
        #(0x289, 0x05), # SERDES PLL DIV MODE + 4. 
        (0x289,0x04),
        (0x280, 0x01), # Enable the SERDES PLL.2
        (0x268, 0x62), # See the Equalization Mode
        ]
# sleep 20ms after physical_layer2


data_link_layer = [
        (0x301,0x01), #subclass 1
        #(0x304,0x01), #Set the LMFC delay setting LMFCDel 
        (0x304,0x00), #Set the LMFC delay setting LMFCDel 
        (0x306,0x00), #LMFCVar 
        (0x03A,0x02), #Set sync mode = continuous sync
        (0x03A,0x82), #Enable the sync machine.
        #(0x03A,0xC2), #Arm the sync machine.
        (0x03A,0xC2), #Arm the sync machine.
        (0x034,0x00), #Sync error window tolerance.
        (0x308,0x08), #XBarVals lane0,1 receive from serdes0,1
        (0x309,0x1A), #XBarVals lane2,3 receive from serdes2,3
        #(0x308,0x00), #XBarVals lane0,1 receive from serdes0,1
        #(0x309,0x09), #XBarVals lane2,3 receive from serdes2,3
        (0x334,0x00), #InvLanes
        #(0x300,0x41), #Bit 0 = 1 to enable Link 0.
        (0x300,0x01), #Check sum mode = 0, calculate by link config register sum
        #(0x0E7,0x30), #tunr off cal clock 
        ]

relink = [
        (0x300, 0x00), # disable link
        (0x300, 0x01), # enable link
        ]
#Readback monitoring registers and compare expected value
monitoring = [
        #(0x005, 0x91), # byte 1 device id
        #(0x08D,0x7B),
        #(0x004, 0x52), # byte 2 device id
        (0x084, 0x2a), # (result & 0x02) gives PLL locked
        (0x281, 0x0b), # (result & 0x01) gives SERDES PLL locked
        #(0x03A, 0x00), # bit 6 should be 1
        #(0x03B, 0x00),   # bit 3 should read back 1 to indicate the LMFC sync locked
        #(0x03C, 0x00), #last phase error
        #(0x03D, 0x00), # error flags
        #(0x038, 0x00),
        #(0x039, 0x00),
        (0x302, 0x00), #DYN_LINK_LATENCY_0. should be 0x00 for determinsitic latency setting
        #(0x402, 0x00), #Lane 0 identification, must be 0
        (0x470, 0x0f), #check CGS 
        (0x471, 0x0f), #frame sync
        (0x472, 0x0f), #good check sum
        (0x473, 0x0f), #ILAS
        #(0x040, 0x00), #From 0x040 to 0x043: gain code for IDAC and QDAC
        #(0x041, 0x00),
        #(0x042, 0x00),
        #(0x043, 0x00),
        ]
# the last four should read back 0x0f

# there is more monitoring that we omit here


#f = open("reg_powerup.txt", "w")
f = open("reg_powerup.txt", "w")
for e in power_up + power_up2:
    #s = (e[0]<<8) + e[1]
    #f.write(str(s)+"\n")
    s = format(((e[0]>>8)&0xFF),'#04x')
    f.write(str(s)+",")
    s = format((e[0]&0xFF),'#04x')
    f.write(str(s)+",")
    s = format(e[1],'#04x')
    f.write(str(s)+"\n")
f.close()

f = open("reg_plls.txt", "w")
#f = open("Fastdacserdespll.txt", "w")
for e in serdes_pll:
    #s = (e[0]<<8) + e[1]
    #f.write(str(s)+"\n")
    s = format(((e[0]>>8)&0xFF),'#04x')
    f.write(str(s)+",")
    s = format((e[0]&0xFF),'#04x')
    f.write(str(s)+",")
    s = format(e[1],'#04x')
    f.write(str(s)+"\n")
f.close()

f = open("reg_seq1.txt", "w")
for e in dac_pll + dac_pll_optional + digital_data_path + transport_layer + physical_layer1:
    #s = (e[0]<<8) + e[1]
    #f.write(str(s)+"\n")
    s = format(((e[0]>>8)&0xFF),'#04x')
    f.write(str(s)+",")
    s = format((e[0]&0xFF),'#04x')
    f.write(str(s)+",")
    s = format(e[1],'#04x')
    f.write(str(s)+"\n")
f.close()

f = open("reg_seq2.txt", "w")
for e in physical_layer2 + data_link_layer:
    #s = (e[0]<<8) + e[1]
    #f.write(str(s)+"\n")
    s = format(((e[0]>>8)&0xFF),'#04x')
    f.write(str(s)+",")
    s = format((e[0]&0xFF),'#04x')
    f.write(str(s)+",")
    s = format(e[1],'#04x')
    f.write(str(s)+"\n")
f.close()

f = open("reg_monitor.txt", "w")
for e in monitoring:
    #s = (e[0]<<8) + e[1]
    #f.write(str(s)+"\n")
    s = format(((e[0]>>8)&0xFF),'#04x')
    f.write(str(s)+",")
    s = format((e[0]&0xFF),'#04x')
    f.write(str(s)+",")
    s = format(e[1],'#04x')
    f.write(str(s)+"\n")
f.close()

f = open("reg_relink.txt", "w")
for e in relink:
   # s = (e[0]<<8) + e[1]
   # f.write(str(s)+"\n")
    s = format(((e[0]>>8)&0xFF),'#04x')
    f.write(str(s)+",")
    s = format((e[0]&0xFF),'#04x')
    f.write(str(s)+",")
    s = format(e[1],'#04x')
    f.write(str(s)+"\n")
f.close()

