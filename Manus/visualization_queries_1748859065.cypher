// Afficher tous les glyphes
MATCH (g:Glyph) RETURN g

// Afficher les relations entre glyphes
MATCH (g1:Glyph)-[r:RELATES_TO]->(g2:Glyph) RETURN g1, r, g2

// Afficher les glyphes par type de concept
MATCH (g:Glyph) RETURN g.concept_type, count(g)

// Afficher le graphe complet avec relations typées
MATCH p=(g1:Glyph)-[r:RELATES_TO]->(g2:Glyph) RETURN p

// Afficher les propriétés d'un glyphe spécifique
MATCH (g:Glyph {id: 'techglyph_202505140900_1'}) RETURN g

// Rechercher des glyphes par concept_type
MATCH (g:Glyph) WHERE g.concept_type CONTAINS 'PROBLEM' RETURN g