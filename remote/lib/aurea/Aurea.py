#!/bin/python

from ctypes import *
import time
# Import OEM_SPD wrapper file  
import lib.aurea.SPD_OEM as SPD_OEM
import fcntl
import os
import subprocess
import sys
import threading

HW_CONTROL = "/home/vq-user/hw_control"
LOCKFILE = "/tmp/aurea.lock"
# How long to wait for another process to finish with the detector before giving
# up. Generous: a mode change plus its settling sleep is about a second, so
# anything near this means the other holder is stuck, and failing is better than
# opening the device underneath it.
LOCK_TIMEOUT = 30.0

# Minimum gap between closing the device and opening it again. The OEM library
# cannot take a re-open immediately after a close: with no gap at all the second
# openDevice segfaults, every time, in a bare loop that does nothing but open and
# close -- measured on bob2, and the original code fails identically, so this is
# the library and not the wrapper. Any spacing avoids it; 0.1 s already passes 5
# of 5. 0.5 s is what Ensure_Spd_Mode already sleeps and leaves a wide margin.
#
# This is the "usb failure ... mutex stuff": the same race surfaces either as the
# segfault or as libusb aborting the process with
#   usbi_mutex_destroy: Assertion `pthread_mutex_destroy(mutex) == 0' failed
# and it shows up exactly when two detector operations land back to back -- a
# mode change followed by mon's temperature poll, say.
#
# The gap is enforced against the lockfile's mtime, stamped at close while the
# lock is still held, so it applies between processes and threads too, not only
# to a re-open on this side. It costs nothing unless something really is
# re-opening sooner than the settle time.
AUREA_SETTLE = 0.5

# Guards the calls within one process; the flock below guards across processes.
aurea_lock = threading.Lock()


class AureaBusy(RuntimeError):
    """Another process still holds the detector."""


class _Session():
    """One exclusive session with the SPD over USB, in this process.

    hw.py, hws.py and mon.py all import ctl_bob and all reach the detector, so
    every open here races two other processes. The exclusion used to be a
    lockfile tested with os.path.isfile and *deleted by the waiter* once it was
    10 s old, which meant a holder that merely took a while had its lock stolen
    and a second process opened the device while the first still had it. Two
    libusb contexts over one device is what produces

        usbi_mutex_destroy: Assertion `pthread_mutex_destroy(mutex) == 0' failed

    and that assertion aborts the whole process, taking the service with it.

    flock replaces the heuristic: the kernel releases it when the fd closes or
    the process dies, so a lock cannot go stale and cannot be stolen. The lock is
    held for the whole open-to-close session rather than per call, and close() is
    idempotent, so a failure part way through cannot leave the device open.

    Usable as a context manager, which is the way to be sure close() runs:

        with Aurea() as a:
            a.mode('gated')
    """

    def __init__(self, timeout=LOCK_TIMEOUT):
        self._lock_fd = None
        self._opened = False
        self.iDev = c_short(0)

        self._acquire(timeout)
        try:
            devList, nDev = self._list()
            if nDev == 0:
                # Bounded, and inside the lock: waiting forever here used to
                # hold the lockfile until someone else deleted it.
                print("No device connected, waiting...")
                deadline = time.time() + timeout
                while nDev == 0:
                    if time.time() >= deadline:
                        raise AureaBusy(
                            f"no SPD OEM device appeared within {timeout:.0f} s")
                    time.sleep(1)
                    devList, nDev = self._list()
            elif nDev > 1:
                # Never prompt: these run as services with no stdin, where an
                # input() raises EOFError and used to leak the lock and the
                # open device with it.
                print(f"Found {nDev} devices, using 0: " + ", ".join(devList))

            with aurea_lock:
                ret = SPD_OEM.openDevice(self.iDev)
            if ret < 0:
                raise AureaBusy("failed to open the SPD OEM device")
            self._opened = True
            print("Device correctly opened")
        except BaseException:
            # Never keep the lock for a session that did not start.
            self._release()
            raise

    # ------------------------------------------------------------ locking --
    def _acquire(self, timeout):
        fd = open(LOCKFILE, 'a+')
        try:
            os.chmod(LOCKFILE, 0o666)
        except OSError:
            pass                      # another user owns it; the flock still works
        deadline = time.time() + timeout
        while True:
            try:
                fcntl.flock(fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                self._lock_fd = fd
                self._settle()
                return
            except OSError:
                if time.time() >= deadline:
                    fd.close()
                    raise AureaBusy(
                        f"another process has held the detector for more than "
                        f"{timeout:.0f} s")
                time.sleep(0.1)

    def _settle(self):
        """Wait out the rest of AUREA_SETTLE since the last close, if any."""
        try:
            since = time.time() - os.path.getmtime(LOCKFILE)
        except OSError:
            return
        if 0 <= since < AUREA_SETTLE:
            time.sleep(AUREA_SETTLE - since)

    def _release(self):
        fd, self._lock_fd = self._lock_fd, None
        if fd is not None:
            try:
                fcntl.flock(fd.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
            fd.close()               # closing releases the lock in any case

    def _list(self):
        with aurea_lock:
            return SPD_OEM.listDevices()

    # ------------------------------------------------------------ session --
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    def close(self):
        """Close the device and drop the lock. Safe to call more than once."""
        try:
            if self._opened:
                with aurea_lock:
                    ret = SPD_OEM.closeDevice(self.iDev)
                if ret < 0:
                    print(" -> failed\n")
                else:
                    print(" Device correctly closed ")
        finally:
            self._opened = False
            # Stamp the close time before dropping the lock, so whoever takes it
            # next waits out the settle rather than re-opening on top of us.
            try:
                os.utime(LOCKFILE, None)
            except OSError:
                pass
            self._release()

    def __del__(self):
        # Last resort for a caller that never reached close(): without this the
        # device stays open and the next open races it.
        try:
            self.close()
        except Exception:
            pass

    # ------------------------------------------------------------ settings --
    def mode(self, choice):
        if choice == 'gated': val = 1
        elif choice == 'continuous': val = 0
        else: raise ValueError(f"unknown detection mode {choice!r}")
        with aurea_lock:
            ret = SPD_OEM.setDetectionMode(self.iDev, val)
        if ret < 0: print(" -> failed\n")
        else: print(" set mode to " + choice + " done\n")

    def deadtime(self, val):
        with aurea_lock:
            ret = SPD_OEM.setDeadtime(self.iDev, val)
        if ret < 0: print(" -> failed\n")
        else: print(" set deadtime " + str(val) + " us done\n")

    def temp(self):
        with aurea_lock:
            ret, temp = SPD_OEM.getBodySocketTemp(self.iDev)
        return temp

    def effi(self, val):
        with aurea_lock:
            ret = SPD_OEM.setEfficiency(self.iDev, val)
        if ret < 0: print(" -> failed\n")
        else: print(" set efficiency " + str(val) + "(%) done\n")


class Aurea():
    """The detector, driven one short-lived subprocess at a time.

    The OEM library tolerates exactly **one open per process lifetime**. Opening
    it again after another process has used the device in between aborts, every
    time, with

        usbi_mutex_destroy: Assertion `pthread_mutex_destroy(mutex) == 0' failed

    Measured on bob2: 8 sequential sessions inside a single process are fine, and
    12 short-lived processes racing each other are fine, but three processes
    doing 8 sessions each abort all three. Spacing the opens does not help; only
    not re-opening does. So every session runs in a fresh subprocess that exits
    afterwards, and `_Session` -- the flock, the settle, the open and the close
    -- runs there rather than here.

    The API is unchanged for callers. Settings are batched and applied by one
    subprocess at close(), so a mode-plus-deadtime change still costs a single
    open; temp() has to answer immediately and takes its own.
    """

    def __init__(self, timeout=LOCK_TIMEOUT):
        self._timeout = timeout
        self._pending = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    def _run(self, argv):
        cmd = [sys.executable, os.path.abspath(__file__)] + argv
        # Running the file directly puts only its own directory on sys.path, so
        # `import lib.aurea.SPD_OEM` needs hw_control added explicitly.
        env = dict(os.environ)
        env['PYTHONPATH'] = (HW_CONTROL + os.pathsep + env['PYTHONPATH']
                             if env.get('PYTHONPATH') else HW_CONTROL)
        try:
            r = subprocess.run(cmd, cwd=HW_CONTROL, capture_output=True,
                               text=True, env=env, timeout=self._timeout + 30)
        except subprocess.TimeoutExpired:
            raise AureaBusy(f"detector command {argv} timed out")
        if r.stdout:
            print(r.stdout, end='')
        if r.returncode != 0:
            raise AureaBusy(
                f"detector command {argv} failed ({r.returncode}): "
                f"{(r.stderr or '').strip()[-300:]}")
        return r.stdout

    def mode(self, choice):
        if choice not in ('gated', 'continuous'):
            raise ValueError(f"unknown detection mode {choice!r}")
        self._pending += ['--mode', choice]

    def deadtime(self, val):
        self._pending += ['--dt', str(val)]

    def effi(self, val):
        self._pending += ['--eff', str(val)]

    def temp(self):
        out = self._run(['--temp'])
        for line in out.splitlines():
            if line.startswith('TEMP '):
                return float(line.split()[1])
        raise AureaBusy("the detector did not report a temperature")

    def close(self):
        """Apply anything still pending. Safe to call more than once."""
        pending, self._pending = self._pending, []
        if pending:
            self._run(pending)


if __name__=="__main__":
    import argparse

    parser = argparse.ArgumentParser(description='control the APD')

    parser.add_argument("--eff", type=int , help="set efficiency in %%")
    parser.add_argument("--dt", type=float , help="set deadtime in us")
    parser.add_argument("--mode", choices=["gated", "continuous"], help="choose running mode")
    parser.add_argument("--temp", action="store_true", help="print the body socket temperature")

    args = parser.parse_args()

    # The one open this process will ever do.
    with _Session() as session:
        if args.eff is not None:
            session.effi(args.eff)
        if args.dt is not None:
            session.deadtime(args.dt)
        if args.mode is not None:
            session.mode(args.mode)
        if args.temp:
            t = session.temp()
            print("TEMP " + str(float(t.value if hasattr(t, 'value') else t)))
