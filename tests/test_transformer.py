import time
from src.topology_intention_transformer import TopologyIntentionTransformer


def test_transform_connect_similar_glyphs():
    transformer = TopologyIntentionTransformer()
    intention = {
        "type": "CONNECT_SIMILAR_GLYPHS",
        "source_glyph": {"id": "g1", "concept_type": "PROBLEM"},
        "target_glyph": {"id": "g2", "concept_type": "PROBLEM"},
        "similarity_score": 0.8,
        "suggested_relation": "RELATED_TO_CONCEPT",
        "priority": "MEDIUM",
        "rationale": "rationale",
    }
    result = transformer.transform_intentions([intention])[0]
    assert result["action_type"] == "CREATE_RELATIONSHIP"
    assert result["details_structured_json"]["action_parameters"]["source_glyph_id"] == "g1"
    assert result["details_structured_json"]["source_metadata"]["intention_type"] == "CONNECT_SIMILAR_GLYPHS"


def test_transform_create_solution_for_problem_cluster():
    transformer = TopologyIntentionTransformer()
    intention = {
        "type": "CREATE_SOLUTION_FOR_PROBLEM_CLUSTER",
        "target_cluster_id": "cluster_1",
        "problems": [
            {"id": "g1"},
            {"id": "g2"},
        ],
        "avg_similarity": 0.8,
        "priority": "HIGH",
        "rationale": "cluster rationale",
    }
    result = transformer.transform_intentions([intention])[0]
    assert result["action_type"] == "CREATE_SOLUTION_NODE"
    params = result["details_structured_json"]["action_parameters"]
    assert params["problem_glyphs"] == ["g1", "g2"]
    metadata = result["details_structured_json"]["source_metadata"]
    assert metadata["intention_type"] == "CREATE_SOLUTION_FOR_PROBLEM_CLUSTER"
