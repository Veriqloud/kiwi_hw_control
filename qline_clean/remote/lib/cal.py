#!/bin/python
import time
import numpy as np
from scipy.optimize import curve_fit


def Shift_Unit(j,party):
    #times_ref_click0=[]
    #times_ref_click1=[]
    if party == 'alice':
        data = np.loadtxt("data/tdc/pm_a_shift_"+str(j)+".txt",usecols=(2,3,4), dtype=np.int64)
        gc_compensation=59
    elif party == 'bob':
        data = np.loadtxt("data/tdc/pm_b_shift_"+str(j)+".txt",usecols=(2,3,4), dtype=np.int64)
        gc_compensation=61

    gc = data[:,0] 
    r = data[:,1]
    q_pos = data[:,2]
    gc0 = (gc[r==0]*2 + q_pos[r==0] + gc_compensation) % 64
    gc1 = (gc[r==1]*2 + q_pos[r==1] + gc_compensation) % 64

    return gc0, gc1
    #seq = 64  #[q_bins]
    #int_click_gated[0] = int_click_gated[0] + gc_compensation
    #for i in range(len(int_click_gated[1])):
    #    if (int_click_gated[1][i] == 0):
    #        if (int_click_gated[2][i] == 0):
    #            gc_q = (int_click_gated[0][i]%(seq/2))*2
    #        elif(int_click_gated[2][i] == 1):
    #            gc_q = (int_click_gated[0][i]%(seq/2))*2 + 1
    #        times_ref_click0.append(gc_q)

    #    elif (int_click_gated[1][i] == 1):
    #        if (int_click_gated[2][i] == 0):
    #            gc_q = (int_click_gated[0][i]%(seq/2))*2
    #        elif(int_click_gated[2][i] == 1):
    #            gc_q = (int_click_gated[0][i]%(seq/2))*2 + 1
    #        times_ref_click1.append(gc_q)
    #return times_ref_click0, times_ref_click1

def Sine_Function(x, A, B, C, D):
    return A*np.sin(B*2*np.pi*x + C) + D

def Fre_Est(x,y):
    fft_result = np.fft.fft(y)
    frequencies = np.fft.fftfreq(len(x), x[1] - x[0])  # Frequencies corresponding to FFT
    power_spectrum = np.abs(fft_result)**2  # Power spectrum

    # Find the peak frequency
    positive_frequencies = frequencies[frequencies > 0]
    positive_power = power_spectrum[frequencies > 0]
    dominant_frequency = positive_frequencies[np.argmax(positive_power)]
    return dominant_frequency

def Fit_Sine(party):
    return_arr = []
    delta_cnt0_arr = []
    for i in range(10):
        times_ref_click0, times_ref_click1 = Shift_Unit(i,party)
        n0, bins0 = np.histogram(times_ref_click0, 64)
        n1, bins1 = np.histogram(times_ref_click1, 64)
        bin_center0 = (bins0[:-1] + bins0[1:])/2
        bin_center1 = (bins1[:-1] + bins1[1:])/2
        
        n0[1::2] = n0[1::2][::-1]
        n1[1::2] = n1[1::2][::-1]


        amp_guess = (max(n0)-min(n0))/2
        fre_guess = np.pi*2*10*Fre_Est(bin_center0,n0)
        phase_guess = 0
        offset_guess = np.mean(n0)
        param_bounds = ([0, 1, -np.pi, -np.inf],[200, 3, np.pi, np.inf])	# print(amp_guess)
        # FIT SIN
        initial_guess_0 = [amp_guess, fre_guess, phase_guess, offset_guess]
        params_0, params_covariance_0 = curve_fit(Sine_Function, bin_center0/64, n0, p0=initial_guess_0, maxfev=10000)
        A0,B0,C0,D0 = params_0
        fitted_y_data_0 = Sine_Function(bin_center0/64, A0, B0, C0, D0)
        return_arr.append((round(A0,2),round(B0,2),i))

    return return_arr

def Best_Shift(party):
    return_arr = Fit_Sine(party)
    amp_fre_arr=[]
    print("amp     fre   i")
    for amp,fre,i in return_arr:
        if (abs(amp) < 1000):
            if (0.1<fre<5):
                amp_fre_arr.append(((abs(amp)*fre),i))
                print(f"{abs(amp):.2f}  {fre:.2f}  {i:.2f}")

    max_ele = max(amp_fre_arr, key=lambda t: t[0])
    best_shift = max_ele[1]
    print("Best shift: ", best_shift)
    return best_shift

def Find_First_Peak(ref_time_arr):
    y, x = np.histogram(ref_time_arr, bins=np.arange(0,1255, 5)-2.5)
    import matplotlib.pyplot as plt

    amax1 = y.argmax()
    ytmp = np.copy(y)
    ytmp[max(0,amax1-10): amax1+10] = 0
    if (amax1<10):
        ytmp[-10+amax1:] = 0
    if (amax1>240):
        ytmp[0:10-250+amax1] = 0

    amax2 = ytmp.argmax()
    ytmp[max(0,amax2-10): amax2+10] = 0
    if (amax2<10):
        ytmp[-10+amax2:] = 0
    if (amax2>240):
        ytmp[0:10-250+amax2] = 0

    amax3 = ytmp.argmax()
    ytmp[max(0,amax3-10): amax3+10] = 0
    if (amax3<10):
        ytmp[-10+amax3:] = 0
    if (amax3>240):
        ytmp[0:10-250+amax3] = 0

    amax4 = ytmp.argmax()
    ytmp[max(0,amax4-10): amax4+10] = 0
    if (amax4<10):
        ytmp[-10+amax4:] = 0
    if (amax4>240):
        ytmp[0:10-250+amax4] = 0

    p = np.sort([x[amax1], x[amax2], x[amax3], x[amax4]])
    d0 = (p[0] - p[3]) % 1250
    d1 = p[1] - p[0]
    d2 = p[2] - p[1]
    d3 = p[3] - p[2]
    first_peak = (p[np.argmax([d0, d1, d2, d3])]+2.5) % 625
    # print("First peak: ",first_peak)
    return int(first_peak)


# Best_Shift('bob')
