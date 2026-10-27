"""Internal toy negative-control solver, NOT SYN, ChatGPT or an LLM.

Parses only the final current task, never opens or reads the sealed oracle.
In the toy pack its ceiling performance reveals that tasks may be too easy.
"""
import re
from datetime import date, timedelta


def answer(prompt):
    task = prompt.split('Current task:\n\n')[-1]
    if task.startswith('Calculate '):
        m = re.fullmatch(r'Calculate (\d+) times \((-?\d+)\) minus 2 times \((-?\d+)\)\. Return a single integer\.', task)
        assert m, task
        c, a, b = map(int, m.groups())
        return str(c * a - 2 * b), 0
    if task.startswith('What is the UTC calendar date'):
        m = re.fullmatch(r'What is the UTC calendar date (\d+) days after (\d{4}-\d{2}-\d{2})\? Return YYYY-MM-DD\.', task)
        assert m, task
        days, dt = m.groups()
        return (date.fromisoformat(dt) + timedelta(days=int(days))).isoformat(), 0
    if task.startswith('Directed graph edges:'):
        m = re.fullmatch(r'Directed graph edges: (.*)\. Is there a directed path from ([A-F]) to ([A-F])\? Reply YES or NO\.', task)
        assert m, task
        edges, start, end = m.groups()
        links = re.findall(r'([A-F])->([A-F])', edges)
        todo, seen = [start], {start}
        while todo:
            cur = todo.pop(0)
            for a, b in links:
                if a == cur and b not in seen:
                    seen.add(b)
                    todo.append(b)
        return ('YES' if end in seen else 'NO'), 0
    raise ValueError(task)
