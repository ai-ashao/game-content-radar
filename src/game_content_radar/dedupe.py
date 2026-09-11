from __future__ import annotations

import hashlib
import re
from difflib import SequenceMatcher
from urllib.parse import urlsplit, urlunsplit

from game_content_radar.models import EventCluster, SourceItem

_STOP = {
    "the", "a", "an", "of", "and", "to", "for", "in", "on", "with", "is", "now",
    "game", "steam", "update", "new", "official", "free",
}


def normalize_url(url: str) -> str:
    try:
        p = urlsplit(url)
        return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path.rstrip("/"), "", ""))
    except Exception:
        return url.strip()


def normalize_text(text: str) -> str:
    text = re.sub(r"[^\w\u4e00-\u9fff]+", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def _tokens(text: str) -> set[str]:
    return {x for x in normalize_text(text).split() if len(x) > 1 and x not in _STOP}


def item_similarity(a: SourceItem, b: SourceItem) -> float:
    if normalize_url(a.source_url) and normalize_url(a.source_url) == normalize_url(b.source_url):
        return 1.0
    game_a = normalize_text(a.game_name)
    game_b = normalize_text(b.game_name)
    if game_a and game_b and game_a != game_b:
        return 0.0
    ta, tb = _tokens(a.title), _tokens(b.title)
    jaccard = (len(ta & tb) / len(ta | tb)) if ta and tb else 0.0
    seq = SequenceMatcher(None, normalize_text(a.title), normalize_text(b.title)).ratio()
    same_game = bool(game_a and game_b and game_a == game_b)
    # Cross-source signals often use very different wording. A player spike, a major
    # update and a community-trend post about the same named game are allowed to
    # cluster even when lexical similarity is weak. This is intentionally narrow to
    # avoid collapsing every post about the same game into one event.
    pair = {a.category, b.category}
    compatible_with_spike = "player_spike_story" in pair and pair <= {"player_spike_story", "major_update", "community_trend"}
    if same_game and compatible_with_spike:
        return max(0.72, min(1.0, max(jaccard, seq * 0.8) + 0.30))
    # Update/community posts only get a smaller boost and still need lexical
    # overlap, otherwise unrelated same-day posts about the same game collapse.
    if same_game and pair == {"major_update", "community_trend"} and max(jaccard, seq) >= 0.35:
        return max(0.72, min(1.0, max(jaccard, seq * 0.8) + 0.25))
    game_bonus = 0.22 if same_game else 0.0
    category_bonus = 0.08 if a.category == b.category else 0.0
    return min(1.0, max(jaccard, seq * 0.8) + game_bonus + category_bonus)


def dedupe_exact(items: list[SourceItem]) -> list[SourceItem]:
    seen_urls: set[str] = set()
    seen_ids: set[str] = set()
    output: list[SourceItem] = []
    for item in items:
        url = normalize_url(item.source_url)
        if item.id in seen_ids:
            continue
        if url and url in seen_urls:
            continue
        seen_ids.add(item.id)
        if url:
            seen_urls.add(url)
        output.append(item)
    return output


def cluster_items(items: list[SourceItem], threshold: float = 0.70) -> list[EventCluster]:
    clusters: list[list[SourceItem]] = []
    for item in dedupe_exact(items):
        best_idx = None
        best_score = 0.0
        for idx, cluster in enumerate(clusters):
            score = max(item_similarity(item, existing) for existing in cluster)
            if score > best_score:
                best_score, best_idx = score, idx
        if best_idx is not None and best_score >= threshold:
            clusters[best_idx].append(item)
        else:
            clusters.append([item])

    events: list[EventCluster] = []
    for group in clusters:
        primary = max(group, key=lambda x: (x.source_type == "official", len(x.summary), len(x.title)))
        categories = [x.category for x in group]
        priority = [
            "player_spike_story", "troubleshooting", "controversy", "reputation_shift",
            "major_update", "guide", "free_game", "sale", "release", "community_trend", "other",
        ]
        counts = {c: categories.count(c) for c in set(categories)}
        category = max(counts, key=lambda c: (counts[c], -priority.index(c) if c in priority else -999))
        # When a quantitative player-spike signal is present, preserve that event type
        # even if one or more community posts are clustered with it.
        if "player_spike_story" in categories:
            category = "player_spike_story"
        game = next((x.game_name for x in group if x.game_name), "")
        digest = hashlib.sha1("|".join(sorted(x.id for x in group)).encode()).hexdigest()[:16]
        signals = {
            "source_count": len(group),
            "source_names": sorted(set(x.source for x in group)),
        }
        events.append(EventCluster(
            event_id=f"event-{digest}", event_title=primary.title, game_name=game,
            category=category, sources=group, signals=signals,
        ))
    return events
