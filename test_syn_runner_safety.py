"""Safety checks for portable research-runner entry points."""
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
RUNNERS = (
    "run_syn_prediction_calibration_stress.py",
    "run_syn_provenance_receipt_matrix.py",
    "run_syn_provenance_stress_matrix.py",
    "run_syn_reality_filesystem_stress.py",
    "run_syn_reality_runtime_stress.py",
    "run_syn_reality_state_stress.py",
    "run_syn_roam_live_web_longrun.py",
    "syn_roam_endurance_adaptive_run.py",
    "syn_roam_endurance_adaptive_v2_run.py",
    "syn_roam_endurance_run.py",
    "run_syn_live_source_smoke.py",
)


def _run(script, *args):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, str(ROOT / script), *args], cwd=ROOT,
        env=env, capture_output=True, text=True, timeout=20,
    )


def test_help_has_no_output_side_effects(tmp_path):
    before = set(tmp_path.iterdir())
    for runner in RUNNERS:
        result = _run(runner, "--help")
        assert result.returncode == 0, (runner, result.stderr)
    assert set(tmp_path.iterdir()) == before


def test_rejects_existing_output_without_modifying_it(tmp_path):
    existing = tmp_path / "keep"
    existing.mkdir()
    sentinel = existing / "sentinel.txt"
    sentinel.write_text("keep me")
    result = _run("syn_roam_endurance_run.py", "--output", str(existing))
    assert result.returncode != 0
    assert sentinel.read_text() == "keep me"


def test_live_corpus_is_required_before_output_creation(tmp_path):
    output = tmp_path / "should-not-exist"
    result = _run("run_syn_roam_live_web_longrun.py", "--output", str(output),
                  "--corpus", str(tmp_path / "missing.json"))
    assert result.returncode != 0
    assert "corpus file does not exist" in result.stderr
    assert not output.exists()


def test_importing_runners_does_not_execute_them(tmp_path):
    result = subprocess.run(
        [sys.executable, "-c", "import run_syn_reality_state_stress, syn_roam_endurance_run"],
        cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT)},
        capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stderr
    assert not list(tmp_path.iterdir())
