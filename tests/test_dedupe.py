from game_content_radar.dedupe import cluster_items
from game_content_radar.models import SourceItem


def test_same_game_similar_event_clusters():
    a = SourceItem(id="a", source="steam", source_url="https://a", source_type="official", game_name="Test Game", title="Test Game major update is live", category="major_update")
    b = SourceItem(id="b", source="reddit", source_url="https://b", source_type="community", game_name="Test Game", title="Test Game new major update finally live", category="major_update")
    clusters = cluster_items([a, b], threshold=0.60)
    assert len(clusters) == 1
    assert len(clusters[0].sources) == 2
