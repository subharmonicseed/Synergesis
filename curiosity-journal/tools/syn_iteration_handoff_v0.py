"""Carry SYN curiosity state across iterations without pretending the LLM learned.

This is a deterministic, offline *decision-handoff proposal* generator.
It can only read explicitly supplied public reports and a previous handoff.
It cannot run research, change SYN policies, promote knowledge or call models.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path

SCHEMA = "syn-iteration-handoff-v0"
SOURCE_SCHEMA = "syn-curiosity-v1"
MAX_RECORDS = 2048
MAX_BYTES = 256_000
ACTIONS = {
    ("proposed", "not_tested"): ("run_preregistered_test", 0.20),
    ("assessed", "refuted"): ("investigate_refutation", 0.25),
    ("assessed", "inconclusive"): ("seek_discriminating_evidence", 0.15),
    ("assessed", "supported"): ("independent_replication", 0.05),
    ("blocked", "not_tested"): ("resolve_access_or_evidence_blocker", 0.0),
}


def canonical(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def digest(data: object) -> str:
    return hashlib.sha256(canonical(data).encode("utf-8")).hexdigest()


def require(condition: bool, why: str) -> None:
    if not condition:
        raise ValueError(why)


def _iso(value: object) -> None:
    require(isinstance(value, str), "invalid observed_at")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid observed_at") from exc
    require(stamp.tzinfo is not None and stamp.utcoffset() is not None,
            "observed_at requires timezone")


def _public_record(raw: dict) -> dict:
    """Validate the fields used here; this is NOT a replacement for validate_entry."""
    require(isinstance(raw, dict) and raw.get("schema") == SOURCE_SCHEMA,
            "wrong curiosity report schema")
    for field in ("entry_id", "domain", "question"):
        require(isinstance(raw.get(field), str) and 1 <= len(raw[field]) <= 2048,
                f"invalid {field}")
    _iso(raw.get("observed_at"))
    pair = (raw.get("stage"), raw.get("outcome"))
    require(pair in ACTIONS, "invalid research stage/outcome combination")
    require(raw.get("gap_kind") in {
        "prediction_error", "contradiction", "staleness",
        "missing_domain", "unverified", "unknown"
    }, "invalid gap_kind")
    m = raw.get("metrics")
    require(isinstance(m, dict), "missing priority metrics")
    score = m.get("selection_score")
    require(type(score) in (float, int) and math.isfinite(score)
            and 0 <= score <= 1, "invalid selection_score")
    refs = raw.get("evidence_refs")
    require(isinstance(refs, list) and len(refs) <= 10
            and all(isinstance(x, str) and x.startswith("https://")
                    for x in refs), "invalid evidence references")
    if pair[0] == "assessed":
        require(len(refs) >= 1 and raw.get("uncertainty_after") is not None,
                "assessed entry lacks claimed evidence")
    else:
        require(not refs and raw.get("uncertainty_after") is None,
                "unassessed entry claims evidence")
    action, boost = ACTIONS[pair]
    return {"entry_id": raw["entry_id"], "domain": raw["domain"],
            "stage": pair[0], "outcome": pair[1],
            "gap_kind": raw["gap_kind"], "record_sha256": digest(raw),
            "next_action": action,
            "priority_heuristic": round(min(1.0, score + boost), 6),
            "times_surfaced": 0,
            "requires_independent_review": True}


def _verified_previous(state: dict | None) -> dict | None:
    if state is None:
        return None
    require(isinstance(state, dict) and state.get("schema") == SCHEMA,
            "invalid previous-state schema")
    fields = {"schema", "iteration", "previous_digest", "ledger", "queue", "digest",
              "interpretation"}
    require(set(state) == fields, "unexpected previous-state fields")
    require(type(state["iteration"]) is int and state["iteration"] >= 1,
            "invalid previous iteration")
    require(state["previous_digest"] is None or
            (isinstance(state["previous_digest"], str)
             and len(state["previous_digest"]) == 64),
            "invalid previous digest")
    require(isinstance(state["ledger"], list)
            and len(state["ledger"]) <= MAX_RECORDS, "invalid previous ledger")
    require(isinstance(state["queue"], list), "invalid previous queue")
    require(isinstance(state["digest"], str)
            and digest({k: v for k, v in state.items() if k != "digest"}) ==
            state["digest"], "previous state digest mismatch")
    ids = [r.get("entry_id") for r in state["ledger"] if isinstance(r, dict)]
    require(len(ids) == len(state["ledger"]) and len(set(ids)) == len(ids),
            "duplicate or malformed previous ledger")
    return state


def advance(previous: dict | None, new_reports: list[dict],
            *, capacity: int = 3) -> dict:
    """Advance one state: old entries influence the new queue, but no action runs."""
    old = _verified_previous(previous)
    require(type(capacity) is int and 1 <= capacity <= 20,
            "invalid queue capacity")
    require(isinstance(new_reports, list), "reports must be a list")
    ledger = [dict(r) for r in old["ledger"]] if old is not None else []
    # Surfacing is NOT completion: reduce scheduling monopoly but preserve the gap.
    surfaced = {q["entry_id"] for q in old["queue"]} if old else set()
    for row in ledger:
        require(type(row.get("times_surfaced")) is int and
                0 <= row["times_surfaced"] < 100000,
                "invalid previous surfacing count")
        if row["entry_id"] in surfaced:
            row["times_surfaced"] += 1
    known = {r["entry_id"] for r in ledger}
    require(len(new_reports) + len(ledger) <= MAX_RECORDS,
            "iteration record limit exceeded")
    for raw in new_reports:
        candidate = _public_record(raw)
        require(candidate["entry_id"] not in known,
                "duplicate entry: refusing overwrite or re-import")
        known.add(candidate["entry_id"])
        ledger.append(candidate)
    require(ledger, "cannot create an empty handoff")
    ledger.sort(key=lambda e: e["entry_id"])
    # This fairness penalty is a scheduling heuristic; no task is marked done.
    def effective(row):
        return round(row["priority_heuristic"] /
                     (1 + 0.25 * row["times_surfaced"]), 6)
    ranking = sorted(ledger, key=lambda r: (-effective(r), r["entry_id"]))
    queue = [{"entry_id": r["entry_id"], "domain": r["domain"],
              "proposed_action": r["next_action"],
              "priority_heuristic": effective(r),
              "state": "queued_not_executed"}
             for r in ranking[:capacity]]
    body = {"schema": SCHEMA, "iteration": old["iteration"] + 1 if old else 1,
            "previous_digest": old["digest"] if old else None,
            "ledger": ledger, "queue": queue,
            "interpretation": (
                "Decision proposals derived from uncalibrated attention scores; "
                "no model adaptation, independent verification, execution, "
                "knowledge promotion, or proof of AGI.")}
    return {**body, "digest": digest(body)}


def _read_json(path: Path) -> dict:
    require(path.is_file() and not path.is_symlink()
            and path.stat().st_size <= MAX_BYTES, "invalid or oversized input")
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("malformed JSON") from exc
    require(isinstance(result, dict), "input must be object")
    return result


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--previous", type=Path)
    p.add_argument("--entry", type=Path, action="append", default=[])
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--capacity", type=int, default=3)
    args = p.parse_args()
    require(not args.out.exists() and not args.out.is_symlink(),
            "refusing overwrite")
    previous = _read_json(args.previous) if args.previous else None
    state = advance(previous, [_read_json(x) for x in args.entry],
                    capacity=args.capacity)
    with args.out.open("x", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"Iteration {state['iteration']}, {len(state['ledger'])} inherited "
          f"reports, {len(state['queue'])} proposed next actions; NONE executed")


if __name__ == "__main__":
    main()
