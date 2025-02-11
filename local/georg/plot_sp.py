#!/bin/python
import numpy as np, matplotlib.pyplot as plt

#names = ['single.txt', 'double.txt', 'off.txt', 'softgate.txt']
names = ['verify_gate_off.txt', 'verify_gate_double.txt']

time = []
hist = []
bins = np.arange(0, 1251, 2) - 1
for name in names:
    t = np.loadtxt(name, usecols=1)
    t = t%1250
    h, b = np.histogram(t, bins=bins)
    hist.append(h)



for h in hist:
    plt.plot(bins[:-1]+1, h)

plt.axvline(625, color= 'black')
plt.axvline(20, color= 'red')
plt.axvline(80, color= 'red')
plt.axvline(530, color= 'red')
plt.axvline(590, color= 'red')
plt.ylim(0)
plt.show()



