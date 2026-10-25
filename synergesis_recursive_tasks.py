"""Bounded executable benchmark tasks and a separately implemented toy oracle.

These are synthetic arithmetic/calendar/reachability problems, not discoveries.
The exact executor and the oracle deliberately use different algorithms.
"""
from __future__ import annotations

import calendar
from datetime import date, timedelta
from decimal import Decimal
import random
import re

from synergesis_recursive import digest, require

DOMAINS = ("arithmetic", "calendar", "graph")


def validate_task(task: dict) -> None:
    require(isinstance(task, dict) and set(task) == {"task_id", "domain", "input"}, "bad task fields")
    require(isinstance(task["task_id"], str) and 1 <= len(task["task_id"]) <= 160
            and task["domain"] in DOMAINS and isinstance(task["input"], dict), "bad task")
    domain, data = task["domain"], task["input"]
    if domain == "arithmetic":
        require(set(data) == {"a", "b", "c"} and all(type(v) is int and abs(v) <= 10000
                                                     for v in data.values()), "bad arithmetic")
    elif domain == "calendar":
        require(set(data) == {"date", "days"} and isinstance(data["date"], str)
                and re.fullmatch(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}", data["date"]) is not None
                and type(data["days"]) is int and 1 <= data["days"] <= 365, "bad calendar")
        date.fromisoformat(data["date"])
    else:
        require(set(data) == {"nodes", "edges", "start", "target"}
                and isinstance(data["nodes"], list) and 2 <= len(data["nodes"]) <= 20
                and all(isinstance(n, str) and re.fullmatch(r"[A-Z]", n) for n in data["nodes"])
                and len(set(data["nodes"])) == len(data["nodes"]), "bad graph nodes")
        require(isinstance(data["edges"], list) and len(data["edges"]) <= 400
                and all(isinstance(e, list) and len(e) == 2 and all(n in data["nodes"] for n in e)
                        for e in data["edges"])
                and data["start"] in data["nodes"] and data["target"] in data["nodes"], "bad graph")


def prompt_for(task: dict) -> str:
    validate_task(task)
    d = task["input"]
    if task["domain"] == "arithmetic":
        return f"Calculate {d['c']} times ({d['a']}) minus 2 times ({d['b']}). Return a single integer."
    if task["domain"] == "calendar":
        return f"What is the UTC Gregorian calendar date {d['days']} days after {d['date']}? Return YYYY-MM-DD."
    edges = ", ".join(f"{a}->{b}" for a, b in d["edges"]) or "none"
    return (f"Directed graph edges: {edges}. Is there a directed path from {d['start']} "
            f"to {d['target']}? Reply YES or NO.")


def exact_executor(task: dict) -> str:
    validate_task(task)
    d = task["input"]
    if task["domain"] == "arithmetic":
        return str(d["c"] * d["a"] - 2 * d["b"])
    if task["domain"] == "calendar":
        return (date.fromisoformat(d["date"]) + timedelta(days=d["days"])).isoformat()
    seen, pending = {d["start"]}, [d["start"]]
    while pending:
        current = pending.pop()
        for a, b in d["edges"]:
            if a == current and b not in seen:
                seen.add(b)
                pending.append(b)
    return "YES" if d["target"] in seen else "NO"


def oracle_answer(task: dict) -> str:
    """Evaluator only: Decimal, day-by-day calendar, and Warshall closure."""
    validate_task(task)
    d = task["input"]
    if task["domain"] == "arithmetic":
        return str(int(Decimal(d["a"]) * Decimal(d["c"]) - Decimal(d["b"]) * Decimal(2)))
    if task["domain"] == "calendar":
        year, month, day = map(int, d["date"].split("-"))
        for _ in range(d["days"]):
            day += 1
            if day > calendar.monthrange(year, month)[1]:
                day = 1
                month += 1
                if month == 13:
                    year, month = year + 1, 1
        return f"{year:04d}-{month:02d}-{day:02d}"
    nodes = d["nodes"]
    reach = {(a, b): (a == b or [a, b] in d["edges"]) for a in nodes for b in nodes}
    for k in nodes:
        for a in nodes:
            for b in nodes:
                reach[a, b] = reach[a, b] or (reach[a, k] and reach[k, b])
    return "YES" if reach[d["start"], d["target"]] else "NO"


def make_tasks(seed: int, prefix: str, domains: tuple[str, ...], count: int,
               *, exclude: set[str] | None = None) -> list[dict]:
    require(type(count) is int and 1 <= count <= 500 and all(d in DOMAINS for d in domains),
            "bad generation parameters")
    rng = random.Random(seed)
    seen, tasks = set(exclude or ()), []
    for domain in domains:
        for index in range(count):
            for _ in range(10000):
                if domain == "arithmetic":
                    data = {"a": rng.randint(-700, 700), "b": rng.randint(-700, 700),
                            "c": rng.randint(2, 19)}
                elif domain == "calendar":
                    base = date(2024, 1, 1) + timedelta(days=rng.randrange(1095))
                    data = {"date": base.isoformat(), "days": rng.randint(15, 150)}
                else:
                    nodes = list("ABCDEFGH")
                    a, b = rng.sample(nodes, 2)
                    data = {"nodes": nodes, "edges": [[x, y] for x in nodes for y in nodes
                                                       if x != y and rng.random() < .17],
                            "start": a, "target": b}
                fingerprint = digest({"domain": domain, "input": data})
                if fingerprint not in seen:
                    seen.add(fingerprint)
                    break
            else:
                raise ValueError("unique task space exhausted")
            tasks.append({"task_id": f"{prefix}-{domain}-{index:03d}", "domain": domain, "input": data})
    return tasks
