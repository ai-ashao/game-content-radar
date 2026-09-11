from __future__ import annotations

from typing import Any

from game_content_radar.models import EventCluster


STRONG_CLAIM_TERMS = [
    "史低", "新史低", "永久免费", "免费", "销量", "好评率", "愿望单", "历史峰值",
    "首曝", "首次", "全球第一", "国区最低", "暴涨", "%",
]


def collect_evidence(event: EventCluster) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for source in event.sources:
        for key, value in source.metrics.items():
            if value in (None, "", False):
                continue
            if key in {
                "discount_percent", "original_price_minor", "final_price_minor", "currency",
                "free_until", "player_count", "previous_players_24h", "growth_24h_percent",
                "previous_players_7d", "growth_7d_percent", "review_percent", "wishlist_count",
                "sales_count", "historical_low_verified",
            }:
                evidence.append({
                    "claim_type": key,
                    "value": value,
                    "source": source.source,
                    "source_url": source.source_url,
                    "confidence": "high" if source.source_type == "official" else "medium",
                })
    for key, value in event.signals.items():
        if key in {"deal_count", "free_count", "min_price", "max_discount", "historical_low_verified_count"} and value is not None:
            evidence.append({
                "claim_type": key,
                "value": value,
                "source": "derived",
                "source_url": "",
                "confidence": "high",
            })
    return evidence


def can_claim_historical_low(event: EventCluster) -> bool:
    if event.signals.get("historical_low_verified_count", 0):
        return True
    return any(bool(s.metrics.get("historical_low_verified")) for s in event.sources)


def validate_title(title: str, event: EventCluster) -> tuple[bool, list[str]]:
    issues: list[str] = []
    if ("史低" in title or "新史低" in title) and not can_claim_historical_low(event):
        issues.append("Title uses 史低/新史低 without verified historical-low evidence.")
    if "%" in title:
        has_percent = any(
            any(k in s.metrics for k in ["growth_24h_percent", "growth_7d_percent", "discount_percent", "review_percent"])
            for s in event.sources
        ) or event.signals.get("max_discount") is not None
        if not has_percent:
            issues.append("Title contains a percentage without a source-backed percentage metric.")
    if "免费" in title and event.category not in {"free_game", "freebie_roundup"}:
        has_free = any(s.metrics.get("discount_price_minor") == 0 for s in event.sources)
        if not has_free:
            issues.append("Title claims free without a verified free-game signal.")
    return not issues, issues
