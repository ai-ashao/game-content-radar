from game_content_radar.evidence import validate_title
from game_content_radar.models import EventCluster, SourceItem


def event(low=False):
    item = SourceItem(
        id="1", source="steam_store", source_url="https://store", source_type="official",
        game_name="Game", title="Game", category="sale",
        metrics={"discount_percent": 80, "historical_low_verified": low},
    )
    return EventCluster(event_id="e", event_title="Game sale", game_name="Game", category="sale", sources=[item])


def test_unverified_historical_low_rejected():
    ok, issues = validate_title("Game 史低 -80%", event(False))
    assert not ok
    assert issues


def test_verified_historical_low_allowed():
    ok, issues = validate_title("Game 史低 -80%", event(True))
    assert ok
    assert not issues
