# synergesis/analysis/clustering.py

import numpy as np
from sklearn.cluster import MiniBatchKMeans
from sklearn.decomposition import IncrementalPCA
from qiskit.quantum_info import Statevector

class AutoTuningQuantumClustererPro:
    def __init__(self, min_clusters=3, max_clusters=20, eval_interval=100):
        self.min_clusters = min_clusters
        self.max_clusters = max_clusters
        self.eval_interval = eval_interval
        self.kmeans = MiniBatchKMeans(n_clusters=min_clusters, n_init='auto')
        self.pca = IncrementalPCA(n_components=3)
        self.performance_log = []
        self.n_updates = 0

    def update_clusters(self, patterns):
        if not patterns:
            return

        features = self._extract_features(patterns)
        if not features:
            return

        features_array = np.array(features)

        # PCA requires n_samples >= n_components for the first fit
        if features_array.shape[0] < self.pca.n_components:
            status = f"Skipped PCA: Insufficient samples ({features_array.shape[0]}) for {self.pca.n_components} components."
            print(status)
            self._log_performance(features_array, status=status)
            return

        reduced = self._apply_dimensionality_reduction(features_array)

        # KMeans requires n_samples >= n_clusters
        if reduced.shape[0] < self.kmeans.n_clusters:
            status = f"Skipped KMeans: Insufficient samples ({reduced.shape[0]}) for {self.kmeans.n_clusters} clusters."
            print(status)
            self._log_performance(reduced, status=status)
            return

        self.n_updates += 1
        if self.n_updates % self.eval_interval == 0:
            self._auto_tune_parameters(reduced)

        self._partial_cluster_update(reduced)
        self._log_performance(reduced, status="Clustered successfully.")

    def _extract_features(self, patterns):
        # Assuming patterns is a list of dicts with 'state' and 'weight'
        return [self._quantum_to_vector(p.get('state'), p.get('weight', 1.0)) for p in patterns if 'state' in p]

    def _quantum_to_vector(self, state, weight):
        if isinstance(state, Statevector):
            state = state.data
        elif not isinstance(state, np.ndarray):
            state = np.array(state, dtype=complex)

        real_part = np.real(state)
        imag_part = np.imag(state)
        # Ensure consistent feature vector length, padding if necessary
        # This is a simple fix; a more robust solution would be needed for production
        if len(real_part) < 300: # Example dimension, like spaCy's lg model
            real_part = np.pad(real_part, (0, 300 - len(real_part)))
            imag_part = np.pad(imag_part, (0, 300 - len(imag_part)))

        return np.concatenate([real_part, imag_part]) * np.log1p(weight * 10)

    def _apply_dimensionality_reduction(self, features):
        if features.shape[1] <= self.pca.n_components:
            return features

        try:
            self.pca.partial_fit(features)
            return self.pca.transform(features)
        except Exception as e:
            print(f"PCA Error: {e}")
            # Fallback to using the first N components directly
            return features[:, :self.pca.n_components]

    def _partial_cluster_update(self, features):
        self.kmeans.partial_fit(features)

    def _log_performance(self, features, status="unknown"):
        """Logs clustering performance and status."""
        self.performance_log.append({
            "timestamp": np.datetime64('now'),
            "inertia": self.kmeans.inertia_ if hasattr(self.kmeans, 'inertia_') and "successfully" in status else None,
            "n_clusters": self.kmeans.n_clusters,
            "status": status,
            "n_features_in": features.shape[0]
        })

    def _auto_tune_parameters(self, features):
        # Simple auto-tuning: find best k using silhouette score or elbow method
        # This is a placeholder for a more advanced implementation.
        # For now, we'll just adjust k randomly as a stub
        new_k = np.random.randint(self.min_clusters, self.max_clusters + 1)
        if new_k != self.kmeans.n_clusters:
            print(f"Auto-tuning: Changing number of clusters to {new_k}")
            self.kmeans = MiniBatchKMeans(n_clusters=new_k, n_init='auto')
