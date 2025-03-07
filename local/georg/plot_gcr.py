#!/bin/python
import numpy as np, matplotlib.pyplot as plt

#names = ['gcr.txt', 'gcr2.txt', 'gcr2.txt']
names = ['gcr.txt']#, 'gcr2.txt', 'gcr3.txt', 'gcr4.txt']


hist0 = []
hist1 = []
hist = []
bins = np.arange(65)
for name in names:
    data = np.loadtxt(name, dtype=np.int64)
    gc = data[:,0] 
    r = data[:,1]
    gc0 = gc[r==0]%64 
    gc1 = gc[r==1]%64
    h0, b = np.histogram(gc0, bins=bins)
    h1, b = np.histogram(gc1, bins=bins)
    
    hist0.append(h0)
    hist1.append(h1)
    hist.append(h0-h1)


for i in range(len(hist0)):
    plt.plot(bins[:-1], hist0[i], label=names[i])
    plt.plot(bins[:-1], hist1[i], label=names[i])
    #plt.plot(bins[:-1], hist[i], label=i)

#plt.plot(bins[:-1], hist0[1])
#plt.plot(bins[:-1], hist1[1])
#plt.legend()

plt.ylim(0)
plt.legend()
plt.show()


#data = np.loadtxt('time.txt', usecols=(1), dtype=np.int64)
##bins = np.arange(0,12500*17/20, 20)
#print(data.max())
#h, b = np.histogram(data, bins=1000)
#
#plt.plot(b[1:], h)
##plt.axvline(12500)
#plt.show()



