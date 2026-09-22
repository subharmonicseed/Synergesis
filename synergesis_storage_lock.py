"""Bounded, reentrant advisory locking for cooperating local journal writers.

Local POSIX filesystems only. Paths must not be replaced, hard-linked under
other names, or written outside the protocol while operations are in progress.
"""
from __future__ import annotations

import math
import os
from pathlib import Path
import threading
import time
from typing import Any

try:
    import fcntl
except ImportError:  # Native Windows is unsupported and fails closed.
    fcntl = None

_LOCK_PID = os.getpid()
_LOCK_SETUP = threading.Lock()
_PATH_LOCKS: dict[str, threading.RLock] = {}
_PATH_STATES: dict[str, tuple[int, int, Any]] = {}
_LOCK_POLL_SECONDS = 0.01


class PathTransaction:
    """Reentrant thread/process lock for one canonical ledger path.

    The sidecar lock uses POSIX ``flock`` and therefore requires a platform
    providing ``fcntl``. Unsupported platforms fail closed at lock creation.
    The lock coordinates cooperating processes; it supplies no rollback or
    multi-file atomicity. Keep sidecar files in place while writers run.
    Spawn processes explicitly; inherited fork state is rejected.
    """

    def __init__(self, path: str | Path, *, timeout: float = 10.0, label: str = "journal"):
        if isinstance(timeout, bool) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("lock timeout must be finite and positive")
        if os.getpid() != _LOCK_PID:
            raise RuntimeError("journal locking requires spawn, not inherited fork state")
        if fcntl is None:
            raise RuntimeError("journal locking requires POSIX fcntl support")
        self.timeout = timeout
        self.label = label
        self.key = str(Path(path).resolve())
        self.lock_path = Path(self.key + ".lock")
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with _LOCK_SETUP:
            self.thread_lock = _PATH_LOCKS.setdefault(self.key, threading.RLock())

    def __enter__(self):
        if os.getpid() != _LOCK_PID:
            raise RuntimeError(f"{self.label} requires spawn, not inherited fork state")
        if fcntl is None:
            raise RuntimeError(f"{self.label} locking requires POSIX fcntl support")
        deadline = time.monotonic() + self.timeout
        if not self.thread_lock.acquire(timeout=self.timeout):
            raise TimeoutError(f"timed out acquiring {self.label} lock")
        try:
            state = _PATH_STATES.get(self.key)
            if state is not None:
                _PATH_STATES[self.key] = (state[0], state[1] + 1, state[2])
                return self
            fh = self.lock_path.open("a+")
            try:
                while True:
                    try:
                        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except BlockingIOError:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise TimeoutError(f"timed out acquiring {self.label} lock")
                        time.sleep(min(_LOCK_POLL_SECONDS, remaining))
                _PATH_STATES[self.key] = (fh.fileno(), 1, fh)
            except BaseException:
                fh.close()
                raise
            return self
        except BaseException:
            self.thread_lock.release()
            raise

    def __exit__(self, exc_type, exc, tb):
        try:
            fd, depth, fh = _PATH_STATES[self.key]
            if depth > 1:
                _PATH_STATES[self.key] = (fd, depth - 1, fh)
            else:
                del _PATH_STATES[self.key]
                try:
                    fcntl.flock(fd, fcntl.LOCK_UN)
                finally:
                    fh.close()
        finally:
            self.thread_lock.release()
        return False

