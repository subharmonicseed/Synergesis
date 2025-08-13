import pytest
from ingestion.glyphifier import glyphify_sleep_phase
from models.glyph import Glyph
from datetime import datetime

def test_missing_required_fields():
    """Test that missing required fields are properly handled"""
    class MockLLM:
        def generate_glyphe(self, text):
            return {
                "glyphes": [
                    {
                        "id": "test_glyph",
                        "timestamp": 1234567890,
                        "concept_type": "TEST",  # Missing source
                        "status": "test",
                        "polarité": "test",
                        "alignement": "test",
                        "content": "Test content"
                    }
                ]
            }

    result = glyphify_sleep_phase(
        raw_ctx="Test context",
        parent_doc_id="test_doc",
        source_chunk_index=0,
        llm_name="test_llm",
        llm=MockLLM()
    )

    assert len(result["glyphs"]) == 0  # Should be rejected due to missing source

def test_invalid_content_types():
    """Test that invalid content types are handled correctly"""
    class MockLLM:
        def generate_glyphe(self, text):
            return {
                "glyphes": [
                    {
                        "id": "test_glyph",
                        "timestamp": 1234567890,
                        "source": "test_source",
                        "concept_type": "TEST",
                        "status": "test",
                        "polarité": "test",
                        "alignement": "test",
                        "content": 123  # Invalid content type
                    }
                ]
            }

    result = glyphify_sleep_phase(
        raw_ctx="Test context",
        parent_doc_id="test_doc",
        source_chunk_index=0,
        llm_name="test_llm",
        llm=MockLLM()
    )

    assert len(result["glyphs"]) == 0  # Should be rejected due to invalid content type

def test_too_long_id():
    """Test that overly long IDs are handled correctly"""
    class MockLLM:
        def generate_glyphe(self, text):
            return {
                "glyphes": [
                    {
                        "id": "a" * 256,  # Exceeds typical UUID length
                        "timestamp": 1234567890,
                        "source": "test_source",
                        "concept_type": "TEST",
                        "status": "test",
                        "polarité": "test",
                        "alignement": "test",
                        "content": "Test content"
                    }
                ]
            }

    result = glyphify_sleep_phase(
        raw_ctx="Test context",
        parent_doc_id="test_doc",
        source_chunk_index=0,
        llm_name="test_llm",
        llm=MockLLM()
    )

    assert len(result["glyphs"]) == 0  # Should be rejected due to invalid ID length

def test_schema_validation():
    """Test that Pydantic validates the final glyph structure"""
    glyph_data = {
        "id": "test_glyph",
        "timestamp": 1234567890,
        "source": "test_source",
        "concept_type": "TEST",
        "status": "test",
        "polarité": "test",
        "alignement": "test",
        "content": "Test content",
        "metadata": {
            "parent_doc_id": "test_doc",
            "chunk_index": 0,
            "llm_name": "test_llm"
        }
    }

    try:
        Glyph(**glyph_data)
    except Exception as e:
        pytest.fail(f"Valid glyph failed validation: {e}")

def test_invalid_status():
    """Test that invalid status values are rejected"""
    class MockLLM:
        def generate_glyphe(self, text):
            return {
                "glyphes": [
                    {
                        "id": "test_glyph",
                        "timestamp": 1234567890,
                        "source": "test_source",
                        "concept_type": "TEST",
                        "status": 123,  # Invalid status type
                        "polarité": "test",
                        "alignement": "test",
                        "content": "Test content"
                    }
                ]
            }

    result = glyphify_sleep_phase(
        raw_ctx="Test context",
        parent_doc_id="test_doc",
        source_chunk_index=0,
        llm_name="test_llm",
        llm=MockLLM()
    )

    assert len(result["glyphs"]) == 0  # Should be rejected due to invalid status type
