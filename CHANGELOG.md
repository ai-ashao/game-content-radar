# Changelog

## 0.3.0 — V1.4 Desktop-like Web UX

- Changed the macOS launcher to run the local FastAPI service in the background with `nohup`.
- Added readiness polling before opening the browser, so the dashboard only opens after the server is healthy.
- Added PID and log management under `.game-content-radar-web.pid` and `logs/web.log`.
- Added `scripts/stop-web.command` and `scripts/restart-web.command`.
- Added `/api/health` with ready/busy state and active-job metadata.
- Added real frontend health polling: green = ready, yellow = running, red = disconnected.
- Fixed the misleading state where the UI could show a green dot next to “服务异常”.
- Simplified the daily UI around a single primary action: **运行今日雷达**.
- Moved config / Fixture / Offline / date controls into collapsed advanced options.
- Renamed developer-centric labels to operator-facing Chinese labels.
- Refined the recommendation, candidate, SEO, data-source, warnings, history, and Draft review surfaces.

## 0.2.0 — V1.3 Web Dashboard

- Added a local FastAPI web dashboard as the recommended daily interface.
- Added Live / Fixture / Offline run controls with asynchronous job polling.
- Added a prominent Fixture warning so synthetic test reports cannot be mistaken for real topic signals.
- Added Reach Pick / Value Pick cards, Top Candidates, preliminary SEO candidate, source counts and warnings.
- Added a draft review drawer with title alternatives, editable body/comment hook, evidence, copy and save actions.
- Added report-history navigation and local edited-draft persistence.
- Added `game-radar web` and a macOS double-click launcher.

## 0.1.0 — V1.2

- Calibrated Xiaoheihe content model against public community samples.
- Split Xiaoheihe publish score from preliminary site/SEO opportunity score.
- Added Steam Store, Steam News, Steam current-player history, Reddit RSS, Epic free-game sources.
- Added optional Xiaoheihe and SteamDB public-web enrichers with fail-soft behavior.
- Added event clustering, sale/freebie aggregation, Reach/Value selection, title evidence guard, media plans and reports.
