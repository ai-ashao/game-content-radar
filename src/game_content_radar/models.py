from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class SourceItem:
    id: str
    source: str
    source_url: str
    source_type: str
    game_name: str
    title: str
    summary: str = ""
    published_at: str | None = None
    collected_at: str = field(default_factory=utc_now_iso)
    language: str = "en"
    category: str = "other"
    metrics: dict[str, Any] = field(default_factory=dict)
    raw_text: str = ""
    media_urls: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SourceItem":
        allowed = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in data.items() if k in allowed})


@dataclass(slots=True)
class ScoreBreakdown:
    total: int
    components: dict[str, int]
    reasons: list[str] = field(default_factory=list)
    confidence: str = "medium"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class EventCluster:
    event_id: str
    event_title: str
    game_name: str
    category: str
    sources: list[SourceItem]
    signals: dict[str, Any] = field(default_factory=dict)
    xhh_score: ScoreBreakdown | None = None
    site_score: ScoreBreakdown | None = None
    needs_serp_validation: bool = True

    @property
    def source_urls(self) -> list[str]:
        return list(dict.fromkeys(x.source_url for x in self.sources if x.source_url))

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_title": self.event_title,
            "game_name": self.game_name,
            "category": self.category,
            "sources": [s.to_dict() for s in self.sources],
            "signals": self.signals,
            "xhh_score": self.xhh_score.to_dict() if self.xhh_score else None,
            "site_score": self.site_score.to_dict() if self.site_score else None,
            "needs_serp_validation": self.needs_serp_validation,
        }


@dataclass(slots=True)
class TitleCandidate:
    title: str
    style: str
    hook: str
    evidence: list[dict[str, Any]] = field(default_factory=list)
    score: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class DraftPackage:
    selected_title: str
    title_candidates: list[TitleCandidate]
    body_markdown: str
    comment_hook: str
    media_plan: dict[str, Any]
    evidence: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "selected_title": self.selected_title,
            "title_candidates": [t.to_dict() for t in self.title_candidates],
            "body_markdown": self.body_markdown,
            "comment_hook": self.comment_hook,
            "media_plan": self.media_plan,
            "evidence": self.evidence,
        }
