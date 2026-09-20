"""SYN-AEGIS: capability security and provenance controls for Synergesis.

AEGIS complements Glyph Protocol v1. It does not trust natural-language claims
of authority. Authority is represented by cryptographically signed capability
grants and explicit policy configuration.

Security invariants
-------------------
1. Data != instruction != authority.
2. A model or web page cannot grant itself capabilities.
3. Learning never changes permissions.
4. Unknown/unprofiled action types are denied.
5. Quarantined provenance cannot authorize consequential actions.
6. Signed identity authenticates who sent a message; it does not by itself
   authorize an action.
7. Security decisions are recorded in the Glyph audit graph.

This implementation uses Ed25519 from ``cryptography``. Registry persistence
stores public keys only; private keys remain caller-owned.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timezone
from hashlib import sha256
import base64
import json
import math
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
)

from synergesis_agent_loop_v2 import ActionProposal, PolicyDecision
from synergesis_glyph_protocol import Glyph, GlyphAuditGraph


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("security timestamps must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _canonical_native(value: Any) -> Any:
    if is_dataclass(value):
        return _canonical_native(asdict(value))
    if isinstance(value, Mapping):
        return {
            str(k): _canonical_native(v)
            for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))
        }
    if isinstance(value, (tuple, list)):
        return [_canonical_native(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("non-finite values are not signable")
        return value
    raise TypeError(f"unsupported canonical value: {type(value).__name__}")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        _canonical_native(value),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


def _fingerprint(public_key_bytes: bytes) -> str:
    return sha256(public_key_bytes).hexdigest()


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value.encode("ascii"))


@dataclass(frozen=True)
class IdentityRecord:
    identity_id: str
    public_key_b64: str
    fingerprint: str
    registered_at: str
    status: str = "active"

    def __post_init__(self):
        if not self.identity_id.strip():
            raise ValueError("identity_id is required")
        if self.status not in {"active", "revoked"}:
            raise ValueError("identity status must be active or revoked")


class IdentityRegistry:
    """Append-only public-key registry. No private key is persisted here."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _events(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [
            json.loads(line)
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def register(self, identity_id: str, public_key: Ed25519PublicKey) -> IdentityRecord:
        raw = public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)
        fingerprint = _fingerprint(raw)
        current = self.get_optional(identity_id)
        if current is not None:
            if current.fingerprint != fingerprint:
                raise ValueError("identity already registered with a different key")
            if current.status != "active":
                raise ValueError("revoked identity cannot be silently reactivated")
            return current

        record = IdentityRecord(
            identity_id=identity_id,
            public_key_b64=_b64(raw),
            fingerprint=fingerprint,
            registered_at=_now(),
            status="active",
        )
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"kind": "register", **asdict(record)}, sort_keys=True) + "\n")
        return record

    def revoke(self, identity_id: str, *, reason: str) -> IdentityRecord:
        if not reason.strip():
            raise ValueError("revocation reason is required")
        current = self.get(identity_id)
        if current.status == "revoked":
            return current
        event = {
            "kind": "revoke",
            "identity_id": identity_id,
            "reason": reason,
            "revoked_at": _now(),
        }
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, sort_keys=True) + "\n")
        return self.get(identity_id)

    def get_optional(self, identity_id: str) -> Optional[IdentityRecord]:
        state: Optional[IdentityRecord] = None
        for event in self._events():
            if event.get("identity_id") != identity_id:
                continue
            if event["kind"] == "register":
                state = IdentityRecord(
                    identity_id=event["identity_id"],
                    public_key_b64=event["public_key_b64"],
                    fingerprint=event["fingerprint"],
                    registered_at=event["registered_at"],
                    status="active",
                )
            elif event["kind"] == "revoke" and state is not None:
                state = IdentityRecord(
                    identity_id=state.identity_id,
                    public_key_b64=state.public_key_b64,
                    fingerprint=state.fingerprint,
                    registered_at=state.registered_at,
                    status="revoked",
                )
        return state

    def get(self, identity_id: str) -> IdentityRecord:
        record = self.get_optional(identity_id)
        if record is None:
            raise KeyError(f"unknown identity: {identity_id}")
        return record

    def public_key(self, identity_id: str) -> Ed25519PublicKey:
        record = self.get(identity_id)
        if record.status != "active":
            raise ValueError(f"identity is revoked: {identity_id}")
        return Ed25519PublicKey.from_public_bytes(_unb64(record.public_key_b64))


@dataclass(frozen=True)
class SignedEnvelope:
    actor_id: str
    issued_at: str
    nonce: str
    payload: Mapping[str, Any]
    key_fingerprint: str
    signature_b64: str


class IdentitySigner:
    """Caller-owned Ed25519 key pair for signed inter-agent envelopes/grants."""

    def __init__(self, identity_id: str, private_key: Optional[Ed25519PrivateKey] = None):
        if not identity_id.strip():
            raise ValueError("identity_id is required")
        self.identity_id = identity_id
        self._private_key = private_key or Ed25519PrivateKey.generate()

    @property
    def public_key(self) -> Ed25519PublicKey:
        return self._private_key.public_key()

    @property
    def fingerprint(self) -> str:
        raw = self.public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)
        return _fingerprint(raw)

    def sign_envelope(
        self,
        payload: Mapping[str, Any],
        *,
        nonce: str,
        issued_at: Optional[str] = None,
    ) -> SignedEnvelope:
        if not nonce.strip():
            raise ValueError("nonce is required")
        body = {
            "actor_id": self.identity_id,
            "issued_at": issued_at or _now(),
            "nonce": nonce,
            "payload": dict(payload),
            "key_fingerprint": self.fingerprint,
        }
        signature = self._private_key.sign(_canonical_bytes(body))
        return SignedEnvelope(**body, signature_b64=_b64(signature))


def verify_envelope(
    envelope: SignedEnvelope,
    registry: IdentityRegistry,
) -> Mapping[str, Any]:
    record = registry.get(envelope.actor_id)
    if record.status != "active":
        raise ValueError("signed envelope actor is revoked")
    if record.fingerprint != envelope.key_fingerprint:
        raise ValueError("signed envelope key fingerprint mismatch")
    body = {
        "actor_id": envelope.actor_id,
        "issued_at": envelope.issued_at,
        "nonce": envelope.nonce,
        "payload": dict(envelope.payload),
        "key_fingerprint": envelope.key_fingerprint,
    }
    try:
        registry.public_key(envelope.actor_id).verify(
            _unb64(envelope.signature_b64),
            _canonical_bytes(body),
        )
    except InvalidSignature as exc:
        raise ValueError("invalid signed envelope") from exc
    return dict(envelope.payload)


@dataclass(frozen=True)
class CapabilityGrant:
    grant_id: str
    issuer_id: str
    subject_id: str
    action_type: str
    resource_prefixes: Tuple[str, ...]
    issued_at: str
    expires_at: str
    delegable: bool
    parent_grant_id: Optional[str]
    issuer_fingerprint: str
    signature_b64: str


@dataclass(frozen=True)
class CapabilityRevocation:
    grant_id: str
    issuer_id: str
    reason: str
    revoked_at: str
    issuer_fingerprint: str
    signature_b64: str


def _grant_unsigned_payload(
    *,
    issuer_id: str,
    subject_id: str,
    action_type: str,
    resource_prefixes: Sequence[str],
    issued_at: str,
    expires_at: str,
    delegable: bool,
    parent_grant_id: Optional[str],
    issuer_fingerprint: str,
) -> dict[str, Any]:
    return {
        "issuer_id": issuer_id,
        "subject_id": subject_id,
        "action_type": action_type,
        "resource_prefixes": list(resource_prefixes),
        "issued_at": issued_at,
        "expires_at": expires_at,
        "delegable": bool(delegable),
        "parent_grant_id": parent_grant_id,
        "issuer_fingerprint": issuer_fingerprint,
    }


class CapabilityAuthority:
    def __init__(self, signer: IdentitySigner):
        self.signer = signer

    def issue(
        self,
        *,
        subject_id: str,
        action_type: str,
        resource_prefixes: Sequence[str],
        expires_at: str,
        delegable: bool = False,
        parent_grant_id: Optional[str] = None,
        issued_at: Optional[str] = None,
    ) -> CapabilityGrant:
        if not subject_id.strip() or not action_type.strip():
            raise ValueError("capability subject and action_type are required")
        prefixes = tuple(dict.fromkeys(str(x) for x in resource_prefixes))
        if not prefixes or any(not x.strip() for x in prefixes):
            raise ValueError("capability requires at least one resource prefix")
        issued = issued_at or _now()
        if _parse_time(expires_at) <= _parse_time(issued):
            raise ValueError("capability expiry must be after issuance")

        body = _grant_unsigned_payload(
            issuer_id=self.signer.identity_id,
            subject_id=subject_id,
            action_type=action_type,
            resource_prefixes=prefixes,
            issued_at=issued,
            expires_at=expires_at,
            delegable=delegable,
            parent_grant_id=parent_grant_id,
            issuer_fingerprint=self.signer.fingerprint,
        )
        grant_id = f"cap:{sha256(_canonical_bytes(body)).hexdigest()[:32]}"
        signed = {"grant_id": grant_id, **body}
        signature = self.signer._private_key.sign(_canonical_bytes(signed))
        return CapabilityGrant(
            grant_id=grant_id,
            issuer_id=self.signer.identity_id,
            subject_id=subject_id,
            action_type=action_type,
            resource_prefixes=prefixes,
            issued_at=issued,
            expires_at=expires_at,
            delegable=delegable,
            parent_grant_id=parent_grant_id,
            issuer_fingerprint=self.signer.fingerprint,
            signature_b64=_b64(signature),
        )

    def revoke(
        self,
        grant_id: str,
        *,
        reason: str,
        revoked_at: Optional[str] = None,
    ) -> CapabilityRevocation:
        if not reason.strip():
            raise ValueError("revocation reason is required")
        body = {
            "grant_id": grant_id,
            "issuer_id": self.signer.identity_id,
            "reason": reason,
            "revoked_at": revoked_at or _now(),
            "issuer_fingerprint": self.signer.fingerprint,
        }
        signature = self.signer._private_key.sign(_canonical_bytes(body))
        return CapabilityRevocation(**body, signature_b64=_b64(signature))


class CapabilityStore:
    """Persistent grant/revocation store. Signed objects remain self-verifying."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _append(self, kind: str, value: Any) -> None:
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(
                json.dumps(
                    {"kind": kind, "value": _canonical_native(value)},
                    sort_keys=True,
                ) + "\n"
            )

    def add_grant(self, grant: CapabilityGrant) -> CapabilityGrant:
        existing = self.get_optional(grant.grant_id)
        if existing is not None:
            if existing != grant:
                raise ValueError("grant id collision")
            return existing
        self._append("grant", grant)
        return grant

    def add_revocation(self, revocation: CapabilityRevocation) -> CapabilityRevocation:
        self._append("revocation", revocation)
        return revocation

    def _events(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [
            json.loads(line)
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def grants(self) -> Tuple[CapabilityGrant, ...]:
        return tuple(
            CapabilityGrant(
                **{
                    **event["value"],
                    "resource_prefixes": tuple(event["value"]["resource_prefixes"]),
                }
            )
            for event in self._events()
            if event["kind"] == "grant"
        )

    def revocations(self) -> Tuple[CapabilityRevocation, ...]:
        return tuple(
            CapabilityRevocation(**event["value"])
            for event in self._events()
            if event["kind"] == "revocation"
        )

    def get_optional(self, grant_id: str) -> Optional[CapabilityGrant]:
        for grant in self.grants():
            if grant.grant_id == grant_id:
                return grant
        return None

    def get(self, grant_id: str) -> CapabilityGrant:
        grant = self.get_optional(grant_id)
        if grant is None:
            raise KeyError(f"unknown capability grant: {grant_id}")
        return grant


def verify_grant_signature(
    grant: CapabilityGrant,
    registry: IdentityRegistry,
) -> None:
    issuer = registry.get(grant.issuer_id)
    if issuer.status != "active":
        raise ValueError("capability issuer is revoked")
    if issuer.fingerprint != grant.issuer_fingerprint:
        raise ValueError("capability issuer fingerprint mismatch")
    body = {
        "grant_id": grant.grant_id,
        **_grant_unsigned_payload(
            issuer_id=grant.issuer_id,
            subject_id=grant.subject_id,
            action_type=grant.action_type,
            resource_prefixes=grant.resource_prefixes,
            issued_at=grant.issued_at,
            expires_at=grant.expires_at,
            delegable=grant.delegable,
            parent_grant_id=grant.parent_grant_id,
            issuer_fingerprint=grant.issuer_fingerprint,
        ),
    }
    expected_id = f"cap:{sha256(_canonical_bytes({k: v for k, v in body.items() if k != 'grant_id'})).hexdigest()[:32]}"
    if expected_id != grant.grant_id:
        raise ValueError("capability grant id does not match payload")
    try:
        registry.public_key(grant.issuer_id).verify(
            _unb64(grant.signature_b64),
            _canonical_bytes(body),
        )
    except InvalidSignature as exc:
        raise ValueError("invalid capability signature") from exc


def verify_revocation_signature(
    revocation: CapabilityRevocation,
    registry: IdentityRegistry,
) -> None:
    issuer = registry.get(revocation.issuer_id)
    if issuer.status != "active":
        raise ValueError("revocation issuer identity is revoked")
    if issuer.fingerprint != revocation.issuer_fingerprint:
        raise ValueError("revocation issuer fingerprint mismatch")
    body = {
        "grant_id": revocation.grant_id,
        "issuer_id": revocation.issuer_id,
        "reason": revocation.reason,
        "revoked_at": revocation.revoked_at,
        "issuer_fingerprint": revocation.issuer_fingerprint,
    }
    try:
        registry.public_key(revocation.issuer_id).verify(
            _unb64(revocation.signature_b64),
            _canonical_bytes(body),
        )
    except InvalidSignature as exc:
        raise ValueError("invalid capability revocation signature") from exc


@dataclass(frozen=True)
class ActionSecurityProfile:
    action_type: str
    requires_capability: bool
    forbidden_taints: frozenset[str]
    require_clean_provenance: bool = True
    require_bound_origins: bool = False
    minimum_origin_rank: Optional[int] = None

    def __post_init__(self):
        if not self.action_type.strip():
            raise ValueError("action security profile requires action_type")
        if self.minimum_origin_rank is not None:
            if (
                isinstance(self.minimum_origin_rank, bool)
                or not isinstance(self.minimum_origin_rank, int)
                or self.minimum_origin_rank < 0
            ):
                raise ValueError("minimum_origin_rank must be an integer >= 0")


@dataclass(frozen=True)
class SecurityContext:
    actor_id: str
    provenance_glyph_ids: Tuple[str, ...] = ()
    capability_grant_ids: Tuple[str, ...] = ()
    resource: str = "*"

    def __post_init__(self):
        if not self.actor_id.strip():
            raise ValueError("security actor_id is required")
        if not self.resource.strip():
            raise ValueError("security resource is required")


@dataclass(frozen=True)
class ProvenanceAssessment:
    glyph_ids: Tuple[str, ...]
    taints: frozenset[str]
    quarantined_glyph_ids: Tuple[str, ...]
    root_glyph_ids: Tuple[str, ...] = ()
    unbound_root_glyph_ids: Tuple[str, ...] = ()
    origin_bindings: Tuple[Mapping[str, Any], ...] = ()
    minimum_origin_rank: Optional[int] = None


class AegisSecurityGraph:
    """Security labels/quarantine as immutable Glyph Protocol policy events."""

    def __init__(self, graph: GlyphAuditGraph, *, actor: str = "SYN-AEGIS"):
        self.graph = graph
        self.actor = actor

    ORIGIN_CLASSES = {
        "unknown": 0,
        "external_untrusted": 1,
        "external_authenticated": 2,
        "trusted_observation": 3,
        "user_intent": 4,
        "control_plane": 4,
        "runtime_attested": 5,
        "system": 6,
    }

    def bind_origin(
        self,
        glyph_id: str,
        *,
        authority_class: str,
        reason: str,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> Glyph:
        """Bind a provenance root to an immutable origin authority class.

        Rebinding may preserve or *lower* authority (for example after source
        compromise) but can never raise it. Explicit elevation must happen
        through a separate capability/review mechanism, not by relabelling the
        same origin.
        """
        self.graph.ledger.get(glyph_id)
        if authority_class not in self.ORIGIN_CLASSES:
            raise ValueError(f"unsupported origin authority class: {authority_class}")
        if not reason.strip():
            raise ValueError("origin binding reason is required")

        existing = self.origin_binding(glyph_id)
        rank = self.ORIGIN_CLASSES[authority_class]
        if existing is not None:
            old_rank = int(existing.content["rank"])
            if rank > old_rank:
                raise ValueError("origin authority cannot be elevated by rebinding")
            if (
                rank == old_rank
                and existing.content.get("authority_class") == authority_class
            ):
                return existing

        policy = self.graph.create(
            "policy",
            actor=self.actor,
            content={
                "kind": "origin_authority",
                "authority_class": authority_class,
                "rank": rank,
                "reason": reason,
                **dict(metadata or {}),
            },
            derived_from=(glyph_id,),
        )
        self.graph.relate(
            policy.glyph_id,
            glyph_id,
            "targets",
            actor=self.actor,
        )
        if existing is not None:
            self.graph.relate(
                policy.glyph_id,
                existing.glyph_id,
                "supersedes",
                actor=self.actor,
            )
        return policy

    def origin_binding(self, glyph_id: str) -> Optional[Glyph]:
        bindings = self._policy_targets("origin_authority", glyph_id)
        return bindings[-1] if bindings else None

    def _policy_targets(self, kind: str, target_glyph_id: str) -> list[Glyph]:
        out = []
        for edge in self.graph.ledger.edges_to(
            target_glyph_id,
            relation="targets",
        ):
            glyph = self.graph.ledger.get(edge.source)
            if (
                glyph.glyph_type == "policy"
                and glyph.content.get("kind") == kind
            ):
                out.append(glyph)
        return out

    def mark_taint(self, glyph_id: str, *, label: str, reason: str) -> Glyph:
        if not label.strip() or not reason.strip():
            raise ValueError("taint label and reason are required")
        self.graph.ledger.get(glyph_id)
        policy = self.graph.create(
            "policy",
            actor=self.actor,
            content={
                "kind": "taint",
                "label": label,
                "active": True,
                "reason": reason,
            },
            derived_from=(glyph_id,),
        )
        self.graph.relate(
            policy.glyph_id,
            glyph_id,
            "targets",
            actor=self.actor,
        )
        return policy

    def clear_taint(self, glyph_id: str, *, label: str, reason: str) -> Glyph:
        self.graph.ledger.get(glyph_id)
        if not reason.strip():
            raise ValueError("taint clear reason is required")
        policy = self.graph.create(
            "policy",
            actor=self.actor,
            content={
                "kind": "taint",
                "label": label,
                "active": False,
                "reason": reason,
            },
            derived_from=(glyph_id,),
        )
        self.graph.relate(policy.glyph_id, glyph_id, "targets", actor=self.actor)
        return policy

    def quarantine(self, glyph_id: str, *, reason: str) -> Glyph:
        self.graph.ledger.get(glyph_id)
        if not reason.strip():
            raise ValueError("quarantine reason is required")
        policy = self.graph.create(
            "policy",
            actor=self.actor,
            content={"kind": "quarantine", "active": True, "reason": reason},
            derived_from=(glyph_id,),
        )
        self.graph.relate(policy.glyph_id, glyph_id, "targets", actor=self.actor)
        return policy

    def release(self, glyph_id: str, *, reason: str) -> Glyph:
        self.graph.ledger.get(glyph_id)
        if not reason.strip():
            raise ValueError("release reason is required")
        policy = self.graph.create(
            "policy",
            actor=self.actor,
            content={"kind": "quarantine", "active": False, "reason": reason},
            derived_from=(glyph_id,),
        )
        self.graph.relate(policy.glyph_id, glyph_id, "targets", actor=self.actor)
        return policy

    def active_taints(self, glyph_id: str) -> frozenset[str]:
        states: dict[str, bool] = {}
        for policy in self._policy_targets("taint", glyph_id):
            label = str(policy.content["label"])
            states[label] = bool(policy.content["active"])
        return frozenset(label for label, active in states.items() if active)

    def is_quarantined(self, glyph_id: str) -> bool:
        policies = self._policy_targets("quarantine", glyph_id)
        if not policies:
            return False
        return bool(policies[-1].content["active"])

    def assess_provenance(
        self,
        glyph_ids: Sequence[str],
        *,
        max_depth: int = 32,
    ) -> ProvenanceAssessment:
        seen: set[str] = set()
        for glyph_id in glyph_ids:
            trace = self.graph.upstream(glyph_id, max_depth=max_depth)
            seen.update(g.glyph_id for g in trace.glyphs)

        taints: set[str] = set()
        quarantined = []
        for glyph_id in seen:
            taints.update(self.active_taints(glyph_id))
            if self.is_quarantined(glyph_id):
                quarantined.append(glyph_id)

        # A provenance root is a node in the influence trace that has no
        # outgoing derived_from edge to another node in that same trace.
        # If lineage is "laundered" by creating a new trusted-looking object
        # without preserving its parent edge, that object becomes a new root
        # and must carry an explicit origin binding or fail closed.
        has_parent = {
            glyph_id
            for glyph_id in seen
            if any(
                edge.target in seen
                for edge in self.graph.ledger.edges_from(
                    glyph_id,
                    relation="derived_from",
                )
            )
        }
        roots = tuple(sorted(seen - has_parent))
        unbound = []
        bindings = []
        ranks = []
        for root_id in roots:
            binding = self.origin_binding(root_id)
            if binding is None:
                unbound.append(root_id)
                continue
            rank = int(binding.content["rank"])
            ranks.append(rank)
            binding_info = {
                "root_glyph_id": root_id,
                "policy_glyph_id": binding.glyph_id,
                "authority_class": binding.content["authority_class"],
                "rank": rank,
            }
            for key in (
                "origin_receipt_id",
                "true_origin_glyph_id",
                "receipt_hops",
            ):
                if key in binding.content:
                    binding_info[key] = binding.content[key]
            bindings.append(binding_info)

        return ProvenanceAssessment(
            glyph_ids=tuple(sorted(seen)),
            taints=frozenset(taints),
            quarantined_glyph_ids=tuple(sorted(quarantined)),
            root_glyph_ids=roots,
            unbound_root_glyph_ids=tuple(sorted(unbound)),
            origin_bindings=tuple(bindings),
            minimum_origin_rank=min(ranks) if ranks else None,
        )

    def quarantine_descendants(
        self,
        glyph_id: str,
        *,
        reason: str,
        max_depth: int = 64,
    ) -> Tuple[str, ...]:
        trace = self.graph.impacted_by(glyph_id, max_depth=max_depth)
        affected = []
        for glyph in trace.glyphs:
            if not self.is_quarantined(glyph.glyph_id):
                self.quarantine(glyph.glyph_id, reason=reason)
            affected.append(glyph.glyph_id)
        return tuple(sorted(affected))


class AegisGuard:
    """Pre-action gate combining allowlist, provenance and signed capabilities."""

    def __init__(
        self,
        *,
        graph: GlyphAuditGraph,
        identity_registry: IdentityRegistry,
        capability_store: CapabilityStore,
        trusted_capability_issuers: frozenset[str],
        allowed_actions: frozenset[str],
        profiles: Sequence[ActionSecurityProfile],
        security_graph: Optional[AegisSecurityGraph] = None,
        actor: str = "SYN-AEGIS",
    ):
        if not allowed_actions:
            raise ValueError("AEGIS allowed_actions cannot be empty")
        self.graph = graph
        self.identity_registry = identity_registry
        self.capability_store = capability_store
        self.trusted_capability_issuers = trusted_capability_issuers
        self.allowed_actions = allowed_actions
        self.profiles = {p.action_type: p for p in profiles}
        self.security_graph = security_graph or AegisSecurityGraph(graph, actor=actor)
        self.actor = actor

    def _active_revocations(self) -> dict[str, CapabilityRevocation]:
        out = {}
        for revocation in self.capability_store.revocations():
            verify_revocation_signature(revocation, self.identity_registry)
            out[revocation.grant_id] = revocation
        return out

    def _grant_valid_for(
        self,
        grant: CapabilityGrant,
        *,
        actor_id: str,
        action_type: str,
        resource: str,
        now: datetime,
    ) -> bool:
        verify_grant_signature(grant, self.identity_registry)
        if grant.issuer_id not in self.trusted_capability_issuers:
            return False
        if grant.subject_id != actor_id or grant.action_type != action_type:
            return False
        if not (_parse_time(grant.issued_at) <= now < _parse_time(grant.expires_at)):
            return False
        if not any(
            prefix == "*" or resource.startswith(prefix)
            for prefix in grant.resource_prefixes
        ):
            return False
        if grant.grant_id in self._active_revocations():
            return False
        if grant.parent_grant_id is not None:
            # Delegated grants are denied until a strict delegation-chain verifier
            # is enabled. No silent partial delegation semantics.
            return False
        return True

    def _record_decision(
        self,
        proposal: ActionProposal,
        context: SecurityContext,
        *,
        allowed: bool,
        reason: str,
        provenance: ProvenanceAssessment,
        capability_grant_id: Optional[str],
    ) -> Glyph:
        parents = [
            glyph_id
            for glyph_id in context.provenance_glyph_ids
            if any(g.glyph_id == glyph_id for g in self.graph.ledger.glyphs())
        ]
        return self.graph.create(
            "policy",
            actor=self.actor,
            content={
                "kind": "aegis_action_decision",
                "allowed": allowed,
                "reason": reason,
                "proposal_id": proposal.proposal_id,
                "action_type": proposal.action_type,
                "actor_id": context.actor_id,
                "resource": context.resource,
                "taints": sorted(provenance.taints),
                "quarantined_glyph_ids": list(provenance.quarantined_glyph_ids),
                "root_glyph_ids": list(provenance.root_glyph_ids),
                "unbound_root_glyph_ids": list(provenance.unbound_root_glyph_ids),
                "origin_bindings": [dict(x) for x in provenance.origin_bindings],
                "minimum_origin_rank": provenance.minimum_origin_rank,
                "capability_grant_id": capability_grant_id,
            },
            # Keep a shared lookup ref but never deduplicate security checks:
            # time-dependent capability expiry/revocation can change the result.
            external_refs=(f"aegis:{proposal.proposal_id}",),
            derived_from=tuple(parents),
        )

    def check(
        self,
        proposal: ActionProposal,
        context: SecurityContext,
        *,
        now: Optional[datetime] = None,
    ) -> PolicyDecision:
        current_time = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)

        if proposal.action_type not in self.allowed_actions:
            provenance = self.security_graph.assess_provenance(
                context.provenance_glyph_ids
            )
            self._record_decision(
                proposal, context,
                allowed=False,
                reason="aegis:action_not_globally_allowlisted",
                provenance=provenance,
                capability_grant_id=None,
            )
            return PolicyDecision(False, "aegis:action_not_globally_allowlisted")

        profile = self.profiles.get(proposal.action_type)
        if profile is None:
            provenance = self.security_graph.assess_provenance(
                context.provenance_glyph_ids
            )
            self._record_decision(
                proposal, context,
                allowed=False,
                reason="aegis:unprofiled_action",
                provenance=provenance,
                capability_grant_id=None,
            )
            return PolicyDecision(False, "aegis:unprofiled_action")

        provenance = self.security_graph.assess_provenance(
            context.provenance_glyph_ids
        )
        if profile.require_clean_provenance and provenance.quarantined_glyph_ids:
            self._record_decision(
                proposal, context,
                allowed=False,
                reason="aegis:quarantined_provenance",
                provenance=provenance,
                capability_grant_id=None,
            )
            return PolicyDecision(False, "aegis:quarantined_provenance")

        if profile.require_bound_origins and provenance.unbound_root_glyph_ids:
            self._record_decision(
                proposal, context,
                allowed=False,
                reason="aegis:unbound_origin",
                provenance=provenance,
                capability_grant_id=None,
            )
            return PolicyDecision(False, "aegis:unbound_origin")

        if profile.minimum_origin_rank is not None:
            if (
                provenance.minimum_origin_rank is None
                or provenance.minimum_origin_rank < profile.minimum_origin_rank
            ):
                self._record_decision(
                    proposal, context,
                    allowed=False,
                    reason="aegis:origin_authority_below_threshold",
                    provenance=provenance,
                    capability_grant_id=None,
                )
                return PolicyDecision(
                    False,
                    "aegis:origin_authority_below_threshold",
                )

        forbidden = provenance.taints & profile.forbidden_taints
        if forbidden:
            self._record_decision(
                proposal, context,
                allowed=False,
                reason="aegis:forbidden_taint:" + ",".join(sorted(forbidden)),
                provenance=provenance,
                capability_grant_id=None,
            )
            return PolicyDecision(
                False,
                "aegis:forbidden_taint:" + ",".join(sorted(forbidden)),
            )

        capability_used = None
        if profile.requires_capability:
            for grant_id in context.capability_grant_ids:
                grant = self.capability_store.get_optional(grant_id)
                if grant is None:
                    continue
                if self._grant_valid_for(
                    grant,
                    actor_id=context.actor_id,
                    action_type=proposal.action_type,
                    resource=context.resource,
                    now=current_time,
                ):
                    capability_used = grant.grant_id
                    break
            if capability_used is None:
                self._record_decision(
                    proposal, context,
                    allowed=False,
                    reason="aegis:no_valid_capability",
                    provenance=provenance,
                    capability_grant_id=None,
                )
                return PolicyDecision(False, "aegis:no_valid_capability")

        self._record_decision(
            proposal, context,
            allowed=True,
            reason="aegis:authorized",
            provenance=provenance,
            capability_grant_id=capability_used,
        )
        return PolicyDecision(True, "aegis:authorized")
