#!/bin/python
import numpy as np, matplotlib.pyplot as plt


gc0 = np.loadtxt('gc.txt', dtype=np.int64) - 34
angles = np.loadtxt('angles.txt', dtype=np.int64)

l = min(len(gc0), len(angles)) - 1000

print(len(gc0), len(angles))

offset = []
value = []

for offset_gc in range(0, 512, 1):
    offset.append(offset_gc)
    offset_angles = 256

    gc = gc0[offset_gc:l+offset_gc]
    #r = angles[:l,2]
    #aa = angles[offset_angles:l+offset_angles,0]
    ab = angles[offset_angles:l+offset_angles,1]
    
    #gcr0 = gc[r==0]%(80*400)
    #gcr1 = gc[r==1]%(80*400)

    #gcaa0 = gc[aa==0]%(80*400) 
    #gcaa1 = gc[aa==1]%(80*400)

    gcab0 = gc[ab==0]%(80*400) 
    gcab1 = gc[ab==1]%(80*400)

    bins= np.arange(0, 80*401, 80)
    
    #hr0, b = np.histogram(gcr0, bins=bins)
    #hr1, b = np.histogram(gcr1, bins=bins)
    #haa0, b = np.histogram(gcaa0, bins=bins)
    #haa1, b = np.histogram(gcaa1, bins=bins)
    hab0, b = np.histogram(gcab0, bins=bins)
    hab1, b = np.histogram(gcab1, bins=bins)

    value.append(hab1[0])

    print(offset_gc, hab1[0])

    #plt.plot(b[:-1], hr0, label="gcr0")
    #plt.plot(b[:-1], hr1, label="gcr1")
    #plt.plot(b[:-1], hab0, label=offset_gc)
    #plt.plot(b[:-1], hab1, label=offset_gc)

#plt.plot(bq[:-1], hq0, "o", label="ar0")
#plt.plot(bq[:-1], hq1, "x", label="ar1")
#plt.plot(bq[:-1], h, "s", label="a")

plt.plot(offset, value)

#plt.ylim(0)
#plt.legend()
#plt.title("bob")
#
#
plt.show()




