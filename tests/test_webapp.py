from pathlib import Path

import pytest
from fastapi import HTTPException

from game_content_radar.config import load_config
from game_content_radar.pipeline import run_daily
from game_content_radar.webapp import _resolve_under_root, build_report_payload, create_app


def test_resolve_under_root_rejects_parent_path(tmp_path: Path) -> None:
    with pytest.raises(HTTPException, match="Path must stay inside project root"):
        _resolve_under_root(tmp_path, "../outside")


def test_web_payload_from_fixture(tmp_path: Path) -> None:
    cfg = load_config(Path("config/default.yaml"))
    fixture = Path("tests/fixtures/sample-items.json").resolve()
    result = run_daily(cfg, tmp_path, run_date="2026-09-11", fixture=fixture)

    payload = build_report_payload(result.report_dir)

    assert payload["date"] == "2026-09-11"
    assert payload["mode"] == "fixture"
    assert payload["stats"]["raw_items"] == len(result.raw_items)
    assert payload["stats"]["events"] == len(result.events)
    assert payload["reach_pick"] is not None
    assert payload["seo_pick"] is not None
    assert payload["candidates"]
    assert payload["warnings"]


def test_health_endpoint_reports_ready(tmp_path: Path) -> None:
    app = create_app(tmp_path)
    route = next(route for route in app.routes if getattr(route, "path", None) == "/api/health")
    payload = route.endpoint()

    assert payload["ok"] is True
    assert payload["status"] == "ready"
    assert payload["version"] == "0.3.0"
    assert payload["active_job"] is None
