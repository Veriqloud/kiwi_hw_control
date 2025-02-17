import cal_lib
import numpy as np
import matplotlib.pyplot as plt

ref_time = np.loadtxt("../../local/georg/time2.txt",usecols=1,unpack=True,dtype=np.int32)
#ref_time_arr = (ref_time*20)%25000/20
ref_time_arr = ref_time%1250
#Find first peak of histogram
first_peak = cal_lib.Find_First_Peak(ref_time_arr)
print("First peak: ",first_peak)


y,b = np.histogram(ref_time_arr, bins=500)
plt.plot(b[:-1], y, color='blue')
plt.ylim(0)
plt.axvline(first_peak, color='green')
plt.axvline(first_peak+625, color='green')
plt.show()

