from __future__ import annotations

import hashlib
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from heybox_content_studio.collectors.base import CollectorResult
from heybox_content_studio.http import HttpClient
from heybox_content_studio.models import SourceItem


class XiaoheihePublicCollector:
    """Best-effort scraper for public web pages only.

    It intentionally avoids authenticated/private APIs. This source is optional and
    must never make the daily pipeline fail.
    """

    name = "xiaoheihe"
    HOME = "https://www.xiaoheihe.cn/app/bbs/home"

    def __init__(self, http: HttpClient) -> None:
        self.http = http

    def collect(self) -> CollectorResult:
        result = CollectorResult(source=self.name)
        try:
            html = self.http.get_text(self.HOME)
            soup = BeautifulSoup(html, "html.parser")
            seen: set[str] = set()
            for a in soup.find_all("a", href=True):
                href = str(a.get("href"))
                if "/app/bbs/link/" not in href:
                    continue
                url = urljoin(self.HOME, href)
                if url in seen:
                    continue
                seen.add(url)
                title = " ".join(a.stripped_strings)
                if len(title) < 4:
                    continue
                iid = hashlib.sha1(url.encode()).hexdigest()[:16]
                result.items.append(SourceItem(
                    id=f"xhh-{iid}", source=self.name, source_url=url,
                    source_type="community", game_name="", title=title[:220],
                    summary=title[:700], category="community_trend", language="zh-CN",
                ))
            if not result.items:
                result.warnings.append("Xiaoheihe public HTML returned no parsable feed items; source treated as unavailable.")
        except Exception as exc:
            result.warnings.append(f"Xiaoheihe public web source unavailable: {exc}")
        return result
