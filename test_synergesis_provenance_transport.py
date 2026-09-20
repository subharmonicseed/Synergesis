from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from synergesis_aegis import (
    AegisSecurityGraph,
    IdentityRegistry,
    IdentitySigner,
)
from synergesis_glyph_protocol import GlyphAuditGraph, GlyphLedger
from synergesis_provenance_receipts import (
    ProvenanceReceiptAuthority,
    ProvenanceReceiptStore,
    ProvenanceReceiptVerifier,
)
from synergesis_provenance_transport import (
    PortableProvenanceBundle,
    ProvenanceReplayLedger,
    ProvenanceTransportExporter,
    ProvenanceTransportImporter,
    ProvenanceTransportPolicy,
)


BASE = datetime(2026, 9, 12, 12, 0, tzinfo=timezone.utc)


def setup(tmp_path, *, origin_class="trusted_observation", allowed=None):
    registry = IdentityRegistry(tmp_path / "identities.jsonl")
    ingress_signer = IdentitySigner("ingress")
    relay_signer = IdentitySigner("relay")
    sender_signer = IdentitySigner("agent-A")
    for signer in (ingress_signer, relay_signer, sender_signer):
        registry.register(signer.identity_id, signer.public_key)

    remote_graph = GlyphAuditGraph(GlyphLedger(tmp_path / "remote_glyphs.jsonl"))
    remote_security = AegisSecurityGraph(remote_graph)
    remote_store = ProvenanceReceiptStore(tmp_path / "remote_receipts.jsonl")

    origin = remote_graph.create(
        "observation",
        actor="sensor",
        content={"kind": "sensor_claim", "value": 42},
    )
    origin_receipt = ProvenanceReceiptAuthority(ingress_signer).issue_origin(
        glyph_id=origin.glyph_id,
        authority_class=origin_class,
        rank=remote_security.ORIGIN_CLASSES[origin_class],
    )
    remote_store.append(origin_receipt)

    leaf = remote_graph.create(
        "fact",
        actor="relay",
        content={"kind": "derived_claim", "value": 42},
        derived_from=(origin.glyph_id,),
    )
    leaf_receipt = ProvenanceReceiptAuthority(relay_signer).issue_derivation(
        glyph_id=leaf.glyph_id,
        parent_receipt_id=origin_receipt.receipt_id,
        transform_kind="cross_agent_relay",
    )
    remote_store.append(leaf_receipt)

    exporter = ProvenanceTransportExporter(
        graph=remote_graph,
        receipt_store=remote_store,
        signer=sender_signer,
    )
    bundle = exporter.export(
        glyph_id=leaf.glyph_id,
        leaf_receipt_id=leaf_receipt.receipt_id,
        ttl_seconds=300,
        issued_at=BASE,
    )

    local_graph = GlyphAuditGraph(GlyphLedger(tmp_path / "local_glyphs.jsonl"))
    local_security = AegisSecurityGraph(local_graph)
    local_store = ProvenanceReceiptStore(tmp_path / "local_receipts.jsonl")
    verifier = ProvenanceReceiptVerifier(
        store=local_store,
        identity_registry=registry,
        trusted_origin_issuers=frozenset({"ingress"}),
        trusted_derivation_issuers=frozenset({"relay"}),
        origin_ranks=local_security.ORIGIN_CLASSES,
    )
    replay = ProvenanceReplayLedger(tmp_path / "replay.jsonl")
    importer = ProvenanceTransportImporter(
        graph=local_graph,
        security_graph=local_security,
        receipt_store=local_store,
        receipt_verifier=verifier,
        replay_ledger=replay,
        policy=ProvenanceTransportPolicy(
            trusted_senders=frozenset({"agent-A"}),
            allowed_origin_classes=frozenset(
                allowed if allowed is not None else {origin_class}
            ),
            max_lifetime_seconds=600,
            max_future_skew_seconds=30,
            max_receipts=8,
        ),
        now_fn=lambda: BASE + timedelta(seconds=10),
    )
    return {
        "registry": registry,
        "sender": sender_signer,
        "remote_graph": remote_graph,
        "remote_store": remote_store,
        "leaf": leaf,
        "bundle": bundle,
        "local_graph": local_graph,
        "local_security": local_security,
        "local_store": local_store,
        "verifier": verifier,
        "replay": replay,
        "importer": importer,
    }


def resign(bundle, signer, **changes):
    values = {
        "bundle_id": bundle.bundle_id,
        "sender_id": bundle.sender_id,
        "issued_at": bundle.issued_at,
        "expires_at": bundle.expires_at,
        "leaf_glyph": bundle.leaf_glyph,
        "leaf_receipt_id": bundle.leaf_receipt_id,
        "receipts": bundle.receipts,
    }
    values.update(changes)
    unsigned = {
        "sender_id": values["sender_id"],
        "issued_at": values["issued_at"],
        "expires_at": values["expires_at"],
        "leaf_glyph": dict(values["leaf_glyph"]),
        "leaf_receipt_id": values["leaf_receipt_id"],
        "receipts": list(values["receipts"]),
    }
    # Keep the original bundle id if explicitly requested by the test; otherwise
    # recompute would hide payload mismatch/replay scenarios.
    payload = {**unsigned, "bundle_id": values["bundle_id"]}
    envelope = signer.sign_envelope(
        payload,
        nonce=values["bundle_id"],
        issued_at=values["issued_at"],
    )
    return PortableProvenanceBundle(
        bundle_id=values["bundle_id"],
        sender_id=values["sender_id"],
        issued_at=values["issued_at"],
        expires_at=values["expires_at"],
        leaf_glyph=values["leaf_glyph"],
        leaf_receipt_id=values["leaf_receipt_id"],
        receipts=values["receipts"],
        envelope=envelope,
    )


def test_fresh_signed_bundle_imports_as_remote_claim_not_runtime_fact(tmp_path):
    s = setup(tmp_path)
    result = s["importer"].import_bundle(s["bundle"])

    local = s["local_graph"].ledger.get(result.local_glyph_id)
    assert local.glyph_type == "observation"
    assert local.content["kind"] == "remote_signed_claim"
    assert local.content["channel"] == "remote_transport"
    assert local.content["runtime_local"] is False
    assert local.content["remote_glyph_id"] == s["leaf"].glyph_id
    assert local.content["remote_content"]["value"] == 42

    binding = s["local_security"].origin_binding(local.glyph_id)
    assert binding.content["authority_class"] == "trusted_observation"
    assert result.origin_authority_class == "trusted_observation"
    assert s["replay"].verify()[0] == 1


def test_bundle_replay_is_rejected(tmp_path):
    s = setup(tmp_path)
    s["importer"].import_bundle(s["bundle"])
    with pytest.raises(ValueError, match="replay"):
        s["importer"].import_bundle(s["bundle"])
    assert len(s["replay"].events()) == 1


def test_expired_bundle_is_rejected_before_import(tmp_path):
    s = setup(tmp_path)
    importer = ProvenanceTransportImporter(
        graph=s["local_graph"],
        security_graph=s["local_security"],
        receipt_store=s["local_store"],
        receipt_verifier=s["verifier"],
        replay_ledger=s["replay"],
        policy=s["importer"].policy,
        now_fn=lambda: BASE + timedelta(seconds=301),
    )
    with pytest.raises(ValueError, match="expired"):
        importer.import_bundle(s["bundle"])
    assert s["local_graph"].ledger.find_by_external_ref(
        f"remote-bundle:{s['bundle'].bundle_id}"
    ) == ()


def test_future_dated_bundle_beyond_skew_is_rejected(tmp_path):
    s = setup(tmp_path)
    future_issued = BASE + timedelta(minutes=5)
    future_bundle = s["remote_graph"].ledger.get(s["leaf"].glyph_id)
    exporter = ProvenanceTransportExporter(
        graph=s["remote_graph"],
        receipt_store=s["remote_store"],
        signer=s["sender"],
    )
    leaf_receipt = s["bundle"].leaf_receipt_id
    bundle = exporter.export(
        glyph_id=future_bundle.glyph_id,
        leaf_receipt_id=leaf_receipt,
        ttl_seconds=60,
        issued_at=future_issued,
    )
    with pytest.raises(ValueError, match="future"):
        s["importer"].import_bundle(bundle)


def test_untrusted_sender_is_rejected(tmp_path):
    s = setup(tmp_path)
    other = IdentitySigner("agent-B")
    s["registry"].register("agent-B", other.public_key)
    forged_sender = resign(
        s["bundle"],
        other,
        sender_id="agent-B",
    )
    with pytest.raises(ValueError, match="untrusted"):
        s["importer"].import_bundle(forged_sender)


def test_tampering_bundle_content_breaks_sender_signature(tmp_path):
    s = setup(tmp_path)
    tampered_leaf = dict(s["bundle"].leaf_glyph)
    tampered_leaf["content"] = {"kind": "derived_claim", "value": 999}
    tampered = replace(s["bundle"], leaf_glyph=tampered_leaf)
    with pytest.raises(ValueError):
        s["importer"].import_bundle(tampered)


def test_trusted_sender_still_cannot_import_invalid_receipt_chain(tmp_path):
    s = setup(tmp_path)
    receipts = list(s["bundle"].receipts)
    # Remove the origin receipt but re-sign the transport payload as the trusted
    # sender. Transport authentication alone must not replace provenance proof.
    invalid = resign(
        s["bundle"],
        s["sender"],
        receipts=(receipts[0],),
    )
    with pytest.raises((KeyError, ValueError)):
        s["importer"].import_bundle(invalid)
    assert s["replay"].events() == ()


def test_origin_authority_must_be_explicitly_allowed(tmp_path):
    s = setup(
        tmp_path,
        origin_class="trusted_observation",
        allowed={"external_authenticated"},
    )
    with pytest.raises(ValueError, match="not allowed"):
        s["importer"].import_bundle(s["bundle"])


def test_even_allowed_remote_runtime_attestation_is_not_local_runtime_observation(tmp_path):
    s = setup(
        tmp_path,
        origin_class="runtime_attested",
        allowed={"runtime_attested"},
    )
    result = s["importer"].import_bundle(s["bundle"])
    local = s["local_graph"].ledger.get(result.local_glyph_id)
    binding = s["local_security"].origin_binding(local.glyph_id)

    assert binding.content["authority_class"] == "runtime_attested"
    assert local.content["kind"] == "remote_signed_claim"
    assert local.content["channel"] == "remote_transport"
    assert local.content["runtime_local"] is False
    assert local.content["kind"] != "runtime_reality_observation"


def test_replay_ledger_detects_tampering(tmp_path):
    s = setup(tmp_path)
    s["importer"].import_bundle(s["bundle"])
    raw = s["replay"].path.read_text(encoding="utf-8")
    s["replay"].path.write_text(
        raw.replace(
            s["leaf"].glyph_id,
            "glyph:tampered",
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="integrity failure"):
        s["replay"].verify()


def test_revoked_sender_is_rejected(tmp_path):
    s = setup(tmp_path)
    s["registry"].revoke("agent-A", reason="compromised")
    with pytest.raises(ValueError, match="revoked"):
        s["importer"].import_bundle(s["bundle"])
