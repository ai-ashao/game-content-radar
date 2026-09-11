from datetime import datetime, timedelta, timezone

from game_content_radar.history import HistoryStore


def test_history_finds_prior_snapshot(tmp_path):
    h = HistoryStore(tmp_path / "radar.db")
    now = datetime(2026, 9, 11, 0, 0, tzinfo=timezone.utc)
    h.add_player_snapshot(1, "Game", 1000, (now - timedelta(hours=24)).isoformat())
    row = h.nearest_before(1, 24, now)
    h.close()
    assert row is not None
    assert row[1] == 1000
