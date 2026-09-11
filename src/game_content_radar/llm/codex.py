from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from game_content_radar.evidence import collect_evidence, validate_title
from game_content_radar.models import DraftPackage, EventCluster, TitleCandidate
from game_content_radar.writer import build_draft


_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "selected_title": {"type": "string"},
        "title_candidates": {
            "type": "array",
            "minItems": 3,
            "maxItems": 5,
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "style": {"type": "string"},
                    "hook": {"type": "string"},
                },
                "required": ["title", "style", "hook"],
                "additionalProperties": False,
            },
        },
        "body_markdown": {"type": "string"},
        "comment_hook": {"type": "string"},
    },
    "required": ["selected_title", "title_candidates", "body_markdown", "comment_hook"],
    "additionalProperties": False,
}


class CodexDraftProvider:
    """Use the installed Codex CLI for evidence-grounded copy editing.

    Data collection/scoring stays deterministic. Codex is only used to turn an
    already-selected event and evidence bundle into Xiaoheihe-native Chinese copy.
    If Codex is unavailable, times out, or violates the title evidence guard, the
    deterministic writer is returned.
    """

    def __init__(self, workdir: Path, binary: str = "codex", timeout_seconds: int = 240) -> None:
        self.workdir = workdir
        self.binary = binary
        self.timeout_seconds = timeout_seconds
        self.last_warning: str | None = None

    def _prompt(self, event: EventCluster, fallback: DraftPackage) -> str:
        payload = {
            "event": event.to_dict(),
            "evidence": collect_evidence(event),
            "deterministic_draft": fallback.to_dict(),
        }
        return (
            "你是小黑盒游戏内容编辑。请把下面的事件包改写成可人工发布的简体中文草稿。\n\n"
            "硬规则：\n"
            "1. 只能使用事件包、来源摘要、metrics 和 evidence 中已有的事实；不得靠记忆补事实。\n"
            "2. 不得自行补价格、日期、玩家数、版本号、销量、好评率、愿望单、开发商关系。\n"
            "3. 未明确验证 historical_low_verified 时，不得写‘史低/新史低’。\n"
            "4. 把新闻写成玩家视角：发生什么、为什么值得关心、对谁有影响。\n"
            "5. 避免‘值得注意的是/此外/与此同时/综上所述/总的来说’等明显AI套话。\n"
            "6. 标题要有信息量，不用‘震惊/炸裂/家人们谁懂’等空情绪词。\n"
            "7. 如果证据不足以解释原因，明确说‘目前无法确认原因’，不要硬编故事。\n"
            "8. 输出3-5个标题候选；selected_title必须从中选择。\n"
            "9. 正文不包含外部新事实；来源URL由程序随后附加。\n"
            "10. 结尾给一个具体、容易回答的评论问题。\n\n"
            "返回必须符合给定 JSON Schema。\n\n"
            "事件包：\n" + json.dumps(payload, ensure_ascii=False, indent=2)
        )

    def build(self, event: EventCluster) -> DraftPackage:
        fallback = build_draft(event)
        self.last_warning = None
        if not shutil.which(self.binary):
            self.last_warning = f"Codex binary '{self.binary}' not found; deterministic draft used."
            return fallback

        with tempfile.TemporaryDirectory(prefix="game-radar-codex-") as td:
            temp = Path(td)
            schema_path = temp / "schema.json"
            output_path = temp / "result.json"
            schema_path.write_text(json.dumps(_OUTPUT_SCHEMA, ensure_ascii=False, indent=2), encoding="utf-8")
            cmd = [
                self.binary,
                "exec",
                "--ephemeral",
                "--sandbox",
                "read-only",
                "--output-schema",
                str(schema_path),
                "-o",
                str(output_path),
                "-",
            ]
            try:
                proc = subprocess.run(
                    cmd,
                    cwd=self.workdir,
                    input=self._prompt(event, fallback),
                    text=True,
                    capture_output=True,
                    timeout=self.timeout_seconds,
                    check=False,
                )
                if proc.returncode != 0 or not output_path.exists():
                    detail = (proc.stderr or proc.stdout or "unknown error")[-800:]
                    self.last_warning = f"Codex draft failed (exit {proc.returncode}); fallback used. {detail}"
                    return fallback
                data = json.loads(output_path.read_text(encoding="utf-8"))
                selected = str(data.get("selected_title") or "").strip()
                raw_titles = data.get("title_candidates") or []
                titles: list[TitleCandidate] = []
                for idx, row in enumerate(raw_titles[:5]):
                    title = str(row.get("title") or "").strip()
                    ok, _ = validate_title(title, event)
                    if title and ok:
                        titles.append(TitleCandidate(
                            title=title,
                            style=str(row.get("style") or "codex"),
                            hook=str(row.get("hook") or ""),
                            evidence=collect_evidence(event),
                            score=95 - idx * 3,
                        ))
                valid_selected, issues = validate_title(selected, event)
                candidate_titles = {t.title for t in titles}
                if not valid_selected or selected not in candidate_titles:
                    self.last_warning = f"Codex title rejected by evidence guard ({'; '.join(issues) or 'not in candidates'}); fallback used."
                    return fallback
                body = str(data.get("body_markdown") or "").strip()
                comment = str(data.get("comment_hook") or "").strip()
                if not body or not comment:
                    self.last_warning = "Codex returned incomplete draft; fallback used."
                    return fallback
                return DraftPackage(
                    selected_title=selected,
                    title_candidates=titles,
                    body_markdown=body + "\n\n## 来源核对\n" + "\n".join(f"- {s.source}: {s.source_url}" for s in event.sources if s.source_url) + "\n\n> 发布前人工检查：标题强 Claim、时间、价格、人数、版本号、免费截止时间。",
                    comment_hook=comment,
                    media_plan=fallback.media_plan,
                    evidence=collect_evidence(event),
                )
            except Exception as exc:
                self.last_warning = f"Codex draft exception; fallback used: {exc}"
                return fallback
