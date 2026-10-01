import json
import pytest
from synergesis_compare import main


def test_demo_is_explicit_and_audited(tmp_path, capsys):
    output = tmp_path / "fresh"
    assert main(["--output", str(output)]) == 0
    assert "CONTRÔLE SIMULÉ" in capsys.readouterr().out
    report = json.loads((output / "report.json").read_text())
    assert report["identity"]["scripted_demo"] is True
    assert report["contains_scripted_demo"] is True
    assert report["summary"]["syn"]["success_count"] == 6
    assert report["summary"]["matched_context"]["success_count"] == 6
    assert report["summary"]["bare_model"]["success_count"] == 2


def test_existing_output_not_overwritten(tmp_path):
    marker = tmp_path / "keep"
    marker.write_text("original")
    with pytest.raises(SystemExit) as exc:
        main(["--output", str(tmp_path)])
    assert exc.value.code == 2
    assert marker.read_text() == "original"


def test_missing_model_no_artifact(tmp_path):
    output = tmp_path / "not-created"
    with pytest.raises(SystemExit):
        main(["--provider", "ollama", "--output", str(output)])
    assert not output.exists()
