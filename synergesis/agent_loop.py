"""Main orchestration loop for Synergesis."""
from __future__ import annotations

import schedule

from .cognitive_core.intention_generator import IntentionGenerator
from .cognitive_core.simulation_engine import SimulationEngine


def task_generate_and_simulate() -> None:
    generator = IntentionGenerator()
    actions = generator.propose_actions()
    sim = SimulationEngine()
    for act in actions:
        sim.simulate_action(act, {})


def run() -> None:
    schedule.every(1).seconds.do(task_generate_and_simulate)
    while True:
        schedule.run_pending()
