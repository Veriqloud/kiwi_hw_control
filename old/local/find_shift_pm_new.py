#!/bin/python
import numpy as np

max_diff_amplitude = 100
max_exceed_files = 3

def load_gc_amplitudes(j, party, gc_comp):
    if party == 'alice':
        data = np.loadtxt(f"pm_shift_data/pm_a_shift_{j}.txt", usecols=(2,3,4), dtype=np.int64)
    elif party == 'bob':
        data = np.loadtxt(f"pm_shift_data/pm_b_shift_{j}.txt", usecols=(2,3,4), dtype=np.int64)
    else:
        raise ValueError("Party must be 'alice' or 'bob'")

    gc = data[:, 0]
    r = data[:, 1]
    q_pos = data[:, 2]

    gc0 = (gc[r == 0]*2 + q_pos[r == 0] + gc_comp) % 64
    n0, _ = np.histogram(gc0, bins=64, range=(0, 64))
    n0[1::2] = n0[1::2][::-1]
    return n0

def detect_valid_gc_comps(party):
    valid_gc_comps = []

    for gc_comp in range(64):
        histos = []
        for i in range(10):
            histo = load_gc_amplitudes(i, party, gc_comp)
            histos.append(histo)

        histos = np.array(histos)
        exceed_count = 0

        for file_idx in range(10):
            signal = histos[file_idx]
            if any(abs(signal[i+1] - signal[i]) > max_diff_amplitude for i in range(63)):
                exceed_count += 1

        if exceed_count < max_exceed_files:
            valid_gc_comps.append(gc_comp)

    return valid_gc_comps

if __name__ == "__main__":
    valid_alice = detect_valid_gc_comps('alice')
    valid_bob   = detect_valid_gc_comps('bob')

    print("Valid GC_COMP values for Alice:", valid_alice)
    print("Valid GC_COMP values for Bob  :", valid_bob)
