"""Timing analysis for Bob's TDC histograms.

Pure functions: nothing here touches the hardware, so it can be exercised
offline against recorded time tags.

Units
-----
A TDC time tag counts 20 ps steps.  The names below are the ones used
throughout: `units` always means 20 ps steps, `slots` means the 1.25 ns step of
`am_shift`, `ps` means picoseconds.

    PERIOD      625 units    12.5 ns   one 80 MHz period, the frame the gates
                                       and the whole double-pulse comb live in
    SP_FRAME   1250 units    25.0 ns   the single-pulse repetition, two periods
    SLOT         62.5 units   1.25 ns  one dac0 sample, one am_shift step
    GATE_SLOT    52.0833      1.0417   one bit of the 12-bit APD gate pattern

The single-pulse geometry
-------------------------
Alice sends one pulse per SP_FRAME.  Bob's unbalanced Mach-Zehnder splits it
into two arrivals `t1` apart (the ~1 m arm), and its two complementary output
ports are recombined onto the one detector through a ~2 m delay `t2`.  Four
arrivals per frame result:

    p0,   p0+t1,   p0+t2,   p0+t1+t2

so `t1` and `t2` are read straight off the histogram, and everything the double
pulse does follows from them.  In double mode Alice emits a pair separated by
`d`; with `d == t1` the eight arrivals collapse to a five-peak comb, of which
the two that carry the interference -- one per output port -- sit at

    p0+t1   and   p0+t1+t2

which is where the two soft gates belong.  Their separation is `t2` modulo the
period, and that separation is what the physical APD gate has to span.
"""

import numpy as np

UNIT_PS = 20.0
PERIOD = 625                  # units, 12.5 ns
SP_FRAME = 2 * PERIOD         # units, 25 ns
SLOT = 62.5                   # units per am_shift step (1.25 ns)
SLOTS_PER_PERIOD = 10
GATE_SLOTS = 12               # bits in the APD gate pattern
GATE_SLOT = PERIOD / GATE_SLOTS   # units per gate slot (1.0417 ns)


# --------------------------------------------------------------- histograms --

def fold(times, frame=SP_FRAME, binw=2):
    """Histogram of time tags folded into one `frame`, `binw` units per bin."""
    t = np.asarray(times, dtype=float) % frame
    nbins = int(round(frame / binw))
    h, _ = np.histogram(t, bins=np.arange(nbins + 1) * float(binw))
    return h.astype(float)


def baseline(h):
    """Pedestal level of a folded histogram.

    The median of the *occupied* bins, which is right in both modes this code
    has to cope with.  Free-running, every bin is occupied and the median is the
    70-80% flat pedestal a healthy histogram sits on.  Gated, most of the period
    is hard zero; a median over all bins would then be 0, every occupied bin
    would count as signal, and every threshold built on it would degenerate.
    """
    occupied = h[h > 0]
    return float(np.median(occupied)) if occupied.size else 0.0


def _runs(mask):
    """Start/stop index pairs of the True runs in `mask`, wrap included."""
    if not mask.any():
        return []
    if mask.all():
        return [(0, len(mask))]
    # Rotate so index 0 is outside a run, then unrotate the results.
    off = int(np.argmin(mask))
    m = np.roll(mask, -off)
    edges = np.diff(np.concatenate(([0], m.view(np.int8), [0])))
    starts = np.where(edges == 1)[0]
    stops = np.where(edges == -1)[0]
    return [((s + off) % len(mask), (e + off - 1) % len(mask) + 1)
            for s, e in zip(starts, stops)]


def find_peaks(h, binw=2, k=4.0, min_gap=3, min_area_frac=0.01, nmax=None):
    """Peaks of a folded histogram, as centroids in units.

    Returns (peaks, base) where each peak is a dict with 'pos' (units),
    'area' (excess counts) and 'height' (excess counts in its tallest bin).

    Centroids of the baseline-subtracted excess, not argmax bins: on these
    histograms that is worth about 0.05 slot on a strong peak against a full
    bin for the argmax, and it is what makes t1 and t2 repeatable.
    """
    h = np.asarray(h, dtype=float)
    base = baseline(h)
    thr = base + max(k * np.sqrt(max(base, 1.0)), 3.0)
    excess = np.clip(h - base, 0.0, None)

    runs = _runs(h > thr)
    if not runs:
        return [], base

    # A run that crosses the end of the frame comes back with its end before its
    # start; carry it past the end so every index range below is monotonic.
    # Without this such a peak spans an empty range, weighs nothing and is
    # dropped -- and a peak lands there routinely, because putting the comb near
    # the start of the period is exactly what gate placement does.
    runs = [(s, e if e > s else e + len(h)) for s, e in runs]

    # Merge runs separated by less than min_gap bins -- one pulse can dip below
    # threshold in its middle when the statistics are thin.
    runs.sort()
    merged = []
    for s, e in runs:
        if merged and s - merged[-1][1] < min_gap:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    if (len(merged) > 1 and
            (merged[0][0] + len(h) - merged[-1][1]) < min_gap):
        merged[0] = (merged[-1][0] - len(h), merged[0][1])
        merged.pop()

    total = excess.sum()
    peaks = []
    for s, e in merged:
        idx = np.arange(s - 1, e + 1)
        w = excess[idx % len(h)]
        if w.sum() <= 0 or (total > 0 and w.sum() < min_area_frac * total):
            continue
        pos = float((idx * w).sum() / w.sum() + 0.5) * binw
        peaks.append({'pos': pos % (len(h) * binw),
                      'area': float(w.sum()),
                      'height': float(w.max())})

    peaks.sort(key=lambda p: -p['area'])
    if nmax is not None:
        peaks = peaks[:nmax]
    peaks.sort(key=lambda p: p['pos'])
    return peaks, base


def pedestal_profile(h, k=21, q=25.0):
    """`h` with its pulses filtered out, leaving the shape of the gate window.

    The window is measured with Alice still carving, and the pulses inside it
    are many times taller than the pedestal that maps it -- so a width taken
    against the raw maximum measures a *pulse* and comes out the same fraction
    of a nanosecond for every gate width.

    A running median is not enough either: a pulse spanning more than half the
    kernel takes the median with it.  So a low quantile first, which pulses
    cannot lift because they only ever add counts; then the bins they occupy are
    marked against that floor and the profile is the local mean of what is left.
    That keeps the pedestal level unbiased, which a quantile on its own would
    not be.
    """
    h = np.asarray(h, dtype=float)
    k = int(k) | 1
    idx = (np.arange(len(h))[:, None] + np.arange(k) - k // 2) % len(h)
    win = h[idx]
    coarse = np.percentile(win, q, axis=1)
    is_peak = h > coarse + 5.0 * np.sqrt(np.maximum(coarse, 1.0))
    keep = ~is_peak[idx]
    n = keep.sum(axis=1)
    total = np.where(keep, win, 0.0).sum(axis=1)
    return np.where(n > 0, total / np.maximum(n, 1), coarse)


def half_width(profile, binw=2):
    """Width in units over which `profile` is at least half its maximum."""
    p = np.asarray(profile, dtype=float)
    return float((p > 0.5 * p.max()).sum()) * binw if p.max() > 0 else 0.0


def support(h, binw=2, frac=0.15):
    """(start, width) in units of the occupied region of a gated histogram.

    Gated, the histogram is hard zero outside the APD gate window, so its
    support *is* the window -- measured with the pedestal as the probe, which
    needs no CW light and no am_bias excursion.  Returns None if the histogram
    is not gated (nothing is zero) or is empty.
    """
    h = np.asarray(h, dtype=float)
    base = baseline(h)
    if base <= 0:
        return None
    inside = h > frac * base
    if inside.all() or not inside.any():
        return None
    runs = _runs(inside)
    s, e = max(runs, key=lambda r: (r[1] - r[0]) % len(h) or len(h))
    width = (e - s) % len(h) or len(h)
    return float((s * binw) % (len(h) * binw)), float(width * binw)


def top_hat(h, binw=2):
    """Area/peak width in units -- the width of the rectangle of equal area.

    The APD gate profile is sharply peaked rather than flat-topped, so a 50%
    width says very little about how much of a pulse it actually collects.
    """
    h = np.asarray(h, dtype=float)
    excess = np.clip(h - baseline(h), 0.0, None)
    peak = excess.max()
    return float(excess.sum() / peak * binw) if peak > 0 else 0.0


def align(h_ref, h_new, binw=2):
    """Circular shift in units that carries `h_ref` onto `h_new`.

    Cross-correlation over the whole histogram rather than a peak-to-peak
    difference, so it works on the free-running/gated comparison where the two
    histograms do not have the same peaks visible.
    """
    a = np.asarray(h_ref, float) - np.mean(h_ref)
    b = np.asarray(h_new, float) - np.mean(h_new)
    c = np.fft.irfft(np.fft.rfft(b) * np.conj(np.fft.rfft(a)), n=len(a))
    k = int(np.argmax(c))
    y0, y1, y2 = c[(k - 1) % len(c)], c[k], c[(k + 1) % len(c)]
    denom = y0 - 2 * y1 + y2
    frac = 0.5 * (y0 - y2) / denom if denom != 0 else 0.0
    return ((k + frac) % len(c)) * binw


# ------------------------------------------------------ single-pulse solution --

def solve_single_pulse(positions, frame=SP_FRAME):
    """Read p0, t1 and t2 off the four single-pulse arrivals.

    The four arrivals are the sumset {0, t1} + {0, t2} offset by p0, so exactly
    one of them is the one whose three offsets to the others satisfy
    `third == first + second`.  Testing that identity picks p0 out without
    relying on which gap happens to be the largest, which matters because
    t2 ~ 2*t1 makes the four peaks very nearly equally spaced.

    Returns a dict with p0, t1, t2, the predicted-vs-measured residual on the
    fourth peak, and the same in ns.
    """
    pos = sorted(float(p) % frame for p in positions)
    if len(pos) != 4:
        raise ValueError(f"need 4 single-pulse peaks, got {len(pos)}")

    # The four arrivals span t1+t2 of the frame and leave the rest empty, so the
    # gap that closes the cycle is much the largest and the peak after it is p0.
    # The sumset identity alone does not decide it: t2 ~ 2*t1 puts the peaks on
    # a nearly uniform grid, where several rotations satisfy z == x + y equally
    # well, and one of them reports t2 as t1+t2.
    def rotation(p0):
        off = sorted((p - p0) % frame for p in pos)
        return off[1], off[2], off[3], abs(off[3] - (off[1] + off[2]))

    # The four arrivals span t1+t2 and leave the rest of the frame empty, so the
    # gap that closes the cycle is the largest and the peak after it is p0.
    gaps = [(pos[(i + 1) % 4] - pos[i]) % frame for i in range(4)]
    wrap = int(np.argmax(gaps))
    gap_margin = gaps[wrap] / max(g for i, g in enumerate(gaps) if i != wrap)
    p0 = pos[(wrap + 1) % 4]

    # Cross-check it against the model's own identity, third offset == first
    # plus second.  The two tests fail in opposite regimes -- the gap test gets
    # weak when the arms are long enough to fill the frame, the identity gets
    # degenerate when the peaks are near uniform -- so the gap answer stands
    # unless the identity positively contradicts it.
    def close(a, b):
        return a <= max(3 * b, b + 8)

    residuals = {c: rotation(c)[3] for c in pos}
    best = min(residuals.values())
    ambiguous = False
    if not close(residuals[p0], best):
        p0 = min(residuals, key=residuals.get)
        rest = sorted(v for c, v in residuals.items() if c != p0)
        ambiguous = bool(rest) and close(rest[0], residuals[p0])

    t1, t2, tsum, res = rotation(p0)

    return {
        'p0': p0, 't1': t1, 't2': t2, 'sum': tsum, 'residual': res,
        'gap_margin': gap_margin, 'ambiguous': ambiguous,
        'p0_ns': p0 * UNIT_PS / 1000.0,
        't1_ns': t1 * UNIT_PS / 1000.0,
        't2_ns': t2 * UNIT_PS / 1000.0,
        'residual_ns': res * UNIT_PS / 1000.0,
        'ratio': t2 / t1 if t1 else float('nan'),
    }


def check_single_pulse(sol, residual_max=15.0, ratio_range=(1.5, 2.5)):
    """Complaints about a solve_single_pulse result, empty list if it is sane.

    The residual is the model's own consistency test and costs nothing; the
    ratio catches a mis-assignment of t1 and t2, which cannot happen for a 1 m
    and a 2 m arm but can happen on a histogram with a spurious peak.
    """
    bad = []
    if sol['residual'] > residual_max:
        bad.append(f"p0+t1+t2 misses the fourth peak by {sol['residual_ns']:.2f} ns")
    lo, hi = ratio_range
    if not lo <= sol['ratio'] <= hi:
        bad.append(f"t2/t1 = {sol['ratio']:.2f}, outside [{lo}, {hi}]")
    if sol.get('ambiguous'):
        bad.append(f"the empty part of the frame is only "
                   f"{sol['gap_margin']:.2f}x the largest gap between arrivals "
                   f"and the sumset does not separate the rotations either, so "
                   f"p0 is not identified")
    return bad


# ------------------------------------------------------------ gate placement --

def gate_pair(t1, t2, frame=PERIOD):
    """Where the two interfering peaks sit relative to p0, and how far apart.

    Returns (first, second, forward, arc).  `first` is port A at p0+t1, `second`
    is port B at p0+t1+t2, `forward` is how far port B trails port A within the
    period, and `arc` is the short way round between them.

    **The order is not free.** Port B's photon leaves the same double pulse as
    port A's and arrives `t2` later, so the two are logically one event and the
    FPGA must be able to give them the same double-pulse index. That happens
    only when both land in the same period, i.e. when port A is early enough
    that `target + forward` still fits inside the frame -- which is why one soft
    gate belongs at the start of the period and the other near its end.

    Folding to the short arc instead would put the two windows side by side and
    look tidier, but the earlier of them would then be catching port B of the
    *previous* double pulse. `arc` is still what the physical APD gate has to
    span, since that gate is periodic and does not care which pulse a click is
    attributed to.
    """
    first = t1 % frame
    second = (t1 + t2) % frame
    forward = (second - first) % frame
    return first, second, forward, min(forward, frame - forward)


def gate_target_fits(target, forward, soft_w, frame=PERIOD):
    """Whether both soft gate windows fit in one period at this target.

    The soft gate registers hold a start and a width and do not wrap, and both
    windows have to sit inside the same period for the pair to share a
    double-pulse index.
    """
    return (target - soft_w / 2.0 >= 0
            and target + forward + soft_w / 2.0 <= frame)


def comb_offsets(t1, t2, d=None, frame=PERIOD, merge=8.0):
    """Folded positions of the merged double-pulse comb, and their weights.

    The eight arrivals are i*d + j*t1 + k*t2 over i, j, k in {0, 1}; with
    d == t1 two pairs coincide, leaving six places with weights
    [1, 2, 1, 1, 2, 1].  Two more merge whenever t2 is close to 2*t1, which is
    why the comb usually shows five peaks with the [1, 2, 2, 1, 2] pattern.

    Built from the *measured* t2 rather than an assumed 2*t1: that is what makes
    the gaps uneven, and the uneven gaps are what identify the comb.

    Returns (offsets, weights).
    """
    d = t1 if d is None else d
    acc = {}
    for a in (0.0, d):
        for b in (0.0, t1):
            for c in (0.0, t2):
                acc[(a + b + c) % frame] = acc.get((a + b + c) % frame, 0) + 1
    offs, wts = [], []
    for v in sorted(acc):
        if offs and (v - offs[-1]) < merge:
            wts[-1] += acc[v]
        else:
            offs.append(v)
            wts.append(acc[v])
    if len(offs) > 1 and (offs[0] + frame - offs[-1]) < merge:
        wts[0] += wts.pop()
        offs.pop()
    return offs, wts


def comb_origin(peaks, offsets, weights=None, frame=PERIOD, prior=None,
                tol=1.5, amp_penalty=30.0, match=12.0):
    """Where the comb starts, by matching its whole shape to the peaks found.

    Every rotation that puts some measured peak on some predicted offset is
    scored by how well the *rest* of the comb then lands on measured peaks.
    That is what distinguishes the rotations: the gaps are uneven because t2 is
    not exactly 2*t1, so only one alignment fits them all.

    Picking the peak nearest a prediction does not survive here -- system1's
    comb is nearly uniform, its peaks 2.5 ns apart, so a prediction off by more
    than 1.25 ns silently selects a neighbour and both gates end up one comb
    position out.

    The gaps alone separate the alignments by only a couple of units, so the
    weights are used too: the singly-occupied positions carry about half the
    light of the doubled ones, and an alignment that puts the strong peaks on
    the weak positions is wrong however well its gaps fit.  Comparing the two
    groups' means rather than peak by peak keeps that true while the two
    interfering peaks breathe with the interferometer phase -- they trade light
    with each other, so their mean holds still even as each one moves.

    `peaks` is a sequence of (position, area).  `prior` breaks ties only, and
    should be passed only when it is genuinely known -- a stale one is worse
    than none, since it pulls a correct fit onto its neighbour.

    Returns (origin, score, margin): score is the mean miss in units, margin how
    much worse the best rejected alignment was.
    """
    if not peaks or not offsets:
        raise ValueError("comb_origin needs at least one peak and one offset")
    pos = [float(p[0]) for p in peaks]
    area = [float(p[1]) for p in peaks]

    def evaluate(origin):
        errs, got = [], []
        for o in offsets:
            want = (origin + o) % frame
            d = [min((q - want) % frame, (want - q) % frame) for q in pos]
            k = int(np.argmin(d))
            errs.append(d[k])
            got.append(area[k] if d[k] <= match else 0.0)
        # Drop the worst: one comb member can be extinguished by the
        # interferometer phase, or fall outside the APD gate.
        pos_err = float(np.mean(sorted(errs)[:max(1, len(errs) - 1)]))
        if not weights:
            return pos_err
        single = [g for g, w in zip(got, weights) if w <= 1]
        double = [g for g, w in zip(got, weights) if w > 1]
        if not single or not double:
            return pos_err
        m1, m2 = float(np.mean(single)), float(np.mean(double))
        # Negative when the light sits where it should; only the wrong sign is
        # penalised, so a faithful alignment is never pushed around by amplitude.
        return pos_err + amp_penalty * max(0.0, (m1 - m2) / (m1 + m2 + 1e-9))

    cands = sorted({round((p - o) % frame, 3) for p in pos for o in offsets})
    scored = sorted((evaluate(c), c) for c in cands)
    best = scored[0][0]
    close = [c for sc, c in scored if sc <= max(best * tol, best + 2.0)]
    if prior is not None and len(close) > 1:
        origin = min(close, key=lambda c: min((c - prior) % frame,
                                              (prior - c) % frame))
    else:
        origin = close[0]
    rejected = [sc for sc, c in scored if c not in close]
    margin = (rejected[0] - best) if rejected else float('inf')
    return origin, evaluate(origin), margin


def gate_slot_candidates(span, window_per_slot=None, margin=SLOT):
    """Gate widths, in pattern slots, that could hold a pair `span` units apart.

    `window_per_slot` is the measured `apd.gate` table: how far each pattern
    width lets the gate pass anything.  It is needed because the detection
    window bears little relation to the nominal pattern -- on system1 a 10-slot,
    10.42 ns pattern passes under 6 ns -- so the nominal width would choose a
    gate far too narrow.  `margin` is the room the pair wants beyond its own
    separation: a pulse is a few hundred ps wide and the placement good to about
    as much again.

    The support is a generous measure -- a pulse at that extreme edge is
    detected poorly -- so this returns every width that could work, narrowest
    first, and the caller picks between them by what they actually capture.
    Without a table it falls back to the nominal widths, which will under-open
    the gate; measure the table.
    """
    need = span + margin
    if window_per_slot:
        ok = [w for w in sorted(window_per_slot) if window_per_slot[w] >= need]
        return ok or [max(window_per_slot)]
    return [w for w in range(1, GATE_SLOTS) if w * GATE_SLOT >= need] or [GATE_SLOTS - 1]


def gate_centre_shift(width_slots, ref_slots):
    """How far the window centre moves when the pattern is widened.

    gate_pattern sets the run of bits *starting* at the offset gate_delay picks,
    so widening the pattern extends it forwards and moves its centre by half the
    added width.  Exact, which is why the centre only has to be measured once.
    """
    return (width_slots - ref_slots) * GATE_SLOT / 2.0


def shift_for_target(current, target, frame=PERIOD):
    """(am_shift, t0) that moves a feature from `current` to `target`.

    am_shift moves the optical pattern in whole 1.25 ns slots, t0 is added to
    every time tag and covers the remainder; both move a feature forwards.
    am_shift comes back reduced mod 10, the slots in one period, so it can be
    applied to the double-pulse pattern as measured on the single one.
    """
    delta = (target - current) % frame
    am_shift = int(delta // SLOT) % SLOTS_PER_PERIOD
    t0 = int(round(delta - am_shift * SLOT)) % frame
    return am_shift, t0


# ------------------------------------------------------------- dac0 geometry --

def rising_crossings(codes):
    """Rising zero crossings of a dac0 code array, in samples.

    The pulse generator triggers on these, so they are where Alice's light
    actually leaves -- and they are the only honest way to relate the single
    and double patterns, whose edges sit at different places inside their
    respective periods.  Reading them off the generated codes rather than
    hard-coding them keeps this correct across am_edge and qdistance.
    """
    from lib import gen_seq
    v = (np.asarray(codes, dtype=float) - 32768.0) / 32767.0
    if gen_seq.DAC0_INVERT:
        # gen_seq emits the inverted sequence because the dac0 output stage
        # inverts it again; the light follows the analog waveform, so undo the
        # code-side inversion here or every crossing comes out as its falling
        # neighbour -- the ones that are independent of qdistance.
        v = -v
    out = []
    for i in range(len(v)):
        a0, a1 = v[i], v[(i + 1) % len(v)]
        if a0 < 0 <= a1:
            out.append((i + (-a0) / (a1 - a0)) % len(v))
    return sorted(out)


def separation_slots(a):
    """Pulse separation of dac0_double, in slots, for qdistance `a`.

    seq0 = [1, 1, 0, -1, -1, a, 1, 0, -1, -a]: for a >= 0 the rising crossings
    are at 4+1/(1+a) and 9+a/(1+a); for a < 0 the pair moves to the 5->6 and
    8->9 edges.  The knob reaches 3 to 5 slots, i.e. 3.75 to 6.25 ns.
    """
    a = float(a)
    if a >= 0:
        return 5.0 + (a - 1.0) / (1.0 + a)
    return 3.0 + (1.0 + a) / (1.0 - a)


def qdistance_for_separation(d_slots):
    """qdistance that emits a pair `d_slots` apart -- inverse of the above."""
    d = float(d_slots)
    if 4.0 <= d <= 5.0:
        u = d - 5.0
        return (1.0 + u) / (1.0 - u)
    if 3.0 <= d < 4.0:
        y = d - 3.0
        return (y - 1.0) / (y + 1.0)
    raise ValueError(f"pulse separation {d:.3f} slots is outside the 3..5 "
                     f"slots dac0_double can emit")


def qdistance_for_arm(t1):
    """qdistance that makes Alice's pair match the interferometer arm `t1`.

    The comb merges when the emitted separation equals t1.  The pattern repeats
    every 10 slots, so a separation of t1 and of 10-t1 describe the same train
    and either may be the one the generator can reach.

    Returns (qdistance, separation_slots).
    """
    d = (t1 / SLOT) % SLOTS_PER_PERIOD
    for cand in (d, SLOTS_PER_PERIOD - d):
        if 3.0 <= cand <= 5.0:
            return qdistance_for_separation(cand), cand
    raise ValueError(f"arm delay {t1 * UNIT_PS / 1000:.3f} ns needs a pulse "
                     f"separation of {d:.3f} slots, which dac0_double cannot emit")
