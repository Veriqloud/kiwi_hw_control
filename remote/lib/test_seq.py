import  gen_seq
import numpy as np
import matplotlib.pyplot as plt


shift = 474


#seq_old = (gen_seq.dac0_single_old(4, 6))
#ls2 = gen_seq.lin_seq_2()
#seq_old = gen_seq.dac1_sample_old(gen_seq.lin_seq_2(), 0, shift)
seq = gen_seq.dac1_sample(gen_seq.lin_seq_2(), shift)
seq2 = gen_seq.dac1_sample_same_as_dpram(gen_seq.lin_seq_2(), shift)
#seq_tight = gen_seq.dac1_sample_tight(gen_seq.lin_seq_2(), shift)
#seq_single = gen_seq.dac0_single(64, shift)
#seq_single_single = gen_seq.dac0_single_single(64, shift)

#seq = gen_seq.dac0_single(4, 6)

#print(seq)
#a = []
#for e in seq_old:
#    a.append(int(e, 16))


#print(a)
#print(len(a))
#a = np.array(a)

#print(a[:10])

#plt.plot(a[:50], marker='x')
plt.plot(seq, marker='o')
plt.plot(seq2, marker='p')
#plt.plot(seq_single*0.98, marker='p')
#plt.plot(seq_single_single, marker='p')
plt.axvline(3 + shift, color='black')
plt.axvline(10/12.5*5 + 3 + shift, color='black')
plt.show()




#seq_old = gen_seq.dac0_double_old(2, [-0.92, 0.92], 4, shift)
#seq = gen_seq.dac0_double(4, 0, shift+1)
#seq2 = gen_seq.dac0_double(4, 1, shift+1)
#a = []
#for e in seq_old:
#    a.append(int(e, 16))
#
#
#plt.plot(a, marker='x')
#plt.plot(seq, marker='x')
##plt.plot(seq2, marker='x')
#plt.axhline(32768, color='black')
#plt.axvline(5.6 + shift, color='black')
#plt.axvline(10/12.5*5 + 5.6 + shift, color='black')
#plt.show()

#seq_old = gen_seq.dac0_single_old(4,6)
#seq = gen_seq.dac0_single(4, 6)
#a = []
#for e in seq_old:
#    a.append(int(e, 16))
#
#
#plt.plot(a, marker='x')
#plt.plot(seq, marker='x')
#plt.axhline(32768, color='black')
#plt.axvline(5.6 + shift, color='black')
#plt.axvline(10/12.5*5 + 5.6 + shift, color='black')
#plt.show()




