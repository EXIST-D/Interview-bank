"""OS advisory locks. The inode stays put; process exit releases its lock."""
import os
import time
from contextlib import contextmanager

from .errors import LockConflict

if os.name == "nt":
    import msvcrt
else:
    import fcntl


def lock_timeout():
    """Seconds to wait for another short command; INTERVIEW_BANK_LOCK_TIMEOUT overrides (0 = fail fast)."""
    try:
        return max(0.0, float(os.environ.get("INTERVIEW_BANK_LOCK_TIMEOUT", "10")))
    except ValueError:
        return 10.0


def _try_lock(handle):
    handle.seek(0)
    try:
        if os.name == "nt":
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


@contextmanager
def bank_lock(bank, timeout=None):
    # Critical sections take ~0.1 s, so concurrent callers queue briefly instead of failing at once.
    path = bank / ".bank.lock"
    with path.open("a+b") as handle:
        handle.seek(0, 2)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        deadline = time.monotonic() + (lock_timeout() if timeout is None else timeout)
        delay = 0.01
        while not _try_lock(handle):
            if time.monotonic() >= deadline:
                raise LockConflict(f"Bank is busy: {bank}")
            time.sleep(delay)
            delay = min(delay * 2, 0.2)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
