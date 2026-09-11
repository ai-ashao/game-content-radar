from __future__ import annotations

from typing import Protocol

from game_content_radar.models import DraftPackage, EventCluster


class DraftProvider(Protocol):
    def build(self, event: EventCluster) -> DraftPackage: ...
