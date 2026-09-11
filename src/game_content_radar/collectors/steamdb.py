from __future__ import annotations

import hashlib
import re

from bs4 import BeautifulSoup

from game_content_radar.collectors.base import CollectorResult
from game_content_radar.http import HttpClient
from game_content_radar.models import SourceItem


class SteamDBPublicCollector:
    """Optional best-effort public HTML enrichment.

    SteamDB is deliberately NOT a hard dependency: there is no stable public API
    contract for this project to rely on. Failures are warnings only.
    """

    name = "steamdb"
    URL = "https://steamdb.info/charts/"

    def __init__(self, http: HttpClient) -> None:
        self.http = http

    def collect(self) -> CollectorResult:
        result = CollectorResult(source=self.name)
        try:
            html = self.http.get_text(self.URL)
            soup = BeautifulSoup(html, "html.parser")
            for row in soup.select("table tbody tr")[:50]:
                link = row.select_one('a[href^="/app/"]')
                if not link:
                    continue
                href = str(link.get("href") or "")
                m = re.search(r"/app/(\d+)", href)
                if not m:
                    continue
                appid = int(m.group(1))
                game = " ".join(link.stripped_strings).strip()
                cells = [" ".join(x.stripped_strings) for x in row.find_all("td")]
                iid = hashlib.sha1(f"steamdb:{appid}:{'|'.join(cells)}".encode()).hexdigest()[:16]
                result.items.append(SourceItem(
                    id=f"steamdb-{iid}", source=self.name,
                    source_url=f"https://steamdb.info/app/{appid}/charts/",
                    source_type="third_party_data", game_name=game, title=f"SteamDB chart signal: {game}",
                    summary=" | ".join(cells)[:700], category="community_trend",
                    metrics={"appid": appid, "cells": cells},
                ))
            if not result.items:
                result.warnings.append("SteamDB HTML parsed zero rows; likely layout/anti-bot change.")
        except Exception as exc:
            result.warnings.append(f"SteamDB optional enrichment unavailable: {exc}")
        return result
