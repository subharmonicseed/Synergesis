import hashlib
import json

import pytest

from synergesis_model_context_bridge import (
    BridgeError, SliceRequest, build_context_pack,
)


COMMIT = "a" * 40


def repo(tmp_path, source="@decorate\ndef target(x):\n    return x + 1\n"):
    (tmp_path / "pkg").mkdir(exist_ok=True)
    path = tmp_path / "pkg" / "sample.py"
    path.write_text(source, encoding="utf-8")
    manifest = json.dumps({"pkg/sample.py": hashlib.sha256(path.read_bytes()).hexdigest()},
                         sort_keys=True, separators=(",", ":")).encode()
    (tmp_path / "MANIFEST_SHA256.json").write_bytes(manifest)
    return hashlib.sha256(manifest).hexdigest()


def build(tmp_path, manifest_hash, **kw):
    return build_context_pack(root=tmp_path, source_commit=COMMIT,
        manifest_sha256=manifest_hash, objective="Review target safely",
        slices=[SliceRequest("pkg/sample.py", "target")], **kw)


def test_exact_symbol_includes_decorator_and_provenance(tmp_path):
    mh = repo(tmp_path)
    result = build(tmp_path, mh, counter=lambda text: len(text),
                   counter_identity="test-counter-v1", budget=10000, reserve=20)
    pack = json.loads(result.text)
    assert pack["slices"][0]["code"].startswith("@decorate")
    assert pack["slices"][0]["symbol"] == "target"
    assert pack["source_commit"] == COMMIT
    assert "not Git commit attestation" in pack["warning"]
    assert result.accounting["measured"] == len(result.text)
    assert result.accounting["total_with_reserve"] == len(result.text) + 20


def test_unknown_symbol_and_manifest_changes_fail(tmp_path):
    mh = repo(tmp_path)
    with pytest.raises(BridgeError, match="not found"):
        build_context_pack(root=tmp_path, source_commit=COMMIT, manifest_sha256=mh,
            objective="x", slices=[SliceRequest("pkg/sample.py", "missing")])
    with (tmp_path / "pkg/sample.py").open("a") as f:
        f.write("\n# changed\n")
    with pytest.raises(BridgeError, match="file hash"):
        build(tmp_path, mh)


def test_manifest_bytes_must_match_external_pin(tmp_path):
    mh = repo(tmp_path)
    with (tmp_path / "MANIFEST_SHA256.json").open("ab") as f:
        f.write(b" ")
    with pytest.raises(BridgeError, match="manifest bytes"):
        build(tmp_path, mh)


def test_budget_is_all_or_nothing_and_counter_contract(tmp_path):
    mh = repo(tmp_path)
    with pytest.raises(BridgeError, match="budget exceeded"):
        build(tmp_path, mh, budget=1)
    for val in (True, -1, 1.5):
        with pytest.raises(BridgeError):
            build(tmp_path, mh, counter=lambda _: val,
                  counter_identity="bad-counter", budget=10000)
    with pytest.raises(BridgeError, match="identity"):
        build(tmp_path, mh, counter=lambda _: 1, budget=10000)


@pytest.mark.parametrize("source", [
    "# token = 'do-not-print-this'\ndef target():\n    pass\n",
    "secret = 'ordinary-literal'\ndef target():\n    pass\n",
    "# -----BEGIN RSA PRIVATE KEY-----\ndef target():\n    pass\n",
])
def test_source_secret_patterns_refused(tmp_path, source):
    mh = repo(tmp_path, source)
    with pytest.raises(BridgeError, match="secret pattern"):
        build(tmp_path, mh)


def update_manifest(root, extra):
    path = root / "MANIFEST_SHA256.json"
    manifest = json.loads(path.read_bytes())
    manifest.update(extra)
    raw = json.dumps(manifest, sort_keys=True).encode()
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def test_symlink_selected_file_refused(tmp_path):
    repo(tmp_path)
    (tmp_path / "alias.py").symlink_to(tmp_path / "pkg" / "sample.py")
    mh = update_manifest(tmp_path, {
        "alias.py": hashlib.sha256((tmp_path / "pkg/sample.py").read_bytes()).hexdigest()
    })
    with pytest.raises(BridgeError):
        build_context_pack(root=tmp_path, source_commit=COMMIT, manifest_sha256=mh,
            objective="x", slices=[SliceRequest("alias.py", "target")])


@pytest.mark.parametrize("path", ["../sample.py", "/sample.py", "pkg/../sample.py", "pkg/sample.txt"])
def test_unsafe_or_non_python_selection_refused(tmp_path, path):
    mh = repo(tmp_path)
    with pytest.raises(BridgeError):
        build_context_pack(root=tmp_path, source_commit=COMMIT, manifest_sha256=mh,
            objective="x", slices=[SliceRequest(path, "target")])


def test_test_role_is_referenced_not_run(tmp_path):
    mh = repo(tmp_path)
    result = build_context_pack(root=tmp_path, source_commit=COMMIT, manifest_sha256=mh,
        objective="Review test", slices=[SliceRequest("pkg/sample.py", "target", "test")])
    assert json.loads(result.text)["slices"][0]["test_status"] == "referenced_not_run"


def test_mixed_manifest_does_not_read_unselected_entries(tmp_path):
    repo(tmp_path)
    mh = update_manifest(tmp_path, {
        "README.md": "b" * 64,
        ".github/workflows/test.yml": "c" * 64,
        "data/config.json": "d" * 64,
    })
    assert json.loads(build(tmp_path, mh).text)["slices"][0]["symbol"] == "target"


def test_distinct_methods_share_verified_source(tmp_path):
    mh = repo(tmp_path, "class Engine:\n    def first(self):\n        return 1\n    def second(self):\n        return 2\n")
    result = build_context_pack(root=tmp_path, source_commit=COMMIT, manifest_sha256=mh,
        objective="Review methods", slices=[SliceRequest("pkg/sample.py", "Engine.first"),
                                          SliceRequest("pkg/sample.py", "Engine.second")])
    payload = json.loads(result.text)
    assert [item["symbol"] for item in payload["slices"]] == ["Engine.first", "Engine.second"]
    assert payload["slices"][0]["sha256"] == payload["slices"][1]["sha256"]


@pytest.mark.parametrize("key,value", [
    ("budget", True), ("budget", 6000.0), ("budget", float("nan")),
    ("budget", 0), ("reserve", True), ("reserve", 0.5), ("reserve", -1),
])
def test_budget_and_reserve_require_strict_integers(tmp_path, key, value):
    mh = repo(tmp_path)
    with pytest.raises(BridgeError):
        build(tmp_path, mh, **{key: value})


def test_request_generator_stops_at_cap(tmp_path):
    mh = repo(tmp_path)
    seen = []
    def requests():
        for number in range(34):
            seen.append(number)
            yield SliceRequest("pkg/sample.py", "target", "interface")
        pytest.fail("request collection exceeded bounded lookahead")
    with pytest.raises(BridgeError):
        build_context_pack(root=tmp_path, source_commit=COMMIT, manifest_sha256=mh,
            objective="x", slices=requests())
    assert len(seen) <= 33


def test_secret_environment_lookup_is_not_a_literal(tmp_path):
    mh = repo(tmp_path, "import os\nNEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD')\ndef target():\n    return NEO4J_PASSWORD\n")
    assert json.loads(build(tmp_path, mh).text)["slices"][0]["symbol"] == "target"


def test_source_is_parsed_without_execution(tmp_path):
    marker = tmp_path / "executed"
    mh = repo(tmp_path, f"from pathlib import Path\nPath({str(marker)!r}).write_text('bad')\ndef target():\n    raise RuntimeError('not to execute')\n")
    assert "raise RuntimeError" in build(tmp_path, mh).text
    assert not marker.exists()


def test_symlink_manifest_refused_even_with_correct_bytes_pin(tmp_path):
    mh = repo(tmp_path)
    manifest = tmp_path / "MANIFEST_SHA256.json"
    real = tmp_path / "pinned.json"
    manifest.rename(real)
    manifest.symlink_to(real)
    with pytest.raises(BridgeError):
        build(tmp_path, mh)


def test_symlink_source_ancestor_refused(tmp_path):
    mh = repo(tmp_path)
    (tmp_path / "pkg").rename(tmp_path / "actual_pkg")
    (tmp_path / "pkg").symlink_to(tmp_path / "actual_pkg", target_is_directory=True)
    with pytest.raises(BridgeError):
        build(tmp_path, mh)


def test_interface_excludes_implementation_body(tmp_path):
    mh = repo(tmp_path, "def target(value: int = 3) -> int:\n    implementation_marker = 40\n    return value + implementation_marker\n")
    result = build_context_pack(root=tmp_path, source_commit=COMMIT, manifest_sha256=mh,
        objective="Review interface", slices=[SliceRequest("pkg/sample.py", "target", "interface")])
    item = json.loads(result.text)["slices"][0]
    assert "def target(" in item["code"]
    assert "implementation_marker" not in item["code"]
    assert "int" in item["code"]


def test_cli_failure_never_creates_output(tmp_path):
    from synergesis_model_context_bridge import main
    mh = repo(tmp_path)
    output = tmp_path / "context.json"
    with pytest.raises(SystemExit) as error:
        main(["--root", str(tmp_path), "--commit", COMMIT,
              "--manifest-sha256", mh, "--objective", "review",
              "--slice", "pkg/sample.py:target", "--budget", "1",
              "--output", str(output)])
    assert error.value.code == 2
    assert not output.exists()


def test_cli_refuses_overwriting_existing_output(tmp_path):
    from synergesis_model_context_bridge import main
    mh = repo(tmp_path)
    output = tmp_path / "context.json"
    output.write_text("preserve me")
    with pytest.raises(SystemExit):
        main(["--root", str(tmp_path), "--commit", COMMIT,
              "--manifest-sha256", mh, "--objective", "review",
              "--slice", "pkg/sample.py:target", "--output", str(output)])
    assert output.read_text() == "preserve me"
