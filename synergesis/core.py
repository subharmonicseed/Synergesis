# synergesis/core.py

import uuid
from datetime import datetime, timezone
import numpy as np

from synergesis.analysis.clustering import AutoTuningQuantumClustererPro
from synergesis.processing.context_validator import AdvancedContextValidator
from synergesis.glyph_core import Glyph
from synergesis.storage.neo4j_interface import Neo4jInterface

class SynergesisCore:
    """
    The advanced Synergesis core, integrating processing, analysis, and storage.
    """
    def __init__(self):
        """Initializes the core components."""
        self.validator = AdvancedContextValidator()
        self.clusterer = AutoTuningQuantumClustererPro()
        self.memory: list[Glyph] = []

        try:
            self.storage = Neo4jInterface()
            print("Successfully connected to Neo4j.")
        except Exception as e:
            print(f"Warning: Could not connect to Neo4j. Storage will be disabled. Error: {e}")
            self.storage = None

    def process_input(self, state: np.ndarray, context: str = "") -> Glyph:
        """
        Processes an input, creates a Glyph, updates clusters, and stores the result.
        """

        # 1. Validate context
        validation_results = self.validator.analyze_context(context)

        # 2. Create the Glyph object
        glyph = Glyph(
            content=context,
            weight=(validation_results.get('ethical_score', 0) + 1) * 5.0,
            metadata={"validation": validation_results}
        )

        self.memory.append(glyph)

        # 3. Update clusters
        cluster_pattern = {
            "state": state,
            "weight": glyph.weight,
            "glyph_id": glyph.id
        }
        self.clusterer.update_clusters([cluster_pattern])

        # 4. Persist the new glyph to the database
        if self.storage:
            try:
                self.storage.bulk_upsert_glyphs([glyph])
            except Exception as e:
                # Log the error but don't crash the application
                print(f"Warning: Failed to store glyph {glyph.id} in Neo4j. Error: {e}")

        return glyph

    def close(self):
        """Cleanly closes downstream connections."""
        if self.storage:
            self.storage.close()
