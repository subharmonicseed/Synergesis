import pytest
from ingestion.glyphifier import glyphify_sleep_phase
from models.glyph import Glyph

def test_glyphifier_structure():
    # Create a mock LLM that returns a glyph with the typo
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
                        "polaritǸ": "test",  # Note the typo
                        "alignement": "test",
                        "content": "Test content from LLM",
                    }
                ]
            }

    # Test data
    raw_ctx = "This is a test context that should be used as content"
    parent_doc_id = "test_doc"
    source_chunk_index = 0
    llm_name = "test_llm"
    mock_llm = MockLLM()

    # Run glyphifier
    result = glyphify_sleep_phase(
        raw_ctx=raw_ctx,
        parent_doc_id=parent_doc_id,
        source_chunk_index=source_chunk_index,
        llm_name=llm_name,
        llm=mock_llm
    )

    # Verify results
    assert len(result["glyphs"]) == 1
    glyph = result["glyphs"][0]
    
    # Check field normalization
    assert glyph["polarité"] == "test"
    assert "polaritǸ" not in glyph
    
    # Check content fallback
    assert glyph["content"] == "Test content from LLM"
    
    # Check metadata
    assert glyph["metadata"] == {
        "parent_doc_id": parent_doc_id,
        "chunk_index": source_chunk_index,
        "llm_name": llm_name,
    }

    # Validate against Pydantic model
    try:
        Glyph(**glyph)
    except Exception as e:
        pytest.fail(f"Glyph failed validation: {e}")
