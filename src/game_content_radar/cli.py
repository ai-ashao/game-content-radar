from __future__ import annotations

import argparse
from pathlib import Path

from game_content_radar.config import load_config
from game_content_radar.pipeline import run_daily


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="game-radar", description="Game content + demand radar")
    sub = parser.add_subparsers(dest="command", required=True)

    daily = sub.add_parser("daily", help="Run the daily radar pipeline")
    daily.add_argument("--config", default="config/default.yaml", help="Config YAML path")
    daily.add_argument("--root", default=".", help="Project root for reports/data")
    daily.add_argument("--date", default=None, help="Output date label YYYY-MM-DD")
    daily.add_argument("--fixture", default=None, help="Load items from JSON fixture instead of network")
    daily.add_argument("--no-network", action="store_true", help="Skip all network collectors")

    web = sub.add_parser("web", help="Open the local web dashboard")
    web.add_argument("--config", default="config/codex.yaml", help="Default config shown in the dashboard")
    web.add_argument("--root", default=".", help="Project root for reports/data")
    web.add_argument("--host", default="127.0.0.1", help="Web server host")
    web.add_argument("--port", type=int, default=8787, help="Web server port")
    web.add_argument("--no-browser", action="store_true", help="Do not open the browser automatically")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "daily":
        root = Path(args.root).resolve()
        cfg_path = Path(args.config)
        if not cfg_path.is_absolute():
            cfg_path = root / cfg_path
        cfg = load_config(cfg_path)
        fixture = Path(args.fixture).resolve() if args.fixture else None
        result = run_daily(cfg, root, run_date=args.date, fixture=fixture, no_network=args.no_network)
        print(f"Report: {result.report_dir / 'daily-radar.md'}")
        print(f"Raw items: {len(result.raw_items)} | Events: {len(result.events)} | Warnings: {len(result.warnings)}")
        if result.reach_pick:
            print(f"Reach: {result.reach_pick.event_title} ({result.reach_pick.xhh_score.total})")
        if result.value_pick:
            print(f"Value: {result.value_pick.event_title} ({result.value_pick.xhh_score.total})")
        return 0
    if args.command == "web":
        from game_content_radar.webapp import serve

        serve(
            base_dir=Path(args.root).resolve(),
            default_config=args.config,
            host=args.host,
            port=args.port,
            open_browser=not args.no_browser,
        )
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
