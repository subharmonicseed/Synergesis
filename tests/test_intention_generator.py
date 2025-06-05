from synergesis.cognitive_core.intention_generator import IntentionGenerator
from synergesis.cognitive_core.memory_system import MemorySystem


class FakeNeo4j:
    pass


def test_intention_generator_propose_actions():
    ig = IntentionGenerator(FakeNeo4j(), MemorySystem())
    actions = ig.propose_actions()
    assert isinstance(actions, list)
    if actions:
        g = actions[0]
        assert g["concept_type"] == "POTENTIAL_ACTION"
