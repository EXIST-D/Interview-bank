"""OS advisory locks with shared (reader) and exclusive (writer) modes.

The inode stays put; process exit releases its lock. POSIX uses flock; Windows uses LockFileEx on
the first byte, which supports both modes (msvcrt.locking is exclusive-only).
"""
import os
import time
from contextlib import contextmanager

from .errors import LockConflict

if os.name == "nt":
    import ctypes
    import msvcrt
    from ctypes import wintypes

    class _Overlapped(ctypes.Structure):
        _fields_ = [("Internal", ctypes.c_void_p), ("InternalHigh", ctypes.c_void_p),
                    ("Offset", wintypes.DWORD), ("OffsetHigh", wintypes.DWORD), ("hEvent", wintypes.HANDLE)]

    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _kernel32.LockFileEx.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
                                     wintypes.DWORD, ctypes.POINTER(_Overlapped)]
    _kernel32.LockFileEx.restype = wintypes.BOOL
    _kernel32.UnlockFileEx.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
                                       ctypes.POINTER(_Overlapped)]
    _kernel32.UnlockFileEx.restype = wintypes.BOOL
    _EXCLUSIVE, _FAIL_IMMEDIATELY = 0x2, 0x1
else:
    import fcntl


def lock_timeout():
    """Seconds to wait for another short command; INTERVIEW_BANK_LOCK_TIMEOUT overrides (0 = fail fast)."""
    try:
        return max(0.0, float(os.environ.get("INTERVIEW_BANK_LOCK_TIMEOUT", "10")))
    except ValueError:
        return 10.0


def _try_lock(handle, shared=False):
    if os.name == "nt":
        flags = _FAIL_IMMEDIATELY | (0 if shared else _EXCLUSIVE)
        overlapped = _Overlapped()
        return bool(_kernel32.LockFileEx(msvcrt.get_osfhandle(handle.fileno()), flags, 0, 1, 0, ctypes.byref(overlapped)))
    try:
        fcntl.flock(handle.fileno(), (fcntl.LOCK_SH if shared else fcntl.LOCK_EX) | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


def _unlock(handle):
    if os.name == "nt":
        overlapped = _Overlapped()
        _kernel32.UnlockFileEx(msvcrt.get_osfhandle(handle.fileno()), 0, 1, 0, ctypes.byref(overlapped))
    else:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def bank_lock(bank, timeout=None, shared=False):
    """Readers share the lock; a writer waits for readers and excludes everyone.

    Critical sections take ~0.1 s, so concurrent callers queue briefly instead of failing at once.
    """
    path = bank / ".bank.lock"
    with path.open("a+b") as handle:
        handle.seek(0, 2)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        deadline = time.monotonic() + (lock_timeout() if timeout is None else timeout)
        delay = 0.01
        while not _try_lock(handle, shared):
            if time.monotonic() >= deadline:
                raise LockConflict(f"Bank is busy: {bank}")
            time.sleep(delay)
            delay = min(delay * 2, 0.2)
        try:
            yield
        finally:
            _unlock(handle)
