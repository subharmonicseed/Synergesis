import importlib
import types

import pytest

# Ensure project root on path handled in other tests; replicate
import os
import sys
ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import synergesis.processing.glyph_lint as glyph_lint


def test_valid_glyph_passes():
    glyph = {
        "id": "g1",
        "concept_type": "POTENTIAL_ACTION",
        "timestamp": 1.0,
        "status": "from_llm",
    }
    errors, warnings, logs = glyph_lint.validate_glyphs_data([glyph])
    assert errors == 0
    assert warnings == 0


def test_missing_concept_type_error_basic(monkeypatch):
    glyph = {"id": "g1", "timestamp": 1.0, "status": "from_llm"}
    monkeypatch.setattr(glyph_lint, "BaseModel", None)
    errors, warnings, _ = glyph_lint.validate_glyphs_data([glyph], strict_errors=True)
    assert errors == 1
    assert warnings == 0


def test_extra_field_warning(monkeypatch):
    glyph = {
        "id": "g1",
        "concept_type": "POTENTIAL_ACTION",
        "timestamp": 1.0,
        "status": "from_llm",
        "extra": "X",
    }
    errors, warnings, logs = glyph_lint.validate_glyphs_data([glyph], strict_warnings=True)
    assert errors == 0
    assert warnings == 1
