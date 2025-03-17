#!/bin/python
import numpy as np, matplotlib.pyplot as plt

def get_fiber_delay(fname):
    with open(fname) as f:
        lines = f.readlines()
        for l in lines:
            s = l[:-1].split("\t")
            key = s[0]
            value = s[1]
            if key == 'fiber_delay_mod':
                return int(value)



names = ['fd_b_single_long.txt', 'fd_a_single_long.txt']



fiber_delay_mod = {}
fiber_delay_mod[names[0]] = get_fiber_delay('tmp_b.txt')
fiber_delay_mod[names[1]] = get_fiber_delay('tmp_a.txt')


hist0 = []
hist1 = []
hist = []
bins = np.arange(0,80*401,80)
for name in names:
    data = np.loadtxt(name, usecols=(2, 3, 4), dtype=np.int64)
    gc = data[:,0] 
    r = data[:,1]
    q_pos = data[:,2]
    gc0 = (gc[r==0]*2 + q_pos[r==0] - fiber_delay_mod[name]) % (80*400)
    gc1 = (gc[r==1]*2 + q_pos[r==1] - fiber_delay_mod[name]) % (80*400)

    h0, b = np.histogram(gc0, bins=bins)
    h1, b = np.histogram(gc1, bins=bins)
    
    hist0.append(h0)
    hist1.append(h1)
    hist.append(h0-h1)


for i in range(len(hist0)):
    plt.plot(hist0[i], '-x', label=names[i])
    plt.plot(hist1[i], '-x', label=names[i])


plt.ylim(0)
plt.legend()
plt.show()





