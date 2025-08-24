# Intégration des Modules de Post-traitement Synergesis

Ce document présente l'architecture et l'intégration des trois modules de post-traitement pour le pipeline de glyphisation Synergesis :

1. `glyph_fixer.py` (v0.1) - Implémenté et testé
2. `glyph_lint.py` (à développer)
3. `glyph_enricher.py` (à développer)

## 1. Architecture Globale

```
                                 ┌─────────────────┐
                                 │                 │
                                 │  LLM Output     │
                                 │  (Raw Glyphs)   │
                                 │                 │
                                 └────────┬────────┘
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│  ┌────────────────┐      ┌────────────────┐     ┌────────────────┐  │
│  │                │      │                │     │                │  │
│  │  glyph_fixer   │──────▶  glyph_lint    │─────▶ glyph_enricher │  │
│  │  (v0.1)        │      │  (v0.2+)       │     │  (v0.3+)       │  │
│  │                │      │                │     │                │  │
│  └────────────────┘      └────────────────┘     └────────────────┘  │
│                                                                     │
│                    Post-Processing Pipeline                         │
└─────────────────────────────────────────────────────────────────┬───┘
                                                                  │
                                                                  ▼
                                 ┌─────────────────┐
                                 │                 │
                                 │  Neo4j Graph    │
                                 │  Database       │
                                 │                 │
                                 └─────────────────┘
```

## 2. Flux de Données et Responsabilités

### 2.1 glyph_fixer.py (v0.1) - Implémenté

**Entrée** : Liste brute de dictionnaires GlyphData issus du LLM
**Sortie** : Liste de dictionnaires GlyphData avec corrections structurelles "SAFE"
**Responsabilités** :
- Correction des erreurs de structure (champs manquants, types incorrects)
- Conversion des types de données (string → int/float)
- Sérialisation des objets JSON
- Validation basique des relations
- Journalisation des corrections et erreurs

**Limites observées lors des tests** :
- Ne corrige pas les valeurs non convertibles (ex: "not_a_number" → int)
- Ne valide pas les valeurs énumérées (polarité, alignement)
- Ne vérifie pas la cohérence sémantique entre les glyphes

### 2.2 glyph_lint.py (v0.2+) - À développer

**Entrée** : Liste de dictionnaires GlyphData corrigés par glyph_fixer
**Sortie** : Liste de dictionnaires GlyphData validés + rapport de validation détaillé
**Responsabilités** :
- Validation stricte via Pydantic (types, bornes, énumérations)
- Vérification des contraintes métier (cohérence polarité/concept_type)
- Validation des relations inter-glyphes
- Détection des incohérences sémantiques
- Génération d'un rapport de validation détaillé

**Spécifications techniques** :
```python
# Modèle Pydantic pour GlyphData
class GlyphData(BaseModel):
    id: str
    timestamp: float
    source_document_id: str
    source_chunk_index: int
    natural_prompt: str
    polarité: Literal['+', '-', '0', '±', '?']
    alignement: Literal['Celestial', 'Chthonic', 'Void', 'Harmonic', 'Elemental', 'Expansion', 'Error']
    fréquence: conint(ge=60, le=120)
    poids: conint(ge=1, le=9)
    tags: List[str]
    entropy_score: confloat(ge=0.0, le=1.0)
    status: str
    details_json: str
    llm_prompt_version: str
    relationships: List[RelationshipModel]
    
    # Validateurs pour les règles métier
    @validator('polarité')
    def validate_polarite_concept_type(cls, v, values):
        # Vérifier cohérence polarité/concept_type
        tags = values.get('tags', [])
        if 'Problem' in tags and v != '-':
            return v  # Warning, pas d'erreur
        return v
    
    # Autres validateurs...
```

**Fonctions principales** :
```python
def validate_glyphs_data(
    glyphs_list: List[Dict[str, Any]], 
    strict_errors: bool = True,
    strict_warnings: bool = False
) -> Tuple[int, int, List[Dict[str, Any]]]:
    """
    Valide une liste de glyphes selon le modèle Pydantic.
    
    Args:
        glyphs_list: Liste de dictionnaires GlyphData
        strict_errors: Si True, lève une exception à la première erreur
        strict_warnings: Si True, traite les warnings comme des erreurs
        
    Returns:
        Tuple[int, int, List[Dict]]: (nombre d'erreurs, nombre de warnings, résumé des problèmes)
    """
    # Implémentation...
```

### 2.3 glyph_enricher.py (v0.3+) - À développer

**Entrée** : Liste de dictionnaires GlyphData validés par glyph_lint
**Sortie** : Liste de dictionnaires GlyphData enrichis
**Responsabilités** :
- Standardisation des tags selon une taxonomie prédéfinie
- Calcul du semantic_hash
- Ajout de relations inférées entre glyphes
- Calcul de scores de similarité sémantique
- Liaison avec des ontologies externes

**Spécifications techniques** :
```python
class GlyphEnricher:
    def __init__(self, taxonomy_file: str = None, ontology_file: str = None):
        """
        Initialise l'enrichisseur avec des taxonomies et ontologies optionnelles.
        
        Args:
            taxonomy_file: Chemin vers le fichier de taxonomie des tags
            ontology_file: Chemin vers le fichier d'ontologie externe
        """
        # Implémentation...
    
    def standardize_tags(self, glyph: Dict[str, Any]) -> Dict[str, Any]:
        """
        Standardise les tags selon la taxonomie définie.
        
        Args:
            glyph: Dictionnaire GlyphData
            
        Returns:
            Dict: GlyphData avec tags standardisés
        """
        # Implémentation...
    
    def calculate_semantic_hash(self, glyph: Dict[str, Any]) -> str:
        """
        Calcule un hash sémantique basé sur le contenu du glyphe.
        
        Args:
            glyph: Dictionnaire GlyphData
            
        Returns:
            str: Hash sémantique
        """
        # Implémentation...
    
    def infer_relationships(self, glyphs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Infère des relations supplémentaires entre les glyphes.
        
        Args:
            glyphs: Liste de dictionnaires GlyphData
            
        Returns:
            List[Dict]: Liste de glyphes avec relations inférées
        """
        # Implémentation...
    
    def enrich_glyphs_batch(self, glyphs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Applique toutes les étapes d'enrichissement à un lot de glyphes.
        
        Args:
            glyphs: Liste de dictionnaires GlyphData
            
        Returns:
            List[Dict]: Liste de glyphes enrichis
        """
        # Implémentation...
```

## 3. Intégration et Orchestration

### 3.1 Script d'Orchestration Principal

```python
#!/usr/bin/env python3
# File: process_glyphs_pipeline.py

import json
import logging
import sys
from typing import List, Dict, Any, Tuple
from pathlib import Path

from glyph_fixer import GlyphFixer
# Importer les autres modules quand ils seront disponibles
# from glyph_lint import validate_glyphs_data
# from glyph_enricher import GlyphEnricher

def process_glyphs(
    input_file: str,
    output_dir: str,
    run_fixer: bool = True,
    run_linter: bool = True,
    run_enricher: bool = True,
    strict_validation: bool = False
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Traite un fichier de glyphes à travers le pipeline complet.
    
    Args:
        input_file: Chemin vers le fichier JSON contenant les glyphes bruts
        output_dir: Répertoire de sortie pour les résultats
        run_fixer: Exécuter le module fixer
        run_linter: Exécuter le module linter
        run_enricher: Exécuter le module enricher
        strict_validation: Arrêter le pipeline en cas d'erreur de validation
        
    Returns:
        Tuple[bool, str, Dict]: (succès, chemin du fichier de sortie, rapport)
    """
    # Implémentation...
    
    # 1. Charger les données d'entrée
    with open(input_file, 'r') as f:
        raw_glyphs = json.load(f)
    
    # 2. Exécuter le fixer
    if run_fixer:
        fixer = GlyphFixer()
        fixed_glyphs, fixer_corrections, fixer_errors = fixer.fix_glyphs_batch(raw_glyphs)
    else:
        fixed_glyphs = raw_glyphs
        fixer_corrections = []
        fixer_errors = []
    
    # 3. Exécuter le linter (quand disponible)
    if run_linter:
        # lint_errors, lint_warnings, problematic_glyphs = validate_glyphs_data(
        #     fixed_glyphs, strict_errors=strict_validation
        # )
        # Simulation en attendant l'implémentation
        lint_errors, lint_warnings, problematic_glyphs = 0, 0, []
    else:
        lint_errors, lint_warnings, problematic_glyphs = 0, 0, []
    
    # 4. Exécuter l'enricher (quand disponible)
    if run_enricher:
        # enricher = GlyphEnricher()
        # enriched_glyphs = enricher.enrich_glyphs_batch(fixed_glyphs)
        # Simulation en attendant l'implémentation
        enriched_glyphs = fixed_glyphs
    else:
        enriched_glyphs = fixed_glyphs
    
    # 5. Préparer le rapport et sauvegarder les résultats
    report = {
        "input_file": input_file,
        "glyphs_count": len(raw_glyphs),
        "fixer": {
            "corrections_count": len(fixer_corrections),
            "errors_count": len(fixer_errors),
            "corrections": fixer_corrections[:10],  # Limiter pour la lisibilité
            "errors": fixer_errors[:10]
        },
        "linter": {
            "errors_count": lint_errors,
            "warnings_count": lint_warnings,
            "problematic_glyphs": problematic_glyphs[:10]
        },
        "success": lint_errors == 0 or not strict_validation
    }
    
    # Sauvegarder les glyphes traités
    output_file = Path(output_dir) / f"processed_{Path(input_file).stem}.json"
    with open(output_file, 'w') as f:
        json.dump(enriched_glyphs, f, indent=2)
    
    return report["success"], str(output_file), report

def main():
    """Point d'entrée principal"""
    # Implémentation...

if __name__ == "__main__":
    main()
```

### 3.2 Tests d'Intégration

```python
#!/usr/bin/env python3
# File: test_integration.py

import json
import logging
import sys
from pathlib import Path

from process_glyphs_pipeline import process_glyphs

# Implémentation des tests d'intégration...
```

## 4. Prochaines Étapes

1. **Développement de glyph_lint.py (v0.2)**
   - Implémenter les modèles Pydantic
   - Développer les validateurs pour les règles métier
   - Créer le système de rapport de validation

2. **Développement de glyph_enricher.py (v0.3)**
   - Implémenter le calcul du semantic_hash
   - Développer la standardisation des tags
   - Créer le système d'inférence de relations

3. **Finalisation de l'Orchestration**
   - Implémenter le script d'orchestration principal
   - Développer les tests d'intégration
   - Documenter l'utilisation du pipeline complet

4. **Validation sur le Golden Set**
   - Tester le pipeline complet sur les données du golden set
   - Comparer les résultats avec les attentes
   - Itérer sur les modules selon les résultats

## 5. Conclusion

L'architecture proposée pour les modules de post-traitement offre une approche modulaire et robuste pour traiter les glyphes générés par le LLM. Chaque module a une responsabilité claire et bien définie, permettant une évolution indépendante et une maintenance facilitée.

Les tests réalisés sur glyph_fixer.py (v0.1) ont démontré sa capacité à corriger les erreurs structurelles courantes, tout en identifiant clairement ses limites. Ces limites seront adressées par les modules suivants (glyph_lint.py et glyph_enricher.py), complétant ainsi le pipeline de post-traitement.

L'intégration de ces trois modules permettra d'obtenir des glyphes de haute qualité, prêts à être intégrés dans la base de connaissances Neo4j de Synergesis.
