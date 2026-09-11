from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET

from game_content_radar.collectors.base import CollectorResult
from game_content_radar.http import HttpClient
from game_content_radar.models import SourceItem


class GenericRSSCollector:
    name = "official_rss"

    def __init__(self, http: HttpClient, urls: list[str]) -> None:
        self.http = http
        self.urls = urls

    def collect(self) -> CollectorResult:
        result = CollectorResult(source=self.name)
        for url in self.urls:
            try:
                text = self.http.get_text(url)
                root = ET.fromstring(text)
                rows = root.findall(".//item")
                if rows:
                    for row in rows[:30]:
                        title = (row.findtext("title") or "").strip()
                        link = (row.findtext("link") or "").strip()
                        summary = re.sub(r"<[^>]+>", " ", row.findtext("description") or "")
                        iid = hashlib.sha1((link or title).encode()).hexdigest()[:16]
                        result.items.append(SourceItem(
                            id=f"rss-{iid}", source=self.name, source_url=link or url,
                            source_type="official", game_name="", title=title,
                            summary=re.sub(r"\s+", " ", summary).strip()[:700],
                            published_at=row.findtext("pubDate"), category="other",
                        ))
                    continue
                ns = {"a": "http://www.w3.org/2005/Atom"}
                for entry in root.findall(".//a:entry", ns)[:30]:
                    title = (entry.findtext("a:title", default="", namespaces=ns) or "").strip()
                    link_el = entry.find("a:link", ns)
                    link = link_el.attrib.get("href", "") if link_el is not None else ""
                    summary = entry.findtext("a:summary", default="", namespaces=ns) or ""
                    iid = hashlib.sha1((link or title).encode()).hexdigest()[:16]
                    result.items.append(SourceItem(
                        id=f"rss-{iid}", source=self.name, source_url=link or url,
                        source_type="official", game_name="", title=title,
                        summary=re.sub(r"<[^>]+>", " ", summary)[:700],
                        published_at=entry.findtext("a:updated", default=None, namespaces=ns),
                        category="other",
                    ))
            except Exception as exc:
                result.warnings.append(f"RSS source failed {url}: {exc}")
        return result
