# Synergesis storage operations

Use `secure_roam_runtime_session(config=..., ...)` from
`synergesis_runtime_session` to own one runtime stack at a time for a storage
root. Ownership starts before stack construction and continues until the
context exits. A second session in the same process is rejected immediately;
other processes are rejected by default or can wait for a finite interval with
`lock_timeout`. The lock file is persistent, while the kernel lock is released
on normal exit, exceptions, and process termination. This POSIX implementation
requires `flock` support and a filesystem that honors advisory locks.

Run `python -m synergesis_runtime_session ROOT` for a read-only metadata
summary. Bounds apply to root-level directory entries, JSONL bytes, and line
length; symlinks are ignored. The diagnostic does not invoke the GlyphLedger
verifier because it may create a sidecar lock file, so hash-chain integrity is
not checked. It detects malformed JSON lines, overlong lines, unterminated final
lines, and recognized root-level attempt or pending markers. It reports names,
sizes, counts, and status only, never record payloads. Its scope is intentionally partial: this is not a global audit of
nested directories, unrelated formats, or every legacy journal writer, and it
does not claim that all historical storage paths enforce these bounds.

For checkpointing or archival, stop writers by exiting their managed session,
then make a cold, dated copy of the entire storage root to a separate backup
location and verify that copy before retention or transfer. Keep originals
until an operator explicitly approves a retention action. Do not silently
truncate, delete, reset, or rewrite journals as part of diagnosis or backup.

The Glyph ledger separately caps serialized events at 1 MiB and its full file at
64 MiB by default, rejecting oversized writes before mutation and bounded reads
before chain verification. Constructor limits can be explicitly configured.
This is not a shared global quota for every other journal. The standard discovery
runner now uses the managed session; direct low-level builders still require
caller ownership discipline.
