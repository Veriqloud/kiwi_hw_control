#!/bin/python
import numpy as np, matplotlib.pyplot as plt


bins = np.arange(65)
data = np.loadtxt('time.txt', usecols=(2, 3, 4), dtype=np.int64)
gc = data[:,0] 
r = data[:,1]
q_pos = data[:,2]
#gc0 = (gc[r==0]%32)*2 + q_pos[r==0] 
#gc1 = (gc[r==1]%32)*2 + q_pos[r==1] 
#h0, b = np.histogram(gc0, bins=bins)
#h1, b = np.histogram(gc1, bins=bins)
    
h0, b = np.histogram(gc[r==1], bins=1000)

plt.plot(h0, label='0')
#plt.plot(bins[:-1], h1, label='1')
#plt.legend()
plt.show()





