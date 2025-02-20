#!/bin/python
import numpy as np, matplotlib.pyplot as plt

#names = ['single.txt', 'double.txt', 'off.txt', 'softgate.txt']

names = ['../pm_shift_data/pm_b_shift_7.txt']
#names = ['time.txt', 'time2.txt']

gc_shift =  31

hist0 = []
hist1 = []
bins = np.arange(65)
for name in names:
    data = np.loadtxt(name, usecols=(2, 3, 4), dtype=np.int64)
    gc = data[:,0] + gc_shift
    r = data[:,1]
    q_pos = data[:,2]
    gc0 = (gc[r==0]%32)*2 + q_pos[r==0] 
    gc1 = (gc[r==1]%32)*2 + q_pos[r==1] 
    h0, b = np.histogram(gc0, bins=bins)
    h1, b = np.histogram(gc1, bins=bins)

    # revert the alteration of the sequence
    h0[1::2] = h0[1::2][::-1]
    h1[1::2] = h1[1::2][::-1]

    hist0.append(h0)
    hist1.append(h1)


#data = np.loadtxt("single64.txt", usecols=(2, 3, 4), dtype=np.int64)
data = np.loadtxt("time.txt", usecols=(2, 3, 4), dtype=np.int64)
gc = data[:,0] + gc_shift
q_pos = data[:,2]
gc0 = (gc%32)*2 + q_pos 
h, b = np.histogram(gc0, bins=bins)

print(h.argmax())

plt.plot(bins[:-1], hist0[0], color='b')
plt.plot(bins[:-1], hist1[0], color='g')
#plt.plot(bins[:-1], hist0[1], color='g')
#plt.plot(bins[:-1], hist1[1], color='g')
#plt.plot(bins[:-1], h)

plt.ylim(0)
plt.show()



