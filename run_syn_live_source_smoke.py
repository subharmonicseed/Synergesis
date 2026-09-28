"""Explicit, bounded arXiv connectivity smoke test; performs no work on import."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from synergesis_live_sources import (
    ArxivSearchAdapter, DiskHttpCache, PoliteHttpClient,
    arxiv_documented_http_policy,
)
from synergesis_runner_support import fresh_output_dir


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="new output directory (must not already exist)")
    parser.add_argument("--query", required=True, help="short arXiv search phrase")
    parser.add_argument("--max-items", type=int, default=1, choices=range(1, 4),
                        help="maximum results to request (1 to 3; default: 1)")
    args = parser.parse_args(argv)
    output = fresh_output_dir(args.output, "syn_live_source_smoke")
    policy = arxiv_documented_http_policy(
        timeout_seconds=5, max_response_bytes=1_000_000, max_retries=0,
        retry_backoff_seconds=0, max_redirects=0, cache_ttl_seconds=3600,
        max_total_seconds=8,
    )
    client = PoliteHttpClient(policy=policy, cache=DiskHttpCache(output / "cache"))
    adapter = ArxivSearchAdapter(
        client=client, cost_units_per_item=0.0,
        user_agent="Synergesis-optional-smoke/1.0 (bounded research probe)",
    )
    items = adapter.search(query=args.query, max_items=args.max_items)
    result = [{"source_ref": item.source_ref, "title": item.title} for item in items]
    (output / "results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Retrieved {len(result)} arXiv records; results saved to {output}")


if __name__ == "__main__":
    main()
