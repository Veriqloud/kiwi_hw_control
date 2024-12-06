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


def dac1_sample(seq, shift_pm,fit_calib):
    list_dac1 = []
    # First 32 cycles, Delta_phi [+max to 0]
    #seq = []
    
    newseq = seq
    amp_max = 18000

    newseq_int = np.array(np.round(newseq * amp_max + 32768), dtype=int)
    newseq_int_inv = np.array(np.round(-newseq * amp_max + 32768), dtype=int)
    arr_new = []

    for i in range(newseq_int.shape[0]):
        i_string = format(newseq_int[i],'016b')
        i_string_inv = format(newseq_int_inv[i],'016b')
        arr_new.extend(['1000000000000000',i_string,i_string,'1000000000000000','1000000000000000',i_string_inv,i_string_inv,'1000000000000000','1000000000000000','1000000000000000'])
    list_dac1 = arr_new

    #for i in range(int(cycle_num/2)):
    #    # amp0 = 32768 + round(32767*(cycle_num/2 - i)/(cycle_num/2))
    #    amp0 = round( 32768 + 18000*(cycle_num/2 - i)/(cycle_num/2))
    #    amp_0_tmp.append(amp0)
    #    amp0_bin = format(amp0,'016b')
    #    # minus_amp0 = 32768 - round(32767*(cycle_num/2 - i)/(cycle_num/2))
    #    minus_amp0 = round(32767 - 18000*(cycle_num/2 - i)/(cycle_num/2))
    #    seq.append(amp0)
    #    minus_amp0_bin = format(minus_amp0,'016b')
    #    arr1 = ['1000000000000000',amp0_bin,amp0_bin,'1000000000000000','1000000000000000',minus_amp0_bin,minus_amp0_bin,'1000000000000000','1000000000000000','1000000000000000']
    #    list_dac1.extend(arr1)
    ## Last  32 cycle, Delta_phi [0 to -max]
    #for j in range(int(cycle_num/2)):
    #    # amp0 = 32768 + round(32767*j/(cycle_num/2))
    #    amp0 = round(32768 + 18000*j/(cycle_num/2))
    #    amp0_bin = format(amp0,'016b')
    #    # minus_amp0 = 32768 - round(32767*j/(cycle_num/2))
    #    minus_amp0 = round(32767 - 18000*j/(cycle_num/2))
    #    amp_0_tmp.append(minus_amp0)
    #    seq.append(amp0)
    #    minus_amp0_bin = format(minus_amp0,'016b')
    #    arr2 = ['1000000000000000',minus_amp0_bin,minus_amp0_bin,'1000000000000000','1000000000000000',amp0_bin,amp0_bin,'1000000000000000','1000000000000000','1000000000000000']
    #    list_dac1.extend(arr2)

    for i in range(fit_calib):
        list_dac1.insert(0,list_dac1.pop())

    for i in range(shift_pm):
        list_dac1.insert(0,list_dac1.pop())
    # Records data in the COE init dpram file
    # file = open('sequence_dac1.txt', "w+")
    # Writes	
    list_dac1_return = []
    for x in list_dac1:	
        list_dac1_return.append("0x{:04x}".format(int(x,2)))
        # file.write("0x{:04x}".format(int(x,2)))
        # file.write('\n')
    # file.close()
    return list_dac1_return

def dac1_off(cycle_num):
    arr1 = ['1000000000000000']
    #print(arr0)
    #Generate list of 80 samples
    list_dac1 =  arr1*10*cycle_num  

    # Records data in the COE init dpram file
    # file = open('sequence_dac1_off.txt', "w+")

    # Writes	
    list_dac1_off_return = []
    for x in list_dac1:	
        list_dac1_off_return.append("0x{:04x}".format(int(x,2)))
        # file.write("0x{:04x}".format(int(x,2)))
        # file.write('\n')
    # file.close()
    return list_dac1_off_return


def dac0_off(cycle_num):
    arr0 = ['1111111111111111']
    #print(arr0)
    #Generate list of 80 samples
    list_dac0 =  arr0*10*cycle_num  

    # Records data in the COE init dpram file
    # file = open('sin_sequence_dac0_off.txt', "w+")

    # Writes	
    list_dac0_off_return = []
    for x in list_dac0:	
        list_dac0_off_return.append("{:04x}".format(int(x,2)))
        # file.write("0x{:04x}".format(int(x,2)))
        # file.write('\n')
    # file.close()
    return list_dac0_off_return

def dac0_single(cycle_num, shift_am):
    arr_s0 = ['1111111111111111', '1110000000000000', '1101000000000000', '1100000000000000', '1011000000000000', '1010000000000000', '1001000000000000', '1000000000000000', '0011001001100111', '0011001001100111']
    #arr_s0 = ['1110111011011001', '1110111011011001', '1100110110011000', '1100110110011000', '1100110110011000', '1100110110011000', '1100110110011000', '1000000000000000', '0011001001100111', '0011001001100111']

    #arr0 = ['1111000000000000']*70
    arr0 = ['1111111111111111']
    #Generate list of 80 samples
    # list_dac0 =   arr0*60 + arr_s0 + arr0*10   
    list_dac0 = arr0*10 + arr_s0  
    list_dac0_full = list_dac0 * int(cycle_num/2)
    #print(list_dac0_full)

    for i in range(shift_am):
        list_dac0_full.insert(0,list_dac0_full.pop())

    # Records data in the COE init dpram file
    # file = open('sin_sequence_dac0_single.txt', "w+")
    # Writes	
    list_dac0_single_return = []
    for x in list_dac0_full:	
        list_dac0_single_return.append("{:04x}".format(int(x,2)))
        # file.write("0x{:04x}".format(int(x,2)))
        # file.write('\n')
    # file.close()
    return list_dac0_single_return

def dac0_single_10(cycle_num, shift_am):
    arr_s0 = ['1111111111111111', '1110000000000000', '1101000000000000', '1100000000000000', '1011000000000000', '1010000000000000', '1001000000000000', '1000000000000000', '0011001001100111', '0011001001100111']
    #arr_s0 = ['1110111011011001', '1110111011011001', '1100110110011000', '1100110110011000', '1100110110011000', '1100110110011000', '1100110110011000', '1000000000000000', '0011001001100111', '0011001001100111']

    #arr0 = ['1111000000000000']*70
    arr0 = ['1111111111111111']
    #Generate list of 80 samples
    list_dac0 =   arr0*60 + arr_s0 + arr0*10   
    # list_dac0 = arr0*10 + arr_s0  
    list_dac0_full = list_dac0 * int(cycle_num/2)
    #print(list_dac0_full)

    for i in range(shift_am):
        list_dac0_full.insert(0,list_dac0_full.pop())

    # Records data in the COE init dpram file
    # file = open('sin_sequence_dac0_single.txt', "w+")
    # Writes    
    list_dac0_single_return = []
    for x in list_dac0_full:    
        list_dac0_single_return.append("{:04x}".format(int(x,2)))
        # file.write("0x{:04x}".format(int(x,2)))
        # file.write('\n')
    # file.close()
    return list_dac0_single_return

def dac0_double_10(cycle_num, shift_am):
    arr_s0 = ['1111111111111111', '1110000000000000', '1101000000000000', '1100000000000000', '1011000000000000', '1010000000000000', '1001000000000000', '1000000000000000', '0011001001100111', '0011001001100111']
    #arr_s0 = ['1110111011011001', '1110111011011001', '1100110110011000', '1100110110011000', '1100110110011000', '1100110110011000', '1100110110011000', '1000000000000000', '0011001001100111', '0011001001100111']

    #arr0 = ['1111000000000000']*70
    arr0 = ['1111111111111111']
    #Generate list of 80 samples
    list_dac0 =  arr_s0 + arr0*50 + arr_s0 + arr0*10   
    # list_dac0 = arr0*10 + arr_s0  
    list_dac0_full = list_dac0 * int(cycle_num/2)
    #print(list_dac0_full)

    for i in range(shift_am):
        list_dac0_full.insert(0,list_dac0_full.pop())

    # Records data in the COE init dpram file
    # file = open('sin_sequence_dac0_single.txt', "w+")
    # Writes    
    list_dac0_single_return = []
    for x in list_dac0_full:    
        list_dac0_single_return.append("{:04x}".format(int(x,2)))
        # file.write("0x{:04x}".format(int(x,2)))
        # file.write('\n')
    # file.close()
    return list_dac0_single_return

def dac0_double(num_delays,delays,cycle_num, shift_am):
    # Données initiales
    time = np.array([0.02083333, 0.10416667, 0.14583333, 0.1875, 0.22916667, 0.27083333, 0.35416667, 0.39583333,
                     0.4375, 0.47916667])

    sinewave = np.array([-2.83779204e+04, 2.83779204e+04, 2.83779204e+04, 4.01292263e-12, -2.83779204e+04,
            -2.83779204e+04, 2.83779204e+04, 2.83779204e+04, 1.20387679e-11, -2.83779204e+04])

    # Calcul des nouvelles amplitudes

    amplitude_1 = ((1 - abs(delays[0])) * 600)
    amplitude_2 = ((1 - abs(delays[1])) * 600)

    amplitudes_1 = (amplitude_1 * 32768) / 600
    amplitudes_2 = (amplitude_2 * 32768) / 600

    # Recalcul des amplitudes des points

    # Déterminer les indices en fonction des signes de delays
    indices = [1, 2, 6, 7] if delays[0] >= 0 and delays[1] >= 0 else \
              [0, 9, 4, 5] if delays[0] < 0 and delays[1] < 0 else \
              [1, 2, 4, 5] if delays[0] >= 0 and delays[1] < 0 else \
              [0, 9, 6, 7]

    # Recalculer les amplitudes pour les indices appropriés
    sinewave[indices[0:2]] = amplitudes_1 * np.sin(2 * np.pi * 4 * time[indices[0:2]] - np.pi/2)
    sinewave[indices[2:4]] = amplitudes_2 * np.sin(2 * np.pi * 4 * time[indices[2:4]] - np.pi/2)


    # Tracer la sinusoïde après les modifications
    # plt.plot(time, sinewave, "b:o", label="sin(x)")
    # plt.show()
    # Convertir chaque valeur analogique en hexadécimal
    list_dac0 = [convert_analog_to_hex(x) for x in sinewave]
    # plt.plot(time, list_dac0, "b:o", label="sin(x)")
    # plt.show()
    #print(list_dac0)

    for i in range(shift_am):
        list_dac0.insert(0,list_dac0.pop())

    # Sauvegarder les données dans un fichier
    # file = open('sin_sequence_dac0.txt', "w+")

    # Écriture
    list_dac0_return = []
    for _ in range(cycle_num):
        # for i, x in enumerate(list_dac0[:10]):
            # file.write(f'0X0000{x}\n')
        list_dac0_return.extend(list_dac0)
    # file.close()
    return list_dac0_return

def seq_dacs_dp(num_delays,delays,cycle_num,shift_pm,fit_calib,shift_am):
    list0_dp = dac0_double(num_delays, delays, cycle_num, shift_am)
    list1 = dac1_sample(lin_seq_2(), shift_pm, fit_calib)
    for k in range (cycle_num):
        dp_final_list = [i+j for i,j in zip(list1,list0_dp)]
    return dp_final_list

def seq_dacs_dp_10(cycle_num, shift_pm, shift_am):
    list0_dp = dac0_double_10(cycle_num, shift_am)
    list1 = dac1_sample(lin_seq_2(), shift_pm, 320)
    for k in range (cycle_num):
        dp_final_list = [i+j for i,j in zip(list1,list0_dp)]
    return dp_final_list

def seq_dacs_sp(num_delays,delays,cycle_num,shift_pm, shift_am):
    list0_sp = dac0_single(cycle_num, shift_am)
    list1 = dac1_sample(lin_seq_2(), shift_pm, 320)
    for k in range (cycle_num):
        sp_final_list = [i+j for i,j in zip(list1,list0_sp)]
    return sp_final_list

def seq_dacs_sp_10(cycle_num,shift_pm, shift_am):
    list0_sp = dac0_single_10(cycle_num, shift_am)
    list1 = dac1_sample(lin_seq_2(), shift_pm), 320
    for k in range (cycle_num):
        sp_final_list = [i+j for i,j in zip(list1,list0_sp)]
    return sp_final_list

def seq_dacs_off(cycle_num):
    list0_off = dac0_off(cycle_num)
    list1_off = dac1_off(cycle_num)
    for k in range (cycle_num):
        off_final_list = [i+j for i,j in zip(list1_off,list0_off)]
    return off_final_list

def seq_dac0_off(cycle_num,shift_pm):
    list0_off = dac0_off(cycle_num)
    list1 = dac1_sample(lin_seq_2(), shift_pm, 320)
    for k in range (cycle_num):
        off0_final_list = [i+j for i,j in zip(list1,list0_off)]
    return off0_final_list

def seq_dac1_off(num_delays,delays,cycle_num,shift_pm, shift_am):
    list0_dp = dac0_double(num_delays, delays, cycle_num, shift_am)
    list1_off = dac1_off(cycle_num)
    for k in range (cycle_num):
        off1_final_list = [i+j for i,j in zip(list1_off,list0_dp)]
    return off1_final_list

#-----------------------Sequence Rng Gen----------------------------------------------

def seq_rng_zero(dpram_max_addr):
    ele = ['00000000']
    list_rng_zero =  ele*int(dpram_max_addr/8)  
    # Writes    
    list_rng_zero_return = []
    for x in list_rng_zero: 
        list_rng_zero_return.append("0x{:08x}".format(int(x,16)))
    # print(list_rng_zero_return)
    return list_rng_zero_return

# def seq_rng_ddr0():
def seq_rng_short(dpram_max_addr):
    ele = ['00000000']
    list_rng_short =  ['00000008'] + ele*int(dpram_max_addr/8 - 1)  
    # Writes    
    list_rng_short_return = []
    for x in list_rng_short: 
        list_rng_short_return.append("0x{:08x}".format(int(x,16)))
    # print(list_rng_short_return)
    return list_rng_short_return

def seq_rng_long(dpram_max_addr, non_zero_size):
    ele = ['00000000']
    ele_non_zero = ['aaaaaaaa']
    # ele_non_zero0 = ['aaaaaaaa']
    # ele_non_zero1 = ['000000aa']

    x = non_zero_size%8
    y = np.floor(non_zero_size/8)
    if (x == 0):
        list_non_zero = ele_non_zero*int(y)
        list_rng_long = list_non_zero + ele*(int(dpram_max_addr/8) - int(y))
    elif (x == 1):
        list_non_zero = ele_non_zero*int(y) + ['0000000a']
        list_rng_long = list_non_zero + ele*(int(dpram_max_addr/8) - int(y+1))
    elif (x == 2):
        list_non_zero = ele_non_zero*int(y) + ['000000aa']
        list_rng_long = list_non_zero + ele*(int(dpram_max_addr/8) - int(y+1))
    elif (x == 3):
        list_non_zero = ele_non_zero*int(y) + ['00000aaa']
        list_rng_long = list_non_zero + ele*(int(dpram_max_addr/8) - int(y+1))
    elif (x == 4):
        list_non_zero = ele_non_zero*int(y) + ['0000aaaa']
        list_rng_long = list_non_zero + ele*(int(dpram_max_addr/8) - int(y+1))
    elif (x == 5):
        list_non_zero = ele_non_zero*int(y) + ['000aaaaa']
        list_rng_long = list_non_zero + ele*(int(dpram_max_addr/8) - int(y+1))
    elif (x == 6):
        list_non_zero = ele_non_zero*int(y) + ['00aaaaaa']
        list_rng_long = list_non_zero + ele*(int(dpram_max_addr/8) - int(y+1))
    elif (x == 7):
        list_non_zero = ele_non_zero*int(y) + ['0aaaaaaa']
        list_rng_long = list_non_zero + ele*(int(dpram_max_addr/8) - int(y+1))

    # list_rng_long =  ele_non_zero*int(non_zero_size/8) + ele*int(non_zero_size/8) + ele_non_zero*int(non_zero_size/8) + ele*(int(dpram_max_addr/8) - int(non_zero_size*3/8))  
    # list_rng_long =  ele_non_zero*int(non_zero_size/8) + ele*(int(dpram_max_addr/8) - int(non_zero_size/8))  
    # list_rng_long =  ele_non_zero0*2 + ele_non_zero1 + ele*(int(dpram_max_addr/8) - 3)  
    # Writes    
    list_rng_long_return = []
    for x in list_rng_long: 
        list_rng_long_return.append("0x{:08x}".format(int(x,16)))
    # print(list_rng_long_return)
    return list_rng_long_return

# seq_rng_zero(8)
# seq_rng_long(64)
# seq_rng_long(64,8)

# def concat_dacs(num_delays,delays,cycle_num,shift_pm, shift_am):
#     list0_dp = dac0_double(num_delays, delays, cycle_num, shift_am)
#     list0_sp = dac0_single(cycle_num, shift_am)
#     list0_off = dac0_off(cycle_num)
#     list1_off = dac1_off(cycle_num)
#     #print(list0)
#     list1 = dac1_sample(cycle_num, shift_pm)
#     # print(list1)

#     for k in range (cycle_num):
#         dp_final_list = [i+j for i,j in zip(list1,list0_dp)]
#         sp_final_list = [i+j for i,j in zip(list1,list0_sp)]
#         off_final_list = [i+j for i,j in zip(list1_off,list0_off)]
#         off0_final_list = [i+j for i,j in zip(list1,list0_off)]
#         off1_final_list = [i+j for i,j in zip(list1_off,list0_dp)]

#     dp_file_o = open('seq_dacs_dp.txt','w+')
#     sp_file_o = open('seq_dacs_sp.txt','w+')
#     off_file_o = open('seq_dacs_off.txt','w+')
#     off0_file_o = open('seq_dac0_off.txt','w+')
#     off1_file_o = open('seq_dac1_off.txt','w+')

#     for ele in dp_final_list:
#         dp_file_o.write(ele +'\n')
#     for ele in sp_final_list:
#         sp_file_o.write(ele +'\n')
#     for ele in off_final_list:
#         off_file_o.write(ele +'\n')
#     for ele in off0_final_list:
#         off0_file_o.write(ele +'\n')
#     for ele in off1_final_list:
#         off1_file_o.write(ele +'\n')
#     dp_file_o.close()
#     sp_file_o.close()
#     off_file_o.close()
#     off0_file_o.close()
#     off1_file_o.close()


# def main():
#     parser = argparse.ArgumentParser(description='Generate sinewaves based on user input')
#     # parser.add_argument('--num_delays', type=int, choices=[1, 2], default=1, help='Number of delays (1 or 2)')
#     parser.add_argument('--delays', type=float, nargs='+', help='Delay values (should be in the range [-1, 1])')
#     parser.add_argument('--shift_pm', type=int, nargs=1,metavar=('shift_pm'), help='shift samples of dac1, in the range [0..10])')
#     parser.add_argument('--shift_am', type=int, nargs=1,metavar=('shift_am'), help='shift samples of dac0, in the range [0..10])')
#     # parser.add_argument('--cycle_num', type=int, nargs=1,metavar=('cycle_num'), help='cycle values (should be in the range [1..20])')

#     args = parser.parse_args()

#     # num_delays = args.num_delays
#     num_delays = 2
#     shift_pm = int(args.shift_pm[0])
#     shift_am = int(args.shift_am[0])
#     # cycle_num = int(args.cycle_num[0])
#     cycle_num = 64

#     if args.delays is None or len(args.delays) != num_delays:
#         print(f"Error: Please provide {num_delays} delay value(s).")
#         parser.print_help()
#         return
#     # Si l'utilisateur fournit un nombre de délais autre que 1 ou 2, définir num_delays à 1 par défaut
#     if num_delays not in [1, 2]:
#         num_delays = 1

#     # Si un seul délai est fourni, dupliquer sa valeur pour le deuxième délai
#     if num_delays == 1:
#         delays.append(delays[0])

#     # Vérifier et ajuster les valeurs de delay
#     delays = [max(-1, min(1, delay)) for delay in args.delays]
# #------------MERGE DACS SAMPLES-----------------------------------
#     dac1_sample(cycle_num, shift_pm)
#     dac1_off(cycle_num)
#     dac0_off(cycle_num)
#     dac0_single(cycle_num, shift_am)
#     dac0_double(num_delays,delays,cycle_num, shift_am)
#     concat_dacs(num_delays,delays,cycle_num,shift_pm, shift_am)

# if __name__ == "__main__":
#     main()
