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


def put_interferometer(d, nm, t1, t2, residual, qdistance, separation):
    from lib.timing import UNIT_PS
    d.setdefault('interferometer', {})[str(nm)] = {
        't1_units': round(float(t1), 3),
        't2_units': round(float(t2), 3),
        't1_ns': round(float(t1) * UNIT_PS / 1000.0, 4),
        't2_ns': round(float(t2) * UNIT_PS / 1000.0, 4),
        'residual_ns': round(float(residual) * UNIT_PS / 1000.0, 4),
        'qdistance': round(float(qdistance), 4),
        'separation_slots': round(float(separation), 4),
        'measured': now(),
    }
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
