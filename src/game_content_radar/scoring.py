from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from game_content_radar.config import RadarConfig
from game_content_radar.models import EventCluster, ScoreBreakdown


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    value = value.strip()
    try:
        if value.endswith("Z"):
            return datetime.fromisoformat(value[:-1] + "+00:00")
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _freshness(event: EventCluster, now: datetime) -> int:
    dates = [_parse_dt(x.published_at) for x in event.sources]
    dates = [x for x in dates if x is not None]
    if not dates:
        # Store snapshots/freebies often have no article publish timestamp.
        return 15 if event.category in {"sale_roundup", "freebie_roundup", "sale", "free_game"} else 7
    hours = max(0.0, (now - max(dates)).total_seconds() / 3600)
    if hours < 6: return 15
    if hours < 12: return 14
    if hours < 24: return 12
    if hours < 48: return 8
    if hours < 72: return 5
    return 2


def score_xhh(event: EventCluster, cfg: RadarConfig, now: datetime | None = None) -> ScoreBreakdown:
    now = now or datetime.now(timezone.utc)
    cat = event.category
    signals = event.signals

    fit_map = {
        "sale_roundup": 20, "freebie_roundup": 20, "player_spike_story": 20,
        "major_update": 18, "controversy": 19, "reputation_shift": 19,
        "guide": 18, "troubleshooting": 19, "game_analysis": 17,
        "sale": 13, "free_game": 16, "release": 13, "community_trend": 12,
    }
    audience_fit = fit_map.get(cat, 10)
    freshness = _freshness(event, now)

    if cat == "sale_roundup":
        n = int(signals.get("deal_count") or len(event.sources))
        utility = min(15, 10 + n // 10)
        breadth = min(10, 6 + n // 10)
    elif cat == "freebie_roundup":
        n = int(signals.get("free_count") or len(event.sources))
        utility = min(15, 10 + n)
        breadth = min(10, 6 + n)
    elif cat in {"guide", "troubleshooting"}:
        utility, breadth = 15, 7
    else:
        utility = min(15, 5 + 2 * len(event.sources))
        breadth = 7 if cat in {"major_update", "player_spike_story", "controversy"} else 5

    evidence_points = 0
    evidence_reasons: list[str] = []
    metric_keys = set()
    for s in event.sources:
        metric_keys.update(k for k, v in s.metrics.items() if v not in (None, "", False))
    for key in ["growth_24h_percent", "growth_7d_percent", "player_count", "discount_percent", "free_until", "review_percent", "wishlist_count", "sales_count"]:
        if key in metric_keys or signals.get(key) is not None:
            evidence_points += 2
    if cat == "sale_roundup" and signals.get("deal_count"):
        evidence_points += 3
    if cat == "freebie_roundup" and signals.get("free_count"):
        evidence_points += 2
    evidence = min(10, evidence_points)
    if evidence:
        evidence_reasons.append("Contains quantitative/source-backed signals")

    hook = 7
    if cat in {"player_spike_story", "controversy", "reputation_shift"}: hook = 15
    elif cat in {"major_update", "sale_roundup", "freebie_roundup"}: hook = 12
    elif signals.get("known_anchor"): hook = 14
    elif evidence >= 6: hook = 11

    discussion = 5
    if cat in {"controversy", "reputation_shift"}: discussion = 10
    elif cat in {"player_spike_story", "major_update", "game_analysis"}: discussion = 8
    elif cat in {"sale_roundup", "freebie_roundup"}: discussion = 7

    if any(bool(s.metrics.get("top_seller")) for s in event.sources):
        breadth = min(10, breadth + 1)
        hook = min(15, hook + 1)
    if any(bool(s.metrics.get("new_release")) for s in event.sources) and cat == "release":
        hook = min(15, hook + 1)

    source_types = {s.source_type for s in event.sources}
    if "official" in source_types and len(event.sources) >= 2:
        source_conf = 5
        confidence = "high"
    elif "official" in source_types:
        source_conf = 4
        confidence = "medium"
    else:
        source_conf = 2
        confidence = "low"

    components = {
        "xiaoheihe_audience_fit": audience_fit,
        "freshness": freshness,
        "utility_density": utility,
        "hook_story_strength": hook,
        "discussion_potential": discussion,
        "evidence_strength": evidence,
        "audience_breadth": breadth,
        "source_confidence": source_conf,
    }
    reasons = [
        f"Category={cat}",
        f"Sources={len(event.sources)} ({', '.join(sorted(set(s.source for s in event.sources)))})",
        *evidence_reasons,
    ]
    return ScoreBreakdown(total=min(100, sum(components.values())), components=components, reasons=reasons, confidence=confidence)


def _existing_site_fit(event: EventCluster, cfg: RadarConfig) -> tuple[int, str | None]:
    hay = " ".join([event.event_title, event.game_name] + [s.title + " " + s.summary for s in event.sources]).lower()
    best_site, best_hits = None, 0
    for site, terms in cfg.existing_sites.items():
        hits = sum(1 for term in terms if term and term in hay)
        if hits > best_hits:
            best_site, best_hits = site, hits
    return (10 if best_hits >= 2 else 7 if best_hits == 1 else 0), best_site


def score_site_preliminary(event: EventCluster, cfg: RadarConfig) -> ScoreBreakdown:
    """Pre-SERP score only. This deliberately does not pretend to know keyword volume/KD."""
    cat = event.category
    search_intent = {
        "troubleshooting": 25, "guide": 23, "player_spike_story": 13,
        "major_update": 14, "release": 13, "community_trend": 10,
        "sale_roundup": 5, "freebie_roundup": 6, "sale": 5, "free_game": 6,
    }.get(cat, 9)

    growth = 8
    growth_signal = 0.0
    for s in event.sources:
        for key in ("growth_24h_percent", "growth_7d_percent"):
            try:
                growth_signal = max(growth_signal, float(s.metrics.get(key) or 0))
            except Exception:
                pass
    if growth_signal >= 300: growth = 20
    elif growth_signal >= 100: growth = 17
    elif growth_signal >= 50: growth = 14
    elif len(event.sources) >= 3: growth = 12

    text = " ".join([event.event_title] + [s.title + " " + s.summary for s in event.sources]).lower()
    page_terms = ["code", "codes", "tier list", "wiki", "guide", "how to", "error", "not working", "download", "tracker", "calculator", "build", "location", "boss", "攻略", "下载", "错误", "代码"]
    hits = sum(1 for x in page_terms if x in text)
    expandability = min(15, 5 + hits * 3)

    site_fit, matched_site = _existing_site_fit(event, cfg)
    if matched_site:
        event.signals["matched_existing_site"] = matched_site

    monetization = 7
    if any(x in text for x in ["download", "tool", "tracker", "calculator", "wiki", "guide", "攻略", "下载"]):
        monetization = 10
    elif cat in {"sale_roundup", "freebie_roundup"}:
        monetization = 4

    # SERP opportunity cannot be known here. Reserve 10/20 neutral points and force validation.
    serp_placeholder = 10
    components = {
        "search_intent": search_intent,
        "demand_growth": growth,
        "serp_opportunity_placeholder": serp_placeholder,
        "page_expandability": expandability,
        "existing_site_fit": site_fit,
        "monetization_potential": monetization,
    }
    reasons = ["Preliminary score only: SERP/keyword data has not been validated."]
    if matched_site:
        reasons.append(f"Matches existing site: {matched_site}")
    return ScoreBreakdown(total=min(100, sum(components.values())), components=components, reasons=reasons, confidence="low")
