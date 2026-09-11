from game_content_radar.collectors.base import CollectorResult
from game_content_radar.pipeline import _collect


class Good:
    name = "good"
    def collect(self):
        return CollectorResult(source="good", items=[], warnings=["minor warning"])


class Bad:
    name = "bad"
    def collect(self):
        raise RuntimeError("boom")


def test_source_failure_does_not_abort():
    items, warnings = _collect([Good(), Bad()])
    assert items == []
    assert any("minor warning" in w for w in warnings)
    assert any("bad failed" in w for w in warnings)
