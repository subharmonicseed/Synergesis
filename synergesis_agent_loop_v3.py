"""Agent Loop v3 with optional SYN-AEGIS pre-execution authorization.

The existing PermissionPolicy remains the first boundary. AEGIS is a second,
stricter boundary that may only deny an already allowlisted proposal; it cannot
expand permissions.
"""
from __future__ import annotations

from synergesis_agent_loop_v2 import *  # re-export canonical v2 data contracts
from synergesis_agent_loop_v2 import SynAgentLoop as _SynAgentLoopV2
from synergesis_aegis import AegisGuard, SecurityContext


class SynAgentLoopV3(_SynAgentLoopV2):
    def __init__(self, *, aegis_guard: AegisGuard | None = None, **kwargs):
        super().__init__(**kwargs)
        self.aegis_guard = aegis_guard

    def run_cycle(
        self,
        *,
        goal: Goal,
        observation: AgentObservation,
        required_predicates: Sequence[str] = (),
        rules: Sequence[Any] = (),
        action_scope: Optional[frozenset[str]] = None,
        security_context: SecurityContext | None = None,
    ) -> AgentCycle:
        # If AEGIS is absent, preserve v2 behavior exactly.
        if self.aegis_guard is None:
            return super().run_cycle(
                goal=goal,
                observation=observation,
                required_predicates=required_predicates,
                rules=rules,
                action_scope=action_scope,
            )

        # We need the v2 orchestration but with AEGIS inserted between the
        # ordinary policy/scope checks and executor dispatch. To avoid changing
        # the stable v2 file, use a temporary policy that can only narrow access.
        base_policy = self.policy
        guard = self.aegis_guard
        supplied_context = security_context

        class _CompositePolicy:
            allowed_actions = base_policy.allowed_actions

            def check(_self, proposal):
                ordinary = base_policy.check(proposal)
                if not ordinary.allowed:
                    return ordinary
                if supplied_context is None:
                    # Security-enabled loop must not invent actor/provenance.
                    return PolicyDecision(False, "aegis:missing_security_context")
                return guard.check(proposal, supplied_context)

        self.policy = _CompositePolicy()
        try:
            return super().run_cycle(
                goal=goal,
                observation=observation,
                required_predicates=required_predicates,
                rules=rules,
                action_scope=action_scope,
            )
        finally:
            self.policy = base_policy
