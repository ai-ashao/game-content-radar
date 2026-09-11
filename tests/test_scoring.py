from game_content_radar.config import RadarConfig
from game_content_radar.models import EventCluster, SourceItem
from game_content_radar.scoring import score_site_preliminary, score_xhh


def test_sale_roundup_high_xhh_low_site_relative():
    sources = [
        SourceItem(id=str(i), source="steam_store", source_url=f"https://s/{i}", source_type="official", game_name=f"G{i}", title=f"G{i}", category="sale", metrics={"discount_percent": 70})
        for i in range(30)
    ]
    e = EventCluster("e", "Steam 30 deals", "Steam", "sale_roundup", sources, signals={"deal_count": 30, "max_discount": 70})
    x = score_xhh(e, RadarConfig())
    s = score_site_preliminary(e, RadarConfig())
    assert x.total > s.total
    assert x.components["utility_density"] >= 10


def test_troubleshooting_matches_existing_site():
    cfg = RadarConfig(existing_sites={"WorkshopFetch": ["steam workshop", "workshop download", "steamcmd"]})
    item = SourceItem(id="1", source="reddit", source_url="https://r", source_type="community", game_name="", title="Steam Workshop download stuck", summary="steam workshop error and workshop download not working", category="troubleshooting")
    e = EventCluster("e", item.title, "", "troubleshooting", [item])
    s = score_site_preliminary(e, cfg)
    assert s.components["existing_site_fit"] == 10
    assert e.signals["matched_existing_site"] == "WorkshopFetch"
