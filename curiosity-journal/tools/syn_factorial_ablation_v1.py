"""Factorial memory x skill-card prompt experiment for SYN (NOT autonomous learning).

Uses the existing local Ollama runner and scorecard. The four historical arm
names map to 2x2 factors: baseline=00, journal=10, research=01, skills=11.
A skill card is frozen training material, not proof that SYN learned it.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import random

ARMS = ("baseline", "journal", "research", "skills")
FACTORS = {"baseline": (0, 0), "journal": (1, 0), "research": (0, 1), "skills": (1, 1)}


def _module(name: str):
    file = Path(__file__).with_name(name + ".py")
    spec = importlib.util.spec_from_file_location(name, file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _require(ok: bool, message: str):
    if not ok:
        raise ValueError(message)


def validate_cards(cards: dict, train: list[dict], test: list[dict]) -> dict[str, dict]:
    _require(isinstance(cards, dict) and set(cards) == {"schema", "cards"}
             and cards["schema"] == "syn-factorial-skill-cards-v1", "bad skill-card schema")
    _require(isinstance(cards["cards"], list), "cards must be a list")
    train_ids = {r["task_id"] for r in train}
    test_ids = {r["task_id"] for r in test}
    result = {}
    for card in cards["cards"]:
        _require(isinstance(card, dict) and set(card) == {
            "domain", "skill_id", "procedure", "origin", "training_evidence_ids"
        }, "bad card object")
        d, sid, procedure = card["domain"], card["skill_id"], card["procedure"]
        _require(isinstance(d, str) and d in ("arithmetic", "calendar", "graph")
                 and d not in result, "unknown or duplicate card domain")
        _require(isinstance(sid, str) and 1 <= len(sid) <= 120 and sid.strip() == sid,
                 "invalid skill id")
        _require(isinstance(procedure, str) and 1 <= len(procedure) <= 1500,
                 "invalid procedure")
        _require(card["origin"] in ("human_authored", "syn_candidate"), "unknown card origin")
        e = card["training_evidence_ids"]
        _require(isinstance(e, list) and all(isinstance(k, str) for k in e)
                 and len(set(e)) == len(e)
                 and all(k in train_ids and k not in test_ids for k in e),
                 "invalid skill evidence IDs")
        _require(card["origin"] != "syn_candidate" or len(e) > 0,
                 "SYN candidate needs training evidence (not proof of learning)")
        _require(all(row["prompt"] not in procedure for row in test),
                 "test prompt leaked into skill card")
        result[d] = card
    return result


def build(manifest: dict, train: list[dict], test: list[dict], cards: dict,
          *, seed: int = 26) -> list[dict]:
    """Return four factorial conditions, balanced order for blocks of 4 tasks."""
    _require(type(seed) is int and 0 <= seed <= 2**31 - 1, "invalid seed")
    old = _module("syn_four_arm_trial_v0")
    tasks, by_domain = old._rows(manifest, train, test)
    card_by_domain = validate_cards(cards, train, tasks)
    _require(set(card_by_domain) == {x["domain"] for x in tasks},
             "exactly one skill card required for each test domain")
    rng = random.Random(seed)
    tasks = sorted(tasks, key=lambda row: row["task_id"])
    rng.shuffle(tasks)
    req = []
    for i, task in enumerate(tasks):
        order = list(ARMS[i % 4:]) + list(ARMS[:i % 4])
        for arm in order:
            memory, skill = FACTORS[arm]
            parts = ["Controlled comparison. Reply with JSON containing only a string key 'answer'."]
            if memory:
                parts.append("Training examples from this domain:")
                parts += [f"Q: {ex['prompt']}\nA: {ex['answer']}"
                          for ex in by_domain[task["domain"]]]
            if skill:
                parts.extend(["Candidate procedure (not validated on held-out tasks):",
                              card_by_domain[task["domain"]]["procedure"]])
            parts += ["Current task:", task["prompt"]]
            prompt = "\n\n".join(parts)
            _require(len(prompt) <= 25000, "prompt too long")
            req.append({"task_id": task["task_id"], "arm": arm,
                        "domain": task["domain"], "model_id": manifest["model_id"],
                        "prompt": prompt,
                        "skill_ids": [card_by_domain[task["domain"]]["skill_id"]] if skill else []})
    return req


def summarize(scored: dict) -> dict:
    rates = {a: scored["results_by_arm"][a]["pass_rate"] for a in ARMS}
    m00, m10, m01, m11 = (rates[a] for a in ARMS)
    return {"schema": "syn-factorial-summary-v1", "study_id": scored["study_id"],
            "accuracy": rates,
            "memory_effect_without_skill": m10 - m00,
            "memory_effect_with_skill": m11 - m01,
            "skill_effect_without_memory": m01 - m00,
            "skill_effect_with_memory": m11 - m10,
            "interaction": m11 - m10 - m01 + m00,
            "interpretation": "DESCRIPTIVE_ONLY. Skill cards are supplied, not proven learned. "
                              "No causality, general intelligence or calibration established."}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("action", choices=("prepare", "run-ollama", "analyze"))
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--train", type=Path)
    ap.add_argument("--test", type=Path)
    ap.add_argument("--cards", type=Path)
    ap.add_argument("--oracle", type=Path)
    ap.add_argument("--attempts", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=26)
    ap.add_argument("--ollama-port", type=int, default=11434)
    args = ap.parse_args()
    old = _module("syn_four_arm_trial_v0")
    scoring = _module("syn_skill_transfer_eval_v0")
    manifest = old._read_json(args.manifest)
    if args.action == "analyze":
        _require(args.oracle is not None and args.attempts is not None,
                 "analyze needs --oracle and --attempts")
        full = scoring.evaluate(manifest, scoring._read_jsonl(args.oracle),
                                scoring._read_jsonl(args.attempts))
        summary = summarize(full)
        old._atomic_new(args.out, json.dumps(summary, indent=2) + "\n")
    else:
        _require(args.train is not None and args.test is not None and args.cards is not None,
                 "prepare/run-ollama need --train --test --cards")
        train = old._read_jsonl(args.train)
        test = old._read_jsonl(args.test)
        cards = old._read_json(args.cards)
        requests = build(manifest, train, test, cards, seed=args.seed)
        if args.action == "prepare":
            _require(not args.out.exists(), "refusing to overwrite")
            args.out.mkdir(parents=True, mode=0o700)
            old._atomic_new(args.out / "requests.jsonl",
                            "".join(json.dumps(q, ensure_ascii=False) + "\n" for q in requests))
            old._atomic_new(args.out / "receipt.json", json.dumps({
                "arms": FACTORS, "seed": args.seed, "status": "prepared_not_executed",
                "cards_sha256": sha256(args.cards.read_bytes()).hexdigest(),
                "n_requests": len(requests),
                "warning": "Factorial prompt study, NOT four independent SYN agents."
            }, indent=2) + "\n")
            summary = {"status": "prepared_not_executed", "n_requests": len(requests)}
        else:
            backend = old.LocalOllama(manifest["model_id"], port=args.ollama_port,
                                      seed=args.seed)
            summary = old.run(requests, manifest["model_id"], backend, args.out)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
