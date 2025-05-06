#!/bin/python
import numpy as np, matplotlib.pyplot as plt

#names = ['single.txt', 'double.txt', 'off.txt', 'softgate.txt']
#names = ['time.txt', 'time2.txt', 'time3.txt']
names = ['verify_gate_off.txt', 'verify_gate_double.txt']
#names = ['verify_gate_ad_0.txt', 'verify_gate_ad_1.txt', 'verify_gate_ad_2.txt', 'time.txt', 'time_4000.txt']
#names = ['double.txt', 'single.txt', 'single64.txt']

time = []
hist = []
bins = np.arange(0, 1251, 2) - 1
for name in names:
    t = np.loadtxt(name, usecols=1)
    t = t%1250
    h, b = np.histogram(t, bins=bins)
    hist.append(h)



for i in range(len(hist)):
    plt.plot(bins[:-1]+1, hist[i], label=names[i])

plt.axvline(625, color= 'black')
plt.axvline(20, color= 'red')
plt.axvline(80, color= 'red')
plt.axvline(530, color= 'red')
plt.axvline(590, color= 'red')
plt.ylim(0)
plt.legend()
plt.show()



