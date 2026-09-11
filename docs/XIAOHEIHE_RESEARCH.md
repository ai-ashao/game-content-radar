# Xiaoheihe content research notes

Research date: 2026-09-11

This project was calibrated against publicly accessible Xiaoheihe web pages rather than generic assumptions about game-content platforms.

## Pages sampled

- Public community home: https://www.xiaoheihe.cn/app/bbs/home
- Steam-oriented posts and public creator profile pages reachable from the community feed
- Public post pages such as https://www.xiaoheihe.cn/app/bbs/link/190255690
- Public creator examples sampled from active Steam/game-content accounts

## What the sample showed

### 1. Steam deal roundups are a first-class content format

The public feed contained repeated high-engagement posts using a pattern close to:

`date + Steam + strong change/benefit + number of games + low price / discount signal`

The useful product lesson is not to copy wording. The system should recognize that a broad, dense deal roundup can have substantially higher audience breadth and utility than a single ordinary sale item.

### 2. Data anomaly + story conflict is stronger than a raw news summary

Public examples combined player-count changes with a narrative explanation: localization, major updates, revival, controversy, or a known franchise/developer. This supports a dedicated `player_spike_story` type rather than treating player growth as a generic news item.

### 3. Quantitative evidence is a recurring headline anchor

Common headline anchors included player growth, review percentage, wishlist scale, sales scale, discount depth, price and number of items. Therefore headline generation must be evidence-backed.

### 4. Known anchors reduce explanation cost

Posts frequently explain an unfamiliar title via a known studio, previous game, genre reference, or comparable game. The implementation supports `known_anchor` as an enrichment signal, but it must never invent developer relationships.

### 5. Visual density matters

Many sampled posts used multiple screenshots/images/GIFs. Therefore each draft must include a `media-plan` rather than only Markdown text.

### 6. Xiaoheihe-native writing is not a press release

The feed favors player-facing framing: why it matters, whether it is worth returning/buying/trying, what changed, and what people are arguing about. Drafts avoid press-release openings and generic AI transitions.

## Engineering implications

- Xiaoheihe itself is optional enrichment, not a hard dependency.
- Public HTML may change, so the source must fail soft.
- No authenticated/private API is required.
- No automatic posting is implemented.
- Headline claims such as historical low, free, player growth and review percentage require evidence.
- Xiaoheihe publish value and SEO/site value use separate scores.
