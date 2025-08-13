// Basic Glyph Queries

// Count all glyphs
MATCH (g:Glyph)
RETURN count(DISTINCT g)

// List all glyphs with their properties
MATCH (g:Glyph)
RETURN g
LIMIT 25

// List all unique concept types and their counts
MATCH (g:Glyph)
RETURN DISTINCT g.concept_type, count(*)
ORDER BY count(*) DESC

// Find glyphs by specific concept type
MATCH (g:Glyph {concept_type: 'SYSTEM_GOAL'})
RETURN g
LIMIT 10

// Explore relationships between glyphs
MATCH (g1:Glyph)-[r]->(g2:Glyph)
RETURN g1, type(r), g2
LIMIT 25

// Find glyphs with specific alignment
MATCH (g:Glyph {alignement: 'STRONG'})
RETURN g
LIMIT 10

// Find glyphs by timestamp range
MATCH (g:Glyph)
WHERE g.timestamp > 1744687721 AND g.timestamp < 1744687722
RETURN g
LIMIT 10

// Get glyph statistics
MATCH (g:Glyph)
RETURN 
    count(DISTINCT g) as total_glyphs,
    count(DISTINCT g.concept_type) as unique_concept_types,
    avg(g.polarité) as average_polarity,
    min(g.timestamp) as oldest,
    max(g.timestamp) as newest

// Find recent glyphs
MATCH (g:Glyph)
ORDER BY g.timestamp DESC
RETURN g
LIMIT 10

// Find glyphs by source
MATCH (g:Glyph {source: 'test_pipeline'})
RETURN g
LIMIT 10

// Find glyphs by status
MATCH (g:Glyph {status: 'ACTIVE'})
RETURN g
LIMIT 10

// Create index on glyph ID (if not exists)
CREATE CONSTRAINT IF NOT EXISTS ON (g:Glyph) ASSERT g.id IS UNIQUE

// Find glyphs by ID
MATCH (g:Glyph {id: 'glyph_1d1731d7-bd66-48b4-b6f6-989abeb05b71'})
RETURN g

// Find glyphs with specific metadata
MATCH (g:Glyph)
WHERE g.metadata IS NOT NULL
RETURN g
LIMIT 10
