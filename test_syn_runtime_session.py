import json
import multiprocessing
import os
import time
from types import SimpleNamespace

import pytest

import synergesis_runtime_session as runtime


def test_registry_rejects_nested_same_root_and_releases_after_exception(tmp_path, monkeypatch):
    class Config:
        root = tmp_path
    monkeypatch.setattr("synergesis_secure_roam_stack_v2.build_secure_roam_reality_stack",
                        lambda **kwargs: object(), raising=False)
    # Module is imported inside the context; inject it without importing the real graph.
    import sys, types
    fake = types.ModuleType("synergesis_secure_roam_stack_v2")
    fake.build_secure_roam_reality_stack = lambda **kwargs: object()
    monkeypatch.setitem(sys.modules, fake.__name__, fake)
    with pytest.raises(runtime.RuntimeSessionBusy):
        with runtime.secure_roam_runtime_session(config=Config()):
            with runtime.secure_roam_runtime_session(config=Config()):
                pass
    with runtime.secure_roam_runtime_session(config=Config()):
        pass


def _hold_lock(root, ready, release):
    class Config:
        pass
    Config.root = root
    import sys, types
    fake = types.ModuleType("synergesis_secure_roam_stack_v2")
    fake.build_secure_roam_reality_stack = lambda **kwargs: object()
    sys.modules[fake.__name__] = fake
    with runtime.secure_roam_runtime_session(config=Config()):
        ready.set()
        release.wait(10)


def test_second_process_is_rejected_and_crash_releases_lock(tmp_path, monkeypatch):
    import sys, types
    fake = types.ModuleType("synergesis_secure_roam_stack_v2")
    fake.build_secure_roam_reality_stack = lambda **kwargs: object()
    monkeypatch.setitem(sys.modules, fake.__name__, fake)
    ctx = multiprocessing.get_context("spawn")
    ready, release = ctx.Event(), ctx.Event()
    process = ctx.Process(target=_hold_lock, args=(str(tmp_path), ready, release))
    process.start()
    assert ready.wait(10)
    class Config:
        root = tmp_path
    with pytest.raises(runtime.RuntimeSessionBusy):
        with runtime.secure_roam_runtime_session(config=Config()):
            pass
    process.terminate()
    process.join(10)
    assert process.exitcode is not None
    with runtime.secure_roam_runtime_session(config=Config()):
        pass


def test_diagnostic_bounds_and_reports_truncated_jsonl_without_payload(tmp_path):
    (tmp_path / "good.jsonl").write_text('{"safe":1}\n{"partial":', encoding="utf8")
    (tmp_path / "large.jsonl").write_bytes(b"x" * 100)
    (tmp_path / "x.transport-attempt.json").write_text('{"secret":"do-not-print"}')
    result = runtime.inspect_storage(tmp_path, max_files=10, max_file_bytes=30, max_line_bytes=10)
    by_name = {entry["file"]: entry for entry in result["jsonl_files"]}
    assert by_name["good.jsonl"]["trailing_truncated_line"]
    assert by_name["good.jsonl"]["status"] == "malformed_or_overlong"
    assert by_name["large.jsonl"]["status"] == "over_file_limit"
    rendered = json.dumps(result)
    assert "do-not-print" not in rendered and "secret" not in rendered
    assert result["recognized_pending"][0]["name"] == "x.transport-attempt.json"


def test_timeout_must_be_finite(tmp_path):
    class Config:
        root = tmp_path
    for value in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError):
            with runtime.secure_roam_runtime_session(config=Config(), lock_timeout=value):
                pass


def test_diagnostic_ignores_symlinks_and_caps_entry_inventory(tmp_path):
    (tmp_path / "a.jsonl").write_text('{"ok":true}\n')
    outside = tmp_path.parent / "outside.jsonl"
    outside.write_text('{"secret":"not scanned"}\n')
    (tmp_path / "link.jsonl").symlink_to(outside)
    (tmp_path / "z.pending").write_text("pending")
    result = runtime.inspect_storage(tmp_path, max_files=2)
    assert len(result["jsonl_files"]) <= 2
    assert result["inventory_truncated"]
    assert all(entry["file"] != "link.jsonl" for entry in result["jsonl_files"])
    assert "not scanned" not in json.dumps(result)


def test_diagnostic_does_not_create_glyph_verifier_sidecar(tmp_path):
    ledger = tmp_path / "glyph_ledger.jsonl"
    ledger.write_text('{"event":1}\n')
    before = set(tmp_path.iterdir())
    runtime.inspect_storage(tmp_path)
    assert set(tmp_path.iterdir()) == before
