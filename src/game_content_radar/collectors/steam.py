from __future__ import annotations

import hashlib
import html
import re
from datetime import datetime, timezone
from typing import Iterable

from game_content_radar.collectors.base import CollectorResult
from game_content_radar.http import HttpClient
from game_content_radar.models import SourceItem


def _id(prefix: str, value: str) -> str:
    return prefix + "-" + hashlib.sha1(value.encode("utf-8", "ignore")).hexdigest()[:16]


def _clean(text: str) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    return re.sub(r"\s+", " ", text).strip()


class SteamStoreCollector:
    """Collect broad store signals from Steam's public featured-categories endpoint.

    This source is useful for current specials/top sellers/new releases. It does NOT
    prove that a discount is an all-time historical low.
    """

    name = "steam_store"

    def __init__(self, http: HttpClient, country: str = "CN", language: str = "schinese") -> None:
        self.http = http
        self.country = country
        self.language = language

    def collect(self) -> CollectorResult:
        url = "https://store.steampowered.com/api/featuredcategories"
        data = self.http.get_json(url, params={"cc": self.country, "l": self.language})
        by_app: dict[int, SourceItem] = {}

        def merge_rows(rows: Iterable[dict], category: str, bucket: str) -> None:
            for row in rows or []:
                try:
                    appid = int(row.get("id"))
                except Exception:
                    continue
                name = str(row.get("name") or appid)
                item = by_app.get(appid)
                if item is None:
                    item = SourceItem(
                        id=_id("steam", str(appid)),
                        source=self.name,
                        source_url=f"https://store.steampowered.com/app/{appid}/",
                        source_type="official",
                        game_name=name,
                        title=name,
                        summary=f"Steam storefront signal: {name}",
                        category=category,
                        metrics={"appid": appid, "buckets": []},
                        media_urls=[],
                    )
                    by_app[appid] = item
                buckets = item.metrics.setdefault("buckets", [])
                if bucket not in buckets:
                    buckets.append(bucket)
                if bucket == "specials":
                    discount = int(row.get("discount_percent") or 0)
                    item.category = "sale"
                    item.metrics.update({
                        "discount_percent": discount,
                        "original_price_minor": row.get("original_price"),
                        "final_price_minor": row.get("final_price"),
                        "currency": row.get("currency"),
                        "historical_low_verified": False,
                    })
                    item.summary = f"Steam current discount snapshot: {name}, discount {discount}%"
                elif bucket == "top_sellers":
                    item.metrics["top_seller"] = True
                    if item.category not in {"sale", "release"}:
                        item.category = "community_trend"
                elif bucket == "new_releases":
                    item.metrics["new_release"] = True
                    if item.category != "sale":
                        item.category = "release"
                for image in [row.get("large_capsule_image"), row.get("small_capsule_image"), row.get("header_image")]:
                    if image and image not in item.media_urls:
                        item.media_urls.append(str(image))

        merge_rows((data.get("specials") or {}).get("items", []), "sale", "specials")
        merge_rows((data.get("top_sellers") or {}).get("items", []), "community_trend", "top_sellers")
        merge_rows((data.get("new_releases") or {}).get("items", []), "release", "new_releases")
        return CollectorResult(source=self.name, items=list(by_app.values()))



class SteamNewsCollector:
    name = "steam_news"

    def __init__(self, http: HttpClient, watched_apps: dict[int, str], count_per_app: int = 5) -> None:
        self.http = http
        self.watched_apps = watched_apps
        self.count_per_app = count_per_app

    @staticmethod
    def _category(title: str, contents: str) -> str:
        text = (title + " " + contents).lower()
        if any(k in text for k in ["major update", "update", "patch", "season", "version"]):
            return "major_update"
        if any(k in text for k in ["dlc", "expansion"]):
            return "major_update"
        if any(k in text for k in ["release", "launched", "available now"]):
            return "release"
        if any(k in text for k in ["sale", "discount", "weekend"]):
            return "sale"
        return "other"

    def collect(self) -> CollectorResult:
        result = CollectorResult(source=self.name)
        for appid, game_name in self.watched_apps.items():
            try:
                url = "https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/"
                data = self.http.get_json(
                    url,
                    params={"appid": appid, "count": self.count_per_app, "maxlength": 1500, "format": "json"},
                )
                for row in ((data.get("appnews") or {}).get("newsitems") or []):
                    title = _clean(str(row.get("title") or ""))
                    contents = _clean(str(row.get("contents") or ""))
                    if not title:
                        continue
                    ts = row.get("date")
                    published = None
                    if isinstance(ts, (int, float)):
                        published = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
                    source_url = str(row.get("url") or f"https://store.steampowered.com/news/app/{appid}")
                    result.items.append(
                        SourceItem(
                            id=_id("steamnews", str(row.get("gid") or source_url)),
                            source=self.name,
                            source_url=source_url,
                            source_type="official",
                            game_name=game_name,
                            title=title,
                            summary=contents[:700],
                            published_at=published,
                            category=self._category(title, contents),
                            metrics={"appid": appid, "feedname": row.get("feedname")},
                            raw_text=contents,
                        )
                    )
            except Exception as exc:
                result.warnings.append(f"Steam news failed for app {appid} ({game_name}): {exc}")
        return result


class SteamCurrentPlayersClient:
    """Official current-player snapshot client used with local history."""

    def __init__(self, http: HttpClient) -> None:
        self.http = http

    def current_players(self, appid: int) -> int | None:
        # Steamworks currently documents the partner.steam-api.com route. The
        # long-standing public api.steampowered.com route is retained as fallback
        # because deployment environments can differ.
        urls = [
            "https://partner.steam-api.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/",
            "https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/",
        ]
        last_error: Exception | None = None
        for url in urls:
            try:
                data = self.http.get_json(url, params={"appid": appid, "format": "json"})
                response = data.get("response") or {}
                if int(response.get("result") or 0) != 1:
                    continue
                value = response.get("player_count")
                return int(value) if value is not None else None
            except Exception as exc:
                last_error = exc
        if last_error:
            raise last_error
        return None
