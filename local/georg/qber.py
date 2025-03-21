#!/bin/python
import numpy as np, matplotlib.pyplot as plt

l = 32000

gcr_a = np.loadtxt('gcr_a.txt', dtype=np.int64)
gcr_b = np.loadtxt('gcr_b.txt', dtype=np.int64)
alpha_a = np.loadtxt('alpha_a.txt', dtype=np.int64)
alpha_b = np.loadtxt('alpha_b.txt', dtype=np.int64)

gc_a = gcr_a[:l,0]
r_a = gcr_a[:l,1]
gc_b = gcr_b[:l,0]
r_b = gcr_b[:l,1]
a = alpha_a[:l]
b = alpha_b[:l]
    
ar0 = a[r_a==0]
ar1 = a[r_a==1]

br0 = b[r_b==0]
br1 = b[r_b==1]

bins = np.arange(5)

aq0, bq = np.histogram(ar0, bins=bins)
aq1, bq = np.histogram(ar1, bins=bins)

bq0, bq = np.histogram(br0, bins=bins)
bq1, bq = np.histogram(br1, bins=bins)

qber_a =aq0/(aq0+aq1)
qber_b =bq0/(bq0+bq1)

print(np.round(qber_a, 4))
print(np.round(qber_b, 4))

plt.plot(bq[:-1], aq0, "x", label="ar0")
plt.plot(bq[:-1], aq1, "x", label="ar1")
plt.plot(bq[:-1], bq0, "o", label="br0")
plt.plot(bq[:-1], bq1, "o", label="br1")

#plt.plot(bq[:-1], h, "s", label="a")


plt.ylim(0)
plt.legend()


plt.show()




