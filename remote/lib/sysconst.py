"""Measured constants of one QKD system, kept on Bob.

What belongs here is everything `find_gates` measures that is a property of the
*hardware* rather than of the current tuning: the two interferometer delays,
the offset between the free-running and gated detector, and how much detection
window each APD gate width actually opens.  Those change when someone moves a
fiber or reflashes the board, not between runs, so measuring them once and
reading them back makes gate placement a calculation instead of a search.

The interferometer entries are per laser wavelength.  Alice carries both lasers
and the fiber is patched by hand, the delays differ between them, and nothing
in the hardware says which one is connected -- so `laser` in Alice's tmp.txt
decides which entry applies, the same statement `qdistance_for_laser` reads.

Why a file of its own, and JSON: `get_tmp` parses every key it does not know
with `int()`, so one float in tmp.txt takes down all hardware control while the
service still looks healthy.  These values are floats and there are nested ones,
so they stay out of tmp.txt entirely.
"""

import datetime
import json
import os

HW_CONTROL = '/home/vq-user/hw_control/'
PATH = HW_CONTROL + 'config/system_constants.json'

VERSION = 1


def now():
    return datetime.datetime.now().isoformat(timespec='seconds')


def load(path=None):
    """The constants file, or an empty skeleton if it does not exist yet."""
    try:
        with open(path or PATH) as f:
            d = json.load(f)
    except (OSError, ValueError):
        d = {}
    d.setdefault('version', VERSION)
    d.setdefault('interferometer', {})
    d.setdefault('apd', {})
    d.setdefault('sequence', {})
    return d


def save(d, path=None):
    """Write the constants file atomically.

    Through a temporary file and os.replace: a half-written constants file
    would be read back as "never measured" and silently trigger a full
    re-characterisation on the next run.
    """
    path = path or PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.new'
    with open(tmp, 'w') as f:
        json.dump(d, f, indent=2, sort_keys=True)
        f.write('\n')
    os.replace(tmp, path)


def get_interferometer(d, nm):
    """Measured t1/t2 for laser `nm`, or None."""
    return d.get('interferometer', {}).get(str(nm))


def get_frozen_interferometer(d, nm):
    """The frozen t1/t2/qdistance for laser `nm`, or None if never frozen."""
    entry = get_interferometer(d, nm)
    return entry if entry and entry.get('frozen') else None


# --------------------------------------------------------------- modulator --
# `angle2 = -angle1` assumes the phase modulator is odd: that the same drive
# either side of zero gives the same phase either side of zero. It is not.
# Measured on qline1 at 1550 nm against the QBER matrix, both modulators need
# more drive on the negative side -- k2 about 1.13 -- and the two cells that
# angle2 trades, 32/33 for Alice and 23/33 for Bob, only balance there. angle3
# needs no such factor: 2*angle1 measured right twice on Alice (k3 1.001 and
# 0.999), so only this one number is stored.
#
# Cell 33 depends on BOTH parties' angle2, so the two k2 are not independent:
# measuring one while the other sits at a different value gives a different
# answer, which is what made a stable quantity look like it was drifting 10 %
# overnight. freeze_angles.py iterates them to their joint fixed point. The
# measurement itself repeats to 0.3 %.
K2_DEFAULT = 1.0


def get_k2(d, party, nm):
    """The frozen angle2/angle1 ratio for `party` at laser `nm`, or 1.0."""
    try:
        return float(d['modulator'][party][str(nm)]['k2'])
    except (KeyError, TypeError, ValueError):
        return K2_DEFAULT


def put_k2(d, party, nm, k2, note=''):
    """Record `party`'s k2 for laser `nm`."""
    entry = d.setdefault('modulator', {}).setdefault(party, {}).setdefault(str(nm), {})
    entry.update(k2=round(float(k2), 4), measured=now())
    if note:
        entry['source'] = note
    return entry


def get_laser(d):
    """The laser find_gates last ran on, or None.

    fs_a/fs_b have no link to Alice to ask, and find_gates always runs before
    them in full_init, so it leaves the answer here for them.
    """
    return d.get('laser')


def put_laser(d, nm):
    d['laser'] = str(nm)


def unfreeze_interferometer(d, nm):
    """Drop the frozen flag for laser `nm`, keeping the values as a prior.

    find_gates then measures the geometry again and re-records it, instead of
    reusing the frozen numbers and failing when the day's read is more than
    FG_FREEZE_TOL off them. Use it when the hardware really changed and the
    freeze is now wrong; `force` is the way to ignore it for a single run.
    Returns the entry, or None if there was nothing frozen.
    """
    entry = get_interferometer(d, nm)
    if not entry or not entry.get('frozen'):
        return None
    for k in ('frozen', 'samples', 't1_spread_ns', 't2_spread_ns',
              'qdistance_geometric', 'qdistance_source'):
        entry.pop(k, None)
    entry['unfrozen'] = now()
    return entry


def forget_interferometer(d, nm):
    """Remove laser `nm`'s entry entirely. Returns it, or None if absent."""
    return d.get('interferometer', {}).pop(str(nm), None)


def put_interferometer(d, nm, t1, t2, residual, qdistance, separation,
                       samples=None, am_edge=None):
    """Record the interferometer geometry for laser `nm`.

    `samples`, the (t1, t2) of each measurement a median was taken over, marks
    the entry frozen: find_gates then uses it as it is rather than re-deriving
    qdistance from one noisy histogram on every run, and re-imposes `am_edge`,
    the pulse shape the geometry was measured with.
    """
    from lib.timing import UNIT_PS
    entry = {
        't1_units': round(float(t1), 3),
        't2_units': round(float(t2), 3),
        't1_ns': round(float(t1) * UNIT_PS / 1000.0, 4),
        't2_ns': round(float(t2) * UNIT_PS / 1000.0, 4),
        'residual_ns': round(float(residual) * UNIT_PS / 1000.0, 4),
        'qdistance': round(float(qdistance), 4),
        'separation_slots': round(float(separation), 4),
        'measured': now(),
    }
    if samples:
        spread = lambda i: max(s[i] for s in samples) - min(s[i] for s in samples)
        entry.update(frozen=True, samples=len(samples),
                     t1_spread_ns=round(spread(0) * UNIT_PS / 1000.0, 4),
                     t2_spread_ns=round(spread(1) * UNIT_PS / 1000.0, 4))
        if am_edge:
            entry['am_edge'] = am_edge
    d.setdefault('interferometer', {})[str(nm)] = entry
    return d


def get_apd(d):
    return d.get('apd', {})


def put_apd(d, **kw):
    apd = d.setdefault('apd', {})
    apd.update(kw)
    apd['measured'] = now()
    return d


def put_gate_window(d, width_slots, window_units, half=None, top_hat=None,
                    rate=None):
    """Record the window a gate width actually opens.

    `window_units` is the support -- the full extent over which the gate passes
    anything -- and is what gate placement is decided on, because it is the one
    measure that rises monotonically with the pattern width.  The half-height
    width and the top hat (area over peak, the measure the earlier hand
    measurements were quoted in) are kept beside it for comparison, but the
    profile is part gate and part afterpulse decay and neither is stable enough
    to choose a gate by.
    """
    from lib.timing import UNIT_PS
    gate = d.setdefault('apd', {}).setdefault('gate', {})
    entry = {
        'window_units': round(float(window_units), 2),
        'window_ns': round(float(window_units) * UNIT_PS / 1000.0, 3),
        'measured': now(),
    }
    if half is not None:
        entry['half_ns'] = round(float(half) * UNIT_PS / 1000.0, 3)
    if top_hat is not None:
        entry['top_hat_ns'] = round(float(top_hat) * UNIT_PS / 1000.0, 3)
    if rate is not None:
        entry['rate'] = round(float(rate))
    gate[str(int(width_slots))] = entry
    return d


def window_per_slot(d):
    """The gate table as {width_slots: window_units}, for gate_slots_for_span."""
    gate = d.get('apd', {}).get('gate', {})
    out = {}
    for k, v in gate.items():
        try:
            out[int(k)] = float(v['window_units'])
        except (ValueError, KeyError, TypeError):
            continue
    return out


def get_sequence(d, nm):
    """Residual between the predicted and measured double-pulse comb, or None."""
    return d.get('sequence', {}).get(str(nm))


def put_sequence(d, nm, residual_units, am_edge, convention=None):
    """The leftover between the predicted and the measured comb position.

    Keyed by `am_edge`, which moves the emission within the period, and by the
    `convention` naming which peak the target refers to -- a residual measured
    against a different reference peak is off by a comb spacing and would send
    the next run to the wrong place.
    """
    d.setdefault('sequence', {})[str(nm)] = {
        'residual_units': round(float(residual_units), 2),
        'am_edge': am_edge,
        'convention': convention,
        'measured': now(),
    }
    return d


def put_last_run(d, **kw):
    """What the last find_gates measured and decided.

    Not a hardware constant, but it belongs with them: it is what lets a plot
    made later -- from the histogram files alone, by local/plot_gates.py --
    label itself with the numbers the run actually reached, instead of the
    reader having to dig them out of Bob's log.
    """
    kw['measured'] = now()
    d['last_run'] = kw
    return d


def summary(d):
    """One-screen dump of what has been measured, for the calibration log."""
    lines = []
    for nm, v in sorted(d.get('interferometer', {}).items()):
        lines.append(f"  {nm} nm: t1 {v['t1_ns']:.3f} ns, t2 {v['t2_ns']:.3f} ns, "
                     f"qdistance {v['qdistance']:.4f} ({v['measured']})")
    apd = d.get('apd', {})
    if 'mode_offset_units' in apd:
        lines.append(f"  apd: free-running to gated offset "
                     f"{apd['mode_offset_units'] * 0.02:.3f} ns")
    if 'centre_at_zero_units' in apd:
        lines.append(f"  apd: window centre at gate_delay 0 is unit "
                     f"{apd['centre_at_zero_units']:.1f}")
    for w, v in sorted(apd.get('gate', {}).items(), key=lambda kv: int(kv[0])):
        lines.append(f"  apd: gate {w} slots opens {v['window_ns']:.2f} ns")
    last = d.get('last_run')
    if last:
        lines.append(f"  last run: {last.get('status', '?')} at {last.get('measured', '?')}")
    return '\n'.join(lines) if lines else '  (nothing measured yet)'
