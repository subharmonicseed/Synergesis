import os
import sys
from unittest import mock
import pytest

# Ensure project root is on the path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from synergesis.storage.neo4j_interface import Neo4jInterface
from synergesis.glyph_core import Glyph


@pytest.fixture
def mock_neo4j_driver():
    """Provides a mock Neo4j driver, session, and the GraphDatabase mock object."""
    with mock.patch("synergesis.storage.neo4j_interface.GraphDatabase") as mock_graph_db:
        mock_session = mock.MagicMock()
        mock_driver = mock.MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session
        mock_graph_db.driver.return_value = mock_driver
        yield mock_driver, mock_session, mock_graph_db

def test_constructor_uses_injected_driver(mock_neo4j_driver):
    """Tests that the constructor prioritizes an injected driver."""
    mock_driver, _, _ = mock_neo4j_driver
    interface = Neo4jInterface(driver=mock_driver)
    assert interface._driver is mock_driver

@mock.patch.dict(os.environ, {
    "NEO4J_URI": "bolt://localhost:7687",
    "NEO4J_USER": "neo4j",
    "NEO4J_PASSWORD": "password"
})
def test_constructor_uses_env_vars(mock_neo4j_driver):
    """Tests that the constructor falls back to environment variables."""
    mock_driver, _, mock_graph_db = mock_neo4j_driver
    interface = Neo4jInterface()
    assert interface._driver is mock_driver
    mock_graph_db.driver.assert_called_once_with("bolt://localhost:7687", auth=("neo4j", "password"))

def test_constructor_raises_error_if_config_missing():
    """Tests that a ValueError is raised if connection info is missing."""
    with pytest.raises(ValueError, match="Database connection details are missing"):
        Neo4jInterface()

def test_bulk_upsert_glyphs_uses_unwind(mock_neo4j_driver):
    """
    Tests that bulk_upsert_glyphs uses a single, efficient UNWIND query.
    """
    mock_driver, mock_session, _ = mock_neo4j_driver
    interface = Neo4jInterface(driver=mock_driver)

    glyphs = [
        Glyph(content="Glyph 1"),
        Glyph(content="Glyph 2"),
    ]

    interface.bulk_upsert_glyphs(glyphs)

    # Assert that a session was created and a single query was run
    mock_session.run.assert_called_once()

    # Get the actual arguments passed to session.run()
    args, kwargs = mock_session.run.call_args
    query = args[0]
    params = kwargs.get("glyphs", [])

    # Check the query for efficiency and correctness
    assert "UNWIND" in query
    assert "MERGE (g:Glyph {id: glyph_props.id})" in query
    assert "SET g = glyph_props" in query

    # Check that the parameters are a list of dictionaries
    assert isinstance(params, list)
    assert len(params) == 2
    assert params[0]["content"] == "Glyph 1"
    assert params[1]["id"] == glyphs[1].id

def test_bulk_upsert_glyphs_does_nothing_for_empty_list(mock_neo4j_driver):
    """Tests that no query is run if the input list is empty."""
    mock_driver, mock_session, _ = mock_neo4j_driver
    interface = Neo4jInterface(driver=mock_driver)

    interface.bulk_upsert_glyphs([])

    mock_session.run.assert_not_called()
