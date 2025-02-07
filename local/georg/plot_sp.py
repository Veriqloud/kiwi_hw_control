#!/bin/python
import numpy as np, matplotlib.pyplot as plt

time = np.loadtxt("time.txt", usecols=1)
time = time%1250

time2 = np.loadtxt("time2.txt", usecols=1)
time2 = time2%1250

time3 = np.loadtxt("time3.txt", usecols=1)
time3 = time3%1250

time4 = np.loadtxt("time4.txt", usecols=1)
time4 = time4%1250

y,b = np.histogram(time, bins=500)
y2,b = np.histogram(time2, bins=b)
y3,b = np.histogram(time3, bins=b)
y4,b = np.histogram(time4, bins=b)

plt.plot(b[:-1], y, 'blue')
plt.plot(b[:-1], y2, 'green')
plt.plot(b[:-1], y3, 'red')
plt.plot(b[:-1], y4, 'orange')
plt.vlines([625], [0], [np.max(y)], 'black')
plt.ylim(0)
plt.show()


#time = np.loadtxt("../time.txt", usecols=1)
#time = time%1250
#
#y,b = np.histogram(time, bins=500)
#
#plt.plot(b[:-1], y)
#plt.show()

