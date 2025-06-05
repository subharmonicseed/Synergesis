import os
import sys
import math
from unittest import mock

ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import synergesis.storage.neo4j_interface as n4


def test_single_upsert(monkeypatch):
    sample = {"id": "g1", "timestamp": 1.0, "source": "test", "concept_type": "TEST"}
    driver_calls = {"run": 0}

    class FakeSession:
        def run(self, q, **p):
            driver_calls["run"] += 1

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    class FakeDriver:
        def session(self):
            return FakeSession()

    monkeypatch.setattr(
        n4,
        "GraphDatabase",
        type("Stub", (), {"driver": lambda *a, **k: FakeDriver()}),
    )
    db = n4.Neo4jInterface("bolt://x", "u", "p")
    db.upsert_glyph_node(sample)
    assert driver_calls["run"] == 1



def test_upsert_query_contains_merge():
    fake_driver = mock.MagicMock()
    session = mock.MagicMock()
    fake_driver.session.return_value.__enter__.return_value = session
    interface = n4.Neo4jInterface(driver=fake_driver)
    glyph = {"id": "g1", "concept_type": "TEST"}
    interface.upsert_glyph_node(glyph)
    session.run.assert_called_once()
    query = session.run.call_args[0][0]
    assert "MERGE (g:Glyph {id:$id})" in query
    assert session.run.call_args[1]["id"] == "g1"



def test_bulk_upsert_calls_execute_query(monkeypatch):
    fake_driver = mock.MagicMock()
    fake_driver.session.return_value.__enter__.return_value = mock.MagicMock()
    interface = n4.Neo4jInterface(driver=fake_driver)
    call_count = {"n": 0}

    def fake_execute(q, p):
        call_count["n"] += 1

    monkeypatch.setattr(interface, "_execute_query", fake_execute)
    glyphs = [
        {"id": "g1", "concept_type": "TEST"},
        {"id": "g2", "concept_type": "TEST"},
        {"id": "g3", "concept_type": "TEST"},
    ]
    interface.bulk_upsert_glyphs(glyphs, batch_size=2)
    assert call_count["n"] == math.ceil(len(glyphs) / 2)
