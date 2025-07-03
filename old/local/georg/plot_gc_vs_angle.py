#!/bin/python
import numpy as np, matplotlib.pyplot as plt


gc = np.loadtxt('gc.txt', dtype=np.int64)
angles = np.loadtxt('angles.txt', dtype=np.int64)

l = min(len(gc), len(angles))

print(l)

gc = gc[:l]
r = angles[:l,2]
aa = angles[:l,0]
ab = angles[:l,1]
    
gcr0 = gc[r==0]%80 
gcr1 = gc[r==1]%80

gcaa0 = gc[aa==0]%80 
gcaa1 = gc[aa==1]%80

gcab0 = gc[ab==0]%80 
gcab1 = gc[ab==1]%80

#ar0 = a[r==0]
#ar1 = a[r==1]


bins= np.arange(81)
binsa = np.arange(5)
    
hr0, b = np.histogram(gcr0, bins=bins)
hr1, b = np.histogram(gcr1, bins=bins)
haa0, b = np.histogram(gcaa0, bins=bins)
haa1, b = np.histogram(gcaa1, bins=bins)
hab0, b = np.histogram(gcab0, bins=bins)
hab1, b = np.histogram(gcab1, bins=bins)

#hq0, bq = np.histogram(ar0, bins=binsa)
#hq1, bq = np.histogram(ar1, bins=binsa)
#h, bq = np.histogram(a, bins=binsa)

plt.plot(b[:-1], hr0, label="gcr0")
plt.plot(b[:-1], hr1, label="gcr1")
plt.plot(b[:-1], hab0, label="gcab0")
plt.plot(b[:-1], hab1, label="gcab1")

#plt.plot(bq[:-1], hq0, "o", label="ar0")
#plt.plot(bq[:-1], hq1, "x", label="ar1")
#plt.plot(bq[:-1], h, "s", label="a")


plt.ylim(0)
plt.legend()
plt.title("bob")


plt.show()




