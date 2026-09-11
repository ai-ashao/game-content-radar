from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from game_content_radar.collectors.base import CollectorResult
from game_content_radar.http import HttpClient
from game_content_radar.models import SourceItem


class EpicFreeGamesCollector:
    name = "epic"

    def __init__(self, http: HttpClient, country: str = "CN", locale: str = "zh-CN") -> None:
        self.http = http
        self.country = country
        self.locale = locale

    @staticmethod
    def _active_free(promotions: dict) -> tuple[bool, str | None]:
        now = datetime.now(timezone.utc)
        groups = promotions.get("promotionalOffers") or []
        for group in groups:
            for offer in group.get("promotionalOffers") or []:
                try:
                    start = datetime.fromisoformat(str(offer["startDate"]).replace("Z", "+00:00"))
                    end = datetime.fromisoformat(str(offer["endDate"]).replace("Z", "+00:00"))
                except Exception:
                    continue
                discount = offer.get("discountSetting") or {}
                if start <= now <= end and int(discount.get("discountPercentage") or 0) == 0:
                    return True, end.isoformat()
        return False, None

    def collect(self) -> CollectorResult:
        result = CollectorResult(source=self.name)
        url = "https://store-site-backend-static-ipv4.ak.epicgames.com/freeGamesPromotions"
        try:
            data = self.http.get_json(
                url,
                params={"locale": self.locale, "country": self.country, "allowCountries": self.country},
            )
            elements = (((data.get("data") or {}).get("Catalog") or {}).get("searchStore") or {}).get("elements") or []
            for row in elements:
                active, end_at = self._active_free(row.get("promotions") or {})
                total = ((row.get("price") or {}).get("totalPrice") or {})
                discount_price = total.get("discountPrice")
                original_price = total.get("originalPrice")
                # Require an active promotion and a normally-paid product. This
                # avoids treating permanent free-to-play games as weekly freebies.
                if not active or discount_price != 0:
                    continue
                try:
                    if original_price is None or int(original_price) <= 0:
                        continue
                except Exception:
                    continue
                title = str(row.get("title") or "")
                slug = row.get("productSlug") or row.get("urlSlug") or ""
                page = f"https://store.epicgames.com/{self.locale}/p/{slug}" if slug else "https://store.epicgames.com/free-games"
                iid = hashlib.sha1((str(row.get("id")) + title).encode()).hexdigest()[:16]
                media = []
                for img in row.get("keyImages") or []:
                    if img.get("url"):
                        media.append(str(img["url"]))
                result.items.append(
                    SourceItem(
                        id=f"epic-{iid}",
                        source=self.name,
                        source_url=page,
                        source_type="official",
                        game_name=title,
                        title=f"Epic free game: {title}",
                        summary=str(row.get("description") or "")[:700],
                        category="free_game",
                        metrics={
                            "original_price_minor": original_price,
                            "discount_price_minor": discount_price,
                            "currency": total.get("currencyCode"),
                            "free_until": end_at,
                        },
                        media_urls=media,
                    )
                )
        except Exception as exc:
            result.warnings.append(f"Epic free-games source failed: {exc}")
        return result
