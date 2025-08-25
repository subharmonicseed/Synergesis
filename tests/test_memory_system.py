import pytest
from datetime import datetime, timedelta
from synergesis.cognitive_core.memory_system import MemorySystem
from synergesis.cognitive_core.glyph_core import GlyphData

def test_memory_decay():
    """Test memory decay over time."""
    # Create a memory system with decay rate
    ms = MemorySystem(decay_rate=0.95)  # 5% decay per time unit
    
    # Create two glyphs with different timestamps and statuses
    now = int(datetime.now().timestamp())  # Convert to int
    recent_glyph = GlyphData(
        id="recent",
        timestamp=now,
        source="test",
        concept_type="ACTION",
        status="executed",
        polarité="positive",
        alignement="strong",
        content="Recent action",
        parent_doc_id="test_doc",
    )
    
    old_glyph = GlyphData(
        id="old",
        timestamp=now - 3600,  # 1 hour old
        source="test",
        concept_type="ACTION",
        status="gated",
        polarité="positive",
        alignement="strong",
        content="Old action",
        parent_doc_id="test_doc",
    )
    
    # Store both glyphs
    ms.record_trace(recent_glyph, recent_glyph)  # Using same glyph for action/outcome
    ms.record_trace(old_glyph, old_glyph)
    
    # Fast-forward time by 1 hour
    ms.update_time(now + 3600)
    
    # Recent glyph should have higher weight
    recent_weight = ms.get_weight(recent_glyph)
    old_weight = ms.get_weight(old_glyph)
    
    assert recent_weight > old_weight, "Recent glyph should have higher weight"
    assert old_weight < 1.0, "Old glyph weight should have decayed"
    # Check decay formula - weight is base * status_factor * decay
    # For old_glyph:
    #   base = 1.0
    #   status_factor = 0.5   (gated)
    #   age_hours = 2 (already 1 hour old + 1 hour time jump)
    #   decay = 0.95 ** 2
    expected_weight = 0.5 * (0.95 ** 2)  # 2 hours decay
    assert pytest.approx(old_weight, 0.001) == expected_weight, "Decay formula mismatch"

def test_memory_relevance():
    """Test how memory decay affects relevance."""
    ms = MemorySystem(decay_rate=0.95)
    now = int(datetime.now().timestamp())  # Convert to int
    
    # Create glyphs with different timestamps and polarities
    strong_recent = GlyphData(
        id="strong_recent",
        timestamp=now,
        source="test",
        concept_type="ACTION",
        status="executed",
        polarité="strong",
        alignement="positive",
        content="Strong recent action",
        parent_doc_id="test_doc",
    )
    
    weak_old = GlyphData(
        id="weak_old",
        timestamp=now - 3600,
        source="test",
        concept_type="ACTION",
        status="gated",
        polarité="weak",
        alignement="neutral",
        content="Weak old action",
        parent_doc_id="test_doc",
    )
    
    # Store both glyphs
    ms.record_trace(strong_recent, strong_recent)
    ms.record_trace(weak_old, weak_old)
    
    # Check relevance ranking
    relevance = ms.get_relevance(strong_recent)
    assert relevance > ms.get_relevance(weak_old), "Strong recent glyph should be more relevant"
    
    # Fast-forward time and check decay
    ms.update_time(now + 7200)  # 2 hours later
    assert ms.get_relevance(strong_recent) < relevance, "Relevance should have decayed over time"

def test_edge_cases():
    """Test edge cases for memory system."""
    now = int(datetime.now().timestamp())
    
    # Test with extreme decay rate
    ms = MemorySystem(decay_rate=1.0)  # No decay
    recent = GlyphData(
        id="recent",
        timestamp=now,
        source="test",
        concept_type="ACTION",
        status="executed",
        polarité="positive",
        alignement="strong",
        content="Recent action",
        parent_doc_id="test_doc",
    )
    
    ms.record_trace(recent, recent)
    ms.update_time(now + 3600)  # 1 hour later
    assert pytest.approx(ms.get_weight(recent), 0.01) == 1.5, "No decay should keep original weight"
    
    # Test with very fast decay
    ms = MemorySystem(decay_rate=0.5)  # 50% decay per hour
    rapid = GlyphData(
        id="rapid",
        timestamp=now,
        source="test",
        concept_type="ACTION",
        status="executed",
        polarité="positive",
        alignement="strong",
        content="Rapid decay action",
        parent_doc_id="test_doc",
    )
    
    ms.record_trace(rapid, rapid)
    ms.update_time(now + 3600)  # 1 hour later
    assert pytest.approx(ms.get_weight(rapid), 0.01) == 0.75, "50% decay should reduce weight by half"
    
    # Test with unknown status
    ms = MemorySystem(decay_rate=0.95)  # Fresh instance with default decay
    unknown = GlyphData(
        id="unknown",
        timestamp=now,
        source="test",
        concept_type="ACTION",
        status="unknown_status",
        polarité="positive",
        alignement="strong",
        content="Unknown status action",
        parent_doc_id="test_doc",
    )
    
    ms.record_trace(unknown, unknown)
    assert pytest.approx(ms.get_weight(unknown), 0.01) == 0.75, "Unknown status should use conservative weight"
    assert pytest.approx(ms.get_weight(unknown), 0.01) == 0.75, "Unknown status should use conservative weight (no decay)"
    
    # Test with very old glyph
    ms = MemorySystem(decay_rate=0.95)  # Using default decay
    ancient = GlyphData(
        id="ancient",
        timestamp=now - 86400 * 30,  # 30 days old
        source="test",
        concept_type="ACTION",
        status="executed",
        polarité="positive",
        alignement="strong",
        content="Ancient action",
        parent_doc_id="test_doc",
    )
    
    ms.record_trace(ancient, ancient)
    ms.update_time(now)  # Set current time to now
    weight = ms.get_weight(ancient)
    assert weight < 0.01, "Very old glyph should have near-zero weight"
    assert weight > 0, "Weight should never be zero or negative"
    
    # Test with future timestamp
    ms = MemorySystem(decay_rate=0.95)  # Using default decay
    future = GlyphData(
        id="future",
        timestamp=now + 3600,  # 1 hour in the future
        source="test",
        concept_type="ACTION",
        status="executed",
        polarité="positive",
        alignement="strong",
        content="Future action",
        parent_doc_id="test_doc",
    )
    
    ms.record_trace(future, future)
    assert pytest.approx(ms.get_weight(future), 0.01) == 1.5, "Future timestamp should not decay yet"
