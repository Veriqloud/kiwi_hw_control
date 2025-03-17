import argparse
import numpy as np
# import matplotlib.pyplot as plt

def convert_analog_to_hex(analog_value, resolution=65536):
    # Normaliser la valeur analogique dans la plage 0 - 65535
    normalized_value = int((analog_value + 32768) /(resolution - 1) * 65535)
    # Convertir la valeur normalisée en hexadécimal
    hex_value = format(normalized_value, '04X')
    return hex_value


def lin_seq():
    return np.linspace(1,-1,64)

def lin_seq_2():
    # alternating up dow sequence
    seq = np.linspace(1,-1,64)
    seq[::2] = -seq[::2]
    return seq

def dac0_off(cycle_num):
    return np.zeros(cycle_num*10, dtype=int)

def dac0_single(cycle_num, shift):
    cycle_num = cycle_num // 2
    shift = shift + 2
    transition = np.array([-1, np.sin(-np.pi/4), 0, np.sin(np.pi/4), 1])
    rest = np.linspace(1, -1, 20-len(transition))
    seq0 = np.zeros(20)
    seq0[:len(rest)] = rest
    seq0[len(rest):] = transition
    seq = np.zeros(cycle_num * 20)
    seqs = np.zeros(cycle_num * 20)
    for i in range(cycle_num):
        seq[i*20:i*20+20] = seq0
    seqs[shift:] = seq[:-shift]
    seqs[:shift] = seq[-shift:]
    return np.array(seqs*32767 + 32768, dtype=int)

def dac0_single_single(cycle_num, shift):
    cycle_num = cycle_num
    shift = shift + 3   # needs to be shifted one more to overlap with dac0_single in real
    transition = np.array([-1, np.sin(-np.pi/4), 0, np.sin(np.pi/4), 1])
    len_const = cycle_num*5 - 2*len(transition)
    up = np.ones(len_const)
    down = -1*np.ones(len_const) 
    rest = np.linspace(1, -1, cycle_num*10-len(transition)-2*len_const)
    seq = np.zeros(10*cycle_num)
    seq[-len(transition):] = transition
    seq[0:len_const] = up
    seq[len_const:len_const + len(rest)] = rest
    seq[len_const + len(rest):-len(transition)] = down
    seqs = np.zeros(cycle_num * 10)
    seqs[shift:] = seq[:-shift]
    seqs[:shift] = seq[-shift:]
    return np.array(seqs*32767 + 32768, dtype=int)

def dac0_double(cycle_num, distance, shift):
    cycle_num = cycle_num 
    a = distance
    seq0 = np.array([1, 1, 0, -1, -1, a, 1, 0, -1, -a])
    seq = np.zeros(cycle_num * 10)
    seqs = np.zeros(cycle_num * 10)
    for i in range(cycle_num):
        seq[i*10:i*10+10] = seq0
    if shift:
        seqs[shift:] = seq[:-shift]
        seqs[:shift] = seq[-shift:]
    else:
        seqs = seq
    return np.array(seqs*32767 + 32768, dtype=int)


def dac1_sample(seq, shift):
    amp_max = 18000
    sample = np.zeros(len(seq)*10)
    sample2 = np.zeros(len(seq)*10)
    sample3 = np.zeros(len(seq)*10)
    for i in range(len(seq)):
        a = seq[i]
        # sample based on oscilloscope result to have flat plateaus
        #sample[10*i:10*(i+1)] = [a/2, 0.8*a, a, a, 0.7*a, -0.7*a, -a, -a, -0.8*a, -a/2] 
        sample[10*i:10*(i+1)] = [0, 0, a, a, 0, 0, -a, -a, 0, 0] 

    shift_calib = 28        # calibration to align to fake_rng
    sample2[shift_calib:] = sample[:-shift_calib]
    sample2[:shift_calib] = sample[-shift_calib:]

    if shift:
        sample3[shift:] = sample2[:-shift]
        sample3[:shift] = sample2[-shift:]
    else:
        sample3 = sample2
    return np.array(sample3*amp_max + 32768, dtype=int)

#def dac1_sample_same_as_dpram(seq, shift):
#    amp_max = 18000
#    shift_calibration = 26  # to get overlap with the fake_rng sequence on the oscilloscope
#    sample = np.zeros(len(seq)*10)
#    sample2 = np.zeros(len(seq)*10)
#    sample3 = np.zeros(len(seq)*10)
#    for i in range(len(seq)):
#        a = seq[i]
#        # sample based on oscilloscope result to have flat plateaus
#        sample[10*i:10*(i+1)] = [0, a, a, a, a, -a, -a, -a, -a, 0] 
#    sample2[shift_calibration:] = sample[:-shift_calibration]
#    sample2[:shift_calibration] = sample[-shift_calibration:]
#    # user shift 
#    if shift:
#        sample3[shift:] = sample2[:-shift]
#        sample3[:shift] = sample2[-shift:]
#    else:
#        sample3 = sample2
#    return np.array(sample3*amp_max + 32768, dtype=int)

#def dac1_sample_tight(seq, shift):
#    amp_max = 18000
#    sample = np.zeros(len(seq)*10)
#    samples = np.zeros(len(seq)*10)
#    for i in range(len(seq)):
#        a = seq[i]
#        sample[10*i:10*(i+1)] = [0, 0, a/2, a, a/2, 0, -a/2, -a, -a/2, 0] 
#    if shift:
#        samples[shift:] = sample[:-shift]
#        samples[:shift] = sample[-shift:]
#    else:
#        samples = sample
#    return np.array(samples*amp_max + 32768, dtype=int)



#def seq_dacs_dp(num_delays,delays,cycle_num,shift_pm,fit_calib,shift_am):
#    list0_dp = dac0_double(num_delays, delays, cycle_num, shift_am)
#    list1 = dac1_sample(lin_seq_2(), shift_pm, fit_calib)
#    list0_dp* + list1
#
#    dp_final_list = [i+j for i,j in zip(list1,list0_dp)]
#    return dp_final_list


#def seq_dacs_sp(num_delays,delays,cycle_num,shift_pm, shift_am):
#    list0_sp = dac0_single(cycle_num, shift_am)
#    list1 = dac1_sample(lin_seq_2(), shift_pm, 320)
#    for k in range (cycle_num):
#        sp_final_list = [i+j for i,j in zip(list1,list0_sp)]
#    return sp_final_list
#
#
#def seq_dacs_off():
#    cycle_num = 64
#    list0_off = dac0_off(cycle_num)
#    list1_off = dac1_off(cycle_num)
#    for k in range (cycle_num):
#        off_final_list = [i+j for i,j in zip(list1_off,list0_off)]
#    return off_final_list
#
#def seq_dac0_off(cycle_num,shift_pm):
#    list0_off = dac0_off(cycle_num)
#    list1 = dac1_sample(lin_seq_2(), shift_pm, 320)
#    for k in range (cycle_num):
#        off0_final_list = [i+j for i,j in zip(list1,list0_off)]
#    return off0_final_list
#
#def seq_dac1_off(num_delays,delays,cycle_num,shift_pm, shift_am):
#    list0_dp = dac0_double(num_delays, delays, cycle_num, shift_am)
#    list1_off = dac1_off(cycle_num)
#    for k in range (cycle_num):
#        off1_final_list = [i+j for i,j in zip(list1_off,list0_dp)]
#    return off1_final_list

#-----------------------Sequence Rng Gen----------------------------------------------

#def seq_rng_zero(dpram_max_addr):
#    ele = ['00000000']
#    list_rng_zero =  ele*int(dpram_max_addr/8)  
#    # Writes    
#    list_rng_zero_return = []
#    for x in list_rng_zero: 
#        list_rng_zero_return.append("0x{:08x}".format(int(x,16)))
#    # print(list_rng_zero_return)
#    return list_rng_zero_return

## def seq_rng_ddr0():
#def seq_rng_short(dpram_max_addr):
#    ele = ['00000000']
#    list_rng_short =  ['00000008'] + ele*int(dpram_max_addr/8 - 1)  
#    # Writes    
#    list_rng_short_return = []
#    for x in list_rng_short: 
#        list_rng_short_return.append("0x{:08x}".format(int(x,16)))
#    # print(list_rng_short_return)
#    return list_rng_short_return

def seq_rng_zeros():
    # a word is 32bit = 16 angles
    # angles are little endian but pairwise inversed: ...CDAB
    num_words = 400*80//16
    message = np.zeros(num_words, dtype=np.int32)
    return message

def seq_rng_all_one():
    # a word is 32bit = 16 angles
    num_words = 400*80//16
    word0 = 0b01010101010101010101010101010101
    message = np.zeros(num_words, dtype=np.uint32)
    message[:] = word0
    print("fake rng_seq_single written")
    return message

#def seq_rng_one_in_sixteen(shift=0):
#    # a word is 32bit = 16 angles
#    word = 1<<(shift*2)
#    message = np.zeros(4, dtype=np.int32)
#    for i in range(4):
#        message[i] = word
#    return message

def seq_rng_single(pos=0):
    # pseudo random requence of length 80 angles
    # a word is 32bit = 16 angles
    # angles are little endian but pairwise inversed: ...CDAB
    num_words_total = 400*80//16
    num_words = 5
    pos_inversed = (pos&0xfffffffe) + ((pos+1)%2)
    word0 = 1<<(2*pos_inversed)
    message = np.zeros(num_words_total, dtype=np.uint32)
    for i in range(num_words_total//num_words):
        message[i*num_words] = word0
    return message

def seq_rng_random():
    # pseudo random requence of length 80 angles
    # a word is 32bit = 16 angles
    num_words = 400*80//16
    message = np.random.randint(0, 1<<32, size=num_words, dtype='uint32')
    return message

def seq_rng_block1():
    # an 80 angle long block of angles nr 1, rest nr 0. Total length 400*80 qubits.
    # a word is 32bit = 16 angles
    num_words = 400*80//16
    message = np.zeros(num_words, dtype=np.uint32)
    word0 = 0b01010101010101010101010101010101
    message[:5] = word0
    return message

    

#def seq_rng_long(dpram_max_addr, non_zero_size):
#    ele = ['00000000']
#    ele_non_zero = ['aaaaaaaa']
#    # ele_non_zero0 = ['aaaaaaaa']
#    # ele_non_zero1 = ['000000aa']
#
#    x = non_zero_size%8
#    y = np.floor(non_zero_size/8)
#    if (x == 0):
#        list_non_zero = ele_non_zero*int(y)
#        list_rng_long = list_non_zero + ele*(int(dpram_max_addr/8) - int(y))
#    elif (x == 1):
#        list_non_zero = ele_non_zero*int(y) + ['0000000a']
#        list_rng_long = list_non_zero + ele*(int(dpram_max_addr/8) - int(y+1))
#    elif (x == 2):
#        list_non_zero = ele_non_zero*int(y) + ['000000aa']
#        list_rng_long = list_non_zero + ele*(int(dpram_max_addr/8) - int(y+1))
#    elif (x == 3):
#        list_non_zero = ele_non_zero*int(y) + ['00000aaa']
#        list_rng_long = list_non_zero + ele*(int(dpram_max_addr/8) - int(y+1))
#    elif (x == 4):
#        list_non_zero = ele_non_zero*int(y) + ['0000aaaa']
#        list_rng_long = list_non_zero + ele*(int(dpram_max_addr/8) - int(y+1))
#    elif (x == 5):
#        list_non_zero = ele_non_zero*int(y) + ['000aaaaa']
#        list_rng_long = list_non_zero + ele*(int(dpram_max_addr/8) - int(y+1))
#    elif (x == 6):
#        list_non_zero = ele_non_zero*int(y) + ['00aaaaaa']
#        list_rng_long = list_non_zero + ele*(int(dpram_max_addr/8) - int(y+1))
#    elif (x == 7):
#        list_non_zero = ele_non_zero*int(y) + ['0aaaaaaa']
#        list_rng_long = list_non_zero + ele*(int(dpram_max_addr/8) - int(y+1))
#
#    # list_rng_long =  ele_non_zero*int(non_zero_size/8) + ele*int(non_zero_size/8) + ele_non_zero*int(non_zero_size/8) + ele*(int(dpram_max_addr/8) - int(non_zero_size*3/8))  
#    # list_rng_long =  ele_non_zero*int(non_zero_size/8) + ele*(int(dpram_max_addr/8) - int(non_zero_size/8))  
#    # list_rng_long =  ele_non_zero0*2 + ele_non_zero1 + ele*(int(dpram_max_addr/8) - 3)  
#    # Writes    
#    list_rng_long_return = []
#    for x in list_rng_long: 
#        list_rng_long_return.append("0x{:08x}".format(int(x,16)))
#    # print(list_rng_long_return)
#    return list_rng_long_return



#def dac1_sample_old(seq, shift_pm,fit_calib):
#    list_dac1 = []
#    shift_pm = shift_pm + 1
#    # First 32 cycles, Delta_phi [+max to 0]
#    #seq = []
#    
#    newseq = seq
#    amp_max = 18000
#
#    newseq_int = np.array(np.round(newseq * amp_max + 32768), dtype=int)
#    newseq_int_inv = np.array(np.round(-newseq * amp_max + 32768), dtype=int)
#    arr_new = []
#
#    for i in range(newseq_int.shape[0]):
#        i_string = format(newseq_int[i],'016b')
#        i_string_inv = format(newseq_int_inv[i],'016b')
#        arr_new.extend(['1000000000000000',i_string,i_string,'1000000000000000','1000000000000000',i_string_inv,i_string_inv,'1000000000000000','1000000000000000','1000000000000000'])
#    list_dac1 = arr_new
#
#    #for i in range(int(cycle_num/2)):
#    #    # amp0 = 32768 + round(32767*(cycle_num/2 - i)/(cycle_num/2))
#    #    amp0 = round( 32768 + 18000*(cycle_num/2 - i)/(cycle_num/2))
#    #    amp_0_tmp.append(amp0)
#    #    amp0_bin = format(amp0,'016b')
#    #    # minus_amp0 = 32768 - round(32767*(cycle_num/2 - i)/(cycle_num/2))
#    #    minus_amp0 = round(32767 - 18000*(cycle_num/2 - i)/(cycle_num/2))
#    #    seq.append(amp0)
#    #    minus_amp0_bin = format(minus_amp0,'016b')
#    #    arr1 = ['1000000000000000',amp0_bin,amp0_bin,'1000000000000000','1000000000000000',minus_amp0_bin,minus_amp0_bin,'1000000000000000','1000000000000000','1000000000000000']
#    #    list_dac1.extend(arr1)
#    ## Last  32 cycle, Delta_phi [0 to -max]
#    #for j in range(int(cycle_num/2)):
#    #    # amp0 = 32768 + round(32767*j/(cycle_num/2))
#    #    amp0 = round(32768 + 18000*j/(cycle_num/2))
#    #    amp0_bin = format(amp0,'016b')
#    #    # minus_amp0 = 32768 - round(32767*j/(cycle_num/2))
#    #    minus_amp0 = round(32767 - 18000*j/(cycle_num/2))
#    #    amp_0_tmp.append(minus_amp0)
#    #    seq.append(amp0)
#    #    minus_amp0_bin = format(minus_amp0,'016b')
#    #    arr2 = ['1000000000000000',minus_amp0_bin,minus_amp0_bin,'1000000000000000','1000000000000000',amp0_bin,amp0_bin,'1000000000000000','1000000000000000','1000000000000000']
#    #    list_dac1.extend(arr2)
#
#    for i in range(fit_calib):
#        list_dac1.insert(0,list_dac1.pop())
#
#    for i in range(shift_pm):
#        list_dac1.insert(0,list_dac1.pop())
#    # Records data in the COE init dpram file
#    # file = open('sequence_dac1.txt', "w+")
#    # Writes	
#    list_dac1_return = []
#    for x in list_dac1:	
#        list_dac1_return.append("0x{:04x}".format(int(x,2)))
#        # file.write("0x{:04x}".format(int(x,2)))
#        # file.write('\n')
#    # file.close()
#    return list_dac1_return


#def dac0_single_old(cycle_num, shift_am):
#    arr_s0 = ['1111111111111111', '1110000000000000', '1101000000000000', '1100000000000000', '1011000000000000', '1010000000000000', '1001000000000000', '1000000000000000', '0011001001100111', '0011001001100111']
#    #arr_s0 = ['1110111011011001', '1110111011011001', '1100110110011000', '1100110110011000', '1100110110011000', '1100110110011000', '1100110110011000', '1000000000000000', '0011001001100111', '0011001001100111']
#
#    #arr0 = ['1111000000000000']*70
#    arr0 = ['1111111111111111']
#    #Generate list of 80 samples
#    # list_dac0 =   arr0*60 + arr_s0 + arr0*10   
#    list_dac0 = arr0*10 + arr_s0  
#    list_dac0_full = list_dac0 * int(cycle_num/2)
#    #print(list_dac0_full)
#
#    for i in range(shift_am):
#        list_dac0_full.insert(0,list_dac0_full.pop())
#
#    # Records data in the COE init dpram file
#    # file = open('sin_sequence_dac0_single.txt', "w+")
#    # Writes	
#    list_dac0_single_return = []
#    for x in list_dac0_full:	
#        list_dac0_single_return.append("{:04x}".format(int(x,2)))
#        # file.write("0x{:04x}".format(int(x,2)))
#        # file.write('\n')
#    # file.close()
#    return list_dac0_single_return
#
#def dac0_double_old(num_delays,delays,cycle_num, shift_am):
#    # Données initiales
#    time = np.array([0.02083333, 0.10416667, 0.14583333, 0.1875, 0.22916667, 0.27083333, 0.35416667, 0.39583333,
#                     0.4375, 0.47916667])
#
#    sinewave = np.array([-2.83779204e+04, 2.83779204e+04, 2.83779204e+04, 4.01292263e-12, -2.83779204e+04,
#            -2.83779204e+04, 2.83779204e+04, 2.83779204e+04, 1.20387679e-11, -2.83779204e+04])
#
#    # Calcul des nouvelles amplitudes
#
#    amplitude_1 = ((1 - abs(delays[0])) * 600)
#    amplitude_2 = ((1 - abs(delays[1])) * 600)
#
#    amplitudes_1 = (amplitude_1 * 32768) / 600
#    amplitudes_2 = (amplitude_2 * 32768) / 600
#
#    # Recalcul des amplitudes des points
#
#    # Déterminer les indices en fonction des signes de delays
#    indices = [1, 2, 6, 7] if delays[0] >= 0 and delays[1] >= 0 else \
#              [0, 9, 4, 5] if delays[0] < 0 and delays[1] < 0 else \
#              [1, 2, 4, 5] if delays[0] >= 0 and delays[1] < 0 else \
#              [0, 9, 6, 7]
#
#    # Recalculer les amplitudes pour les indices appropriés
#    sinewave[indices[0:2]] = amplitudes_1 * np.sin(2 * np.pi * 4 * time[indices[0:2]] - np.pi/2)
#    sinewave[indices[2:4]] = amplitudes_2 * np.sin(2 * np.pi * 4 * time[indices[2:4]] - np.pi/2)
#
#
#    # Tracer la sinusoïde après les modifications
#    # plt.plot(time, sinewave, "b:o", label="sin(x)")
#    # plt.show()
#    # Convertir chaque valeur analogique en hexadécimal
#    list_dac0 = [convert_analog_to_hex(x) for x in sinewave]
#    # plt.plot(time, list_dac0, "b:o", label="sin(x)")
#    # plt.show()
#    #print(list_dac0)
#
#    for i in range(shift_am):
#        list_dac0.insert(0,list_dac0.pop())
#
#    # Sauvegarder les données dans un fichier
#    # file = open('sin_sequence_dac0.txt', "w+")
#
#    # Écriture
#    list_dac0_return = []
#    for _ in range(cycle_num):
#        # for i, x in enumerate(list_dac0[:10]):
#            # file.write(f'0X0000{x}\n')
#        list_dac0_return.extend(list_dac0)
#    # file.close()
#    return list_dac0_return
