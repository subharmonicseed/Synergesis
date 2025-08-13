// Requêtes Cypher pour visualiser les résultats de l'enrichissement topologique

// Afficher tous les glyphes avec leur degré de centralité
MATCH (g:Glyph)
WHERE g.degree_centrality IS NOT NULL
RETURN g.id, g.natural_prompt, g.degree_centrality, g.in_degree, g.out_degree
ORDER BY g.degree_centrality DESC
LIMIT 10;

// Visualiser le graphe avec les relations de similarité
MATCH p=(g1:Glyph)-[r:SIMILAR_TO]-(g2:Glyph)
WHERE g1.id < g2.id
RETURN p
LIMIT 25;

// Visualiser le graphe avec les relations sémantiques
MATCH p=(g1:Glyph)-[r:RELATES_TO]->(g2:Glyph)
RETURN p
LIMIT 25;

// Afficher les glyphes les plus centraux par type de concept
MATCH (g:Glyph)
WHERE g.concept_type IS NOT NULL AND g.degree_centrality IS NOT NULL
RETURN g.concept_type, g.id, g.natural_prompt, g.degree_centrality
ORDER BY g.concept_type, g.degree_centrality DESC
LIMIT 15;

// Identifier les communautés potentielles basées sur les relations de similarité
MATCH (g:Glyph)-[r:SIMILAR_TO]-(g2:Glyph)
WHERE r.score > 0.5
WITH g, collect(g2) as similar_glyphs
WHERE size(similar_glyphs) > 1
RETURN g.id, g.natural_prompt, [glyph in similar_glyphs | glyph.id] as similar_ids, size(similar_glyphs) as community_size
ORDER BY community_size DESC
LIMIT 10;
