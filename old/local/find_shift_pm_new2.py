#!/bin/python
import numpy as np

max_diff_amplitude = 150
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

        for signal in histos:
            if any(abs(signal[i+1] - signal[i]) > max_diff_amplitude for i in range(63)):
                exceed_count += 1

        if exceed_count < max_exceed_files:
            valid_gc_comps.append(gc_comp)

    return valid_gc_comps

def select_best_gc_comp(party, valid_gc_comps):
    gc_comp_stats = {}

    for gc_comp in valid_gc_comps:
        max_jumps = []

        for i in range(10):
            histo = load_gc_amplitudes(i, party, gc_comp)
            diffs = np.abs(np.diff(histo))
            max_jump = np.max(diffs)
            max_jumps.append(max_jump)

        avg_max_jump = np.mean(max_jumps)
        gc_comp_stats[gc_comp] = avg_max_jump

    best_gc_comp = min(gc_comp_stats, key=gc_comp_stats.get)
    return best_gc_comp, gc_comp_stats[best_gc_comp]

if __name__ == "__main__":
    for party in ['alice', 'bob']:
        valid_comps = detect_valid_gc_comps(party)
        print(f"Valid GC_COMP values for {party.capitalize()}: {valid_comps}")

        if valid_comps:
            best_gc, avg_jump = select_best_gc_comp(party, valid_comps)
            print(f"Best GC_COMP for {party.capitalize()} = {best_gc} (average max jump = {avg_jump:.2f})")
        else:
            print(f"No valid GC_COMP found for {party.capitalize()}.")
