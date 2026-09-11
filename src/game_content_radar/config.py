from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(slots=True)
class RadarConfig:
    report_root: str = "reports"
    data_root: str = "data"
    request_timeout_seconds: int = 15
    user_agent: str = "game-content-radar/0.1 (+public-web-research)"
    language: str = "zh-CN"
    country: str = "CN"
    daily_candidates: int = 10
    daily_drafts: int = 3
    recommended_posts: int = 2
    sale_roundup_min_items: int = 20
    sale_roundup_min_discount: int = 30
    player_scan_limit: int = 30
    watched_apps: dict[int, str] = field(default_factory=dict)
    subreddits: list[str] = field(default_factory=lambda: ["gaming", "Steam"])
    official_rss: list[str] = field(default_factory=list)
    enabled_sources: dict[str, bool] = field(
        default_factory=lambda: {
            "steam_store": True,
            "steam_news": True,
            "steam_players": True,
            "reddit": True,
            "epic": True,
            "xiaoheihe": False,
            "steamdb": False,
            "official_rss": False,
        }
    )
    existing_sites: dict[str, list[str]] = field(default_factory=dict)
    llm_mode: str = "heuristic"
    llm_command: str = ""
    codex_binary: str = "codex"
    codex_timeout_seconds: int = 240


def _parse_watched_apps(value: Any) -> dict[int, str]:
    result: dict[int, str] = {}
    if isinstance(value, dict):
        for k, v in value.items():
            try:
                result[int(k)] = str(v)
            except (TypeError, ValueError):
                continue
    elif isinstance(value, list):
        for row in value:
            if isinstance(row, dict) and "appid" in row:
                try:
                    result[int(row["appid"])] = str(row.get("name") or row["appid"])
                except (TypeError, ValueError):
                    continue
    return result


def load_config(path: str | Path) -> RadarConfig:
    path = Path(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    cfg = RadarConfig()

    sources = data.get("sources", {})
    if isinstance(sources, dict):
        cfg.enabled_sources.update({str(k): bool(v) for k, v in sources.items()})

    content = data.get("content", {})
    cfg.language = str(content.get("language", cfg.language))
    cfg.daily_candidates = int(content.get("daily_candidates", cfg.daily_candidates))
    cfg.daily_drafts = int(content.get("daily_drafts", cfg.daily_drafts))
    cfg.recommended_posts = int(content.get("recommended_posts", cfg.recommended_posts))

    collection = data.get("collection", {})
    cfg.country = str(collection.get("country", cfg.country))
    cfg.request_timeout_seconds = int(collection.get("request_timeout_seconds", cfg.request_timeout_seconds))
    cfg.sale_roundup_min_items = int(collection.get("sale_roundup_min_items", cfg.sale_roundup_min_items))
    cfg.sale_roundup_min_discount = int(collection.get("sale_roundup_min_discount", cfg.sale_roundup_min_discount))
    cfg.player_scan_limit = int(collection.get("player_scan_limit", cfg.player_scan_limit))
    cfg.subreddits = list(collection.get("subreddits", cfg.subreddits))
    cfg.official_rss = list(collection.get("official_rss", cfg.official_rss))
    cfg.watched_apps = _parse_watched_apps(collection.get("watched_apps", {}))

    paths = data.get("paths", {})
    cfg.report_root = str(paths.get("reports", cfg.report_root))
    cfg.data_root = str(paths.get("data", cfg.data_root))

    cfg.existing_sites = {
        str(site): [str(x).lower() for x in terms]
        for site, terms in (data.get("existing_sites", {}) or {}).items()
        if isinstance(terms, list)
    }

    llm = data.get("llm", {})
    cfg.llm_mode = str(llm.get("mode", cfg.llm_mode))
    cfg.llm_command = str(llm.get("command", cfg.llm_command))
    cfg.codex_binary = str(llm.get("codex_binary", cfg.codex_binary))
    cfg.codex_timeout_seconds = int(llm.get("codex_timeout_seconds", cfg.codex_timeout_seconds))
    return cfg
