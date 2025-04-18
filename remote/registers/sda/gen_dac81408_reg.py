#no-operation
cfg0 = 0x0000    

#SPI config
TEMPALM_EN = 1 
DACBUSY_EN = 0       
CRCALM_EN = 1
RESERVED = 1
SOFTTOGGLE_EN = 0    #0 = not use toggle operation
DEV_PWDWN = 0        #0 = device in active mode
CRC_EN = 0
STR_EN = 0
SDO_EN = 1           #1 = SDO is in operation
FSDO = 1             #0 = SDO updates during posedge of clock
cfg3 = (TEMPALM_EN<<11)+(DACBUSY_EN<<10)+(CRCALM_EN<<9)+(RESERVED<<7)+(SOFTTOGGLE_EN<<6)+(DEV_PWDWN<<5)+(CRC_EN<<4)+(STR_EN<<3)+(SDO_EN<<2)+(FSDO<<1)

#genconfig
REF_PWDWN = 0   #activate internal reference, 1 = powerdown internal reference
cfg4 = 0x3F00   #DAC is not in diff operation

#Brdconfig
cfg5 = 0xFFFF   #defaut value, not using broadcast operation

#syncconfig
cfg6 = 0x0000   #device in async mode (update register immediately)
                #0x0FF0: all 8 channles in sync mode

#toggconfig0
cfg7 = 0x0000   #disable toggle mode, dac 7 to 4

#toggconfig1
cfg8 = 0x0000   #disable toggle mode, dac 3 to 0

#dacpwdwn
cfg9 = 0xF00F   #in active mode, when 0xFFFF, all 8 channels are in powerdown mode

#dacrange
cfg11 = 0x1a0a  #DAC[7:4] range. Set  channel 6 range -10V to 10V, channel 7 and channel 4 range 0-10V. The rest is 0-5V
cfg12 = 0x0000  #DAC[3:0] range. Set all cahnnels range 0-5V. Check datasheet page 42

#trigger
cfg15 = 0x0000  # defaut value, set trigger event for toggle operation/sync mode,
                #0x000A if want to reset device, soft reset

#brdcast
cfg16 = 0x0000  #not use broadcast operation


#data registers
cfg20 = 0xFFFF 
cfg21 = 0xFFFF
cfg22 = 0xFFFF
cfg23 = 0xFFFF
cfg24 = 0xFFFF
cfg25 = 0xFFFF
cfg26 = 0xFFFF
cfg27 = 0x0000

#offset registers
cfg33 = 0x0000
cfg34 = 0x0000


reg_config = [
		(0,cfg0),
		(3,cfg3),
		(4,cfg4),
		(5,cfg5),
		(6,cfg6),
		(7,cfg7),
		(8,cfg8),
		(9,cfg9),
		(11,cfg11),
		(12,cfg12),
		(15,cfg15),
		(16,cfg16),
		(33,cfg33),
		(34,cfg34),
		]

reg_data = [
		(20,cfg20),
		(21,cfg21),
		(22,cfg22),
		(23,cfg23),
		(24,cfg24),
		(25,cfg25),
		(26,cfg26),
		(27,cfg27),
		]
f = open("Dac81408_setting.txt","w")
for e in reg_config:
    #f.write(str(hex(e[0]))+","+str(hex(e[1]))+"\n")
    #print(str(hex(e[0]))+","+str(hex(e[1]))+"\n")
    s = format(e[0],'#04x')
    f.write(str(s)+",")
    s = format(((e[1]>>8)&0xFF),'#04x')
    f.write(str(s)+",")
    s = format((e[1]&0xFF),'#04x')
    f.write(str(s)+"\n")
f.close()
f = open("Dac81408_data.txt","w")
for e in reg_data:
    #f.write(str(hex(e[0]))+","+str(hex(e[1]))+"\n")
    #print(str(hex(e[0]))+","+str(hex(e[1]))+"\n")
    s = format(e[0],'#04x')
    f.write(str(s)+",")
    s = format(((e[1]>>8)&0xFF),'#04x')
    f.write(str(s)+",")
    s = format((e[1]&0xFF),'#04x')
    f.write(str(s)+"\n")
f.close()
