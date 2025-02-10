import  gen_seq
import numpy as np
import matplotlib.pyplot as plt


shift =0 
#seq_old = (gen_seq.dac0_single_old(4, 6))
#ls2 = gen_seq.lin_seq_2()
seq_old = gen_seq.dac1_sample_old(gen_seq.lin_seq_2(), 0, shift)
seq = gen_seq.dac1_sample(gen_seq.lin_seq_2(), shift)

#seq = gen_seq.dac0_single(4, 6)

#print(seq)
a = []
for e in seq_old:
    a.append(int(e, 16))


#print(a)
print(len(a))
a = np.array(a)

print(a[:10])

plt.plot(a[:50], marker='x')
plt.plot(seq[:50], marker='o')
plt.axvline(3 + shift, color='black')
plt.axvline(10/12.5*5 + 3 + shift, color='black')
plt.show()




#seq_old = gen_seq.dac0_double_old(2, [-0.95, 0.95], 2, shift)
#a = []
#for e in seq_old:
#    a.append(int(e, 16))
#
#
#plt.plot(a, marker='x')
#plt.axhline(32768, color='black')
#plt.axvline(5.6 + shift, color='black')
#plt.axvline(10/12.5*5 + 5.6 + shift, color='black')
#plt.show()


