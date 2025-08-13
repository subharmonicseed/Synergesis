#!/usr/bin/env python3
# File: test_schemas.py
# Description: Tests unitaires pour les schémas Pydantic

import unittest
import time
from typing import Dict, Any, List
from pydantic import ValidationError

from schemas import (
    GlyphData,
    PotentialActionGlyph,
    TopologyObservation,
    TopologyIntention,
    SimulationResult,
    ExecutionResult,
    ActionExecutionRecord,
    PipelineResults,
    ConceptType,
    ActionType,
    ActionStatus,
    Priority,
    ObservationType,
    IntentionType,
    ExecutionStatus,
    convert_dict_to_glyph,
    convert_glyph_to_dict
)


class TestGlyphData(unittest.TestCase):
    """Tests pour le modèle GlyphData."""

    def test_valid_glyph(self):
        """Test de création d'un glyphe valide."""
        glyph = GlyphData(
            id="techglyph_202505140900_1",
            concept_type=ConceptType.TECHNICALCONCEPT,
            tags=["ai", "machine_learning"]
        )
        self.assertEqual(glyph.id, "techglyph_202505140900_1")
        self.assertEqual(glyph.concept_type, ConceptType.TECHNICALCONCEPT)
        self.assertEqual(glyph.tags, ["ai", "machine_learning"])
        self.assertEqual(glyph.natural_prompt, "Description non disponible")  # Valeur par défaut

    def test_missing_required_fields(self):
        """Test de validation avec des champs requis manquants."""
        with self.assertRaises(ValidationError):
            GlyphData(id="test_glyph")  # concept_type manquant

    def test_invalid_concept_type(self):
        """Test avec un type de concept invalide."""
        with self.assertRaises(ValidationError):
            GlyphData(
                id="test_glyph",
                concept_type="INVALID_TYPE"
            )

    def test_natural_prompt_default(self):
        """Test de la valeur par défaut pour natural_prompt."""
        glyph = GlyphData(
            id="test_glyph",
            concept_type=ConceptType.PROBLEM
        )
        self.assertEqual(glyph.natural_prompt, "Description non disponible")

    def test_timestamp_auto_generation(self):
        """Test de la génération automatique du timestamp."""
        before = int(time.time())
        glyph = GlyphData(
            id="test_glyph",
            concept_type=ConceptType.PROBLEM
        )
        after = int(time.time())
        self.assertTrue(before <= glyph.timestamp <= after)


class TestPotentialActionGlyph(unittest.TestCase):
    """Tests pour le modèle PotentialActionGlyph."""

    def test_valid_action(self):
        """Test de création d'une action potentielle valide."""
        from schemas import DetailsStructuredJson, ActionParameters, SourceMetadata
        
        action = PotentialActionGlyph(
            id="sem-potentialaction-TOPOGEN-ENRICHHUB-20250620-001",
            action_type=ActionType.ENRICH_HUB_NODE,
            priority=70,
            confidence=0.95,
            details_structured_json=DetailsStructuredJson(
                action_parameters=ActionParameters(
                    target_glyph_id="techglyph_202505140900_3"
                ),
                source_metadata=SourceMetadata(
                    intention_type="ENRICH_HUB_GLYPH"
                )
            ),
            details_text="Enrichir un glyphe hub"
        )
        self.assertEqual(action.id, "sem-potentialaction-TOPOGEN-ENRICHHUB-20250620-001")
        self.assertEqual(action.action_type, ActionType.ENRICH_HUB_NODE)
        self.assertEqual(action.priority, 70)
        self.assertEqual(action.confidence, 0.95)
        self.assertEqual(action.concept_type, ConceptType.POTENTIAL_ACTION)
        self.assertEqual(action.status, ActionStatus.PROPOSED)

    def test_invalid_id_format(self):
        """Test avec un format d'ID invalide."""
        from schemas import DetailsStructuredJson, ActionParameters
        
        with self.assertRaises(ValidationError):
            PotentialActionGlyph(
                id="invalid_id_format",
                action_type=ActionType.ENRICH_HUB_NODE,
                priority=70,
                confidence=0.95,
                details_structured_json=DetailsStructuredJson(
                    action_parameters=ActionParameters(
                        target_glyph_id="techglyph_202505140900_3"
                    )
                ),
                details_text="Enrichir un glyphe hub"
            )

    def test_missing_required_parameters(self):
        """Test avec des paramètres requis manquants."""
        from schemas import DetailsStructuredJson, ActionParameters
        
        with self.assertRaises(ValidationError):
            PotentialActionGlyph(
                id="sem-potentialaction-TOPOGEN-ENRICHHUB-20250620-001",
                action_type=ActionType.CREATE_RELATIONSHIP,  # Nécessite source et target
                priority=70,
                confidence=0.95,
                details_structured_json=DetailsStructuredJson(
                    action_parameters=ActionParameters(
                        target_glyph_id="techglyph_202505140900_3"
                        # source_glyph_id manquant
                    )
                ),
                details_text="Créer une relation"
            )

    def test_priority_range(self):
        """Test de la plage de priorité."""
        from schemas import DetailsStructuredJson, ActionParameters
        
        with self.assertRaises(ValidationError):
            PotentialActionGlyph(
                id="sem-potentialaction-TOPOGEN-ENRICHHUB-20250620-001",
                action_type=ActionType.ENRICH_HUB_NODE,
                priority=101,  # Hors plage (0-100)
                confidence=0.95,
                details_structured_json=DetailsStructuredJson(
                    action_parameters=ActionParameters(
                        target_glyph_id="techglyph_202505140900_3"
                    )
                ),
                details_text="Enrichir un glyphe hub"
            )


class TestTopologyObservation(unittest.TestCase):
    """Tests pour le modèle TopologyObservation."""

    def test_valid_observation(self):
        """Test de création d'une observation valide."""
        observation = TopologyObservation(
            id="obs_1750400459_1",
            type=ObservationType.HUB_GLYPHS_DETECTED,
            confidence=0.95,
            data={
                "hub_glyphs": ["techglyph_202505140900_3"],
                "centrality_scores": {"techglyph_202505140900_3": 5}
            },
            description="Détection de glyphes hub dans le graphe"
        )
        self.assertEqual(observation.id, "obs_1750400459_1")
        self.assertEqual(observation.type, ObservationType.HUB_GLYPHS_DETECTED)
        self.assertEqual(observation.confidence, 0.95)
        self.assertEqual(len(observation.data["hub_glyphs"]), 1)

    def test_invalid_observation_type(self):
        """Test avec un type d'observation invalide."""
        with self.assertRaises(ValidationError):
            TopologyObservation(
                id="obs_1750400459_1",
                type="INVALID_TYPE",
                confidence=0.95,
                data={},
                description="Observation invalide"
            )


class TestTopologyIntention(unittest.TestCase):
    """Tests pour le modèle TopologyIntention."""

    def test_valid_intention(self):
        """Test de création d'une intention valide."""
        intention = TopologyIntention(
            id="int_1750400460_1",
            type=IntentionType.ENRICH_HUB_GLYPH,
            priority=Priority.HIGH,
            confidence=0.95,
            source_observation_ids=["obs_1750400459_1"],
            target_elements={
                "hub_glyph_id": "techglyph_202505140900_3",
                "centrality": 5
            },
            description="Enrichir un glyphe hub important"
        )
        self.assertEqual(intention.id, "int_1750400460_1")
        self.assertEqual(intention.type, IntentionType.ENRICH_HUB_GLYPH)
        self.assertEqual(intention.priority, Priority.HIGH)
        self.assertEqual(intention.confidence, 0.95)
        self.assertEqual(len(intention.source_observation_ids), 1)

    def test_string_priority_conversion(self):
        """Test de conversion de priorité de chaîne en enum."""
        intention = TopologyIntention(
            id="int_1750400460_1",
            type=IntentionType.ENRICH_HUB_GLYPH,
            priority="HIGH",  # Chaîne au lieu de l'enum
            confidence=0.95,
            source_observation_ids=["obs_1750400459_1"],
            target_elements={},
            description="Enrichir un glyphe hub important"
        )
        self.assertEqual(intention.priority, Priority.HIGH)


class TestSimulationResult(unittest.TestCase):
    """Tests pour le modèle SimulationResult."""

    def test_valid_simulation_result(self):
        """Test de création d'un résultat de simulation valide."""
        result = SimulationResult(
            action_id="sem-potentialaction-TOPOGEN-ENRICHHUB-20250620-001",
            action_type=ActionType.ENRICH_HUB_NODE,
            structural_impact=0.07,
            semantic_impact=0.24,
            overall_impact=0.16,
            is_beneficial=True,
            recommendation="EXECUTE"
        )
        self.assertEqual(result.action_id, "sem-potentialaction-TOPOGEN-ENRICHHUB-20250620-001")
        self.assertEqual(result.action_type, ActionType.ENRICH_HUB_NODE)
        self.assertEqual(result.structural_impact, 0.07)
        self.assertEqual(result.semantic_impact, 0.24)
        self.assertEqual(result.overall_impact, 0.16)
        self.assertTrue(result.is_beneficial)
        self.assertEqual(result.recommendation, "EXECUTE")


class TestExecutionResult(unittest.TestCase):
    """Tests pour le modèle ExecutionResult."""

    def test_valid_execution_result(self):
        """Test de création d'un résultat d'exécution valide."""
        from schemas import ExecutionResultData
        
        result = ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            message="Action exécutée avec succès",
            data=ExecutionResultData(
                glyph_id="techglyph_202505140900_3",
                original_prompt="Description originale",
                enriched_prompt="Description enrichie"
            )
        )
        self.assertEqual(result.status, ExecutionStatus.SUCCESS)
        self.assertEqual(result.message, "Action exécutée avec succès")
        self.assertEqual(result.data.glyph_id, "techglyph_202505140900_3")
        self.assertEqual(result.data.original_prompt, "Description originale")
        self.assertEqual(result.data.enriched_prompt, "Description enrichie")


class TestConversionFunctions(unittest.TestCase):
    """Tests pour les fonctions de conversion."""

    def test_dict_to_glyph_conversion(self):
        """Test de conversion d'un dictionnaire en glyphe."""
        glyph_dict = {
            "id": "techglyph_202505140900_1",
            "concept_type": "TECHNICALCONCEPT",
            "tags": ["ai", "machine_learning"]
        }
        glyph = convert_dict_to_glyph(glyph_dict)
        self.assertIsInstance(glyph, GlyphData)
        self.assertEqual(glyph.id, "techglyph_202505140900_1")
        self.assertEqual(glyph.concept_type, ConceptType.TECHNICALCONCEPT)

    def test_dict_to_action_conversion(self):
        """Test de conversion d'un dictionnaire en action potentielle."""
        from schemas import DetailsStructuredJson, ActionParameters
        
        action_dict = {
            "id": "sem-potentialaction-TOPOGEN-ENRICHHUB-20250620-001",
            "action_type": "ENRICH_HUB_NODE",
            "priority": 70,
            "confidence": 0.95,
            "details_structured_json": {
                "action_parameters": {
                    "target_glyph_id": "techglyph_202505140900_3"
                }
            },
            "details_text": "Enrichir un glyphe hub"
        }
        action = convert_dict_to_glyph(action_dict)
        self.assertIsInstance(action, PotentialActionGlyph)
        self.assertEqual(action.id, "sem-potentialaction-TOPOGEN-ENRICHHUB-20250620-001")
        self.assertEqual(action.action_type, ActionType.ENRICH_HUB_NODE)

    def test_glyph_to_dict_conversion(self):
        """Test de conversion d'un glyphe en dictionnaire."""
        glyph = GlyphData(
            id="techglyph_202505140900_1",
            concept_type=ConceptType.TECHNICALCONCEPT,
            tags=["ai", "machine_learning"]
        )
        glyph_dict = convert_glyph_to_dict(glyph)
        self.assertIsInstance(glyph_dict, dict)
        self.assertEqual(glyph_dict["id"], "techglyph_202505140900_1")
        self.assertEqual(glyph_dict["concept_type"], "TECHNICALCONCEPT")
        self.assertEqual(glyph_dict["tags"], ["ai", "machine_learning"])


if __name__ == '__main__':
    unittest.main()
