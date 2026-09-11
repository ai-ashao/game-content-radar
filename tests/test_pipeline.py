from pathlib import Path

from game_content_radar.config import load_config
from game_content_radar.pipeline import run_daily


ROOT = Path(__file__).resolve().parents[1]


def test_offline_fixture_end_to_end(tmp_path):
    cfg = load_config(ROOT / "config" / "default.yaml")
    cfg.report_root = "reports"
    cfg.data_root = "data"
    result = run_daily(
        cfg,
        base_dir=tmp_path,
        run_date="2026-09-11",
        fixture=ROOT / "tests" / "fixtures" / "sample-items.json",
    )
    assert result.reach_pick is not None
    assert result.value_pick is not None
    assert (result.report_dir / "daily-radar.md").exists()
    assert (result.report_dir / "events.json").exists()
    assert (result.report_dir / "xhh" / "reach-pick.md").exists()
    assert (result.report_dir / "seo" / "opportunities.md").exists()
    assert any(e.category == "sale_roundup" for e in result.events)
    assert any(e.category == "freebie_roundup" for e in result.events)
    # Historical-low guard: no unverified 史低 headline in the generated reach draft.
    text = (result.report_dir / "xhh" / "reach-pick.md").read_text(encoding="utf-8")
    assert "史低" not in text.split("\n", 1)[0]
