from pathlib import Path

from game_content_radar.llm.codex import CodexDraftProvider
from game_content_radar.models import EventCluster, SourceItem


def test_codex_missing_binary_falls_back(tmp_path):
    item = SourceItem(id="1", source="steam_news", source_url="https://s", source_type="official", game_name="Game", title="Game update", summary="Update details", category="major_update")
    event = EventCluster("e", "Game update", "Game", "major_update", [item])
    provider = CodexDraftProvider(Path(tmp_path), binary="definitely-not-a-real-codex-binary")
    draft = provider.build(event)
    assert draft.selected_title
    assert provider.last_warning and "not found" in provider.last_warning
