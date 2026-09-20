"""Portable cryptographic provenance receipts for Synergesis.

Why this exists
---------------
A local Glyph Graph can detect that lineage was broken, but it cannot recover a
deleted edge by magic. Provenance receipts make origin authority portable across
process/agent boundaries.

Each receipt is a signed envelope:
- Origin receipt: binds a glyph to an origin authority class.
- Derivation receipt: binds a new glyph to a parent receipt.

A relay may omit the local ``derived_from`` edge, but if it preserves a valid
receipt chain, AEGIS can recover the true signed origin authority. A relay
cannot raise that authority without forging a trusted issuer signature.

This does not make compromised trusted signers harmless. It makes authority
propagation explicit, signed, bounded and auditable.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence, Tuple, Union

from synergesis_aegis import (
    AegisSecurityGraph,
    IdentityRegistry,
    IdentitySigner,
    SignedEnvelope,
    verify_envelope,
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


@dataclass(frozen=True)
class OriginReceipt:
    receipt_id: str
    glyph_id: str
    authority_class: str
    rank: int
    envelope: SignedEnvelope


@dataclass(frozen=True)
class DerivationReceipt:
    receipt_id: str
    glyph_id: str
    parent_receipt_id: str
    transform_kind: str
    envelope: SignedEnvelope


Receipt = Union[OriginReceipt, DerivationReceipt]


@dataclass(frozen=True)
class ReceiptTrace:
    leaf_receipt_id: str
    leaf_glyph_id: str
    true_origin_glyph_id: str
    origin_authority_class: str
    origin_rank: int
    receipt_ids: Tuple[str, ...]
    issuer_ids: Tuple[str, ...]
    hops: int


class ProvenanceReceiptStore:
    """Append-only hash-chained receipt store with verified incremental indexes."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._cache_signature: Optional[tuple[int, int]] = None
        self._events_cache: Tuple[Mapping[str, Any], ...] = ()
        self._receipts_cache: Tuple[Receipt, ...] = ()
        self._by_id: dict[str, Receipt] = {}

    def _file_signature(self) -> Optional[tuple[int, int]]:
        if not self.path.exists():
            return None
        stat = self.path.stat()
        return (int(stat.st_size), int(stat.st_mtime_ns))

    def _raw(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [
            json.loads(line)
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    @staticmethod
    def _decode_envelope(raw: Mapping[str, Any]) -> SignedEnvelope:
        return SignedEnvelope(
            actor_id=raw["actor_id"],
            issued_at=raw["issued_at"],
            nonce=raw["nonce"],
            payload=dict(raw["payload"]),
            key_fingerprint=raw["key_fingerprint"],
            signature_b64=raw["signature_b64"],
        )

    @classmethod
    def _decode_receipt(cls, kind: str, raw: Mapping[str, Any]) -> Receipt:
        envelope = cls._decode_envelope(raw["envelope"])
        if kind == "origin":
            return OriginReceipt(
                receipt_id=raw["receipt_id"],
                glyph_id=raw["glyph_id"],
                authority_class=raw["authority_class"],
                rank=int(raw["rank"]),
                envelope=envelope,
            )
        if kind == "derivation":
            return DerivationReceipt(
                receipt_id=raw["receipt_id"],
                glyph_id=raw["glyph_id"],
                parent_receipt_id=raw["parent_receipt_id"],
                transform_kind=raw["transform_kind"],
                envelope=envelope,
            )
        raise ValueError(f"unknown receipt kind: {kind}")

    def _load_verified(self, *, force: bool = False) -> None:
        signature = self._file_signature()
        if not force and signature == self._cache_signature:
            return

        previous = None
        events = []
        receipts = []
        by_id: dict[str, Receipt] = {}
        for index, event in enumerate(self._raw(), start=1):
            if int(event["sequence"]) != index:
                raise ValueError("receipt ledger sequence failure")
            if event["previous_digest"] != previous:
                raise ValueError("receipt ledger chain failure")
            body = {
                "sequence": event["sequence"],
                "previous_digest": event["previous_digest"],
                "kind": event["kind"],
                "receipt": event["receipt"],
            }
            expected = _digest(body)
            if expected != event["digest"]:
                raise ValueError("receipt ledger integrity failure")
            receipt = self._decode_receipt(event["kind"], event["receipt"])
            if receipt.receipt_id in by_id and by_id[receipt.receipt_id] != receipt:
                raise ValueError("receipt id collision in persisted ledger")
            events.append(event)
            receipts.append(receipt)
            by_id[receipt.receipt_id] = receipt
            previous = expected

        self._events_cache = tuple(events)
        self._receipts_cache = tuple(receipts)
        self._by_id = by_id
        self._cache_signature = signature

    def events(self) -> Tuple[Mapping[str, Any], ...]:
        self._load_verified()
        return self._events_cache

    def verify(self) -> Tuple[Mapping[str, Any], ...]:
        self._load_verified(force=True)
        return self._events_cache

    def append(self, receipt: Receipt) -> Receipt:
        self._load_verified()
        existing = self._by_id.get(receipt.receipt_id)
        if existing is not None:
            if existing != receipt:
                raise ValueError("receipt id collision")
            return existing

        kind = "origin" if isinstance(receipt, OriginReceipt) else "derivation"
        body = {
            "sequence": len(self._events_cache) + 1,
            "previous_digest": (
                self._events_cache[-1]["digest"] if self._events_cache else None
            ),
            "kind": kind,
            "receipt": asdict(receipt),
        }
        event = {**body, "digest": _digest(body)}
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(_canonical(event) + "\n")

        self._events_cache = (*self._events_cache, event)
        self._receipts_cache = (*self._receipts_cache, receipt)
        self._by_id[receipt.receipt_id] = receipt
        self._cache_signature = self._file_signature()
        return receipt

    def receipts(self) -> Tuple[Receipt, ...]:
        self._load_verified()
        return self._receipts_cache

    def get_optional(self, receipt_id: str) -> Optional[Receipt]:
        self._load_verified()
        return self._by_id.get(receipt_id)

    def get(self, receipt_id: str) -> Receipt:
        self._load_verified()
        receipt = self._by_id.get(receipt_id)
        if receipt is None:
            raise KeyError(f"unknown provenance receipt: {receipt_id}")
        return receipt


class ProvenanceReceiptAuthority:
    def __init__(self, signer: IdentitySigner):
        self.signer = signer

    def issue_origin(
        self,
        *,
        glyph_id: str,
        authority_class: str,
        rank: int,
    ) -> OriginReceipt:
        if not glyph_id.strip() or not authority_class.strip():
            raise ValueError("glyph_id and authority_class are required")
        if isinstance(rank, bool) or not isinstance(rank, int) or rank < 0:
            raise ValueError("rank must be an integer >= 0")
        unsigned = {
            "kind": "origin",
            "issuer_id": self.signer.identity_id,
            "glyph_id": glyph_id,
            "authority_class": authority_class,
            "rank": rank,
        }
        receipt_id = f"or:{_digest(unsigned)[:32]}"
        payload = {**unsigned, "receipt_id": receipt_id}
        envelope = self.signer.sign_envelope(
            payload,
            nonce=receipt_id,
        )
        return OriginReceipt(
            receipt_id=receipt_id,
            glyph_id=glyph_id,
            authority_class=authority_class,
            rank=rank,
            envelope=envelope,
        )

    def issue_derivation(
        self,
        *,
        glyph_id: str,
        parent_receipt_id: str,
        transform_kind: str,
    ) -> DerivationReceipt:
        if not glyph_id.strip() or not parent_receipt_id.strip():
            raise ValueError("glyph_id and parent_receipt_id are required")
        if not transform_kind.strip():
            raise ValueError("transform_kind is required")
        unsigned = {
            "kind": "derivation",
            "issuer_id": self.signer.identity_id,
            "glyph_id": glyph_id,
            "parent_receipt_id": parent_receipt_id,
            "transform_kind": transform_kind,
        }
        receipt_id = f"dr:{_digest(unsigned)[:32]}"
        payload = {**unsigned, "receipt_id": receipt_id}
        envelope = self.signer.sign_envelope(
            payload,
            nonce=receipt_id,
        )
        return DerivationReceipt(
            receipt_id=receipt_id,
            glyph_id=glyph_id,
            parent_receipt_id=parent_receipt_id,
            transform_kind=transform_kind,
            envelope=envelope,
        )


class ProvenanceReceiptVerifier:
    def __init__(
        self,
        *,
        store: ProvenanceReceiptStore,
        identity_registry: IdentityRegistry,
        trusted_origin_issuers: frozenset[str],
        trusted_derivation_issuers: frozenset[str],
        origin_ranks: Mapping[str, int],
    ):
        self.store = store
        self.identity_registry = identity_registry
        self.trusted_origin_issuers = trusted_origin_issuers
        self.trusted_derivation_issuers = trusted_derivation_issuers
        self.origin_ranks = dict(origin_ranks)

    def _verify_payload(self, receipt: Receipt) -> Mapping[str, Any]:
        payload = verify_envelope(receipt.envelope, self.identity_registry)
        if payload.get("receipt_id") != receipt.receipt_id:
            raise ValueError("receipt payload id mismatch")
        if payload.get("glyph_id") != receipt.glyph_id:
            raise ValueError("receipt glyph binding mismatch")
        if receipt.envelope.nonce != receipt.receipt_id:
            raise ValueError("receipt nonce mismatch")

        if isinstance(receipt, OriginReceipt):
            if payload.get("kind") != "origin":
                raise ValueError("origin receipt kind mismatch")
            if payload.get("authority_class") != receipt.authority_class:
                raise ValueError("origin authority class mismatch")
            if int(payload.get("rank")) != receipt.rank:
                raise ValueError("origin rank mismatch")
        else:
            if payload.get("kind") != "derivation":
                raise ValueError("derivation receipt kind mismatch")
            if payload.get("parent_receipt_id") != receipt.parent_receipt_id:
                raise ValueError("derivation parent mismatch")
            if payload.get("transform_kind") != receipt.transform_kind:
                raise ValueError("derivation transform mismatch")
        return payload

    def verify_for_glyph(
        self,
        receipt_id: str,
        glyph_id: str,
        *,
        max_hops: int = 64,
    ) -> ReceiptTrace:
        if max_hops < 0:
            raise ValueError("max_hops must be >= 0")

        current = self.store.get(receipt_id)
        if current.glyph_id != glyph_id:
            raise ValueError("leaf receipt does not bind requested glyph")

        seen = set()
        receipt_ids = []
        issuer_ids = []
        hops = 0

        while True:
            if current.receipt_id in seen:
                raise ValueError("provenance receipt cycle detected")
            seen.add(current.receipt_id)
            receipt_ids.append(current.receipt_id)
            payload = self._verify_payload(current)
            issuer_ids.append(current.envelope.actor_id)

            if isinstance(current, OriginReceipt):
                if current.envelope.actor_id not in self.trusted_origin_issuers:
                    raise ValueError("untrusted origin receipt issuer")
                expected_rank = self.origin_ranks.get(current.authority_class)
                if expected_rank is None:
                    raise ValueError("unknown origin authority class")
                if current.rank != expected_rank:
                    raise ValueError("origin receipt rank does not match policy")
                return ReceiptTrace(
                    leaf_receipt_id=receipt_id,
                    leaf_glyph_id=glyph_id,
                    true_origin_glyph_id=current.glyph_id,
                    origin_authority_class=current.authority_class,
                    origin_rank=current.rank,
                    receipt_ids=tuple(receipt_ids),
                    issuer_ids=tuple(issuer_ids),
                    hops=hops,
                )

            if current.envelope.actor_id not in self.trusted_derivation_issuers:
                raise ValueError("untrusted derivation receipt issuer")
            if hops >= max_hops:
                raise ValueError("provenance receipt hop limit exceeded")
            hops += 1
            current = self.store.get(current.parent_receipt_id)


def bind_verified_origin_receipt(
    *,
    security_graph: AegisSecurityGraph,
    glyph_id: str,
    receipt_id: str,
    verifier: ProvenanceReceiptVerifier,
) -> ReceiptTrace:
    """Bind a local provenance root from a verified portable receipt chain."""
    trace = verifier.verify_for_glyph(receipt_id, glyph_id)
    security_graph.bind_origin(
        glyph_id,
        authority_class=trace.origin_authority_class,
        reason="verified portable provenance receipt chain",
        metadata={
            "origin_receipt_id": receipt_id,
            "true_origin_glyph_id": trace.true_origin_glyph_id,
            "receipt_hops": trace.hops,
        },
    )
    return trace
