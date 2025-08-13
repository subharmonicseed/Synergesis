# synergesis/processing/context_validator.py

import numpy as np
import spacy
from qiskit.quantum_info import Statevector
from scipy.stats import entropy
from typing import Dict, Any

# Chargement du modèle NLP avancé
# Note: This should be handled during environment setup, not at runtime.
try:
    nlp = spacy.load("en_core_web_lg")
except OSError:
    print("SpaCy model 'en_core_web_lg' not found.")
    print("Please run 'python -m spacy download en_core_web_lg' before starting the application.")
    # As a fallback for systems without the model, we can use a stub or raise an exception.
    # For now, we will let it fail if not present.
    # In a production system, a proper fallback or error handling is needed.
    raise

# Nouveau système de métriques énergétiques
class QuantumEnergyCalculator:
    def __init__(self):
        self.base_consumption = 1.0  # kWh par opération

    def calculate(self, state: np.ndarray) -> float:
        if isinstance(state, Statevector):
            complexity = np.linalg.norm(state.data)
        else:
            # Assuming state is a numpy array for simplicity if not a Statevector
            # The original code had a potential bug here if state was not a quantum state vector
            # We'll handle both cases more robustly.
            if np.iscomplexobj(state):
                complexity = np.sqrt(np.sum(np.abs(state)**2))
            else:
                # Fallback for non-complex arrays
                complexity = np.sqrt(np.sum(state**2))

        # Entropy calculation needs a probability distribution (sums to 1)
        # We'll normalize the absolute values to create one.
        abs_state = np.abs(state)
        if np.sum(abs_state) > 0:
            probabilities = abs_state / np.sum(abs_state)
            # Add a small epsilon to avoid log(0)
            entropy_val = entropy(probabilities + 1e-9)
        else:
            entropy_val = 0

        return self.base_consumption * complexity * (1 + entropy_val)

# Nouveau système de validation contextuelle
class AdvancedContextValidator:
    def __init__(self):
        self.ethical_framework = self._load_ethical_rules()
        self.energy_model = QuantumEnergyCalculator()

    def _load_ethical_rules(self) -> Dict[str, float]:
        return {
            "santé": 0.8,
            "environnement": 0.9,
            "militaire": -0.7,
            "surveillance": -0.6
        }

    def analyze_context(self, text: str) -> Dict[str, Any]:
        doc = nlp(text)
        semantic_vector = doc.vector
        ethical_score = self._calculate_ethical_score(doc)

        return {
            "semantic_embedding": semantic_vector,
            "ethical_score": ethical_score,
            "energy_impact": self.energy_model.calculate(semantic_vector) # Use semantic_vector for energy calculation
        }

    def _calculate_ethical_score(self, doc) -> float:
        score = 0.0
        for token in doc:
            if token.lemma_ in self.ethical_framework:
                # The original code used token.sentiment which is not a standard spaCy attribute.
                # Using polarity from a library like spacytextblob would be better.
                # For now, we'll use a placeholder logic.
                # Let's assume a positive sentiment if the word is found.
                sentiment_placeholder = 1.0
                score += self.ethical_framework[token.lemma_] * sentiment_placeholder
        return np.tanh(score)  # Normalisation entre -1 et 1
