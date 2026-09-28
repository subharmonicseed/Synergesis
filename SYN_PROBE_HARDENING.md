# SYN-REALITY probe hardening

This increment addresses three bounded runtime-probe risks and clarifies one
probe's evidentiary meaning.

- **SEC-07 — closed:** `SQLiteProbePolicy.query_timeout_seconds` defaults to
  one second. SQLite's progress handler interrupts a running SELECT at its
  deadline. The returned observation explicitly marks the result unknown with
  `unknown_reason: query_timeout`; it does not turn timeout into a negative
  finding. The connection is closed in `finally`, and the next probe opens a
  fresh connection. SQLite callbacks are cooperative at virtual-machine
  instruction boundaries, so this bounds SQL execution rather than all
  possible filesystem stalls while SQLite opens a database.
- **SEC-08 — hardened for supported POSIX platforms:** `FileStateProbe` derives
  its path lexically (rejecting `..`) and walks from a directory descriptor
  opened on the configured root. It requires `O_NOFOLLOW` and `O_DIRECTORY`,
  failing closed if either is unavailable, and rejects symlinks including
  symlinks that point back inside the root. Hashing reads only from the opened
  regular-file descriptor and reads at most `max_hash_bytes + 1`, so concurrent
  file growth cannot make hashing unbounded. Replacing a path after it is opened
  cannot redirect the read. The configured root path and its parent ancestors
  are trusted configuration: this walk does not secure a hostile replacement
  of those ancestors before the root descriptor is opened. Non-regular files
  are reported without reading.
- **SEC-09 — hardened for cooperating ledger writers:** Before creating or
  replaying an observation glyph, the verifier checks every persisted glyph
  with that event ID against the canonical observation body while holding the
  ledger transaction through deduplicated creation. Conflicting IDs are rejected
  before insertion, across verifier instances sharing the same cooperating
  ledger. No separate per-verifier cache is maintained. This guarantee inherits
  the ledger's local transaction/lock assumptions; it does not cover writers
  that bypass that protocol.
- **SEC-06 — partial / semantics clarified:** `ProcessMarkerProbe` reports
  `presence_observed` and explicitly sets
  `creation_attributed_to_action: false`. A marker in the current process table
  proves only that a matching process was observed. This probe has no trusted
  creation nonce or action-bound process-start receipt and therefore must not
  be used to claim that the action created the process.

`test_syn_probe_hardening.py` covers query interruption and subsequent probe
operation, finite timeout validation, symlink and traversal rejection, path
replacement after open, and exact replay versus conflicting event-ID reuse. It
does not constitute an exhaustive platform or hostile-SQL security test.
