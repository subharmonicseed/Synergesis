from dataclasses import dataclass

import pytest

from synergesis_roam_attention import RoamTick
from synergesis_roam_service import (
    RoamServiceLedger,
    RoamServiceLimits,
    SynRoamService,
)


@dataclass(frozen=True)
class Session:
    session_id: str


class Controller:
    def __init__(self, ticks):
        self.ticks = list(ticks)
        self.calls = 0

    def tick_once(self):
        self.calls += 1
        if not self.ticks:
            return RoamTick(None, None, "idle")
        return self.ticks.pop(0)


def test_service_runs_only_explicit_finite_tick_budget(tmp_path):
    controller = Controller(
        [
            RoamTick("need-1", Session("s1"), "researched"),
            RoamTick("need-2", Session("s2"), "researched"),
            RoamTick("need-3", Session("s3"), "researched"),
        ]
    )
    service = SynRoamService(
        controller=controller,
        ledger=RoamServiceLedger(tmp_path / "service.jsonl"),
        limits=RoamServiceLimits(
            max_ticks_per_batch=2,
            stop_when_idle=False,
        ),
    )
    ticks = service.run_bounded()
    assert len(ticks) == 2
    assert controller.calls == 2


def test_service_stops_batch_on_idle_when_configured(tmp_path):
    controller = Controller(
        [
            RoamTick("need-1", Session("s1"), "researched"),
            RoamTick(None, None, "idle"),
            RoamTick("need-2", Session("s2"), "researched"),
        ]
    )
    service = SynRoamService(
        controller=controller,
        ledger=RoamServiceLedger(tmp_path / "service.jsonl"),
        limits=RoamServiceLimits(
            max_ticks_per_batch=10,
            stop_when_idle=True,
        ),
    )
    ticks = service.run_bounded()
    assert [t.status for t in ticks] == ["researched", "idle"]
    assert controller.calls == 2


def test_every_service_tick_is_persisted(tmp_path):
    ledger = RoamServiceLedger(tmp_path / "service.jsonl")
    service = SynRoamService(
        controller=Controller([RoamTick("need-1", Session("s1"), "researched")]),
        ledger=ledger,
        limits=RoamServiceLimits(1, True),
    )
    service.run_bounded()
    records = ledger.records()
    assert len(records) == 1
    assert records[0].need_id == "need-1"
    assert records[0].session_id == "s1"


def test_service_ledger_detects_tampering(tmp_path):
    path = tmp_path / "service.jsonl"
    ledger = RoamServiceLedger(path)
    ledger.append(RoamTick("need-1", Session("s1"), "researched"))
    raw = path.read_text(encoding="utf-8")
    path.write_text(raw.replace("researched", "hacked"), encoding="utf-8")
    with pytest.raises(ValueError, match="integrity failure"):
        ledger.records()


def test_invalid_batch_budget_is_rejected():
    with pytest.raises(ValueError, match=">= 1"):
        RoamServiceLimits(max_ticks_per_batch=0, stop_when_idle=True)
