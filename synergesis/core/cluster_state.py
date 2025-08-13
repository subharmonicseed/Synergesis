# cluster_state.py
"""
Single source of truth for clustering log and counters.
Import this in both the API and the clustering code.
"""
import time
from datetime import datetime

performance_log = []  # List[dict]
patterns_seen = 0
engine_start_ts = time.time()

from collections import defaultdict

def append_cluster_snapshot(patterns, labels=None):
    """Append a meaningful cluster snapshot to the shared performance_log."""
    if not patterns:
        return

    if labels is None or len(patterns) == 1:
        clusters = {"cluster-0": [patterns[-1].id if hasattr(patterns[-1], 'id') else patterns[-1]["id"]]}
    else:
        tmp = defaultdict(list)
        for pat, lbl in zip(patterns, labels):
            pid = pat.id if hasattr(pat, 'id') else pat["id"]
            tmp[f"cluster-{lbl}"].append(pid)
        clusters = dict(tmp)

    snapshot = {
        "ts": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "clusters_total": len(clusters),
        "avg_cluster_size": round(sum(len(m) for m in clusters.values()) / len(clusters), 2),
        "clusters": clusters,
    }
    performance_log.append(snapshot)
    if len(performance_log) > 10000:
        performance_log.pop(0)

# Backwards-compat helper
def ensure_log(pattern_id=None):
    if not performance_log:
        dummy = type('Obj', (), {'id': pattern_id or 'placeholder'})
        append_cluster_snapshot([dummy], None)
