"""Create a small toy sealed test pack for SYN skill-transfer ablations.

No model is run here. Test questions and independent answers are in separate
directories. This is not a blind test if the agent sees the private seed.
"""
from __future__ import annotations

import argparse
from datetime import date, timedelta
import json
import os
from pathlib import Path
import random
import secrets

SCHEMA = "syn-skill-transfer-eval-v0"
ARMS = ["baseline", "journal", "research", "skills"]
DOMAINS = ("arithmetic", "calendar", "graph")


def _jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("x", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _answer_graph(edges: list[tuple[str, str]], start: str, target: str) -> str:
    seen = {start}
    pending = [start]
    while pending:
        node = pending.pop(0)
        for a, b in edges:
            if a == node and b not in seen:
                pending.append(b)
                seen.add(b)
    return "YES" if target in seen else "NO"


def _make(rng: random.Random, domain: str) -> tuple[str, str]:
    if domain == "arithmetic":
        a, b, c = rng.randint(-70, 70), rng.randint(-70, 70), rng.randint(2, 9)
        return (f"Calculate {c} times ({a}) minus 2 times ({b}). Return a single integer.",
                str(c * a - 2 * b))
    if domain == "calendar":
        base = date(2024, 1, 1) + timedelta(days=rng.randrange(0, 1095))
        delta = rng.randrange(1, 90)
        return (f"What is the UTC calendar date {delta} days after {base.isoformat()}? Return YYYY-MM-DD.",
                (base + timedelta(days=delta)).isoformat())
    if domain == "graph":
        nodes = "ABCDEF"
        edges = [(a, b) for a in nodes for b in nodes if a != b and rng.random() < .22]
        start, end = rng.sample(list(nodes), 2)
        label = ", ".join(f"{a}->{b}" for a, b in edges) or "none"
        return (f"Directed graph edges: {label}. Is there a directed path from {start} to {end}? Reply YES or NO.",
                _answer_graph(edges, start, end))
    raise ValueError("unknown domain")


def build(out: Path, *, per_domain_train: int = 4, per_domain_test: int = 8,
          seed: int | None = None, model_id: str = "FILL-WITH-EXACT-FROZEN-MODEL") -> dict:
    if not (1 <= per_domain_train <= 500 and 1 <= per_domain_test <= 500):
        raise ValueError("number of tasks per domain must be 1..500")
    if not isinstance(model_id, str) or not (1 <= len(model_id) <= 300):
        raise ValueError("model_id required")
    if seed is None:
        seed = secrets.randbits(128)
    rng = random.Random(seed)
    if out.exists():
        raise FileExistsError(f"output already exists: {out}")
    out.mkdir(parents=True, mode=0o700)
    release, holdout, sealed = (out / x for x in ("release", "holdout", "sealed"))
    for directory in (release, holdout, sealed):
        directory.mkdir(mode=0o700)
    all_prompts = set()
    train, test, oracle, test_specs = [], [], [], []
    for domain in DOMAINS:
        for phase, count in (("train", per_domain_train), ("test", per_domain_test)):
            for i in range(count):
                for _ in range(5000):
                    question, answer = _make(rng, domain)
                    if question not in all_prompts:
                        all_prompts.add(question)
                        break
                else:
                    raise ValueError("insufficient unique questions")
                task_id = f"{domain}-{phase}-{i:03d}"
                row = {"task_id": task_id, "domain": domain, "prompt": question}
                if phase == "train":
                    train.append({**row, "answer": answer})
                else:
                    test.append(row)
                    test_specs.append({"task_id": task_id, "domain": domain})
                    oracle.append({"task_id": task_id, "answer": answer})
    manifest = {"schema": SCHEMA, "study_id": "toy-holdout-pilot-NOT-A-REAL-AGENT-TRIAL",
                "model_id": model_id, "arms": ARMS,
                "train_task_ids": [x["task_id"] for x in train],
                "test_tasks": test_specs,
                "token_budget_per_arm": 100000}
    _jsonl(release / "train_examples.jsonl", train)
    _jsonl(holdout / "test_prompts.jsonl", test)
    _jsonl(sealed / "oracle.jsonl", oracle)
    (release / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    seed_file = sealed / "seed.txt"
    seed_file.write_text(str(seed) + "\n", encoding="utf-8")
    for file in sealed.iterdir():
        os.chmod(file, 0o600)
    return {"manifest": manifest, "n_train": len(train), "n_test": len(test),
            "note": "Not a blind evaluation unless seed/oracle/holdout remain outside agent access."}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--train-per-domain", type=int, default=4)
    parser.add_argument("--test-per-domain", type=int, default=8)
    parser.add_argument("--model-id", type=str, required=True)
    parser.add_argument("--fixture-seed", type=int, default=None,
                        help="FOR REPRODUCIBLE FIXTURES ONLY; never reveal experimental seeds")
    args = parser.parse_args()
    result = build(args.out, per_domain_train=args.train_per_domain,
                   per_domain_test=args.test_per_domain, seed=args.fixture_seed,
                   model_id=args.model_id)
    print(json.dumps({"n_train": result["n_train"], "n_test": result["n_test"],
                      "output_directory": str(args.out), "warning": result["note"]}, indent=2))


if __name__ == "__main__":
    main()
