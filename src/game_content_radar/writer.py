from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any

from game_content_radar.evidence import collect_evidence, validate_title
from game_content_radar.models import DraftPackage, EventCluster, TitleCandidate


def _money(event: EventCluster) -> str | None:
    value = event.signals.get("min_price")
    if value is None:
        return None
    currency = str(event.signals.get("currency") or "")
    symbol = {"CNY": "¥", "USD": "$", "EUR": "€"}.get(currency, currency + " " if currency else "")
    if float(value).is_integer():
        return f"{symbol}{int(value)}"
    return f"{symbol}{value:.2f}"


def _growth(event: EventCluster) -> float | None:
    vals: list[float] = []
    for s in event.sources:
        for key in ["growth_24h_percent", "growth_7d_percent"]:
            try:
                if s.metrics.get(key) is not None:
                    vals.append(float(s.metrics[key]))
            except Exception:
                pass
    return max(vals) if vals else None


def _deadline(event: EventCluster) -> str | None:
    ds = event.signals.get("deadlines") or []
    if not ds:
        ds = [s.metrics.get("free_until") for s in event.sources if s.metrics.get("free_until")]
    if not ds:
        return None
    raw = str(sorted(ds)[0])
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            dt = dt.astimezone(ZoneInfo("Asia/Shanghai"))
        return dt.strftime("%m月%d日 %H:%M")
    except Exception:
        return raw


def _format_dt(raw: object) -> str:
    if raw in (None, ""):
        return "待确认"
    text = str(raw)
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            dt = dt.astimezone(ZoneInfo("Asia/Shanghai"))
        return dt.strftime("%m月%d日 %H:%M")
    except Exception:
        return text


def _evidence_for_title(event: EventCluster, kinds: list[str]) -> list[dict[str, Any]]:
    return [e for e in collect_evidence(event) if e.get("claim_type") in kinds]


def generate_title_candidates(event: EventCluster) -> list[TitleCandidate]:
    cat = event.category
    game = event.game_name or event.event_title[:24]
    out: list[TitleCandidate] = []

    if cat == "sale_roundup":
        n = int(event.signals.get("deal_count") or len(event.sources))
        min_price = _money(event)
        max_discount = event.signals.get("max_discount")
        price_hook = f"，最低{min_price}" if min_price else ""
        candidates = [
            (f"Steam今天这波折扣值得翻：{n}款高折扣游戏{price_hook}", "benefit", "数量+最低价"),
            (f"等等党可以看看了：Steam {n}款游戏集中打折{price_hook}", "community", "等等党+利益点"),
            (f"Steam折扣清单：从3A到独立游戏，这{n}款值得先看", "utility", "清单价值"),
            (f"今天Steam买什么？先从这{n}款高折扣游戏里挑", "question", "购买决策"),
            (f"最高-{int(max_discount)}%：Steam这波{n}款折扣游戏怎么选" if max_discount else f"Steam这波{n}款折扣游戏怎么选", "data", "折扣幅度"),
        ]
        evidence = _evidence_for_title(event, ["deal_count", "min_price", "max_discount", "discount_percent"])
    elif cat == "freebie_roundup":
        n = int(event.signals.get("free_count") or len(event.sources))
        deadline = _deadline(event)
        tail = f"，{deadline}前记得入库" if deadline else ""
        platform = str(event.signals.get("platform_label") or event.game_name or "游戏平台")
        candidates = [
            (f"本期免费游戏清单：{platform}共{n}款可领{tail}", "utility", "数量+截止时间"),
            (f"别漏领：{platform}这周有{n}款游戏可以免费入库", "benefit", "免费入库"),
            (f"喜加一不只一款：{platform}本周{n}款免费游戏怎么选", "question", "选择题"),
            (f"{platform}本周免费游戏来了：{n}款里哪些最值得领？", "question", "推荐判断"),
            (f"0元入库清单：{platform}本周{n}款免费游戏一次看完", "data", "零元利益点"),
        ]
        evidence = _evidence_for_title(event, ["free_count", "free_until"])
    elif cat == "player_spike_story":
        growth = _growth(event)
        g = f"{growth:.0f}%" if growth is not None else "明显"
        candidates = [
            (f"{game}怎么突然火了？玩家数短期暴涨{g}", "question", "异常数据+原因"),
            (f"短期突然回温：{game}玩家数为什么涨了{g}", "contrast", "反差"),
            (f"玩家数涨了{g}，{game}这波发生了什么？", "data", "数据"),
            (f"{game}玩家突然回流：这波变化背后发生了什么？", "story", "回流故事"),
            (f"从冷到热：拆一下{game}这轮玩家回流", "analysis", "趋势分析"),
        ]
        evidence = _evidence_for_title(event, ["growth_24h_percent", "growth_7d_percent", "player_count"])
    elif cat == "major_update":
        candidates = [
            (f"{game}更新了，但真正值得看的不是版本号", "analysis", "影响而非公告"),
            (f"{game}这次大更新，普通玩家最该看哪几项？", "question", "玩家影响"),
            (f"{game}新版本上线：先看这几个核心变化", "utility", "核心变化"),
            (f"这次更新会让你回坑吗？{game}新版本重点整理", "discussion", "回坑讨论"),
            (f"{game}版本更新：改了什么、影响谁、值不值得回", "utility", "三段判断"),
        ]
        evidence = []
    elif cat in {"release", "community_trend", "other"}:
        candidates = [
            (f"{game}值得关注吗？先看它最有辨识度的几个点", "question", "购买/关注判断"),
            (f"别只看宣传片：{game}真正有意思的是这些玩法", "analysis", "玩法拆解"),
            (f"{game}上线后，我更关注这几个实际信号", "evidence", "信号"),
            (f"这款{game}为什么值得放进观察名单？", "question", "观察名单"),
            (f"从玩法到数据：快速看懂{game}", "utility", "信息密度"),
        ]
        evidence = []
    else:
        candidates = [
            (f"{game}这件事值得关注的，不只是表面消息", "analysis", "深入一层"),
            (f"{game}发生了什么？把关键信息一次讲清", "utility", "完整信息"),
            (f"关于{game}，今天最值得看的几个信号", "data", "信号整理"),
            (f"{game}这波变化，对普通玩家有什么影响？", "question", "玩家影响"),
            (f"先别急下结论：拆一下{game}这次变化", "contrast", "判断"),
        ]
        evidence = []

    for idx, (title, style, hook) in enumerate(candidates):
        ok, issues = validate_title(title, event)
        if not ok:
            continue
        out.append(TitleCandidate(title=title, style=style, hook=hook, evidence=evidence, score=90 - idx * 3))
    return out[:5]


def _source_lines(event: EventCluster) -> str:
    rows = []
    seen = set()
    for s in event.sources:
        if s.source_url and s.source_url not in seen:
            seen.add(s.source_url)
            rows.append(f"- {s.source}: {s.source_url}")
        if len(rows) >= 8:
            break
    return "\n".join(rows)


def _sale_body(event: EventCluster) -> str:
    rows = sorted(
        event.sources,
        key=lambda s: (int(s.metrics.get("discount_percent") or 0), -(int(s.metrics.get("final_price_minor") or 10**12))),
        reverse=True,
    )[:20]
    table = ["| 游戏 | 折扣 | 当前价* |", "|---|---:|---:|"]
    for s in rows:
        discount = int(s.metrics.get("discount_percent") or 0)
        price = s.metrics.get("final_price_minor")
        currency = str(s.metrics.get("currency") or "")
        price_text = "-"
        if price is not None:
            symbol = {"CNY": "¥", "USD": "$", "EUR": "€"}.get(currency, currency + " ")
            price_text = f"{symbol}{int(price)/100:g}"
        table.append(f"| {s.game_name} | -{discount}% | {price_text} |")
    return (
        "今天 Steam 的折扣比较集中。我先按折扣幅度和当前价格筛了一遍，把最值得优先检查的放在前面。\n\n"
        + "\n".join(table)
        + "\n\n*当前价来自本次抓取快照；是否为历史最低价需要单独验证，未验证前不写“史低”。*\n\n"
        "如果你不是为了清库存式买游戏，建议先看三个点：自己是否近期会玩、折扣是否足够大、同系列/捆绑包是否更划算。"
    )


def _freebie_body(event: EventCluster) -> str:
    lines = ["这期免费入库的游戏不止一款，先把能领什么和截止时间放前面。", ""]
    for s in event.sources[:12]:
        deadline = _format_dt(s.metrics.get("free_until"))
        lines.append(f"- **{s.game_name}** — 截止：{deadline} — {s.source_url}")
    lines.extend(["", "建议先入库再决定玩不玩。免费领取信息以官方商店实时页面为准，发布前再检查一次截止时间。"])
    return "\n".join(lines)


def _player_spike_body(event: EventCluster) -> str:
    current = previous = growth = None
    window = "24小时"
    for s in event.sources:
        if s.metrics.get("player_count") is not None:
            current = int(s.metrics["player_count"])
        if s.metrics.get("growth_24h_percent") is not None:
            growth = float(s.metrics["growth_24h_percent"])
            previous = s.metrics.get("previous_players_24h")
            window = "24小时"
            break
        if s.metrics.get("growth_7d_percent") is not None:
            growth = float(s.metrics["growth_7d_percent"])
            previous = s.metrics.get("previous_players_7d")
            window = "7天"
    lines = ["先看数据。"]
    if current is not None:
        lines.append(f"当前采集到的 Steam 同时在线快照约 **{current:,}**。")
    if growth is not None:
        baseline = f"，可比基线约 {int(previous):,}" if previous is not None else ""
        lines.append(f"和{window}前的本地历史快照相比{baseline}，增幅约 **{growth:.1f}%**。")
    lines.extend(["", "## 为什么突然涨", ""])
    context = []
    for s in event.sources:
        if s.source == "steam_players":
            continue
        if s.summary:
            context.append(f"- {s.source}: {s.summary[:350]}")
    if context:
        lines.extend(context[:4])
        lines.append("这些是同时出现的关联信号，但相关性不等于因果。发布时不要把尚未验证的原因写死。")
    else:
        lines.append("目前只有玩家数变化证据，还不足以判断原因。发布前应补官方更新、社区讨论或活动信息。")
    lines.extend(["", "## 接下来值得看什么", "", "- 高峰能否持续 24–72 小时，而不是只冲一次。", "- Steam 评论/社区讨论是否同步增长。", "- 是否有大版本、促销、主播传播或地区性事件能解释回流。"])
    return "\n".join(lines)


def _major_update_body(event: EventCluster) -> str:
    primary = max(event.sources, key=lambda s: (s.source_type == "official", len(s.summary)))
    lines = ["这次更新先不复述整份 Patch Notes，先把当前能确认的重点拎出来。", "", "## 官方信息", "", primary.summary[:1000] or primary.title, "", "## 玩家真正需要继续确认的三件事", "", "1. 哪些改动会直接改变日常玩法或主流构筑。", "2. 是否修复了此前最影响体验的问题。", "3. 更新后的玩家反馈和在线人数能否持续。", "", "如果后续社区反馈与公告出现明显分歧，再单独做第二篇分析，比把整份更新日志翻译一遍更有价值。"]
    return "\n".join(lines)


def _troubleshooting_body(event: EventCluster) -> str:
    primary = event.sources[0]
    return "\n".join([
        "这是一条明确的问题型需求信号，但当前来源不足以直接生成‘解决教程’。", "",
        "## 用户在遇到什么", "", primary.title, "", primary.summary[:700], "",
        "## 发布前必须补证据", "",
        "- Steam/游戏官方是否有对应公告或已知问题。",
        "- 至少复现或找到两条独立用户报告。",
        "- 每个解决步骤必须能解释适用条件，不能凭 AI 猜。",
        "", "如果补证后成立，这类内容通常同时适合小黑盒收藏型帖子和网站 Troubleshooting 页面。"
    ])


def _generic_body(event: EventCluster) -> str:
    primary = max(event.sources, key=lambda s: (s.source_type == "official", len(s.summary)))
    facts = []
    if primary.summary:
        facts.append(primary.summary[:900])
    for s in event.sources:
        if s is primary or not s.summary:
            continue
        snippet = s.summary[:350]
        if snippet not in facts:
            facts.append(snippet)
        if len(facts) >= 3:
            break
    sections = [
        "先说结论：这条信息值得关注，但正文只保留当前来源能够验证的事实，不补未经证实的数据。",
        "",
        "## 发生了什么",
        facts[0] if facts else event.event_title,
    ]
    if len(facts) > 1:
        sections.extend(["", "## 还有哪些信号", *[f"- {x}" for x in facts[1:]]])
    sections.extend([
        "", "## 对玩家意味着什么",
        "目前最值得继续观察的是：实际玩家反馈、后续更新、价格/版本变化，以及数据是否持续，而不是只看一次公告。",
    ])
    return "\n".join(sections)


def build_media_plan(event: EventCluster) -> dict[str, Any]:
    media = []
    seen = set()
    for s in event.sources:
        for url in s.media_urls:
            if url and url not in seen:
                seen.add(url)
                media.append({"purpose": "official/store visual", "source_url": url, "source_page": s.source_url})
    target = 8 if event.category not in {"sale_roundup", "freebie_roundup"} else 6
    return {
        "cover": media[0] if media else None,
        "images": media[:10],
        "suggested_count": target,
        "note": "优先使用官方商店/官方公告素材；发布前人工检查清晰度、重复和平台展示效果。",
    }


def build_comment_hook(event: EventCluster) -> str:
    if event.category == "sale_roundup":
        return "如果这波只能挑一款，你准备买哪款？"
    if event.category == "freebie_roundup":
        return "这期免费游戏里，你最可能真正打开玩的是哪一款？"
    if event.category == "player_spike_story":
        return "你觉得这波热度能留下来，还是更新期的一次短暂回流？"
    if event.category == "major_update":
        return "这次更新里，哪一项最可能让你回坑？"
    return "如果你已经玩过，最值得补充给观望玩家的一点是什么？"


def build_draft(event: EventCluster) -> DraftPackage:
    titles = generate_title_candidates(event)
    if not titles:
        titles = [TitleCandidate(title=event.event_title, style="fallback", hook="source title", score=50)]
    if event.category == "sale_roundup":
        body = _sale_body(event)
    elif event.category == "freebie_roundup":
        body = _freebie_body(event)
    elif event.category == "player_spike_story":
        body = _player_spike_body(event)
    elif event.category == "major_update":
        body = _major_update_body(event)
    elif event.category == "troubleshooting":
        body = _troubleshooting_body(event)
    else:
        body = _generic_body(event)
    body += "\n\n## 来源核对\n" + (_source_lines(event) or "- 无可用URL，发布前必须补来源")
    body += "\n\n> 发布前人工检查：标题强 Claim、时间、价格、人数、版本号、免费截止时间。"
    return DraftPackage(
        selected_title=titles[0].title,
        title_candidates=titles,
        body_markdown=body,
        comment_hook=build_comment_hook(event),
        media_plan=build_media_plan(event),
        evidence=collect_evidence(event),
    )
