from __future__ import annotations

import json
import shlex
import subprocess
from typing import Any

from game_content_radar.evidence import collect_evidence, validate_title
from game_content_radar.models import DraftPackage, EventCluster, TitleCandidate
from game_content_radar.writer import build_draft


class ExternalCommandDraftProvider:
    """Optional adapter for a local/CLI LLM.

    The command receives a JSON prompt envelope on stdin and must return JSON with:
    selected_title, title_candidates, body_markdown, comment_hook, media_plan.
    If it fails or returns unsafe/unparseable output, the deterministic writer is used.
    """

    def __init__(self, command: str, timeout_seconds: int = 180) -> None:
        self.command = command
        self.timeout_seconds = timeout_seconds

    def build(self, event: EventCluster) -> DraftPackage:
        fallback = build_draft(event)
        if not self.command.strip():
            return fallback
        envelope = {
            "task": "Write a Xiaoheihe-native Chinese game post from evidence only. Never invent facts.",
            "event": event.to_dict(),
            "evidence": collect_evidence(event),
            "rules": {
                "title_candidates": 5,
                "avoid_ai_cliches": ["值得注意的是", "此外", "与此同时", "综上所述", "总的来说"],
                "must_not_claim_historical_low_without_evidence": True,
                "must_include_comment_hook": True,
                "must_keep_source_grounding": True,
            },
        }
        try:
            proc = subprocess.run(
                shlex.split(self.command),
                input=json.dumps(envelope, ensure_ascii=False),
                text=True,
                capture_output=True,
                timeout=self.timeout_seconds,
                check=True,
            )
            data: dict[str, Any] = json.loads(proc.stdout)
            selected = str(data.get("selected_title") or "")
            ok, _ = validate_title(selected, event)
            if not selected or not ok:
                return fallback
            raw_titles = data.get("title_candidates") or []
            titles: list[TitleCandidate] = []
            for row in raw_titles[:5]:
                if isinstance(row, str):
                    title = row
                    style = "llm"
                    hook = ""
                else:
                    title = str(row.get("title") or "")
                    style = str(row.get("style") or "llm")
                    hook = str(row.get("hook") or "")
                valid, _ = validate_title(title, event)
                if title and valid:
                    titles.append(TitleCandidate(title=title, style=style, hook=hook, score=90))
            if not titles:
                titles = fallback.title_candidates
            return DraftPackage(
                selected_title=selected,
                title_candidates=titles,
                body_markdown=str(data.get("body_markdown") or fallback.body_markdown),
                comment_hook=str(data.get("comment_hook") or fallback.comment_hook),
                media_plan=data.get("media_plan") or fallback.media_plan,
                evidence=collect_evidence(event),
            )
        except Exception:
            return fallback
