"""Offline science-anomaly triage: videos are leads, not scientific evidence.

Input is externally curated; this module neither browses the web, calls models,
nor certifies papers. Scores are editorial attention heuristics, not probabilities.
"""
from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
from urllib.parse import urlsplit

SCHEMA = "syn-science-anomaly-v0"
EVIDENCE = {"observation", "experiment", "simulation", "review", "unknown"}
STATUS = {"primary_checked", "primary_unchecked"}
MAX_ROWS = 250
MAX_BYTES = 512_000


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise ValueError(reason)


def _https(value: str) -> bool:
    if not isinstance(value, str) or len(value) > 1000:
        return False
    try:
        u = urlsplit(value)
        return (u.scheme == "https" and bool(u.hostname) and
                not u.username and not u.password and not u.fragment and
                u.port in (None, 443))
    except ValueError:
        return False


def _text(value: object, field: str, *, minimum: int = 5, maximum: int = 1200) -> str:
    require(isinstance(value, str) and minimum <= len(value.strip()) <= maximum,
            f"invalid {field}")
    return value.strip()


def _score(value: object, field: str) -> float:
    require(type(value) in (float, int) and 0 <= value <= 1,
            f"invalid heuristic {field}")
    return float(value)


def validate(row: dict) -> dict:
    required = {"schema", "id", "headline", "domain", "lead_url", "primary_url",
                "primary_status", "publication_date", "evidence_kind", "finding",
                "baseline_expectation", "competing_explanation", "falsifier",
                "cross_domain_question", "heuristics"}
    require(isinstance(row, dict) and set(row) == required, "invalid record fields")
    require(row["schema"] == SCHEMA, "invalid record schema")
    _text(row["id"], "id", minimum=1, maximum=120)
    for name in ("headline", "domain", "finding", "baseline_expectation",
                 "competing_explanation", "falsifier", "cross_domain_question"):
        _text(row[name], name)
    require(_https(row["lead_url"]), "lead_url must be a valid HTTPS URL")
    require(row["primary_status"] in STATUS, "invalid primary_status")
    require(row["evidence_kind"] in EVIDENCE, "invalid evidence_kind")
    require(row["primary_url"] is None or _https(row["primary_url"]), "invalid primary_url")
    require(row["primary_status"] != "primary_checked" or row["primary_url"] is not None,
            "a checked primary must identify its source")
    try:
        date.fromisoformat(row["publication_date"])
    except (ValueError, TypeError) as exc:
        raise ValueError("invalid publication date") from exc
    h = row["heuristics"]
    require(isinstance(h, dict) and
            set(h) == {"surprise", "testability", "cross_domain_relevance"},
            "invalid heuristics")
    for k, v in h.items():
        _score(v, k)
    return row


def assess(rows: list[dict], *, capacity: int = 3, domains_max: int = 1) -> dict:
    """Triage external findings; paper verification is a curator claim."""
    require(type(capacity) is int and 1 <= capacity <= 20, "invalid capacity")
    require(type(domains_max) is int and 1 <= domains_max <= 20,
            "invalid per-domain quota")
    require(isinstance(rows, list) and 0 <= len(rows) <= MAX_ROWS,
            "invalid number of rows")
    checked = []
    seen = set()
    for row in rows:
        validate(row)
        require(row["id"] not in seen, "duplicate story ID")
        seen.add(row["id"])
        h = row["heuristics"]
        priority = round(
            (h["surprise"] + 2 * h["testability"] + h["cross_domain_relevance"]) / 4, 4)
        evidence_status = ("curator_checked_primary" if
                           row["primary_status"] == "primary_checked"
                           else "needs_primary_check")
        checked.append({
            "id": row["id"], "domain": row["domain"], "headline": row["headline"],
            "lead_url": row["lead_url"],
            "cited_primary_url": (row["primary_url"] if
                                  evidence_status == "curator_checked_primary" else None),
            "unverified_primary_candidate_url": (
                row["primary_url"] if evidence_status == "needs_primary_check" else None),
            "evidence_kind": row["evidence_kind"], "primary_check": evidence_status,
            "finding": row["finding"],
            "competing_explanation": row["competing_explanation"],
            "falsifier": row["falsifier"],
            "cross_domain_question": row["cross_domain_question"],
            "priority_heuristic": priority,
            "conclusion": ("research_candidate" if
                           evidence_status == "curator_checked_primary"
                           else "verification_only"),
        })
    checked.sort(key=lambda x: (-x["priority_heuristic"], x["id"]))
    selected = []
    counts = {}
    for item in checked:
        if len(selected) == capacity:
            break
        domain = item["domain"]
        if counts.get(domain, 0) >= domains_max:
            continue
        selected.append(item)
        counts[domain] = counts.get(domain, 0) + 1
    return {
        "schema": SCHEMA, "selected": selected, "screened": len(checked),
        "evidence_policy": ("Secondary sources are discovery leads, not independent "
                            "proof; provenance labels are curator claims."),
        "scoring_policy": ("Priority is an editorial heuristic, never calibrated "
                            "scientific confidence."),
        "promotion": ("NONE: requires independent paper evaluation, external testing "
                      "and explicit authorization"),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    require(args.input.is_file() and not args.input.is_symlink(), "invalid input file")
    require(args.input.stat().st_size <= MAX_BYTES, "input too large")
    rows = json.loads(args.input.read_text(encoding="utf-8"))
    report = assess(rows)
    require(not args.output.exists() and not args.output.is_symlink(),
            "refuse to overwrite")
    with args.output.open("x", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"Selected {len(report['selected'])} of {report['screened']} leads; "
          "no knowledge automatically promoted")


if __name__ == "__main__":
    main()
