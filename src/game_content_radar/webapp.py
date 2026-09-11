from __future__ import annotations

import json
import re
import threading
import uuid
import webbrowser
from collections import Counter
from datetime import datetime
from importlib.resources import files
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from game_content_radar.config import load_config
from game_content_radar.pipeline import run_daily

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DRAFT_SLUGS = {"reach-pick", "value-pick", "alternative"}
_WEB_VERSION = "0.3.0"


class RunRequest(BaseModel):
    mode: str = Field(default="live", pattern="^(live|fixture|offline)$")
    config: str | None = None
    date: str | None = None
    fixture: str | None = None


class DraftSaveRequest(BaseModel):
    title: str = ""
    body_markdown: str = ""
    comment_hook: str = ""


def _safe_date(value: str) -> str:
    if not _DATE_RE.fullmatch(value):
        raise HTTPException(status_code=400, detail="Date must use YYYY-MM-DD")
    return value


def _resolve_under_root(root: Path, value: str) -> Path:
    candidate = (root / value).resolve() if not Path(value).is_absolute() else Path(value).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Path must stay inside project root") from exc
    return candidate


def _read_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def _event_card(event: dict[str, Any] | None) -> dict[str, Any] | None:
    if not event:
        return None
    xhh = event.get("xhh_score") or {}
    site = event.get("site_score") or {}
    sources = event.get("sources") or []
    return {
        "event_id": event.get("event_id"),
        "event_title": event.get("event_title") or "Untitled event",
        "game_name": event.get("game_name") or "-",
        "category": event.get("category") or "other",
        "xhh_score": xhh.get("total", 0),
        "site_score": site.get("total", 0),
        "xhh_reasons": xhh.get("reasons") or [],
        "site_reasons": site.get("reasons") or [],
        "source_urls": list(dict.fromkeys(s.get("source_url") for s in sources if s.get("source_url"))),
        "source_names": list(dict.fromkeys(s.get("source") for s in sources if s.get("source"))),
        "needs_serp_validation": bool(event.get("needs_serp_validation", True)),
    }


def _warnings_from_markdown(path: Path) -> list[str]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    warnings: list[str] = []
    in_section = False
    for line in lines:
        if line.strip() == "## Warnings":
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if in_section and line.lstrip().startswith("- "):
            warnings.append(line.strip()[2:].strip())
    return warnings


def _select_cards_from_events(
    events: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None]:
    if not events:
        return None, None, None
    ranked = sorted(events, key=lambda e: ((e.get("xhh_score") or {}).get("total", 0)), reverse=True)
    reach_categories = {
        "sale_roundup",
        "freebie_roundup",
        "player_spike_story",
        "major_update",
        "controversy",
        "release",
        "community_trend",
        "free_game",
    }
    value_categories = {
        "guide",
        "troubleshooting",
        "game_analysis",
        "player_spike_story",
        "major_update",
        "controversy",
        "reputation_shift",
    }
    reach = next(
        (
            e
            for e in ranked
            if e.get("category") in reach_categories and ((e.get("xhh_score") or {}).get("total", 0)) >= 60
        ),
        ranked[0],
    )
    value = next(
        (
            e
            for e in ranked
            if e.get("event_id") != reach.get("event_id")
            and e.get("category") in value_categories
            and ((e.get("xhh_score") or {}).get("total", 0)) >= 60
        ),
        None,
    )
    if value is None:
        value = next(
            (
                e
                for e in ranked
                if e.get("event_id") != reach.get("event_id")
                and ((e.get("xhh_score") or {}).get("total", 0)) >= 68
            ),
            None,
        )
    seo = max(events, key=lambda e: ((e.get("site_score") or {}).get("total", 0)))
    return reach, value, seo


def _infer_mode(warnings: list[str]) -> str:
    lowered = "\n".join(warnings).lower()
    if "fixture mode" in lowered:
        return "fixture"
    if "no-network mode" in lowered:
        return "offline"
    return "live"


def build_report_payload(report_dir: Path) -> dict[str, Any]:
    if not report_dir.exists():
        raise HTTPException(status_code=404, detail="Report not found")

    summary = _read_json(report_dir / "summary.json", {})
    events = _read_json(report_dir / "events.json", [])
    candidates = _read_json(report_dir / "candidates.json", [])
    raw_items = _read_json(report_dir / "raw-items.json", [])
    warnings = list(summary.get("warnings") or [])
    if not warnings:
        warnings = _warnings_from_markdown(report_dir / "daily-radar.md")

    if not summary:
        a_tier = sum(1 for e in events if ((e.get("xhh_score") or {}).get("total", 0) >= 80))
        b_tier = sum(1 for e in events if 65 <= ((e.get("xhh_score") or {}).get("total", 0)) < 80)
        summary = {
            "date": report_dir.name,
            "stats": {
                "raw_items": len(raw_items),
                "events": len(events),
                "a_tier": a_tier,
                "b_tier": b_tier,
            },
            "warnings": warnings,
        }

    source_counts = Counter(str(item.get("source") or "unknown") for item in raw_items)
    candidate_cards = [_event_card(e) for e in candidates]

    drafts: dict[str, Any] = {}
    for slug in sorted(_DRAFT_SLUGS):
        package = _read_json(report_dir / "xhh" / f"draft-package-{slug}.json", None)
        if package:
            drafts[slug] = package

    seo_markdown = ""
    seo_path = report_dir / "seo" / "opportunities.md"
    if seo_path.exists():
        seo_markdown = seo_path.read_text(encoding="utf-8")

    reach_event = summary.get("reach_pick")
    value_event = summary.get("value_pick")
    seo_event = summary.get("seo_pick")
    if not any((reach_event, value_event, seo_event)):
        reach_event, value_event, seo_event = _select_cards_from_events(events)

    return {
        "date": summary.get("date") or report_dir.name,
        "mode": summary.get("mode") or _infer_mode(warnings),
        "stats": summary.get("stats") or {},
        "warnings": warnings,
        "source_counts": dict(source_counts.most_common()),
        "reach_pick": _event_card(reach_event),
        "value_pick": _event_card(value_event),
        "seo_pick": _event_card(seo_event),
        "candidates": candidate_cards,
        "drafts": drafts,
        "seo_markdown": seo_markdown,
    }


def create_app(base_dir: str | Path = ".", default_config: str = "config/codex.yaml") -> FastAPI:
    root = Path(base_dir).resolve()
    state: dict[str, dict[str, Any]] = {}
    state_lock = threading.Lock()

    app = FastAPI(title="Game Content Radar", version=_WEB_VERSION)
    app.state.base_dir = root
    app.state.default_config = default_config
    app.state.started_at = datetime.now().isoformat(timespec="seconds")

    def config_path(config_value: str | None) -> Path:
        return _resolve_under_root(root, config_value or default_config)

    def report_root_for(config_value: str | None) -> Path:
        cfg = load_config(config_path(config_value))
        return _resolve_under_root(root, cfg.report_root)

    @app.get("/", response_class=HTMLResponse)
    def index() -> HTMLResponse:
        html = files("game_content_radar").joinpath("web_ui/index.html").read_text(encoding="utf-8")
        return HTMLResponse(html)

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        with state_lock:
            active = next(
                (job for job in state.values() if job.get("status") in {"queued", "running"}),
                None,
            )
            active_job = None
            if active:
                active_job = {
                    "id": active.get("id"),
                    "status": active.get("status"),
                    "mode": active.get("mode"),
                    "started_at": active.get("started_at") or active.get("created_at"),
                }
        return {
            "ok": True,
            "status": "busy" if active_job else "ready",
            "version": _WEB_VERSION,
            "started_at": app.state.started_at,
            "active_job": active_job,
        }

    @app.get("/api/meta")
    def meta() -> dict[str, Any]:
        configs = []
        config_dir = root / "config"
        if config_dir.exists():
            configs = [str(p.relative_to(root)) for p in sorted(config_dir.glob("*.yaml"))]
        return {
            "project_root": str(root),
            "default_config": default_config,
            "configs": configs,
            "fixture_available": (root / "tests/fixtures/sample-items.json").exists(),
            "web_version": _WEB_VERSION,
        }

    @app.get("/api/reports")
    def reports(config: str | None = None) -> dict[str, Any]:
        try:
            report_root = report_root_for(config)
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not report_root.exists():
            return {"dates": []}
        dates = sorted(
            (p.name for p in report_root.iterdir() if p.is_dir() and _DATE_RE.fullmatch(p.name)),
            reverse=True,
        )
        return {"dates": dates}

    @app.get("/api/reports/{date_label}")
    def report(date_label: str, config: str | None = None) -> dict[str, Any]:
        date_label = _safe_date(date_label)
        try:
            report_root = report_root_for(config)
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return build_report_payload(report_root / date_label)

    def run_job(job_id: str, request: RunRequest) -> None:
        with state_lock:
            state[job_id]["status"] = "running"
            state[job_id]["started_at"] = datetime.now().isoformat(timespec="seconds")
        try:
            cfg_path = config_path(request.config)
            cfg = load_config(cfg_path)
            fixture: Path | None = None
            no_network = False
            if request.mode == "fixture":
                fixture = _resolve_under_root(root, request.fixture or "tests/fixtures/sample-items.json")
                if not fixture.exists():
                    raise FileNotFoundError(f"Fixture not found: {fixture}")
            elif request.mode == "offline":
                no_network = True
            result = run_daily(
                cfg,
                root,
                run_date=request.date,
                fixture=fixture,
                no_network=no_network,
            )
            payload = build_report_payload(result.report_dir)
            with state_lock:
                state[job_id].update(
                    {
                        "status": "done",
                        "finished_at": datetime.now().isoformat(timespec="seconds"),
                        "date": result.report_dir.name,
                        "report": payload,
                    }
                )
        except Exception as exc:  # fail visibly in the local dashboard
            with state_lock:
                state[job_id].update(
                    {
                        "status": "error",
                        "finished_at": datetime.now().isoformat(timespec="seconds"),
                        "error": str(exc),
                    }
                )

    @app.post("/api/run", status_code=202)
    def start_run(request: RunRequest) -> dict[str, Any]:
        if request.date:
            _safe_date(request.date)
        with state_lock:
            if any(job.get("status") in {"queued", "running"} for job in state.values()):
                raise HTTPException(status_code=409, detail="A radar run is already in progress")
            job_id = uuid.uuid4().hex[:12]
            state[job_id] = {
                "id": job_id,
                "status": "queued",
                "mode": request.mode,
                "created_at": datetime.now().isoformat(timespec="seconds"),
            }
            # Keep local process memory bounded across long-running desktop sessions.
            completed = [
                key
                for key, value in state.items()
                if key != job_id and value.get("status") in {"done", "error"}
            ]
            for key in completed[:-20]:
                state.pop(key, None)
        thread = threading.Thread(target=run_job, args=(job_id, request), daemon=True)
        thread.start()
        return state[job_id]

    @app.get("/api/jobs/{job_id}")
    def job(job_id: str) -> dict[str, Any]:
        with state_lock:
            value = state.get(job_id)
            if not value:
                raise HTTPException(status_code=404, detail="Job not found")
            return dict(value)

    @app.put("/api/drafts/{date_label}/{slug}")
    def save_draft(
        date_label: str,
        slug: str,
        request: DraftSaveRequest,
        config: str | None = None,
    ) -> dict[str, Any]:
        date_label = _safe_date(date_label)
        if slug not in _DRAFT_SLUGS:
            raise HTTPException(status_code=400, detail="Unknown draft slug")
        report_root = report_root_for(config)
        report_dir = report_root / date_label
        if not report_dir.exists():
            raise HTTPException(status_code=404, detail="Report not found")
        edited_dir = report_dir / "xhh" / "edited"
        edited_dir.mkdir(parents=True, exist_ok=True)
        path = edited_dir / f"{slug}.md"
        content = (
            f"# {request.title.strip()}\n\n"
            f"{request.body_markdown.strip()}\n\n"
            f"---\n\n**互动问题：** {request.comment_hook.strip()}\n"
        )
        path.write_text(content, encoding="utf-8")
        return {"saved": True, "path": str(path.relative_to(root))}

    return app


def serve(
    base_dir: str | Path = ".",
    default_config: str = "config/codex.yaml",
    host: str = "127.0.0.1",
    port: int = 8787,
    open_browser: bool = True,
) -> None:
    import uvicorn

    url = f"http://{host}:{port}"
    if open_browser and host in {"127.0.0.1", "localhost"}:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    uvicorn.run(create_app(base_dir, default_config), host=host, port=port, log_level="info")
