# game-content-radar V1.2 — reviewed implementation spec

## 1. Goal

Build a semi-automatic game intelligence pipeline that answers three independent questions every day:

1. What is most worth publishing on Xiaoheihe today?
2. Is there a signal worth turning into a website/SEO page?
3. Is there a game worth entering a deeper game-site validation workflow?

The tool stops at draft generation. Human review and Xiaoheihe publishing remain manual.

## 2. Important corrections from V1.1

### 2.1 SteamDB is not a Tier-1 hard dependency

A production pipeline should not depend on an undocumented third-party HTML layout. V1.2 therefore:

- uses Steam public store/news/current-player endpoints as primary Steam signals;
- stores current-player snapshots locally in SQLite;
- computes 24h/7d growth when history exists;
- keeps SteamDB as optional best-effort enrichment only.

This means player-spike detection becomes more reliable over time instead of failing whenever a third-party page changes.

### 2.2 “SERP Opportunity” cannot be honestly scored without SERP data

The source set in V1.2 does not contain Semrush volume/KD or full Google SERP competitor data. Therefore the site score is explicitly named:

**Preliminary Site Opportunity Score**

The score reserves a neutral SERP placeholder and always emits `needs_serp_validation=true`. A candidate must still go through Semrush + manual SERP validation before building a page/site.

Because the missing SERP component is only half-filled, the pre-validation score effectively caps below a fully validated 100-point score. This is deliberate.

### 2.3 “史低” is evidence-gated

Steam’s current discount snapshot does not prove an all-time historical low. The system must not say 史低/新史低 unless a source explicitly verifies it. Default sale-roundup titles therefore use “折扣 / 高折扣 / 最低价” rather than inventing a historical-low claim.

### 2.4 Xiaoheihe is optional public-web enrichment

Xiaoheihe public pages can help calibrate current China-community interest, but:

- it is disabled by default;
- no login/cookie automation is required;
- no private API is used;
- parsing failure only creates a warning;
- the daily pipeline still completes.

### 2.5 Drafting has a deterministic fallback

AI should improve language, not be required for data integrity. The tool has:

- a deterministic evidence-first writer that always works;
- an optional Codex CLI adapter using non-interactive structured output;
- an optional generic external-command LLM adapter;
- title evidence validation after LLM output;
- human review before publishing.

## 3. Primary source stack

Tier 1:

- Steam Store public storefront signals: specials / top sellers / new releases
- Steam News for configured watched app IDs (documented Steam Web API)
- Steam current-player counts + local history (documented Steam Web API, with host fallback)
- Reddit public RSS (`r/gaming`, `r/Steam` by default)
- Epic free-game promotion storefront feed

The Store featured-categories and Epic promotion feeds are public but not treated as immutable formal contracts; each adapter is isolated and fail-soft.

Tier 2 / optional:

- official RSS feeds configured by the user
- Xiaoheihe public web feed
- SteamDB public HTML enrichment

## 4. Event model

Raw source items are normalized into:

- source + source URL
- source type (official/community/third-party data)
- game name
- title + summary
- published/collected timestamps
- category
- metrics
- media URLs

Items are exact-deduplicated and then clustered semantically into an `EventCluster`.

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

The score is about publish value, not SEO value.

## 7. Preliminary Site Opportunity Score

Components:

- Search intent: 25
- Demand growth: 20
- SERP placeholder: 10 of the eventual 20
- Page expandability: 15
- Existing-site fit: 10
- Monetization potential: 10

Every event is flagged for later SERP validation.

## 8. Sale roundup rules

A synthetic sale roundup is created only when at least the configured number of meaningful deals is available (default 20) and each passes the configured minimum discount (default 30%).

The tool may say:

- number of deals
- highest discount
- current lowest observed price

The tool may NOT say:

- all-time low / historical low
- new historical low

unless that claim is explicitly verified.

## 9. Player-spike rules

The tool stores current-player snapshots locally. When enough history exists it compares the current count to 24h/7d baselines. A spike event requires both meaningful percentage growth and a minimum absolute-player increase, preventing tiny games from being ranked solely on percentage noise.

## 10. Draft output

Each selected Xiaoheihe draft contains:

- selected title
- >=5 title candidates when possible
- evidence-first body
- player-facing comment hook
- source verification section
- pre-publish checklist
- media plan with source URLs

The system targets two distinct picks:

- **Reach Pick** — broad/urgent/high-utility content
- **Value Pick** — analysis/problem-solving/deeper player value

It is allowed to recommend only one post if the second candidate is weak.

## 11. Media plan

The project does not AI-generate images in V1.2. It collects available official/store media URLs and produces a plan. Human review decides what is suitable to publish.

## 12. Existing-site matching

Configurable keyword-to-site routing is included. Initial examples:

- Workshop/SteamCMD issues → WorkshopFetch
- generic game tools/trackers/calculators → GameKitHQ
- Fortnite Sprite → FN Sprite Hub

## 13. Output

`game-radar daily` writes:

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
│   └── media-plan-*.json
└── seo/
    └── opportunities.md
```

## 14. V1.2 non-goals

No:

- Web dashboard
- automatic Xiaoheihe posting
- browser-login automation
- auto-like/comment
- account farms
- SaaS architecture
- external database service
- mandatory LLM API
- mandatory SteamDB/Xiaoheihe access

## 15. Acceptance criteria

`game-radar daily` must:

1. run with >=3 live sources when available;
2. keep running if any one source fails;
3. normalize and cluster events;
4. build sale/freebie roundups when thresholds are met;
5. persist Steam player history and detect later spikes;
6. score XHH and preliminary site value separately;
7. generate Reach/Value picks;
8. produce evidence-gated title candidates;
9. generate source-grounded Chinese drafts;
10. generate media plans;
11. generate a SERP-validation queue;
12. support fully offline fixture mode for repeatable tests.

## 16. North-star metric

Not number of scraped stories and not number of generated drafts.

Primary metric:

**How often does the daily Top 2 contain content actually worth publishing?**

Secondary metrics:

- post engagement after publication;
- useful SEO/site opportunities discovered;
- false-positive rate of headline/evidence claims.
