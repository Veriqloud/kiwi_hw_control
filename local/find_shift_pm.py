#!/bin/python
import time
import numpy as np
import matplotlib.pyplot as plt 
from scipy.optimize import curve_fit
# from scipy.signal import find_peaks


def shift_unit(j,party, ):
    times_ref_click0=[]
    times_ref_click1=[]
    if party == 'alice':
        data = np.loadtxt("pm_shift_data/pm_a_shift_"+str(j)+".txt", usecols=(2,3,4), dtype=np.int64)
        gc_compensation=59
    elif party == 'bob':
        data = np.loadtxt("pm_shift_data/pm_b_shift_"+str(j)+".txt", usecols=(2,3,4), dtype=np.int64)
        gc_compensation=61

    gc = data[:,0] 
    r = data[:,1]
    q_pos = data[:,2]
    gc0 = (gc[r==0]*2 + q_pos[r==0] + gc_compensation) % 64
    gc1 = (gc[r==1]*2 + q_pos[r==1] + gc_compensation) % 64

    return gc0, gc1


    #int_click_gated[0] = int_click_gated[0] + gc_compensation
    #print(int_click_gated)
    #seq = 64  #[q_bins]
    ## time_range = seq
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

def sine_function(x, A, B, C, D):
    return A*np.sin(B*2*np.pi*x + C) + D

def fre_est(x,y):
    fft_result = np.fft.fft(y)
    frequencies = np.fft.fftfreq(len(x), x[1] - x[0])  # Frequencies corresponding to FFT
    power_spectrum = np.abs(fft_result)**2  # Power spectrum

    # Find the peak frequency
    positive_frequencies = frequencies[frequencies > 0]
    positive_power = power_spectrum[frequencies > 0]
    dominant_frequency = positive_frequencies[np.argmax(positive_power)]
    return dominant_frequency

def fit_sine(party):
    fig, sin_his = plt.subplots(5, 2, figsize=(12, 10))
    sin_his = sin_his.ravel()  # Flatten sin_his array for easy indexing
    return_arr = []
    delta_cnt0_arr = []
    for i in range(10):
        times_ref_click0, times_ref_click1 = shift_unit(i,party)
        n0, bins0 = np.histogram(times_ref_click0, 64)
        n1, bins1 = np.histogram(times_ref_click1, 64)
        bin_center0 = (bins0[:-1] + bins0[1:])/2
        bin_center1 = (bins1[:-1] + bins1[1:])/2

        n0[1::2] = n0[1::2][::-1]
        n1[1::2] = n1[1::2][::-1]

    #     delta_cnt0 = max(n0) - min(n0)
    #     delta_cnt1 = max(n1) - min(n1)
    #     if (delta_cnt0 > 0):
    #         delta_cnt0_arr.append((int(delta_cnt0),i))

    # #Fit sine only for top max amplitude
    # for k,i in delta_cnt0_arr:
        #times_ref_click0, times_ref_click1 = shift_unit(i,party)
        #n0, bins0, patches = sin_his[i].hist(times_ref_click0, 64, density=False,color='g',alpha=0.01)
        #n1, bins1, patches = sin_his[i].hist(times_ref_click1, 64, density=False,color='r',alpha=0.01)
        #bin_center0 = (bins0[:-1] + bins0[1:])/2
        #bin_center1 = (bins1[:-1] + bins1[1:])/2

        amp_guess = (max(n0)-min(n0))/2
        fre_guess = np.pi*2*10*fre_est(bin_center0,n0)
        phase_guess = 0
        offset_guess = np.mean(n0)
        param_bounds = ([0, 1, -np.pi, -np.inf],[200, 3, np.pi, np.inf])    # print(amp_guess)
        # print(fre_guess)
        # FIT SIN
        # initial_guess_0 = [100, 2.5, 0, 150]
        initial_guess_0 = [amp_guess, fre_guess, phase_guess, offset_guess]
        params_0, params_covariance_0 = curve_fit(sine_function, bin_center0/64, n0, p0=initial_guess_0, maxfev=10000)
        A0,B0,C0,D0 = params_0
        ma = abs(A0) + D0
        mi = -abs(A0) + D0
        print(i, ma/(ma+mi))
        fitted_y_data_0 = sine_function(bin_center0/64, A0, B0, C0, D0)
        # resi0 = n0 - fitted_y_data_0
        # rmse0 = np.sqrt(np.mean(resi0**2))
        return_arr.append((round(A0,2),round(B0,2),i))
        # print("RMSE: ",rmse0)

        # Fit sine for p1
        # initial_guess_1 = [100, 2.5, 0.5, 150]
        # params_1, params_covariance_1 = curve_fit(sine_function, bin_center1/64, n1, p0=initial_guess_0, maxfev=10000)
        # A1,B1,C1,D1 = params_1
        # fitted_y_data_1 = sine_function(bin_center1/64, A1, B1, C1, D1)

        # ploting fit sin 
        # sin_his.plot(bin_center0, n1-n0)
        sin_his[i].plot(bin_center0, fitted_y_data_0, label='Shift: '+str(i)+f' Fitted Sine Function: y = {A0:.2f} * sin({B0:.2f} * 2pi.x + {C0:.2f}) + {D0:.2f}')
        # sin_his[i].plot(bin_center1, fitted_y_data_1, label=f'Fitted Sine Function: y = {A1:.2f} * sin({B1:.2f} * 2pi.x + {C1:.2f}) + {D1:.2f}')

        # PLOTING
        sin_his[i].scatter(x=bin_center0,y=n0)
        sin_his[i].scatter(x=bin_center1,y=n1)
        # sin_his[i].set_xlabel('time [20ps]')
        sin_his[i].set_ylabel('cnts', fontsize=8)
        sin_his[i].tick_params(axis='both',labelsize=8)    
        # sin_his[i].set_title(f'shift {i}',fontsize=8)
        sin_his[i].legend(prop={'size':8},loc='upper center', bbox_to_anchor=(0.5,-0.15), ncol=1)
        sin_his[i].set_ylim(0)

    return return_arr
    #Find shift with min error
    # print("Error array", error_arr)
    # min_error = min(error_arr, key=lambda t: t[0])
    # best_shift = min_error[3]
    # max_amp = max(error_arr, key=lambda t: abs(t[1])*t[2])
    # best_shift = max_amp[3]
    # print("Best shift: ", best_shift)

    # plt.subplots_adjust(hspace=0.3, wspace=0.3)
    # mng = plt.get_current_fig_manager()
    # mng.full_screen_toggle()
    # plt.tight_layout()
    # plt.show()

def best_shift(party):
    return_arr = fit_sine(party)
    # print(return_arr)


    amp_fre_arr=[]
    for amp,fre,i in return_arr:
        if (abs(amp) < 1000):
            if (0.1<fre<5):
                amp_fre_arr.append(((abs(amp)*fre),i))
                print(amp, fre, i)
    max_ele = max(amp_fre_arr, key=lambda t: t[0])
    best_shift = max_ele[1]
    print("Best shift: ", best_shift)


    plt.subplots_adjust(hspace=0.3, wspace=0.3)
    mng = plt.get_current_fig_manager()
    mng.full_screen_toggle()
    plt.tight_layout()
    plt.show()


# best_shift('alice')
best_shift('alice')
