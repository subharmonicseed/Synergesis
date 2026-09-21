"""Fresh, replay-safe transport for signed Synergesis provenance bundles.

This layer transports *remote claims* plus portable provenance receipts. It does
not turn remote claims into local runtime observations.

Security properties
-------------------
- Bundle sender signature must verify and sender must be explicitly trusted.
- Bundle lifetime and clock skew are bounded.
- Bundle replay is rejected by an append-only hash-chained replay ledger.
- Receipt chains are verified in a temporary staging store before import.
- Imported authority is exactly the signed origin authority and must also be in
  an explicit allowlist; no remapping/elevation occurs.
- Imported Glyphs are always local `observation` Glyphs with
  `kind = remote_signed_claim` and `channel = remote_transport`.
- A remote `runtime_attested` claim, even if explicitly allowed, is still not a
  local `runtime_reality_observation`.

This module never creates capabilities, permissions, executors, or local
runtime facts.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import tempfile
from typing import Any, Mapping, Optional, Sequence, Tuple

from synergesis_aegis import (
    AegisSecurityGraph,
    IdentityRegistry,
    IdentitySigner,
    SignedEnvelope,
    verify_envelope,
)
from synergesis_glyph_protocol import Glyph, GlyphAuditGraph
from synergesis_provenance_receipts import (
    DerivationReceipt,
    OriginReceipt,
    ProvenanceReceiptStore,
    ProvenanceReceiptVerifier,
    Receipt,
    ReceiptTrace,
)


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _digest(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return dt.astimezone(timezone.utc).isoformat()


def _parse_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except Exception as exc:
        raise ValueError("invalid ISO timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class ProvenanceTransportPolicy:
    trusted_senders: frozenset[str]
    allowed_origin_classes: frozenset[str]
    max_lifetime_seconds: float = 3600.0
    max_future_skew_seconds: float = 60.0
    max_receipts: int = 64

    def __post_init__(self):
        if not self.trusted_senders:
            raise ValueError("at least one trusted sender is required")
        if not self.allowed_origin_classes:
            raise ValueError("at least one allowed origin class is required")
        if self.max_lifetime_seconds <= 0:
            raise ValueError("max_lifetime_seconds must be > 0")
        if self.max_future_skew_seconds < 0:
            raise ValueError("max_future_skew_seconds must be >= 0")
        if self.max_receipts < 1:
            raise ValueError("max_receipts must be >= 1")


@dataclass(frozen=True)
class PortableProvenanceBundle:
    bundle_id: str
    sender_id: str
    issued_at: str
    expires_at: str
    leaf_glyph: Mapping[str, Any]
    leaf_receipt_id: str
    receipts: Tuple[Mapping[str, Any], ...]
    envelope: SignedEnvelope


@dataclass(frozen=True)
class ImportedRemoteClaim:
    bundle_id: str
    sender_id: str
    local_glyph_id: str
    remote_glyph_id: str
    origin_authority_class: str
    origin_rank: int
    receipt_ids: Tuple[str, ...]
    replay_event_id: str


@dataclass(frozen=True)
class ReplayEvent:
    sequence: int
    event_id: str
    sender_id: str
    bundle_id: str
    envelope_nonce: str
    remote_glyph_id: str
    local_glyph_id: str
    received_at: str
    previous_digest: Optional[str]
    digest: str


class ProvenanceReplayLedger:
    """Append-only hash chain of accepted transport bundles."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._events: list[ReplayEvent] = []
        self._loaded_size: Optional[int] = None

    def _size(self) -> Optional[int]:
        return self.path.stat().st_size if self.path.exists() else None

    def _load(self, *, force: bool = False) -> None:
        size = self._size()
        if not force and size == self._loaded_size:
            return
        events: list[ReplayEvent] = []
        previous = None
        if self.path.exists():
            for index, line in enumerate(
                self.path.read_text(encoding="utf-8").splitlines(),
                start=1,
            ):
                if not line.strip():
                    continue
                event = ReplayEvent(**json.loads(line))
                if event.sequence != index:
                    raise ValueError("transport replay ledger sequence failure")
                if event.previous_digest != previous:
                    raise ValueError("transport replay ledger chain failure")
                body = {
                    "sequence": event.sequence,
                    "event_id": event.event_id,
                    "sender_id": event.sender_id,
                    "bundle_id": event.bundle_id,
                    "envelope_nonce": event.envelope_nonce,
                    "remote_glyph_id": event.remote_glyph_id,
                    "local_glyph_id": event.local_glyph_id,
                    "received_at": event.received_at,
                    "previous_digest": event.previous_digest,
                }
                if event.digest != _digest(body):
                    raise ValueError("transport replay ledger integrity failure")
                events.append(event)
                previous = event.digest
        self._events = events
        self._loaded_size = self._size()

    def events(self) -> Tuple[ReplayEvent, ...]:
        self._load()
        return tuple(self._events)

    def seen(self, *, sender_id: str, bundle_id: str, nonce: str) -> bool:
        self._load()
        return any(
            event.sender_id == sender_id
            and (event.bundle_id == bundle_id or event.envelope_nonce == nonce)
            for event in self._events
        )

    def append(
        self,
        *,
        sender_id: str,
        bundle_id: str,
        envelope_nonce: str,
        remote_glyph_id: str,
        local_glyph_id: str,
    ) -> ReplayEvent:
        self._load()
        if self.seen(
            sender_id=sender_id,
            bundle_id=bundle_id,
            nonce=envelope_nonce,
        ):
            raise ValueError("transport bundle replay detected")
        previous = self._events[-1].digest if self._events else None
        body = {
            "sequence": len(self._events) + 1,
            "event_id": "transport-replay:" + _digest({
                'sender_id': sender_id,
                'bundle_id': bundle_id,
                'nonce': envelope_nonce,
                'sequence': len(self._events) + 1,
            })[:32],
            "sender_id": sender_id,
            "bundle_id": bundle_id,
            "envelope_nonce": envelope_nonce,
            "remote_glyph_id": remote_glyph_id,
            "local_glyph_id": local_glyph_id,
            "received_at": _iso(_now()),
            "previous_digest": previous,
        }
        event = ReplayEvent(**body, digest=_digest(body))
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(_canonical(asdict(event)) + "\n")
        self._events.append(event)
        self._loaded_size = self._size()
        return event

    def verify(self) -> tuple[int, Optional[str]]:
        self._load(force=True)
        return (
            len(self._events),
            self._events[-1].digest if self._events else None,
        )


def _serialize_receipt(receipt: Receipt) -> Mapping[str, Any]:
    return {
        "kind": "origin" if isinstance(receipt, OriginReceipt) else "derivation",
        "receipt": asdict(receipt),
    }


def _decode_envelope(raw: Mapping[str, Any]) -> SignedEnvelope:
    return SignedEnvelope(
        actor_id=str(raw["actor_id"]),
        issued_at=str(raw["issued_at"]),
        nonce=str(raw["nonce"]),
        payload=dict(raw["payload"]),
        key_fingerprint=str(raw["key_fingerprint"]),
        signature_b64=str(raw["signature_b64"]),
    )


def _decode_receipt(raw: Mapping[str, Any]) -> Receipt:
    kind = raw["kind"]
    receipt = raw["receipt"]
    envelope = _decode_envelope(receipt["envelope"])
    if kind == "origin":
        return OriginReceipt(
            receipt_id=str(receipt["receipt_id"]),
            glyph_id=str(receipt["glyph_id"]),
            authority_class=str(receipt["authority_class"]),
            rank=int(receipt["rank"]),
            envelope=envelope,
        )
    if kind == "derivation":
        return DerivationReceipt(
            receipt_id=str(receipt["receipt_id"]),
            glyph_id=str(receipt["glyph_id"]),
            parent_receipt_id=str(receipt["parent_receipt_id"]),
            transform_kind=str(receipt["transform_kind"]),
            envelope=envelope,
        )
    raise ValueError("unknown transported receipt kind")


class ProvenanceTransportExporter:
    def __init__(
        self,
        *,
        graph: GlyphAuditGraph,
        receipt_store: ProvenanceReceiptStore,
        signer: IdentitySigner,
    ):
        self.graph = graph
        self.receipt_store = receipt_store
        self.signer = signer

    def _chain(self, leaf_receipt_id: str, *, max_hops: int = 64) -> tuple[Receipt, ...]:
        current = self.receipt_store.get(leaf_receipt_id)
        out = []
        seen = set()
        for _ in range(max_hops + 1):
            if current.receipt_id in seen:
                raise ValueError("provenance receipt cycle detected during export")
            seen.add(current.receipt_id)
            out.append(current)
            if isinstance(current, OriginReceipt):
                return tuple(out)
            current = self.receipt_store.get(current.parent_receipt_id)
        raise ValueError("provenance receipt hop limit exceeded during export")

    def export(
        self,
        *,
        glyph_id: str,
        leaf_receipt_id: str,
        ttl_seconds: float,
        issued_at: Optional[datetime] = None,
    ) -> PortableProvenanceBundle:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be > 0")
        glyph = self.graph.ledger.get(glyph_id)
        chain = self._chain(leaf_receipt_id)
        if chain[0].glyph_id != glyph_id:
            raise ValueError("leaf receipt does not bind exported glyph")

        issued = (issued_at or _now()).astimezone(timezone.utc)
        expires = issued + timedelta(seconds=float(ttl_seconds))
        leaf_glyph = asdict(glyph)
        receipts = tuple(_serialize_receipt(receipt) for receipt in chain)
        unsigned = {
            "sender_id": self.signer.identity_id,
            "issued_at": _iso(issued),
            "expires_at": _iso(expires),
            "leaf_glyph": leaf_glyph,
            "leaf_receipt_id": leaf_receipt_id,
            "receipts": list(receipts),
        }
        bundle_id = f"ppb:{_digest(unsigned)[:32]}"
        payload = {**unsigned, "bundle_id": bundle_id}
        envelope = self.signer.sign_envelope(
            payload,
            nonce=bundle_id,
            issued_at=_iso(issued),
        )
        return PortableProvenanceBundle(
            bundle_id=bundle_id,
            sender_id=self.signer.identity_id,
            issued_at=_iso(issued),
            expires_at=_iso(expires),
            leaf_glyph=leaf_glyph,
            leaf_receipt_id=leaf_receipt_id,
            receipts=receipts,
            envelope=envelope,
        )


class ProvenanceTransportImporter:
    actor = "SYN-PROVENANCE-TRANSPORT"

    def __init__(
        self,
        *,
        graph: GlyphAuditGraph,
        security_graph: AegisSecurityGraph,
        receipt_store: ProvenanceReceiptStore,
        receipt_verifier: ProvenanceReceiptVerifier,
        replay_ledger: ProvenanceReplayLedger,
        policy: ProvenanceTransportPolicy,
        now_fn=_now,
    ):
        if security_graph.graph is not graph:
            raise ValueError("security graph must wrap transport glyph graph")
        if receipt_verifier.store is not receipt_store:
            raise ValueError("receipt verifier must use destination receipt store")
        self.graph = graph
        self.security_graph = security_graph
        self.receipt_store = receipt_store
        self.receipt_verifier = receipt_verifier
        self.replay_ledger = replay_ledger
        self.policy = policy
        self.now_fn = now_fn

    def _expected_payload(self, bundle: PortableProvenanceBundle) -> Mapping[str, Any]:
        return {
            "sender_id": bundle.sender_id,
            "issued_at": bundle.issued_at,
            "expires_at": bundle.expires_at,
            "leaf_glyph": dict(bundle.leaf_glyph),
            "leaf_receipt_id": bundle.leaf_receipt_id,
            "receipts": list(bundle.receipts),
            "bundle_id": bundle.bundle_id,
        }

    def _verify_bundle_signature(self, bundle: PortableProvenanceBundle) -> None:
        if bundle.sender_id not in self.policy.trusted_senders:
            raise ValueError("untrusted provenance transport sender")
        if bundle.envelope.actor_id != bundle.sender_id:
            raise ValueError("transport sender/envelope actor mismatch")
        if bundle.envelope.nonce != bundle.bundle_id:
            raise ValueError("transport envelope nonce mismatch")
        payload = verify_envelope(
            bundle.envelope,
            self.receipt_verifier.identity_registry,
        )
        if _canonical(payload) != _canonical(self._expected_payload(bundle)):
            raise ValueError("transport bundle payload mismatch")

    def _verify_freshness(self, bundle: PortableProvenanceBundle) -> None:
        now = self.now_fn().astimezone(timezone.utc)
        issued = _parse_time(bundle.issued_at)
        expires = _parse_time(bundle.expires_at)
        envelope_issued = _parse_time(bundle.envelope.issued_at)
        if envelope_issued != issued:
            raise ValueError("transport envelope issued_at mismatch")
        if expires <= issued:
            raise ValueError("transport bundle expiry must be after issue time")
        lifetime = (expires - issued).total_seconds()
        if lifetime > self.policy.max_lifetime_seconds:
            raise ValueError("transport bundle lifetime exceeds policy")
        if issued > now + timedelta(seconds=self.policy.max_future_skew_seconds):
            raise ValueError("transport bundle issued too far in the future")
        if now > expires:
            raise ValueError("transport bundle expired")

    def _verify_receipts_staged(
        self,
        bundle: PortableProvenanceBundle,
    ) -> tuple[ReceiptTrace, tuple[Receipt, ...]]:
        if not bundle.receipts:
            raise ValueError("transport bundle has no provenance receipts")
        if len(bundle.receipts) > self.policy.max_receipts:
            raise ValueError("transport bundle receipt count exceeds policy")
        decoded = tuple(_decode_receipt(item) for item in bundle.receipts)
        if decoded[0].receipt_id != bundle.leaf_receipt_id:
            raise ValueError("transport receipt list does not begin with leaf receipt")

        with tempfile.TemporaryDirectory(prefix="syn-prov-stage-") as temp:
            staging_store = ProvenanceReceiptStore(Path(temp) / "receipts.jsonl")
            for receipt in decoded:
                staging_store.append(receipt)
            staging_verifier = ProvenanceReceiptVerifier(
                store=staging_store,
                identity_registry=self.receipt_verifier.identity_registry,
                trusted_origin_issuers=self.receipt_verifier.trusted_origin_issuers,
                trusted_derivation_issuers=self.receipt_verifier.trusted_derivation_issuers,
                origin_ranks=self.receipt_verifier.origin_ranks,
            )
            trace = staging_verifier.verify_for_glyph(
                bundle.leaf_receipt_id,
                str(bundle.leaf_glyph["glyph_id"]),
                max_hops=self.policy.max_receipts - 1,
            )
        if trace.origin_authority_class not in self.policy.allowed_origin_classes:
            raise ValueError("signed origin authority is not allowed for transport import")
        return trace, decoded

    def import_bundle(
        self,
        bundle: PortableProvenanceBundle,
    ) -> ImportedRemoteClaim:
        self._verify_bundle_signature(bundle)
        self._verify_freshness(bundle)

        if self.replay_ledger.seen(
            sender_id=bundle.sender_id,
            bundle_id=bundle.bundle_id,
            nonce=bundle.envelope.nonce,
        ):
            raise ValueError("transport bundle replay detected")

        leaf = bundle.leaf_glyph
        if leaf.get("glyph_id") is None or leaf.get("glyph_type") is None:
            raise ValueError("transport bundle leaf glyph is incomplete")
        trace, decoded = self._verify_receipts_staged(bundle)

        # Only verified staged receipts are allowed into the persistent store.
        for receipt in decoded:
            self.receipt_store.append(receipt)
        # Re-run using the destination store to ensure the same chain is valid
        # in the actual persistent environment.
        persisted_trace = self.receipt_verifier.verify_for_glyph(
            bundle.leaf_receipt_id,
            str(leaf["glyph_id"]),
            max_hops=self.policy.max_receipts - 1,
        )
        if persisted_trace != trace:
            raise ValueError("staged/persisted provenance trace mismatch")

        local_ref = f"remote-bundle:{bundle.bundle_id}"
        imported = self.graph.create(
            "observation",
            actor=self.actor,
            content={
                "kind": "remote_signed_claim",
                "channel": "remote_transport",
                "runtime_local": False,
                "bundle_id": bundle.bundle_id,
                "sender_id": bundle.sender_id,
                "remote_glyph_id": leaf["glyph_id"],
                "remote_glyph_type": leaf["glyph_type"],
                "remote_actor": leaf.get("actor"),
                "remote_content": dict(leaf.get("content") or {}),
                "remote_created_at": leaf.get("created_at"),
                "leaf_receipt_id": bundle.leaf_receipt_id,
                "origin_authority_class": trace.origin_authority_class,
                "origin_rank": trace.origin_rank,
                "receipt_hops": trace.hops,
                "freshness": "verified",
                "authorization_effect": "none",
            },
            external_refs=(
                local_ref,
                f"remote-glyph:{leaf['glyph_id']}",
            ),
            metadata={
                "transport": "portable_provenance_bundle",
            },
            dedupe_external_ref=local_ref,
        )

        self.security_graph.bind_origin(
            imported.glyph_id,
            authority_class=trace.origin_authority_class,
            reason="verified fresh remote provenance bundle",
            metadata={
                "bundle_id": bundle.bundle_id,
                "sender_id": bundle.sender_id,
                "remote_glyph_id": leaf["glyph_id"],
                "remote_runtime_local": False,
                "leaf_receipt_id": bundle.leaf_receipt_id,
            },
        )

        replay = self.replay_ledger.append(
            sender_id=bundle.sender_id,
            bundle_id=bundle.bundle_id,
            envelope_nonce=bundle.envelope.nonce,
            remote_glyph_id=str(leaf["glyph_id"]),
            local_glyph_id=imported.glyph_id,
        )
        return ImportedRemoteClaim(
            bundle_id=bundle.bundle_id,
            sender_id=bundle.sender_id,
            local_glyph_id=imported.glyph_id,
            remote_glyph_id=str(leaf["glyph_id"]),
            origin_authority_class=trace.origin_authority_class,
            origin_rank=trace.origin_rank,
            receipt_ids=trace.receipt_ids,
            replay_event_id=replay.event_id,
        )
