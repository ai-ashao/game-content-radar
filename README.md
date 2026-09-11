# game-content-radar

**Game Demand Radar + Xiaoheihe Content Engine + Preliminary SEO Opportunity Radar**

V1.2 is a CLI-first, evidence-first pipeline for game-site operators. It collects public game signals, ranks what is worth posting on Xiaoheihe, generates Chinese drafts, and separately surfaces website/SEO opportunities that still need Semrush/SERP validation.

## Why V1.2

This implementation was revised after sampling real public Xiaoheihe community posts. Two corrections matter most:

1. Xiaoheihe-native reach content includes dense Steam deal/freebie roundups and data-driven game stories, not just generic news summaries.
2. Xiaoheihe publish value and SEO/site value are different questions and therefore have different scores.

See `docs/XIAOHEIHE_RESEARCH.md` and `DEVELOPMENT_SPEC.md`.

## Install

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
pip install -e .
```

Development:

```bash
pip install -e '.[dev]'
pytest
```

## First run: offline demo

The repository includes a deterministic fixture so you can inspect output before touching live sources:

```bash
game-radar daily \
  --config config/default.yaml \
  --fixture tests/fixtures/sample-items.json \
  --date 2026-09-11
```

Then open:

```text
reports/2026-09-11/daily-radar.md
```

## Live run

```bash
game-radar daily --config config/default.yaml
```

A single source failure does not stop the pipeline. Warnings are included in `daily-radar.md`.

## Configure watched Steam games

Edit `config/default.yaml`:

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

SteamDB is useful, but V1.2 does not rely on it as a hard data dependency. The default implementation computes player-growth signals from Steam current-player snapshots stored in local SQLite. Optional SteamDB public-HTML enrichment exists, but is disabled by default.

## Historical-low guard

Current Steam sale data does **not** prove an all-time historical low. V1.2 will not generate “史低/新史低” titles unless `historical_low_verified` evidence is present.

This is intentional: a high-CTR title is not useful if the factual claim is wrong.

## Preliminary SEO/site score

The site score is a discovery score, not a build decision. It does not have Semrush volume/KD or full Google SERP strength, so every candidate remains:

```text
needs_serp_validation = true
```

The next workflow should be:

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

## Codex mode (recommended for your actual daily drafts)

The repository includes `config/codex.yaml`. After the folder is a Git repository and Codex CLI is installed/authenticated, run:

```bash
game-radar daily --config config/codex.yaml
```

The pipeline still performs collection, scoring and evidence checks in Python. Codex is used only for Chinese copy editing of the already-selected evidence bundle. It runs via non-interactive `codex exec` with a JSON output schema; if the Codex call fails, the deterministic draft is used instead.

## Optional local/CLI LLM

Default mode is deterministic and requires no AI API:

```yaml
llm:
  mode: heuristic
```

For a local/CLI LLM, set:

```yaml
llm:
  mode: command
  command: "your-command-here"
```

The command receives a JSON evidence envelope on stdin and must return JSON containing `selected_title`, `title_candidates`, `body_markdown`, `comment_hook`, and optionally `media_plan`.

If it fails or returns a title that violates the evidence guard, the deterministic writer is used.

## What V1.2 deliberately does not do

- automatic Xiaoheihe posting
- automatic login/cookie management
- auto-like/comment
- Web dashboard
- SaaS/user system
- AI-generated images

Human review remains the publishing gate.
