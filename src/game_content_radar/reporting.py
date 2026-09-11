from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from game_content_radar.models import DraftPackage, EventCluster, SourceItem


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _score(event: EventCluster, kind: str) -> int:
    obj = event.xhh_score if kind == "xhh" else event.site_score
    return obj.total if obj else 0


def _event_block(title: str, event: EventCluster | None, draft_path: str | None = None) -> str:
    if event is None:
        return f"## {title}\n\nNo qualified candidate today.\n"
    lines = [
        f"## {title}", "",
        f"**Event:** {event.event_title}",
        f"**Game:** {event.game_name or '-'}",
        f"**Category:** `{event.category}`",
        f"**XHH Score:** {_score(event, 'xhh')}/100",
        f"**Preliminary Site Score:** {_score(event, 'site')}/100",
        f"**SERP validation required:** {'YES' if event.needs_serp_validation else 'NO'}",
    ]
    if draft_path:
        lines.append(f"**Draft:** `{draft_path}`")
    if event.signals.get("matched_existing_site"):
        lines.append(f"**Existing site fit:** {event.signals['matched_existing_site']}")
    lines.extend(["", "**Why:**"])
    if event.xhh_score:
        lines.extend(f"- {x}" for x in event.xhh_score.reasons)
    lines.extend(["", "**Sources:**"])
    lines.extend(f"- {u}" for u in event.source_urls[:8])
    return "\n".join(lines) + "\n"


def write_daily_report(
    report_dir: Path,
    raw_items: list[SourceItem],
    events: list[EventCluster],
    reach: EventCluster | None,
    value: EventCluster | None,
    seo_pick: EventCluster | None,
    warnings: list[str],
) -> None:
    a_tier = sum(1 for e in events if _score(e, "xhh") >= 80)
    b_tier = sum(1 for e in events if 65 <= _score(e, "xhh") < 80)
    lines = [
        "# Game Content Radar — Daily Report", "",
        "## Summary", "",
        f"- Raw items: {len(raw_items)}",
        f"- Events after clustering/aggregation: {len(events)}",
        f"- XHH A-tier (80+): {a_tier}",
        f"- XHH B-tier (65–79): {b_tier}",
        "- Site score is PRE-SERP only; keyword volume/KD/SERP strength still require Semrush/manual validation.",
        "",
    ]
    if warnings:
        lines.extend(["## Warnings", ""] + [f"- {w}" for w in warnings] + [""])
    lines.append(_event_block("Xiaoheihe Reach Pick", reach, "xhh/reach-pick.md"))
    lines.append(_event_block("Xiaoheihe Value Pick", value, "xhh/value-pick.md"))
    lines.append(_event_block("Best SEO / Site Validation Candidate", seo_pick, None))
    lines.extend(["## Top 10 XHH Candidates", "", "| Rank | Event | Category | XHH | Site(pre) |", "|---:|---|---|---:|---:|"])
    ranked = sorted(events, key=lambda e: _score(e, "xhh"), reverse=True)[:10]
    for i, e in enumerate(ranked, 1):
        title = e.event_title.replace("|", "/")
        lines.append(f"| {i} | {title} | {e.category} | {_score(e, 'xhh')} | {_score(e, 'site')} |")
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "daily-radar.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_draft(path: Path, event: EventCluster, draft: DraftPackage) -> None:
    lines = [
        f"# {draft.selected_title}", "",
        f"> XHH Score: {_score(event, 'xhh')} | Site(pre): {_score(event, 'site')}", "",
        draft.body_markdown, "",
        "## 评论引导", "",
        draft.comment_hook, "",
        "## 标题候选", "",
    ]
    for i, t in enumerate(draft.title_candidates, 1):
        lines.append(f"{i}. {t.title}  `[{t.style}]`")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _keyword_hypotheses(event: EventCluster) -> list[str]:
    game = (event.game_name or "").strip()
    title = event.event_title.lower()
    if event.category == "troubleshooting":
        if "steam workshop" in title:
            return ["steam workshop download stuck", "steam workshop not working", "steam workshop download error"]
        if game:
            return [f"{game} not working", f"{game} error", f"{game} fix"]
    if event.category == "major_update" and game:
        return [f"{game} update", f"{game} patch notes", f"{game} new update"]
    if event.category == "player_spike_story" and game:
        return [f"{game} player count", f"{game} steam charts", f"why is {game} popular"]
    if event.category == "guide" and game:
        return [f"{game} guide", f"{game} beginner guide"]
    return []


def write_seo_opportunities(path: Path, events: Iterable[EventCluster]) -> None:
    ranked = sorted(events, key=lambda e: _score(e, "site"), reverse=True)
    lines = [
        "# Preliminary SEO / Game-site Opportunities", "",
        "> These are discovery signals, not final SEO decisions. Validate volume, KD, SERP competitors and intent before building.", "",
    ]
    for e in ranked[:12]:
        if _score(e, "site") < 45:
            continue
        lines.extend([
            f"## {e.event_title}", "",
            f"- Preliminary Site Score: {_score(e, 'site')}",
            f"- XHH Score: {_score(e, 'xhh')}",
            f"- Category: `{e.category}`",
            f"- Needs SERP validation: YES",
        ])
        if e.signals.get("matched_existing_site"):
            lines.append(f"- Existing site fit: **{e.signals['matched_existing_site']}**")
        hypotheses = _keyword_hypotheses(e)
        if hypotheses:
            lines.append("- Keyword hypotheses (not volume-validated):")
            lines.extend(f"  - `{x}`" for x in hypotheses)
        lines.extend(["- Suggested validation:", "  - Semrush keyword variations", "  - Google SERP manual check", "  - competing page age/authority", "  - whether a dedicated page matches intent", "- Sources:"])
        lines.extend(f"  - {u}" for u in e.source_urls[:5])
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
