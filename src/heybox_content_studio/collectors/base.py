from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from heybox_content_studio.models import SourceItem


@dataclass(slots=True)
class CollectorResult:
    source: str
    items: list[SourceItem] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class Collector(Protocol):
    name: str

    def collect(self) -> CollectorResult: ...
