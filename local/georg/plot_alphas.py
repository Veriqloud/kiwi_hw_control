#!/bin/python
import numpy as np, matplotlib.pyplot as plt

l = 32000

gcr = np.loadtxt('gcr.txt', dtype=np.int64)
alpha = np.loadtxt('alpha.txt', dtype=np.int64)

print(l, len(gcr), len(alpha))

gc = gcr[:l,0]
r = gcr[:l,1]
a = alpha[:l]
    
gcr0 = gc[r==0]%64 
gcr1 = gc[r==1]%64

gca0 = gc[a==0]%64 
gca1 = gc[a==1]%64

ar0 = a[r==0]
ar1 = a[r==1]


bins= np.arange(65)
binsa = np.arange(5)
    
#hr0, b = np.histogram(gcr0, bins=bins)
#hr1, b = np.histogram(gcr1, bins=bins)
#ha0, b = np.histogram(gca0, bins=bins)
#ha1, b = np.histogram(gca1, bins=bins)

hq0, bq = np.histogram(ar0, bins=binsa)
hq1, bq = np.histogram(ar1, bins=binsa)
h, bq = np.histogram(a, bins=binsa)

#plt.plot(b[:-1], hr0, label="hr0")
#plt.plot(b[:-1], hr1, label="hr1")
#plt.plot(b[:-1], ha0, label="ha0")
#plt.plot(b[:-1], ha1, label="ha1")

plt.plot(bq[:-1], hq0, "o", label="hq0")
plt.plot(bq[:-1], hq1, "x", label="hq1")
plt.plot(bq[:-1], h, "s", label="ha")


plt.ylim(0)
plt.legend()

plt.show()




