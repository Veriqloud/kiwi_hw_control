#!/bin/python
import time
import numpy as np
import matplotlib.pyplot as plt 
from scipy.optimize import curve_fit
from scipy.signal import find_peaks


fig = plt.figure(1)
raw_his = fig.add_subplot(221)
#-----------------------SINGLE PULSE-----25ns-----CONT----------------
time_sp = np.loadtxt("histogram_sp.txt",usecols=1,unpack=True)
times_ref_sp = (time_sp*20%25000)/20

n, bins, patches = raw_his.hist(times_ref_sp, 400, density=False,alpha=0.5, label='sp')

#-----------------------DOUBLE PULSE------25ns-----CONT------------
time_dp = np.loadtxt('histogram_dp.txt',usecols=(1), unpack=True)
# times_ref_dp = (time_dp*20%25000)/20
times_ref_dp = (time_dp*20%25000)/20
n, bins, patches = raw_his.hist(times_ref_dp, 400, density=False, color='r',alpha=0.3, label='dp')

raw_his.set_xlabel('time[20ps]')
raw_his.set_ylabel('counts')
raw_his.set_title('Histogram of click')
# raw_his.axis([0,1250,0,5000])
raw_his.legend(prop={'size':10})
#plt.axvspan(90,40, facecolor='g', alpha=0.3)
#plt.axvspan(550,600, facecolor='g', alpha=0.3)

#----------------------DOUBLE PULSE-----12.5ns-----GATED + FPGA GATE------

gated_his = fig.add_subplot(224,sharex=raw_his)
#click output form FPGA inside the gate_apply, only click 0 and click 1
time_gated = np.loadtxt("histogram_gated.txt",usecols=1,unpack=True)
times_gated = time_gated%625
n, bins, patches = gated_his.hist(times_gated, 200, density=False,color='g',alpha=0.8, label='apd + fpga gate')
gated_his.legend(prop={'size':10})


#----------------------FIND DELAY----------------------------------------
gc = np.loadtxt("histogram_fd.txt",usecols=2,unpack=True,dtype=np.int64)
gcs_delay = np.array(gc%40000)
np.savetxt('gcs_delay.txt',gcs_delay,fmt='%d')

#----------------------DOUBLE PULSE-----25ns-----GATED-------------------
#clicks output from FPGA, inside the window of apd_gate, apd in gated mode, 
gate_his = fig.add_subplot(222,sharex=raw_his)
time_gate_apd = np.loadtxt("histogram_gate_apd.txt",usecols=1,unpack=True)
times_gate_apd = (time_gate_apd*20%25000)/20
    
n, bins, patches = gate_his.hist(times_gate_apd, 200, density=False,color='b',alpha=0.3, label='apd gate ')
gate_his.legend(prop={'size':10})
# gate_his.axis([0,1250,0,2000])

#Check first peak
# ref_time = np.loadtxt("histogram_gate_apd.txt",usecols=1,unpack=True,dtype=np.int32)
# ref_time_arr = (ref_time*20%12500)/20
# y, x = np.histogram(ref_time_arr, bins=np.arange(0,1255, 5)-2.5)

# amax1 = y.argmax()
# ytmp = np.copy(y)
# ytmp[max(0,amax1-10): amax1+10] = 0
# if (amax1<10):
#     ytmp[-10+amax1:] = 0
# amax2 = ytmp.argmax()
# ytmp[max(0,amax2-10): amax2+10] = 0
# if (amax2<10):
#     ytmp[-10+amax2:] = 0
# amax3 = ytmp.argmax()
# ytmp[max(0,amax3-10): amax3+10] = 0
# if (amax3<10):
#     ytmp[-10+amax3:] = 0
# amax4 = ytmp.argmax()
# ytmp[max(0,amax4-10): amax4+10] = 0
# if (amax4<10):
#     ytmp[-10+amax4:] = 0


# p = np.sort([x[amax1], x[amax2], x[amax3], x[amax4]])
# d0 = (p[0] - p[3]) % 1250
# d1 = p[1] - p[0]
# d2 = p[2] - p[1]
# d3 = p[3] - p[2]
# first_peak = (p[np.argmax([d0, d1, d2, d3])]+2.5) % 625
# print("First peak: ",first_peak)



#-----------------------------------------------------------------------------------
#click output form FPGA inside the gate, only click 0 and click 1
times_ref_click0=[]
times_ref_click1=[]
# int_click_gated = np.loadtxt("histogram_gated.txt",usecols=(0,1,3,2),unpack=True, dtype=np.int64)
int_click_gated = np.loadtxt("histogram_gated.txt",usecols=(2,3,4),unpack=True, dtype=np.int64)

seq_option = [64,8000,160]
seq = seq_option[0]
gc_calib=[]

for i in range(len(int_click_gated[1])):
    if (int_click_gated[1][i] == 0):
        if (int_click_gated[2][i] == 0):
            gc_q = (int_click_gated[0][i]%(seq/2))*2
        elif(int_click_gated[2][i] == 1):
            gc_q = (int_click_gated[0][i]%(seq/2))*2 + 1
        times_ref_click0.append(gc_q)

    elif (int_click_gated[1][i] == 1):
        if (int_click_gated[2][i] == 0):
            gc_q = (int_click_gated[0][i]%(seq/2))*2
        elif(int_click_gated[2][i] == 1):
            gc_q = (int_click_gated[0][i]%(seq/2))*2 + 1
        times_ref_click1.append(gc_q)
#     if (gc_q == 34 ):
#         gc_calib.append([int_click_gated[0][i], (int_click_gated[0][i]-0)%32, int_click_gated[2][i]]),
# np.savetxt('b_gc_calib.txt', gc_calib, fmt='%d')
    if (gc_q == 16 ):
        gc_calib.append([int_click_gated[0][i], (int_click_gated[0][i]%2000), (int_click_gated[0][i]-0)%32, int_click_gated[2][i]]),
np.savetxt('a_gc_calib.txt', gc_calib, fmt='%d')

if (seq == seq_option[0]):
    sin_his = fig.add_subplot(223)
    n0, bins0, patches = sin_his.hist(times_ref_click0, 64, density=False,color='g',alpha=0.01, label='p0')
    n1, bins1, patches = sin_his.hist(times_ref_click1, 64, density=False,color='r',alpha=0.01, label='p1')
    bin_center0 = (bins0[:-1] + bins0[1:])/2
    bin_center1 = (bins1[:-1] + bins1[1:])/2

    sin_his.plot(bin_center0, n1-n0)
    index = np.argmax(np.abs(n1-n0))
    print(index)
    sin_his.scatter(x=bin_center0,y=n0,color='g',label='click0')
    sin_his.scatter(x=bin_center1,y=n1,color='r',label='click1')


elif (seq == seq_option[1]):
    fig2 = plt.figure(2)
    gs = fig2.add_gridspec(2,1,height_ratios=[2,1])
    sin_his = fig2.add_subplot(gs[1])

    n0, bins0, patches = sin_his.hist(times_ref_click0, int(seq/64), density=False,color='g',alpha=0.1, label='p0')
    n1, bins1, patches = sin_his.hist(times_ref_click1, int(seq/64), density=False,color='r',alpha=0.1, label='p1')


    bin_center0 = (bins0[:-1] + bins0[1:])/2
    bin_center1 = (bins1[:-1] + bins1[1:])/2

    fd_his = fig2.add_subplot(gs[0])
    index = np.argmax(np.abs(n1-n0))
    print(index)

    x_axis = list(range(0,int(seq/64),1))
    fd_his.plot(x_axis, n1-n0)
    fd_his.scatter(x=x_axis,y=n0,color='g',label='click0')
    fd_his.scatter(x=x_axis,y=n1,color='r',label='click1')


else: 
    fig2 = plt.figure(2)
    gs = fig2.add_gridspec(2,1,height_ratios=[2,1])
    sin_his = fig2.add_subplot(gs[1])

    n0, bins0, patches = sin_his.hist(times_ref_click0, int(seq), density=False,color='g',alpha=0.1, label='p0')
    n1, bins1, patches = sin_his.hist(times_ref_click1, int(seq), density=False,color='r',alpha=0.1, label='p1')


    bin_center0 = (bins0[:-1] + bins0[1:])/2
    bin_center1 = (bins1[:-1] + bins1[1:])/2

    fd_his = fig2.add_subplot(gs[0])
    index = np.argmax(np.abs(n1-n0))
    print(index)

    x_axis = list(range(0,int(seq),1))
    fd_his.plot(x_axis, n1-n0)
    fd_his.scatter(x=x_axis,y=n0,color='g',label='click0')
    fd_his.scatter(x=x_axis,y=n1,color='r',label='click1')





# PLOTING
sin_his.set_xlabel('time [20ps]')
sin_his.set_ylabel('counts')
sin_his.set_title('Histogram of click0 and click1')
sin_his.legend(prop={'size':8})
# sin_his.legend(loc='lower center', bbox_to_anchor=(0.5,1.05), ncol=2)

plt.subplots_adjust(hspace=0.3, wspace=0.3)
mng = plt.get_current_fig_manager()
mng.full_screen_toggle()
plt.show()


