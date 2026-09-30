#!/usr/bin/env python3
"""Inspect and edit the frozen hardware constants, which live on Bob.

    QLINE_CONFIG_DIR=.../config/qline1 python3 sysconst_tool.py show
    ... sysconst_tool.py unfreeze --laser 1550
    ... sysconst_tool.py forget   --laser 1550

`show` prints every laser's entry. `unfreeze` drops the frozen flag for one
laser, so the next find_gates measures the geometry again and records it,
instead of reusing the frozen values and failing when the day's read is more
than 0.15 ns off them. `forget` removes the entry outright.

Neither is what you want for a single run: `hws.py --command find_gates_force`
ignores the freeze for that run and leaves it in place. Unfreeze is for when
the hardware really changed -- a fiber repatched, the interferometer touched,
the board reflashed -- and the stored geometry is now wrong. After unfreezing,
run `freeze_qdistance.py --laser <nm>` to measure and freeze the new one.

`--clean` does not touch any of this: system_constants.json holds properties of
the hardware, not of the current tuning, which is the whole point of the file.
"""

import argparse
import json
import os
import subprocess
import sys

REMOTE = 'cd ~/hw_control && python3 -c {code}'


def run(bob, code):
    """Run `code` on Bob inside ~/hw_control; returns stdout."""
    r = subprocess.run(['ssh', '-o', 'BatchMode=yes', f'vq-user@{bob}',
                        'cd ~/hw_control && python3 -c ' + json.dumps(code)],
                       stdin=subprocess.DEVNULL, capture_output=True, text=True,
                       timeout=60)
    if r.returncode:
        sys.exit(f'on {bob}: {(r.stderr or r.stdout).strip()}')
    return r.stdout


def bob_host():
    cfg = os.environ.get('QLINE_CONFIG_DIR')
    if not cfg:
        sys.exit('please set QLINE_CONFIG_DIR')
    net = json.load(open(os.path.join(cfg, 'alice', 'network.json')))
    return net['ip']['bob']


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('action', choices=['show', 'unfreeze', 'forget'])
    p.add_argument('--laser', type=int, help='1310, 1510 or 1550')
    p.add_argument('--yes', action='store_true', help='skip the confirmation')
    args = p.parse_args()
    bob = bob_host()

    if args.action == 'show':
        print(run(bob, 'import json, lib.sysconst as s; '
                       'print(json.dumps(s.load().get("interferometer", {}), indent=2))'))
        return

    if not args.laser:
        sys.exit(f'{args.action} needs --laser')
    nm = args.laser

    before = run(bob, 'import json, lib.sysconst as s; '
                      f'print(json.dumps(s.get_interferometer(s.load(), "{nm}")))')
    entry = json.loads(before.strip() or 'null')
    if not entry:
        sys.exit(f'no entry for {nm} nm')
    print(f'{nm} nm, currently:')
    print(json.dumps(entry, indent=2))
    if args.action == 'unfreeze' and not entry.get('frozen'):
        sys.exit('that entry is not frozen; nothing to do')

    if not args.yes:
        what = ('drop the frozen flag (values kept as a prior)'
                if args.action == 'unfreeze' else 'delete the entry')
        if input(f'\n{what} for {nm} nm? [y/N] ').strip().lower() != 'y':
            sys.exit('cancelled')

    fn = 'unfreeze_interferometer' if args.action == 'unfreeze' else 'forget_interferometer'
    out = run(bob, 'import lib.sysconst as s\n'
                   'd = s.load()\n'
                   f'r = s.{fn}(d, "{nm}")\n'
                   'print("changed" if r is not None else "nothing to do")\n'
                   's.save(d)\n')
    print(out.strip())
    if args.action == 'unfreeze':
        print(f'next find_gates will re-measure {nm} nm. Run '
              f'freeze_qdistance.py --laser {nm} to freeze the new geometry.')


if __name__ == '__main__':
    main()
