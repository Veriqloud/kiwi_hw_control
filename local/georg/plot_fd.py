#!/bin/python
import numpy as np, matplotlib.pyplot as plt

#names = ['fd_b_single.txt']
#names = ['time.txt', 'time2.txt', 'time3.txt', 'time4.txt']
names = ['time.txt']


hist0 = []
hist1 = []
hist = []
bins = np.arange(65)
for name in names:
    data = np.loadtxt(name, usecols=(2, 3, 4), dtype=np.int64)
    gc = data[:,0] 
    r = data[:,1]
    q_pos = data[:,2]
    gc0 = (gc[r==0]%32)*2 + q_pos[r==0] 
    gc1 = (gc[r==1]%32)*2 + q_pos[r==1] 
    h0, b = np.histogram(gc0, bins=bins)
    h1, b = np.histogram(gc1, bins=bins)
    
    # revert the alteration of the sequence
#    h0[1::2] = h0[1::2][::-1]
#    h1[1::2] = h1[1::2][::-1]

    hist0.append(h0)
    hist1.append(h1)
    hist.append(h0-h1)


for i in range(len(hist0)):
    plt.plot(bins[:-1], hist0[i])
    plt.plot(bins[:-1], hist1[i])

#plt.plot(bins[:-1], hist0[1])
#plt.plot(bins[:-1], hist1[1])

plt.show()


#data = np.loadtxt('time.txt', usecols=(1), dtype=np.int64)
##bins = np.arange(0,12500*17/20, 20)
#print(data.max())
#h, b = np.histogram(data, bins=1000)
#
#plt.plot(b[1:], h)
##plt.axvline(12500)
#plt.show()



