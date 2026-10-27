"""Offline, read-only detector of *realized* binary forecast surprise.

Forecast timestamps and verification flags are untrusted claims until independently
audited. Shannon surprisal is NOT Bayesian information gain or learning progress.
No model, web access, new permissions, or automatic SYN knowledge promotion.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from urllib.parse import urlsplit

SCHEMA = "syn-prediction-surprise-v0"
MAX_BYTES = 1_000_000
MAX_RECORDS = 2000
FORECAST_FIELDS = frozenset({
    "schema", "event_id", "domain", "question", "forecast_at",
    "window_start", "window_end", "p_true", "forecast_ref"
})
OUTCOME_FIELDS = frozenset({
    "schema", "event_id", "resolved_at", "outcome", "evidence_url",
    "externally_verified", "verifier_id"
})


def _require(ok: bool, reason: str) -> None:
    if not ok:
        raise ValueError(reason)


def _str(value: object, field: str) -> str:
    _require(isinstance(value, str) and 1 <= len(value) <= 1000
             and value.strip() == value, f"invalid {field}")
    return value


def _time(value: object, field: str) -> datetime:
    _str(value, field)
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"invalid {field}") from exc
    _require(dt.tzinfo is not None and dt.utcoffset() is not None,
             f"{field} must contain timezone")
    return dt.astimezone(timezone.utc)


def _https(value: object, field: str) -> None:
    _str(value, field)
    try:
        p = urlsplit(value)
        ok = p.scheme == "https" and bool(p.hostname) and p.port in (None, 443) \
            and not p.username and not p.password and not p.fragment
    except ValueError:
        ok = False
    _require(ok, f"invalid https {field}")


def _read_jsonl(path: Path) -> list[dict]:
    _require(path.is_file() and not path.is_symlink()
             and path.stat().st_size <= MAX_BYTES, "invalid or oversize file")
    rows: list[dict] = []
    try:
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                _require(len(rows) < MAX_RECORDS, "too many records")
                _require(bool(line.strip()), "empty JSONL line")
                row = json.loads(line)
                _require(isinstance(row, dict), "JSONL record must be object")
                rows.append(row)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid JSONL") from exc
    return rows


def _validate_forecast(row: dict) -> tuple[datetime, datetime, datetime]:
    _require(set(row) == FORECAST_FIELDS and row["schema"] == SCHEMA,
             "invalid forecast schema")
    for field in ("event_id", "domain", "question"):
        _str(row[field], field)
    _https(row["forecast_ref"], "forecast_ref")
    p = row["p_true"]
    _require(type(p) in (float, int) and math.isfinite(p) and 0 < p < 1,
             "p_true must be a finite probability strictly between zero and one")
    before = _time(row["forecast_at"], "forecast_at")
    start = _time(row["window_start"], "window_start")
    end = _time(row["window_end"], "window_end")
    _require(before < start < end, "forecast must precede the outcome window")
    return before, start, end


def _validate_outcome(row: dict) -> datetime:
    _require(set(row) == OUTCOME_FIELDS and row["schema"] == SCHEMA,
             "invalid outcome schema")
    _str(row["event_id"], "event_id")
    _https(row["evidence_url"], "evidence_url")
    _require(type(row["outcome"]) is bool, "outcome must be boolean")
    _require(type(row["externally_verified"]) is bool, "verification must be boolean")
    _str(row["verifier_id"], "verifier_id")
    return _time(row["resolved_at"], "resolved_at")


def assess(forecasts: list[dict], outcomes: list[dict], *,
           threshold_bits: float = 2.0, capacity: int = 3,
           max_per_domain: int = 1) -> dict:
    """Score independently resolved *claims* with an explicit verification gate.

    This does not independently verify timestamps, refs, sources or truth.
    """
    _require(type(threshold_bits) in (int, float) and math.isfinite(threshold_bits)
             and 0 < threshold_bits <= 20, "invalid surprise threshold")
    _require(type(capacity) is int and 1 <= capacity <= 20, "invalid capacity")
    _require(type(max_per_domain) is int and 1 <= max_per_domain <= 20,
             "invalid per-domain limit")
    _require(isinstance(forecasts, list) and isinstance(outcomes, list)
             and len(forecasts) <= MAX_RECORDS and len(outcomes) <= MAX_RECORDS,
             "invalid record count")
    fs: dict[str, dict] = {}
    for row in forecasts:
        _require(isinstance(row, dict), "invalid forecast record")
        _, _, end = _validate_forecast(row)
        event_id = row["event_id"]
        _require(event_id not in fs, "duplicate forecast event_id")
        fs[event_id] = {"row": row, "end": end}
    os: dict[str, dict] = {}
    for row in outcomes:
        _require(isinstance(row, dict), "invalid outcome record")
        resolved = _validate_outcome(row)
        event_id = row["event_id"]
        _require(event_id in fs, "outcome lacks preceding forecast")
        _require(event_id not in os, "duplicate outcome event_id")
        _require(resolved >= fs[event_id]["end"],
                 "outcome resolved before forecast window ended")
        os[event_id] = row
    resolved_records, blocked_records = [], []
    for event_id, data in fs.items():
        forecast = data["row"]
        if event_id not in os:
            blocked_records.append({"event_id": event_id, "reason": "no_outcome"})
            continue
        result = os[event_id]
        if not result["externally_verified"]:
            blocked_records.append({"event_id": event_id, "reason": "external_review_required"})
            continue
        y = int(result["outcome"])
        p = forecast["p_true"]
        realized = p if y else 1 - p
        bits = -math.log2(realized)
        brier = (p - y) ** 2
        resolved_records.append({
            "event_id": event_id, "domain": forecast["domain"],
            "question": forecast["question"], "p_true": p,
            "outcome": bool(y), "surprisal_bits": round(bits, 8),
            "brier": round(brier, 8), "forecast_ref": forecast["forecast_ref"],
            "evidence_url": result["evidence_url"], "verifier_id": result["verifier_id"],
            "surprising": bits >= threshold_bits
        })
    resolved_records.sort(key=lambda x: (-x["surprisal_bits"], x["event_id"]))
    selected: list[dict] = []
    domain_counts: dict[str, int] = {}
    for item in resolved_records:
        if len(selected) >= capacity:
            break
        if not item["surprising"]:
            continue
        domain = item["domain"]
        if domain_counts.get(domain, 0) >= max_per_domain:
            continue
        selected.append({
            **item, "next_action": "independent_review_and_competing_hypotheses",
            "promoted_to_knowledge": False
        })
        domain_counts[domain] = domain_counts.get(domain, 0) + 1
    n = len(resolved_records)
    mean_brier = (round(sum(r["brier"] for r in resolved_records) / n, 8)
                  if n else None)
    return {
        "schema": SCHEMA, "n_forecasts": len(fs), "n_outcomes": len(os),
        "n_externally_marked": n, "unscored": blocked_records,
        "all_scored": resolved_records, "surprise_candidates": selected,
        "mean_brier": mean_brier,
        "naive_half_probability_brier": 0.25 if n else None,
        "definition": "realized Shannon surprisal -log2(P(actual outcome)), not Bayesian KL information gain",
        "interpretation": ("High surprise also indicates a bad prediction and may reflect "
                           "randomness or noise; this alone is NOT learning."),
        "integrity_warning": ("offline code cannot authenticate timestamp, archived "
                              "forecast_ref, human verifier identity or evidence_url; "
                              "externally_verified is an input claim, not certification"),
        "promotion": "NONE: no automatic memory write, research execution or policy changes"
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--forecasts", type=Path, required=True)
    ap.add_argument("--outcomes", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--threshold-bits", type=float, default=2.0)
    args = ap.parse_args()
    _require(not args.output.exists() and not args.output.is_symlink(),
             "refuse to overwrite existing report")
    report = assess(_read_jsonl(args.forecasts), _read_jsonl(args.outcomes),
                    threshold_bits=args.threshold_bits)
    with args.output.open("x", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"Resolved {report['n_externally_marked']} claimed-verified outcomes; "
          f"{len(report['surprise_candidates'])} surprise candidates; "
          "no knowledge promotion")


if __name__ == "__main__":
    main()
