from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET

from game_content_radar.collectors.base import CollectorResult
from game_content_radar.http import HttpClient
from game_content_radar.models import SourceItem


class RedditRSSCollector:
    name = "reddit"

    def __init__(self, http: HttpClient, subreddits: list[str]) -> None:
        self.http = http
        self.subreddits = subreddits

    def collect(self) -> CollectorResult:
        result = CollectorResult(source=self.name)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        for subreddit in self.subreddits:
            url = f"https://www.reddit.com/r/{subreddit}/hot/.rss"
            try:
                xml = self.http.get_text(url)
                root = ET.fromstring(xml)
                for entry in root.findall("atom:entry", ns)[:25]:
                    title = (entry.findtext("atom:title", default="", namespaces=ns) or "").strip()
                    link_el = entry.find("atom:link", ns)
                    link = link_el.attrib.get("href", "") if link_el is not None else ""
                    published = entry.findtext("atom:updated", default=None, namespaces=ns)
                    content = entry.findtext("atom:content", default="", namespaces=ns) or ""
                    clean = re.sub(r"<[^>]+>", " ", content)
                    clean = re.sub(r"\s+", " ", clean).strip()
                    if not title:
                        continue
                    iid = hashlib.sha1((link or title).encode()).hexdigest()[:16]
                    result.items.append(
                        SourceItem(
                            id=f"reddit-{iid}",
                            source=self.name,
                            source_url=link,
                            source_type="community",
                            game_name="",
                            title=title,
                            summary=clean[:700],
                            published_at=published,
                            category="community_trend",
                            metrics={"subreddit": subreddit},
                            raw_text=clean,
                        )
                    )
            except Exception as exc:
                result.warnings.append(f"Reddit RSS failed for r/{subreddit}: {exc}")
        return result
