"""Offline discovery of the real SYN audit stack; scripted reasoning, no LLM."""
from __future__ import annotations
import argparse
import json
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path
from synergesis_aegis import ActionSecurityProfile, CapabilityStore, IdentityRegistry, IdentitySigner
from synergesis_agent_loop_v2 import ActionProposal, ActionResult, AgentObservation, Goal, Hypothesis, LearningSignal, ReasoningOutput
from synergesis_agent_loop_v4 import ActionTypeResourceResolver, NoCapabilities, TrustedSourceObservationClassifier
from synergesis_planner import PlanDraft, PlanStepDraft, StepAssessment
from synergesis_reality import FileStateProbe, RealityAssertion, RealityProbeBinding, RealityProfile
from synergesis_roam import RoamLimits, SelectionConfig, SourceRegistry, UtilityWeights
from synergesis_roam_adaptive import AdaptiveSelectionConfig
from synergesis_roam_attention import AttentionWeights
from synergesis_roam_evolution import EvolutionPolicy
from synergesis_roam_service import RoamServiceLimits
from synergesis_glyph_protocol import GlyphLedger
from synergesis_secure_roam_stack_v2 import SecureRoamConfig, build_secure_roam_reality_stack


class Reasoner:
    def reason(self, context):
        return ReasoningOutput(
            (
                Hypothesis.create(
                    "Write the file.",
                    rationale="scripted offline demonstration",
                ),
            ),
            ActionProposal.create(
                "file.write",
                {"path": "integrated.txt", "content": "verified"},
                rationale="scripted offline demonstration",
                expected_outcome="file exists",
                strategy_key="integrated-file-write",
            ),
        )

    def evaluate(self, context, proposal, result):
        return LearningSignal(0.9, "Observed effective result.")

class Planner:
    def create_plan(self, context):
        return PlanDraft(
            rationale="One file step.",
            steps=(
                PlanStepDraft(
                    "Write file",
                    "file is verified",
                    "file.write",
                ),
            ),
        )

    def assess_step(self, context, step, cycle):
        return StepAssessment(
            "completed"
            if cycle.action_result and cycle.action_result.success
            else "blocked",
            "Use verified action result.",
            1.0,
        )

    def replan(self, context, previous_plan, failed_step, assessment):
        return PlanDraft(
            rationale="Retry once.",
            steps=(
                PlanStepDraft(
                    "Retry file",
                    "file is verified",
                    "file.write",
                ),
            ),
        )

def config(tmp_path):
    return SecureRoamConfig(
        root=tmp_path / "stack",
        identity="ZÆL-0",
        allowed_actions=frozenset({"file.write"}),
        context_max_facts=8,
        context_max_evidence=8,
        bm25_k1=1.5,
        bm25_b=0.75,
        max_steps_per_plan=3,
        max_replans=1,
        max_attempts_per_step=2,
        roam_limits=RoamLimits(2, 4, 2.0),
        selection_config=SelectionConfig(0.0, True),
        adaptive_selection_config=AdaptiveSelectionConfig(
            rolling_window_per_method=4,
            max_selection_gap=3,
            exploration_strength=0.1,
            decay_half_life_events=3.0,
        ),
        utility_weights=UtilityWeights(1, 1, 1, 1, 1, 1, 1),
        attention_weights=AttentionWeights(1, 1, 1, 1),
        service_limits=RoamServiceLimits(2, True),
        evolution_policy=EvolutionPolicy(
            max_steps_per_method=2,
            min_trials_per_method=1,
            promotion_margin=0.1,
            require_counter_search=True,
        ),
    )

def run_scenario(root: Path, *, claim_only: bool) -> dict:
    # Caller supplies a fresh directory: old files cannot confirm a new action.
    root.mkdir(parents=True, exist_ok=False)
    runtime = root / "runtime"
    runtime.mkdir()
    target = runtime / "integrated.txt"
    identities = IdentityRegistry(root / "identities.jsonl")
    signer = IdentitySigner("ZÆL-0")
    identities.register(signer.identity_id, signer.public_key)

    def executor(params):
        if params != {"path": "integrated.txt", "content": "verified"}:
            raise ValueError("The demo only permits its fixed local file action")
        if not claim_only:
            target.write_text(params["content"], encoding="utf-8")
        return ActionResult("file.write", True, {"claimed": "ok"})

    probe = FileStateProbe(observer_id="os:file", allowed_root=runtime,
                          path_parameter="path", max_hash_bytes=1024)
    stack = build_secure_roam_reality_stack(
        config=config(root), reasoner=Reasoner(), planning_provider=Planner(),
        executors={"file.write": executor}, identity_registry=identities,
        capability_store=CapabilityStore(root / "capabilities.jsonl"),
        trusted_capability_issuers=frozenset(),
        action_security_profiles=(ActionSecurityProfile("file.write", False, frozenset()),),
        observation_classifier=TrustedSourceObservationClassifier(trusted_sources=frozenset({"user"})),
        capability_resolver=NoCapabilities(), resource_resolver=ActionTypeResourceResolver(),
        reality_probe_bindings=(RealityProbeBinding("os:file", "runtime_attested", probe),),
        reality_profiles=(RealityProfile("file.write", ("os:file",), (
            RealityAssertion("os:file", "exists", "eq", True),
            RealityAssertion("os:file", "sha256", "sha256_parameter_utf8", parameter_key="content"),
        )),),
        source_registry=SourceRegistry(), source_adapters={}, research_methods=(),
    )
    recorded = stack.agent_audit.run_cycle(
        goal=Goal.create("Écrire et vérifier le fichier de démonstration"),
        observation=AgentObservation("request", {"scenario": "offline discovery"}, "user"),
    )
    cycle = recorded.cycle
    ledger_path = root / "stack" / "glyph_ledger.jsonl"
    checkpoint = stack.graph.ledger.verify()
    # Re-open durable audit with a fresh reader, not just the in-memory graph.
    reopened = GlyphLedger(ledger_path)
    if reopened.verify() != checkpoint:
        raise RuntimeError("Audit checkpoint differs on reopening")
    reality = cycle.action_result.output["reality"]
    result = {
        "scenario": "claim_only" if claim_only else "real_write",
        "authorized": cycle.policy.allowed,
        "effective_success": cycle.action_result.success,
        "reality": reality,
        "learning_score": cycle.learning.score,
        "file_exists": target.exists(),
        "audit": asdict(checkpoint),
        "ledger": str(ledger_path),
        "cycle_glyph_id": recorded.cycle_glyph_id,
        "trace_ids": {k: v for k, v in asdict(recorded).items() if k.endswith("glyph_id")},
        "kinds": sorted({g.content.get("kind") for g in reopened.glyphs()
                         if isinstance(g.content, dict) and isinstance(g.content.get("kind"), str)}),
    }
    if not result["authorized"] or result["effective_success"] != (not claim_only):
        raise RuntimeError("Unexpected authorization or observed outcome")
    if claim_only and result["learning_score"] != 0:
        raise RuntimeError("Unconfirmed success was rewarded")
    return result


def run_discovery(output: Path | None = None) -> dict:
    if sys.platform == "win32":
        raise RuntimeError("Cette démonstration nécessite Linux, macOS ou WSL (verrous POSIX).")
    if output is None:
        output = Path(tempfile.mkdtemp(prefix="syn-decouverte-"))
    else:
        output = output.expanduser().resolve()
        output.mkdir(parents=True, exist_ok=False)
    output = output.resolve()
    report = {
        "mode": "scripted_offline_real_stack",
        "limitations": ["No LLM or Internet", "Two isolated fresh scenarios", "Not an autonomy or power-loss qualification"],
        "scenarios": [run_scenario(output / "action_reelle", claim_only=False),
                      run_scenario(output / "annonce_inexacte", claim_only=True)],
    }
    (output / "bilan.json").write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="Découvrir l'auditabilité de SYN, hors réseau et sans clé API.")
    parser.add_argument("--output", type=Path, help="Nouveau dossier pour conserver les traces (ne doit pas exister)")
    args = parser.parse_args(argv)
    try:
        report = run_discovery(args.output)
    except (OSError, RuntimeError, ValueError) as exc:
        parser.exit(1, f"Démonstration arrêtée : {exc}\n")
    print("SYN — première découverte (scénario programmé, sans LLM ni Internet)")
    for r in report["scenarios"]:
        label = "Action réellement effectuée" if r["scenario"] == "real_write" else "Réussite annoncée sans action"
        print(f"\n{label} :")
        print(f"  Constat REALITY : {r['reality']['status']}")
        print(f"  Réussite retenue : {'oui' if r['effective_success'] else 'non'}")
        print(f"  Score d'apprentissage retenu : {r['learning_score']}")
        print(f"  Historique vérifié et relu : {r['audit']['event_count']} événements")
        print(f"  Journal : {r['ledger']}")
    print("\nLes deux contrôles ont réussi. Les observations et décisions sont conservées dans les journaux.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
