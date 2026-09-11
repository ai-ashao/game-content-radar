# game-content-radar

**Game Demand Radar + Xiaoheihe Content Engine + Preliminary SEO Opportunity Radar**

V1.3 adds a local browser dashboard on top of the evidence-first radar pipeline. The web UI is now the recommended daily interface; the CLI remains available for automation and debugging.

The core workflow stays the same:

```text
public game signals
→ normalize / cluster / aggregate
→ Xiaoheihe Publish Score
→ Reach Pick + Value Pick
→ Chinese Draft + Media Plan
→ preliminary SEO / game-site opportunity queue
→ human review
```

## Recommended: Web dashboard

Install once:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Then start the dashboard:

```bash
game-radar web --config config/codex.yaml
```

The browser opens automatically at:

```text
http://127.0.0.1:8787
```

The dashboard provides:

- one-click **Live / Fixture / Offline** runs;
- an explicit banner showing whether the report is real or synthetic fixture data;
- Raw Items, Events + Roundups, A-tier, B-tier and Warning counts;
- **Reach Pick** and **Value Pick** cards;
- Top Candidates with independent XHH and preliminary Site scores;
- best SEO / game-site validation candidate;
- source counts and source/warning visibility;
- Draft drawer with title candidates, body, comment hook and evidence;
- copy-ready Xiaoheihe text;
- editable drafts saved under `reports/YYYY-MM-DD/xhh/edited/`;
- report history by date.

### macOS: double-click launcher

After cloning the repository, you can double-click:

```text
scripts/start-web.command
```

It creates `.venv` and installs the project automatically on first launch, then opens the dashboard. If macOS blocks execution the first time, run `chmod +x scripts/start-web.command` once.

## Important: Fixture is not live data

The included fixture exists only to verify the pipeline and UI deterministically. A report containing a warning such as:

```text
Fixture mode: loaded ... synthetic/offline items ...
```

must not be used for actual Xiaoheihe topic selection. The dashboard highlights Fixture reports prominently to prevent this mistake.

## Live run

From the web UI choose:

```text
Mode: Live · 真实网络
Config: config/codex.yaml
```

and click **运行今日雷达**.

You can still run the same pipeline from the CLI:

```bash
game-radar daily --config config/codex.yaml
```

A single source failure does not stop the pipeline. Failures appear in the dashboard Warnings panel and in `daily-radar.md`.

## Development

```bash
pip install -e '.[dev]'
pytest
```

## Configure watched Steam games

Edit `config/default.yaml` or `config/codex.yaml`:

```yaml
collection:
  watched_apps:
    730: Counter-Strike 2
    570: Dota 2
```

Watched games are used for Steam news and current-player history. Broad Steam store signals are collected separately.

## Source-contract note

Steam News and current-player collection use Steam Web API routes. The Steam storefront featured-categories endpoint and Epic free-games storefront feed are public endpoints used for discovery, but they should still be treated as changeable storefront contracts. Every collector is fail-soft and isolated for this reason.

## SteamDB design decision

SteamDB is useful, but the radar does not rely on it as a hard data dependency. The default implementation computes player-growth signals from Steam current-player snapshots stored in local SQLite. Optional SteamDB public-HTML enrichment exists, but is disabled by default.

## Historical-low guard

Current Steam sale data does **not** prove an all-time historical low. The system will not generate “史低/新史低” titles unless `historical_low_verified` evidence is present.

## Preliminary SEO/site score

The site score is a discovery score, not a build decision. It does not contain Semrush volume/KD or full Google SERP competitor strength, so every candidate remains a validation queue item.

```text
Radar signal
→ Semrush keyword graph
→ Google SERP manual validation
→ existing-site vs new-site decision
```

## Optional Xiaoheihe source

The public-web Xiaoheihe collector is disabled by default:

```yaml
sources:
  xiaoheihe: true
```

It uses public web pages only. No authenticated/private API, cookies, or automatic posting are implemented. If the public layout changes, the source emits a warning and the rest of the run continues.

## Codex mode

`config/codex.yaml` uses Codex CLI after Python has already completed collection, scoring and evidence checks. Codex only edits the selected evidence bundle into Chinese copy. If Codex fails, the deterministic writer is used.

## What V1.3 deliberately does not do

- automatic Xiaoheihe posting;
- automatic login/cookie management;
- auto-like/comment;
- public multi-user SaaS hosting;
- account/user system;
- AI-generated images.

Human review remains the publishing gate.
