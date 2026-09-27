"""Retries across real ROAM ledger/graph/agenda boundaries count one result."""
import pytest

from synergesis_roam import MethodLedger, ResearchMethodLearner, SynRoam
from synergesis_roam_attention import ResearchAgenda, RoamAttentionController
from test_synergesis_roam import build, method, question, metrics
from test_synergesis_roam_attention import stack, need


def test_evaluation_retry_repairs_graph_without_counting_outcome_twice(tmp_path, monkeypatch):
    roam, learner, runtime, graph, *_ = build(tmp_path)
    research_method = method("recovery")
    learner.register(research_method)
    session = roam.research_once(question())
    original = graph.create

    def failed(kind, **kwargs):
        if kwargs.get("content", {}).get("kind") == "research_method_outcome":
            raise OSError("graph unavailable after outcome commit")
        return original(kind, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(graph, "create", failed)
        with pytest.raises(OSError, match="graph unavailable"):
            roam.evaluate(session, metrics())
    first = learner.ledger.outcomes()[0]
    assert graph.ledger.find_by_external_ref(first.outcome_id) == ()
    restarted_learner = ResearchMethodLearner(
        ledger=MethodLedger(learner.ledger.path), config=learner.config,
    )
    restarted_learner.register(research_method)
    restarted = SynRoam(learner=restarted_learner, runtime=runtime,
                        utility_weights=roam.utility_weights)
    result = restarted.evaluate(session, metrics())
    assert result == first
    assert restarted_learner.ledger.stats(session.method_id).observations == 1
    assert len(graph.ledger.find_by_external_ref(first.outcome_id, glyph_type="learning")) == 1
    assert restarted.evaluate(session, metrics()) == first
    assert len(restarted_learner.ledger.events()) == 1
    graph.ledger.verify()


def test_evaluation_retry_repairs_agenda_without_duplicate_learning(tmp_path, monkeypatch):
    graph, agenda, controller = stack(tmp_path)
    item = need("evaluation interrupted", 0.8)
    agenda.add(item)
    tick = controller.tick_once()

    def failed(*args, **kwargs):
        raise OSError("agenda unavailable after learning")

    with monkeypatch.context() as patch:
        patch.setattr(agenda, "mark_evaluated", failed)
        with pytest.raises(OSError, match="agenda unavailable"):
            controller.evaluate_need(need_id=item.need_id, session=tick.session, metrics=metrics())
    stored = controller.roam.learner.ledger.outcomes()[0]
    reopened = ResearchAgenda(agenda.path, graph=graph, weights=agenda.weights, actor=agenda.actor)
    restarted = RoamAttentionController(agenda=reopened, roam=controller.roam)
    assert reopened.get(item.need_id).status == "researched"
    result = restarted.evaluate_need(need_id=item.need_id, session=tick.session, metrics=metrics())
    assert result == stored
    assert reopened.get(item.need_id).status == "evaluated"
    assert reopened.get(item.need_id).event_count == 3
    assert controller.roam.learner.ledger.stats(tick.session.method_id).observations == 1
    assert len(graph.ledger.find_by_external_ref(stored.outcome_id, glyph_type="learning")) == 1
    graph.ledger.verify()


def test_adaptive_snapshot_does_not_mix_concurrent_outcome_generations(tmp_path, monkeypatch):
    import threading
    from test_synergesis_roam_adaptive import build as adaptive_build, method as adaptive_method
    from test_synergesis_roam_adaptive import fake_session, metrics as adaptive_metrics, weights

    learner = adaptive_build(tmp_path)
    candidate = adaptive_method("coherent")
    learner.register(candidate)
    learner.record_outcome(session=fake_session(candidate, 1), metrics=adaptive_metrics(0.2), weights=weights())
    snapshot_ready, release = threading.Event(), threading.Event()
    write_started, write_done = threading.Event(), threading.Event()
    original = learner._global_outcome_events
    scores, failures = [], []

    def held_snapshot():
        events = original()
        if not snapshot_ready.is_set():
            snapshot_ready.set()
            assert release.wait(5)
        return events

    monkeypatch.setattr(learner, "_global_outcome_events", held_snapshot)

    def read():
        try:
            scores.extend(learner._score_snapshot((candidate,)))
        except BaseException as exc:
            failures.append(exc)

    def write():
        try:
            write_started.set()
            learner.record_outcome(session=fake_session(candidate, 2), metrics=adaptive_metrics(0.9), weights=weights())
        except BaseException as exc:
            failures.append(exc)
        finally:
            write_done.set()

    reader, writer = threading.Thread(target=read), threading.Thread(target=write)
    reader.start()
    try:
        assert snapshot_ready.wait(5)
        writer.start()
        assert write_started.wait(5)
        assert not write_done.wait(0.05)
    finally:
        release.set()
        reader.join(10)
        if writer.ident is not None:
            writer.join(10)
    assert not reader.is_alive() and not writer.is_alive()
    assert not failures
    assert scores[0].observations_total == 1
    assert scores[0].observations_window == 1
    assert learner.ledger.stats(candidate.method_id).observations == 2
