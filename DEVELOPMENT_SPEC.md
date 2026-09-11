# game-content-radar V1.3 — Web Dashboard implementation spec

## 1. Goal

Build a semi-automatic game intelligence pipeline that answers three independent questions every day:

1. What is most worth publishing on Xiaoheihe today?
2. Is there a signal worth turning into a website/SEO page?
3. Is there a game worth entering a deeper game-site validation workflow?

V1.3 changes the primary user interface from CLI-first to **local web dashboard first**. The CLI remains available for automation/debugging. The tool still stops at draft generation; human review and Xiaoheihe publishing remain manual.

## 2. Core data/quality rules retained from V1.2

### 2.1 SteamDB is not a Tier-1 hard dependency

Use Steam public store/news/current-player endpoints as primary Steam signals, store current-player snapshots in local SQLite, compute 24h/7d growth when history exists, and keep SteamDB as optional best-effort enrichment.

### 2.2 Site score remains PRE-SERP

The radar does not contain Semrush volume/KD or a full Google competitor set. The site score is therefore **Preliminary Site Opportunity Score** and every candidate keeps `needs_serp_validation=true`.

### 2.3 “史低” remains evidence-gated

Current Steam discount data does not prove an all-time historical low. Do not write 史低/新史低 unless evidence explicitly verifies it.

### 2.4 Xiaoheihe remains optional public-web enrichment

No login/cookie automation, private API dependency, or auto-posting. A Xiaoheihe collector failure must only emit a warning.

### 2.5 Drafting remains deterministic-first

AI improves language, not data integrity. Keep deterministic fallback, optional Codex structured-output drafting, title evidence validation, and human review.

## 3. Primary source stack

Tier 1:

- Steam Store public storefront signals
- Steam News for configured watched app IDs
- Steam current-player counts + local history
- Reddit public RSS
- Epic free-game promotion storefront feed

Tier 2 / optional:

- official RSS feeds
- Xiaoheihe public web feed
- SteamDB public HTML enrichment

All collectors are fail-soft.

## 4. Event model

Raw source items are normalized into source URL/type, game name, title/summary, timestamps, category, metrics and media URLs. Exact duplicates are removed and related signals are clustered into an `EventCluster`.

Synthetic roundup events may be added after clustering, so **event count can be larger than raw-item count**. The web UI must label this clearly as `Events + Roundups`, not imply a one-to-one conversion.

## 5. Content types

Supported categories include:

- `sale_roundup`
- `freebie_roundup`
- `player_spike_story`
- `major_update`
- `release`
- `sale`
- `free_game`
- `controversy`
- `guide`
- `troubleshooting`
- `community_trend`
- `other`

## 6. Xiaoheihe Publish Score (100)

- Xiaoheihe audience fit: 20
- Freshness: 15
- Utility density: 15
- Hook/story strength: 15
- Discussion potential: 10
- Evidence strength: 10
- Audience breadth: 10
- Source confidence: 5

This score answers “worth publishing on Xiaoheihe?”, not “worth building an SEO page?”.

## 7. Preliminary Site Opportunity Score

Components:

- Search intent: 25
- Demand growth: 20
- SERP placeholder: 10 of eventual 20
- Page expandability: 15
- Existing-site fit: 10
- Monetization potential: 10

Every event is queued for later external SERP validation if it becomes a build candidate.

## 8. Reach / Value picks

Target two distinct daily recommendations:

- **Reach Pick** — broad, urgent, useful, high-distribution content
- **Value Pick** — analysis, problem solving, player-spike story, update interpretation, troubleshooting, or deeper player value

The second pick may be absent if it does not meet quality thresholds.

## 9. Draft output

Each selected draft contains:

- selected title
- >=5 title candidates when possible
- evidence-first body
- player-facing comment hook
- source/evidence bundle
- media plan

Drafts remain editable by the human operator before publication.

## 10. Web dashboard — primary interface

V1.3 adds a local FastAPI dashboard served from the same Python package.

Start with:

```bash
game-radar web --config config/codex.yaml
```

Default URL:

```text
http://127.0.0.1:8787
```

### 10.1 Run controls

The UI must expose three explicit run modes:

- **Live** — execute real network collectors
- **Fixture** — deterministic synthetic/offline test data
- **Offline** — no network collectors

The run must execute in a background thread/job so Codex/network work does not freeze the HTTP request. The browser polls job status until completion/failure.

### 10.2 Fixture safety banner

Fixture reports must show a prominent warning:

> This is synthetic test data and must not be used for real Xiaoheihe topic decisions.

This is required because fixture output can look plausible and score normally.

### 10.3 Dashboard summary

Show:

- Raw Items
- Events + Roundups
- XHH A-tier count
- XHH B-tier count
- Warning count
- report date
- run mode

### 10.4 Main decision surface

Show Reach Pick and Value Pick as primary cards with:

- event title
- game
- category
- XHH score
- preliminary Site score
- score reasons
- source names
- Draft action

### 10.5 Candidate table

Show Top Candidates with independent columns for:

- rank
- event
- category
- XHH score
- Site(pre) score
- source set

Do not merge the two scores into one “overall” score.

### 10.6 SEO panel

Show the best preliminary SEO/site validation candidate separately and repeat that it is PRE-SERP only.

### 10.7 Source/warning visibility

The operator must see:

- source item counts
- source failures
- fixture/offline mode warnings
- collection/parsing errors

A report with warnings can still be useful, but the UI must not hide them.

### 10.8 Draft review drawer

Opening a Draft must show:

- selected title
- title alternatives
- editable body
- editable comment hook
- evidence/source details
- Copy publish text
- Save edited draft

Saved human edits are written to:

```text
reports/YYYY-MM-DD/xhh/edited/<slug>.md
```

The generated source package remains unchanged for auditability.

### 10.9 Report history

The UI lists prior `reports/YYYY-MM-DD/` directories and lets the user switch between dates.

## 11. Web API

Minimum local endpoints:

```text
GET  /
GET  /api/meta
GET  /api/reports
GET  /api/reports/{date}
POST /api/run
GET  /api/jobs/{job_id}
PUT  /api/drafts/{date}/{slug}
```

Paths supplied from the browser must remain inside the project root.

## 12. CLI compatibility

`game-radar daily` remains supported without behavior regression.

`game-radar web` is added as the recommended manual-use interface.

## 13. Output

The existing report structure remains authoritative:

```text
reports/YYYY-MM-DD/
├── daily-radar.md
├── raw-items.json
├── candidates.json
├── events.json
├── xhh/
│   ├── reach-pick.md
│   ├── value-pick.md
│   ├── alternative.md
│   ├── draft-package-*.json
│   ├── media-plan-*.json
│   └── edited/
│       └── *.md
└── seo/
    └── opportunities.md
```

The web layer reads these files instead of creating a second database or duplicate business model.

## 14. Deployment scope

V1.3 is a **single-user local web app**, not a public SaaS deployment.

Reason: the current drafting integration can depend on local Codex CLI/authentication and report files. A future public deployment should separate collector/worker execution, persistence, authentication and LLM credentials instead of exposing the local runner directly.

## 15. Non-goals

No:

- automatic Xiaoheihe posting
- browser-login automation
- auto-like/comment
- account farms
- public multi-user SaaS hosting
- external database service
- AI-generated images

## 16. Acceptance criteria

`game-radar daily` must continue to satisfy the V1.2 pipeline acceptance criteria.

`game-radar web` must additionally:

1. start a local dashboard and open the browser by default;
2. list available YAML configs;
3. list historical report dates;
4. run Live / Fixture / Offline jobs without blocking the request;
5. clearly identify Fixture reports;
6. render Reach / Value / SEO picks and Top Candidates;
7. display source counts and warnings;
8. open draft packages with title alternatives/evidence;
9. copy publish-ready text;
10. save edited draft files without mutating the evidence package;
11. preserve CLI behavior.

## 17. North-star metric

Primary metric remains:

**How often does the daily Top 2 contain content actually worth publishing?**

The web dashboard exists to reduce operator friction and make the decision/evidence surface obvious; it must not change scoring simply to make the UI look more active.
