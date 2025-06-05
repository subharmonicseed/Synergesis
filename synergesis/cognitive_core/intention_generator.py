"""Autonomous intention generation logic for Synergesis."""
from __future__ import annotations

import logging
import random
import sys
import time
from typing import Any, Dict, List, Optional

try:
    from ..glyph_core import GlyphData, STATUS_VALUES, RELATIONSHIP_TYPES
    from ..storage.neo4j_interface import Neo4jInterface
    from .memory_system import MemorySystem
    from ..protocols.system_goals import SystemGoal
except Exception:  # pragma: no cover - fall back if dependencies missing
    logging.getLogger(__name__).warning("Using placeholder types for missing imports")
    GlyphData = Dict[str, Any]  # type: ignore
    STATUS_VALUES = ["proposed_by_system"]
    RELATIONSHIP_TYPES = ["action_to_be_simulated_by"]

    class Neo4jInterface:  # type: ignore
        pass

    class MemorySystem:  # type: ignore
        def get_bias_for_strategy(self, strategy_tags: List[str], target_context: Dict[str, Any]) -> float:
            return 0.0

    class SystemGoal:  # type: ignore
        @staticmethod
        def get_active_goals() -> List[Dict[str, Any]]:
            return [
                {
                    "id": "goal_max_resonance",
                    "type": "maximize",
                    "metric": "global_resonance",
                    "target_value": 75.0,
                    "priority": 1.0,
                }
            ]

# ----------------------------------------------------------------------------
log = logging.getLogger("IntentionGenerator")
if not log.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    log.addHandler(handler)
log.setLevel(logging.INFO)

DEFAULT_CONFIDENCE = 0.70
STRATEGY_MEMORY_THRESHOLD_AVOID = -0.5


class IntentionGenerator:
    """Generate `potential_action` glyphs from goals, gradients and memory."""

    def __init__(self, neo4j_iface: Neo4jInterface, memory_system: MemorySystem, config: Optional[Dict[str, Any]] = None) -> None:
        self.neo4j_iface = neo4j_iface
        self.memory_system = memory_system
        self.config = config or {}
        self.generator_id = "sem-intentiongenerator-C01"
        self.counter = 0
        log.info("IntentionGenerator initialised")

    # ------------------------------------------------------------------
    def _next_action_id(self) -> str:
        self.counter += 1
        return f"GEN{self.counter:03d}"

    # ------------------------------------------------------------------
    def _fetch_system_goals(self) -> List[Dict[str, Any]]:
        try:
            return SystemGoal.get_active_goals()  # type: ignore[attr-defined]
        except Exception:  # pragma: no cover - placeholder fallback
            return [
                {
                    "id": "goal_max_resonance",
                    "type": "maximize",
                    "metric": "global_resonance",
                    "target_value": 75.0,
                    "priority": 1.0,
                },
                {
                    "id": "goal_constrain_entropy",
                    "type": "constrain_between",
                    "metric": "global_entropy_avg",
                    "range": [0.35, 0.65],
                    "priority": 0.9,
                },
            ]

    def _fetch_current_gradients(self) -> Dict[str, Any]:
        # Placeholder gradient retrieval
        return {
            "clusters": {
                "cluster_Alpha": {"resonance": 59, "entropy": 0.57, "tags": ["low_resonance_focus"]},
                "cluster_Beta": {"resonance": 81, "entropy": 0.655, "tags": ["high_entropy_focus"]},
            },
            "global_metrics": {"resonance_avg": 55.0, "entropy_avg": 0.47},
        }

    # ------------------------------------------------------------------
    def _evaluate_goal_deviations(self, goals: List[Dict[str, Any]], gradients: Dict[str, Any]) -> List[Dict[str, Any]]:
        devs: List[Dict[str, Any]] = []
        global_res = gradients.get("global_metrics", {}).get("resonance_avg", 50)
        global_ent = gradients.get("global_metrics", {}).get("entropy_avg", 0.5)

        for goal in goals:
            if goal["metric"] == "global_resonance" and global_res < goal.get("target_value", 0):
                devs.append({
                    "goal_id": goal["id"],
                    "metric": "global_resonance",
                    "delta": goal["target_value"] - global_res,
                    "target_zone": "global",
                    "priority": goal["priority"] * abs(goal["target_value"] - global_res) / 20.0,
                })
            elif goal["metric"] == "global_entropy_avg":
                rng = goal.get("range", [0, 1])
                if not (rng[0] <= global_ent <= rng[1]):
                    delta = global_ent - rng[1] if global_ent > rng[1] else rng[0] - global_ent
                    devs.append({
                        "goal_id": goal["id"],
                        "metric": "global_entropy_avg",
                        "delta": delta,
                        "target_zone": "global",
                        "priority": goal["priority"] * abs(delta) / 0.1,
                    })

        for cid, metrics in gradients.get("clusters", {}).items():
            if "low_resonance_focus" in metrics.get("tags", []) and metrics["resonance"] < 75:
                devs.append({
                    "goal_id": "goal_max_resonance_local",
                    "metric": f"{cid}_resonance",
                    "delta": 75 - metrics["resonance"],
                    "target_zone": cid,
                    "priority": 0.8 * abs(75 - metrics["resonance"]) / 20.0,
                })
            if "high_entropy_focus" in metrics.get("tags", []) and metrics["entropy"] > 0.65:
                devs.append({
                    "goal_id": "goal_constrain_entropy_local",
                    "metric": f"{cid}_entropy",
                    "delta": metrics["entropy"] - 0.65,
                    "target_zone": cid,
                    "priority": 0.8 * abs(metrics["entropy"] - 0.65) / 0.1,
                })
        devs.sort(key=lambda d: d["priority"], reverse=True)
        return devs

    # ------------------------------------------------------------------
    def _select_strategy(self, dev: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        tags: List[str] = ["autonomously_generated"]
        if "resonance" in dev["metric"]:
            bias = self.memory_system.get_bias_for_strategy(["celestial_infusion", f"target:{dev['target_zone']}"] , dev)
            if bias < STRATEGY_MEMORY_THRESHOLD_AVOID:
                return None
            return {
                "action_type": "RESONANCE_ENHANCEMENT",
                "polarité": "+",
                "alignement": "Celestial",
                "poids": 7,
                "fréquence": 90,
                "method": "Focused Celestial Harmonization",
                "tags": tags + ["resonance_boost", "celestial_infusion"],
                "impact_key": "local_resonance_delta",
            }
        if "entropy" in dev["metric"]:
            bias = self.memory_system.get_bias_for_strategy(["meta_stabilization", f"target:{dev['target_zone']}"] , dev)
            if bias < STRATEGY_MEMORY_THRESHOLD_AVOID:
                return None
            return {
                "action_type": "ENTROPY_CONTROL_META_RESTRUCTURE",
                "polarité": "0",
                "alignement": {"Void": 0.6, "Celestial": 0.4},
                "poids": 7,
                "fréquence": 75,
                "method": "Void-guided Emergent Structuring",
                "tags": tags + ["meta_stabilization", "entropy_control"],
                "impact_key": "local_entropy_delta",
            }
        return None

    # ------------------------------------------------------------------
    def propose_actions(self) -> List[GlyphData]:
        log.info("Starting intention generation cycle")
        goals = self._fetch_system_goals()
        grads = self._fetch_current_gradients()
        devs = self._evaluate_goal_deviations(goals, grads)
        if not devs:
            log.info("No deviations detected; no actions proposed")
            return []
        dev = devs[0]
        strategy = self._select_strategy(dev)
        if not strategy:
            log.info("No strategy selected for top deviation")
            return []

        action_id = f"sem-potentialaction-{self._next_action_id()}"
        ts = time.time()
        glyph: GlyphData = {
            "id": action_id,
            "timestamp": ts,
            "source": self.generator_id,
            "concept_type": "POTENTIAL_ACTION",
            "action_type": strategy["action_type"],
            "status": "proposed_by_system",
            "priority": int(min(99, dev["priority"] * 10)),
            "confidence": DEFAULT_CONFIDENCE,
            "polarité": strategy["polarité"],
            "alignement": strategy["alignement"],
            "poids": strategy["poids"],
            "fréquence": strategy["fréquence"],
            "target_zone": dev["target_zone"],
            "tags": strategy["tags"] + [f"target:{dev['target_zone']}", f"objective:{dev['goal_id']}", "phase_VIII", "wave_VIII_active"],
            "natural_prompt": f"Action proposée : {strategy['method']} sur {dev['target_zone']}",
            "details_structured_json": {
                "action_parameters": {
                    "target_cluster_id": dev["target_zone"],
                    strategy["impact_key"]: f"{dev['delta']:+.2f}",
                },
                "source_metadata": {
                    "intention_type": "SYSTEM_REGULATION",
                    "triggering_gradient_metric": dev["metric"],
                    "triggering_gradient_delta": dev["delta"],
                    "referenced_goal_id": dev["goal_id"],
                },
                "expected_impact": {"structural_metrics": {strategy["impact_key"]: "approx"}},
                "execution_requirements": {"preconditions": [f"{dev['target_zone']}_exists"]},
                "rollback_procedure": {"action": "MONITOR_AND_COUNTER_IF_ADVERSE_EFFECTS"},
            },
            "details_text": strategy["method"],
            "sourceIds": [self.generator_id],
            "entropy_score": round(0.4 + random.random() * 0.2, 2),
            "relationships": [{"type": "action_to_be_simulated_by", "target_glyph_id": "sem-simulationengine-V01"}],
        }
        log.info("Proposed action %s for zone %s", action_id, dev["target_zone"])
        return [glyph]
