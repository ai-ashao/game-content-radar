from game_content_radar.dedupe import cluster_items
from game_content_radar.models import SourceItem


def test_player_spike_category_survives_community_merge():
    a = SourceItem(id="a", source="steam_players", source_url="https://a", source_type="official", game_name="Same Game", title="Same Game player count spike", category="player_spike_story", metrics={"growth_24h_percent": 200})
    b = SourceItem(id="b", source="reddit", source_url="https://b", source_type="community", game_name="Same Game", title="Same Game is suddenly popular again", category="community_trend")
    clusters = cluster_items([a, b])
    assert len(clusters) == 1
    assert clusters[0].category == "player_spike_story"
