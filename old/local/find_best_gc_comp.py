#!/bin/python
import numpy as np

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

def find_best_gc_comp(party):
    gc_comp_stats = {}

    for gc_comp in range(64):
        max_jumps = []

        for i in range(10):
            histo = load_gc_amplitudes(i, party, gc_comp)
            diffs = np.abs(np.diff(histo))
            max_jump = np.max(diffs)
            max_jumps.append(max_jump)

        avg_max_jump = np.mean(max_jumps)
        gc_comp_stats[gc_comp] = avg_max_jump

    best_gc_comp = min(gc_comp_stats, key=gc_comp_stats.get)
    best_avg_jump = gc_comp_stats[best_gc_comp]

    print(f"Best GC_COMP for {party.capitalize()} = {best_gc_comp} (average max jump = {best_avg_jump:.2f})")
    return best_gc_comp

if __name__ == "__main__":
    best_alice = find_best_gc_comp('alice')
#    best_bob   = find_best_gc_comp('bob')

    print("\nSummary:")
    print(f"  Alice: Best GC_COMP = {best_alice}")
#    print(f"  Bob  : Best GC_COMP = {best_bob}")
