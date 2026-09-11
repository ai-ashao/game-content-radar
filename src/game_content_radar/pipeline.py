from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from game_content_radar.aggregate import build_freebie_roundup, build_sale_roundup
from game_content_radar.collectors.base import Collector, CollectorResult
from game_content_radar.collectors.epic import EpicFreeGamesCollector
from game_content_radar.collectors.reddit import RedditRSSCollector
from game_content_radar.collectors.rss import GenericRSSCollector
from game_content_radar.collectors.steam import SteamCurrentPlayersClient, SteamNewsCollector, SteamStoreCollector
from game_content_radar.collectors.steamdb import SteamDBPublicCollector
from game_content_radar.collectors.xiaoheihe import XiaoheihePublicCollector
from game_content_radar.config import RadarConfig
from game_content_radar.dedupe import cluster_items
from game_content_radar.history import HistoryStore
from game_content_radar.http import HttpClient
from game_content_radar.llm.command import ExternalCommandDraftProvider
from game_content_radar.llm.codex import CodexDraftProvider
from game_content_radar.models import DraftPackage, EventCluster, SourceItem
from game_content_radar.reporting import write_daily_report, write_draft, write_json, write_seo_opportunities
from game_content_radar.scoring import score_site_preliminary, score_xhh
from game_content_radar.writer import build_draft


@dataclass(slots=True)
class DailyRunResult:
    report_dir: Path
    raw_items: list[SourceItem]
    events: list[EventCluster]
    warnings: list[str]
    reach_pick: EventCluster | None
    value_pick: EventCluster | None
    seo_pick: EventCluster | None


def _classify_text(item: SourceItem) -> None:
    if item.category not in {"community_trend", "other"}:
        return
    text = (item.title + " " + item.summary).lower()
    troubleshooting = ["not working", "stuck", "error", "crash", "failed", "can't", "cannot", "help", "卡住", "报错", "打不开", "失败"]
    guide = ["how to", "guide", "tips", "攻略", "教程", "怎么", "如何"]
    controversy = ["review bomb", "controversy", "backlash", "negative reviews", "差评", "争议", "退款"]
    if any(x in text for x in troubleshooting):
        item.category = "troubleshooting"
    elif any(x in text for x in controversy):
        item.category = "controversy"
    elif any(x in text for x in guide):
        item.category = "guide"


def _infer_game_names(items: Iterable[SourceItem], watched_apps: dict[int, str]) -> None:
    names = sorted((n for n in watched_apps.values() if n), key=len, reverse=True)
    for item in items:
        if item.game_name:
            continue
        text = (item.title + " " + item.summary).lower()
        for name in names:
            if name.lower() in text:
                item.game_name = name
                break


def _collect(collectors: list[Collector]) -> tuple[list[SourceItem], list[str]]:
    items: list[SourceItem] = []
    warnings: list[str] = []
    for collector in collectors:
        try:
            result: CollectorResult = collector.collect()
            items.extend(result.items)
            warnings.extend(result.warnings)
        except Exception as exc:
            warnings.append(f"{getattr(collector, 'name', collector.__class__.__name__)} failed: {exc}")
    return items, warnings


def _build_collectors(cfg: RadarConfig, http: HttpClient) -> list[Collector]:
    out: list[Collector] = []
    src = cfg.enabled_sources
    if src.get("steam_store"):
        out.append(SteamStoreCollector(http, country=cfg.country))
    if src.get("steam_news") and cfg.watched_apps:
        out.append(SteamNewsCollector(http, cfg.watched_apps))
    if src.get("reddit"):
        out.append(RedditRSSCollector(http, cfg.subreddits))
    if src.get("epic"):
        out.append(EpicFreeGamesCollector(http, country=cfg.country))
    if src.get("official_rss") and cfg.official_rss:
        out.append(GenericRSSCollector(http, cfg.official_rss))
    if src.get("xiaoheihe"):
        out.append(XiaoheihePublicCollector(http))
    if src.get("steamdb"):
        out.append(SteamDBPublicCollector(http))
    return out


def _load_fixture(path: Path) -> list[SourceItem]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("items") or []
    return [SourceItem.from_dict(x) for x in data]


def _player_spike_items(
    cfg: RadarConfig,
    http: HttpClient,
    history: HistoryStore,
    base_items: list[SourceItem],
    now: datetime,
) -> tuple[list[SourceItem], list[str]]:
    if not cfg.enabled_sources.get("steam_players"):
        return [], []
    app_names = dict(cfg.watched_apps)
    for item in base_items:
        appid = item.metrics.get("appid")
        if appid is None:
            continue
        try:
            app_names.setdefault(int(appid), item.game_name or str(appid))
        except Exception:
            pass
    rows = list(app_names.items())[: cfg.player_scan_limit]
    client = SteamCurrentPlayersClient(http)
    output: list[SourceItem] = []
    warnings: list[str] = []
    for appid, name in rows:
        try:
            current = client.current_players(appid)
            if current is None:
                continue
            prev24 = history.nearest_before(appid, 24, now)
            prev7d = history.nearest_before(appid, 24 * 7, now)
            metrics: dict[str, object] = {"appid": appid, "player_count": current}
            growths = []
            if prev24 and prev24[1] > 0:
                g24 = (current - prev24[1]) / prev24[1] * 100
                metrics.update({"previous_players_24h": prev24[1], "growth_24h_percent": round(g24, 1)})
                growths.append(("24h", g24, current - prev24[1]))
            if prev7d and prev7d[1] > 0:
                g7 = (current - prev7d[1]) / prev7d[1] * 100
                metrics.update({"previous_players_7d": prev7d[1], "growth_7d_percent": round(g7, 1)})
                growths.append(("7d", g7, current - prev7d[1]))
            history.add_player_snapshot(appid, name, current, now.isoformat())
            strongest = max(growths, key=lambda x: x[1], default=None)
            if strongest and strongest[1] >= 50 and strongest[2] >= 500:
                window, growth, delta = strongest
                output.append(SourceItem(
                    id=f"players-{appid}-{now.strftime('%Y%m%d%H')}",
                    source="steam_players",
                    source_url=f"https://store.steampowered.com/app/{appid}/",
                    source_type="official",
                    game_name=name,
                    title=f"{name} player count spike",
                    summary=f"Steam current-player snapshot increased {growth:.1f}% vs local {window} baseline (+{delta:,}).",
                    published_at=now.isoformat(),
                    category="player_spike_story",
                    metrics=metrics,
                ))
        except Exception as exc:
            warnings.append(f"Current-player scan failed for app {appid} ({name}): {exc}")
    return output, warnings


def _select_picks(events: list[EventCluster]) -> tuple[EventCluster | None, EventCluster | None, EventCluster | None]:
    if not events:
        return None, None, None
    ranked_xhh = sorted(events, key=lambda e: e.xhh_score.total if e.xhh_score else 0, reverse=True)
    reach_categories = {"sale_roundup", "freebie_roundup", "player_spike_story", "major_update", "controversy", "release", "community_trend", "free_game"}
    value_categories = {"guide", "troubleshooting", "game_analysis", "player_spike_story", "major_update", "controversy", "reputation_shift"}
    reach = next((e for e in ranked_xhh if e.category in reach_categories and e.xhh_score and e.xhh_score.total >= 60), ranked_xhh[0])
    value = next((e for e in ranked_xhh if e.event_id != reach.event_id and e.category in value_categories and e.xhh_score and e.xhh_score.total >= 60), None)
    if value is None:
        value = next((e for e in ranked_xhh if e.event_id != reach.event_id and e.xhh_score and e.xhh_score.total >= 68), None)
    seo = max(events, key=lambda e: e.site_score.total if e.site_score else 0)
    return reach, value, seo


def _draft_provider(cfg: RadarConfig, base_dir: Path):
    if cfg.llm_mode == "codex":
        return CodexDraftProvider(base_dir, binary=cfg.codex_binary, timeout_seconds=cfg.codex_timeout_seconds)
    if cfg.llm_mode == "command" and cfg.llm_command.strip():
        return ExternalCommandDraftProvider(cfg.llm_command)
    return None


def run_daily(
    cfg: RadarConfig,
    base_dir: Path,
    run_date: str | None = None,
    fixture: Path | None = None,
    no_network: bool = False,
) -> DailyRunResult:
    now = datetime.now(timezone.utc)
    date_label = run_date or now.astimezone().date().isoformat()
    report_root = (base_dir / cfg.report_root).resolve()
    data_root = (base_dir / cfg.data_root).resolve()
    report_dir = report_root / date_label
    report_dir.mkdir(parents=True, exist_ok=True)
    data_root.mkdir(parents=True, exist_ok=True)

    http = HttpClient(timeout=cfg.request_timeout_seconds, user_agent=cfg.user_agent)
    warnings: list[str] = []
    if fixture:
        raw_items = _load_fixture(fixture)
        warnings.append(f"Fixture mode: loaded {len(raw_items)} synthetic/offline items from {fixture}.")
    elif no_network:
        raw_items = []
        warnings.append("No-network mode enabled; no collectors executed.")
    else:
        raw_items, warnings = _collect(_build_collectors(cfg, http))
        history = HistoryStore(data_root / "radar.db")
        try:
            player_items, player_warnings = _player_spike_items(cfg, http, history, raw_items, now)
            raw_items.extend(player_items)
            warnings.extend(player_warnings)
        finally:
            history.close()

    _infer_game_names(raw_items, cfg.watched_apps)
    for item in raw_items:
        _classify_text(item)

    events = cluster_items(raw_items)
    sale_roundup = build_sale_roundup(raw_items, cfg)
    free_roundup = build_freebie_roundup(raw_items)
    if sale_roundup:
        events.append(sale_roundup)
    if free_roundup:
        events.append(free_roundup)

    for event in events:
        event.xhh_score = score_xhh(event, cfg, now)
        event.site_score = score_site_preliminary(event, cfg)
        event.needs_serp_validation = True

    events.sort(key=lambda e: e.xhh_score.total if e.xhh_score else 0, reverse=True)
    reach, value, seo_pick = _select_picks(events)

    write_json(report_dir / "raw-items.json", [x.to_dict() for x in raw_items])
    write_json(report_dir / "events.json", [x.to_dict() for x in events])
    write_json(report_dir / "candidates.json", [x.to_dict() for x in events[: cfg.daily_candidates]])

    provider = _draft_provider(cfg, base_dir)
    picks: list[tuple[str, EventCluster]] = []
    if reach:
        picks.append(("reach-pick", reach))
    if value and value.event_id not in {e.event_id for _, e in picks}:
        picks.append(("value-pick", value))
    for event in events:
        if len(picks) >= cfg.daily_drafts:
            break
        if event.event_id not in {e.event_id for _, e in picks} and event.xhh_score and event.xhh_score.total >= 60:
            picks.append(("alternative", event))

    for slug, event in picks:
        draft: DraftPackage = provider.build(event) if provider else build_draft(event)
        provider_warning = getattr(provider, "last_warning", None) if provider else None
        if provider_warning:
            warnings.append(str(provider_warning))
        write_draft(report_dir / "xhh" / f"{slug}.md", event, draft)
        write_json(report_dir / "xhh" / f"media-plan-{slug}.json", draft.media_plan)
        write_json(report_dir / "xhh" / f"draft-package-{slug}.json", draft.to_dict())

    write_seo_opportunities(report_dir / "seo" / "opportunities.md", events)
    write_daily_report(report_dir, raw_items, events, reach, value, seo_pick, warnings)
    return DailyRunResult(report_dir, raw_items, events, warnings, reach, value, seo_pick)
