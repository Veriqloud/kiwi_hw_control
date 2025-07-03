import numpy as np
# registers value from butterstick project
reg = [
    (  0,0x14),  
    (  2,0x72), 
    (  3,0x15), 
    (  5,0xED), 
    (  6,0x2F), 
    (  8,0x00), 
    ( 10,0x00), 
    ( 11,0x40), 
    ( 19,0x2C), 
    ( 20,0x3E), 
    ( 22,0xDF), 
    ( 23,0x1F), 
    ( 24,0x3F), 
    ( 25,0x20), 
    ( 31,0x00), 
    ( 32,0x00), 
    ( 33,0xC1), 
    ( 40,0x20), 
    ( 41,0x02), 
    ( 42,0x45), 
    ( 43,0x00), 
    ( 44,0x00), 
    ( 45,0x02), 
    ( 46,0x00), 
    ( 47,0x00), 
    ( 48,0x02), 
    (131,0x1F), 
    (132,0x02), 
    (138,0x0F), 
    (139,0xFF), 
    (136,0x40), 
    ]
f = open("Si5319_regs.txt","w")
for e in reg: 
    s = format((e[0]&0xFF),'#04x')
    f.write(str(s)+",")
    s = format(e[1],'#04x')
    f.write(str(s)+"\n")
f.close()
