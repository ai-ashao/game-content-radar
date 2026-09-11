from __future__ import annotations

import hashlib
from collections import Counter
from typing import Iterable

from game_content_radar.config import RadarConfig
from game_content_radar.models import EventCluster, SourceItem


def _minor_to_major(value: object) -> float | None:
    try:
        return round(int(value) / 100, 2)
    except Exception:
        return None


def build_sale_roundup(items: Iterable[SourceItem], cfg: RadarConfig) -> EventCluster | None:
    deals = []
    for item in items:
        if item.source != "steam_store" or item.category != "sale":
            continue
        discount = int(item.metrics.get("discount_percent") or 0)
        if discount < cfg.sale_roundup_min_discount:
            continue
        deals.append(item)
    if len(deals) < cfg.sale_roundup_min_items:
        return None

    deals.sort(key=lambda x: (int(x.metrics.get("discount_percent") or 0), -(int(x.metrics.get("final_price_minor") or 10**12))), reverse=True)
    currencies = Counter(str(x.metrics.get("currency") or "") for x in deals)
    currency = currencies.most_common(1)[0][0] if currencies else ""
    prices = [_minor_to_major(x.metrics.get("final_price_minor")) for x in deals]
    prices = [p for p in prices if p is not None]
    verified_low_count = sum(bool(x.metrics.get("historical_low_verified")) for x in deals)
    digest = hashlib.sha1("|".join(sorted(x.id for x in deals)).encode()).hexdigest()[:16]
    return EventCluster(
        event_id=f"roundup-sale-{digest}",
        event_title=f"Steam {len(deals)} 款高折扣游戏",
        game_name="Steam",
        category="sale_roundup",
        sources=deals,
        signals={
            "deal_count": len(deals),
            "min_price": min(prices) if prices else None,
            "currency": currency,
            "max_discount": max(int(x.metrics.get("discount_percent") or 0) for x in deals),
            "historical_low_verified_count": verified_low_count,
            "source_count": len(deals),
            "source_names": ["steam_store"],
        },
    )


def build_freebie_roundup(items: Iterable[SourceItem]) -> EventCluster | None:
    freebies = [x for x in items if x.category == "free_game"]
    if len(freebies) < 2:
        return None
    digest = hashlib.sha1("|".join(sorted(x.id for x in freebies)).encode()).hexdigest()[:16]
    deadlines = [x.metrics.get("free_until") for x in freebies if x.metrics.get("free_until")]
    names = sorted(set(x.source for x in freebies))
    label_map = {"epic": "Epic", "steam_store": "Steam"}
    platform_label = " / ".join(label_map.get(x, x) for x in names)
    return EventCluster(
        event_id=f"roundup-free-{digest}",
        event_title=f"{platform_label} 本期 {len(freebies)} 款免费游戏可领取",
        game_name=platform_label,
        category="freebie_roundup",
        sources=freebies,
        signals={
            "free_count": len(freebies),
            "deadlines": sorted(set(str(x) for x in deadlines)),
            "platform_label": platform_label,
            "source_count": len(freebies),
            "source_names": names,
        },
    )
