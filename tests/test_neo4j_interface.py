import os
import sys
from unittest import mock

ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from synergesis.storage.neo4j_interface import Neo4jInterface


def make_driver():
    mock_session = mock.MagicMock()
    driver = mock.MagicMock()
    driver.session.return_value.__enter__.return_value = mock_session
    return driver, mock_session


def test_constructor_uses_injected_driver():
    fake_driver, _ = make_driver()
    interface = Neo4jInterface(driver=fake_driver)
    assert interface._driver is fake_driver


def test_upsert_glyph_node_runs_cypher():
    fake_driver, session = make_driver()
    interface = Neo4jInterface(driver=fake_driver)
    glyph = {"id": "g1", "concept_type": "TEST"}
    interface.upsert_glyph_node(glyph)
    query = "MERGE (g:Glyph {id:$id})\nSET g += $props"
    session.run.assert_called_once_with(query, id="g1", props={"concept_type": "TEST"})


def test_bulk_upsert_glyphs_batches_calls():
    fake_driver, _ = make_driver()
    interface = Neo4jInterface(driver=fake_driver)
    with mock.patch.object(interface, "upsert_glyph_node") as upsert:
        glyphs = [
            {"id": "g1", "concept_type": "TEST"},
            {"id": "g2", "concept_type": "TEST"},
            {"id": "g3", "concept_type": "TEST"},
        ]
        interface.bulk_upsert_glyphs(glyphs, batch_size=2)
        assert upsert.call_count == 3
