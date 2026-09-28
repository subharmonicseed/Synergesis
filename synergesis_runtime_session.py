"""Managed single-writer lifetime and bounded, read-only storage diagnostics."""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import os
import math
import stat
from pathlib import Path
import threading
import time
from typing import Iterator

_ACTIVE_ROOTS: set[str] = set()
_ACTIVE_LOCK = threading.Lock()
_PROCESS_ID = os.getpid()


class RuntimeSessionBusy(RuntimeError):
    """Another managed runtime session currently owns this storage root."""


@contextmanager
def secure_roam_runtime_session(*, config, lock_timeout: float = 0.0, **builder_kwargs):
    """Build/yield a secure roam stack while exclusively owning its storage root.

    The POSIX flock spans builder construction and the entire yielded lifetime.
    A process-local registry rejects concurrent sessions before relying on OS
    lock behavior. The lock is automatically released on exceptions or death.
    """
    if (isinstance(lock_timeout, bool) or not isinstance(lock_timeout, (int, float))
            or not math.isfinite(float(lock_timeout)) or lock_timeout < 0):
        raise ValueError("lock_timeout must be a finite non-negative number")
    if os.getpid() != _PROCESS_ID:
        raise RuntimeSessionBusy("forked process inherited active runtime session state")
    root = Path(config.root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    key = os.fspath(root)
    with _ACTIVE_LOCK:
        if key in _ACTIVE_ROOTS:
            raise RuntimeSessionBusy("runtime storage root already has an active session")
        _ACTIVE_ROOTS.add(key)
    lock_file = None
    locked = False
    try:
        lock_file = open(root / ".synergesis-runtime-session.lock", "a+b")
        deadline = time.monotonic() + float(lock_timeout)
        while True:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = True
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise RuntimeSessionBusy("runtime storage root is locked by another process")
                time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))
        # Deliberately imported only after ownership to avoid composition cycles.
        from synergesis_secure_roam_stack_v2 import build_secure_roam_reality_stack
        yield build_secure_roam_reality_stack(config=config, **builder_kwargs)
    finally:
        if lock_file is not None:
            if locked:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()
        with _ACTIVE_LOCK:
            _ACTIVE_ROOTS.discard(key)


def inspect_storage(root: str | Path, *, max_files: int = 256,
                    max_file_bytes: int = 1_048_576,
                    max_line_bytes: int = 65_536) -> dict:
    """Return bounded metadata-only diagnostics without following symlinks.

    Directory enumeration and file reads are capped. The result never includes
    record contents. Glyph chain integrity is not checked here: its verifier
    uses a sidecar lock file and therefore is not strictly read-only.
    """
    for name, value in (("max_files", max_files), ("max_file_bytes", max_file_bytes),
                        ("max_line_bytes", max_line_bytes)):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"{name} must be a positive integer")
    base = Path(root).expanduser().resolve()
    reports: list[dict] = []
    pending_found: list[dict] = []
    truncated_inventory = False
    if not base.exists():
        return {"root": str(base), "jsonl_files": [], "recognized_pending": [],
                "inventory_truncated": False,
                "scope": "bounded root-level metadata only; not a global journal audit"}

    # Inspect at most max_files directory entries, without sorting/materializing
    # an unbounded directory listing. Symlinks are ignored rather than followed.
    examined = 0
    with os.scandir(base) as entries:
        for entry in entries:
            if examined >= max_files:
                truncated_inventory = True
                break
            examined += 1
            try:
                if entry.is_symlink():
                    continue
                if entry.is_file(follow_symlinks=False) and entry.name.endswith(".jsonl"):
                    path = base / entry.name
                    info = entry.stat(follow_symlinks=False)
                    item = {"file": entry.name, "bytes": info.st_size, "status": "ok", "lines": 0}
                    if info.st_size > max_file_bytes:
                        item["status"] = "over_file_limit"
                    else:
                        bad = False
                        consumed = 0
                        pending = bytearray()
                        with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "rb") as stream:
                            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                                raise OSError("diagnostic target is not a regular file")
                            while consumed <= max_file_bytes:
                                chunk = stream.read(min(8192, max_file_bytes + 1 - consumed))
                                if not chunk:
                                    break
                                consumed += len(chunk)
                                pending.extend(chunk)
                                while b"\n" in pending:
                                    line, _, rest = pending.partition(b"\n")
                                    pending = bytearray(rest)
                                    item["lines"] += 1
                                    if len(line) > max_line_bytes:
                                        bad = True
                                    elif line.strip():
                                        try:
                                            import json
                                            json.loads(line)
                                        except (ValueError, UnicodeDecodeError):
                                            bad = True
                                if len(pending) > max_line_bytes:
                                    bad = True
                                    break
                        if consumed > max_file_bytes:
                            item["status"] = "over_file_limit"
                        else:
                            if pending:
                                item["trailing_truncated_line"] = True
                                item["lines"] += 1
                                # JSON without a terminating newline is not a complete JSONL record.
                                bad = True
                            if bad:
                                item["status"] = "malformed_or_overlong"
                    reports.append(item)
                elif (entry.name.endswith((".transport-attempt.json", ".roam-attempt.json", ".pending", ".pending.json"))):
                    item = {"name": entry.name, "kind": "pending_directory" if entry.is_dir(follow_symlinks=False) else "attempt_file"}
                    if entry.is_file(follow_symlinks=False):
                        item["bytes"] = entry.stat(follow_symlinks=False).st_size
                        item["status"] = "over_file_limit" if item["bytes"] > max_file_bytes else "present"
                    pending_found.append(item)
            except (FileNotFoundError, OSError):
                # Concurrent changes make the entry unavailable; do not follow
                # replacement symlinks or expose filesystem error details.
                reports.append({"file": entry.name, "status": "unavailable_during_scan"})
    return {"root": str(base), "jsonl_files": reports, "recognized_pending": pending_found,
            "inventory_truncated": truncated_inventory,
            "scope": "bounded root-level metadata only; not a global journal audit"}


def main(argv=None) -> int:
    import argparse
    import json
    parser = argparse.ArgumentParser(description="Read-only bounded Synergesis storage diagnostics")
    parser.add_argument("root", type=Path)
    parser.add_argument("--max-files", type=int, default=256)
    parser.add_argument("--max-file-bytes", type=int, default=1_048_576)
    parser.add_argument("--max-line-bytes", type=int, default=65_536)
    args = parser.parse_args(argv)
    try:
        result = inspect_storage(args.root, max_files=args.max_files,
                                 max_file_bytes=args.max_file_bytes,
                                 max_line_bytes=args.max_line_bytes)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
