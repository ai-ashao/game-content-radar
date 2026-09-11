from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from .models import Brief, Claim, Settings, SourceRecord, parse_time


def readable(source: SourceRecord) -> bool:
    return source.read_status == 'read' and bool(source.summary.strip() or source.excerpt.strip())


def claim_problems(claim: Claim, brief: Brief, settings: Settings, *, publishing: bool = False, now: datetime | None = None) -> list[str]:
    now = now or datetime.now(timezone.utc)
    sources = {s.id:s for s in brief.sources}
    issues = []
    refs = [sources[i] for i in claim.source_ids if i in sources]
    if claim.kind != 'opinion':
        if not refs or len(refs) != len(claim.source_ids) or any(not readable(s) or s.role!='fact' for s in refs):
            issues.append('来源未完整读取、未标为事实依据或引用不存在')
        if not claim.locator.strip():
            issues.append('缺来源段落 / 时间码 / 表格定位')
    if claim.conflicts.strip() or claim.status == 'conflict':
        issues.append('存在尚未解决的冲突证据')
    if claim.valid_until:
        try:
            if parse_time(claim.valid_until) <= now:
                issues.append('主张已超过有效期')
        except ValueError:
            issues.append('有效期格式不正确')
    d = claim.data
    for key in ('observed_at','end_at'):
        if d.get(key):
            try:
                dt=parse_time(d[key])
                if key=='observed_at' and (dt-now).total_seconds()>300:
                    issues.append('采集时间不能在未来')
                if key=='end_at' and dt<=now: issues.append('相关活动已过截止时间')
            except (ValueError,TypeError,AttributeError):
                issues.append(key+' 必须是包含时区的ISO时间')
    # Derived facts cannot outlive their supporting claim versions.
    for dep in d.get('selected_claim_ids',[]):
        related=next((c for c in brief.claims if c.id==dep),None)
        if related is None or related.id==claim.id or related.status!='verified':
            issues.append('计算清单所依赖的主张需要重新核验')
        elif d.get('selected_claim_fingerprints',{}).get(dep):
            from .storage import fingerprint
            if d['selected_claim_fingerprints'][dep]!=fingerprint({'text':related.text,'data':related.data}):
                issues.append('基础数据已改变，请重新计算清单')
    primary = any(s.is_primary and readable(s) for s in refs)
    if claim.kind in ('quote','design_intent','role','historical_low') and not primary:
        issues.append('该主张需要原始 / 一手出处')
    if claim.kind in ('price','historical_low'):
        for key in ('store','region','currency','sku','edition','observed_at'):
            if not d.get(key): issues.append('价格缺少 '+key)
        amount = d.get('price_minor')
        if type(amount) is not int or amount < 0:
            issues.append('price_minor 必须是非负整数最小货币单位')
        if publishing:
            try:
                age = (now - parse_time(d.get('observed_at',''))).total_seconds() / 60
                if age < -5 or age > settings.price_fresh_minutes:
                    issues.append(f'价格需在发布前{settings.price_fresh_minutes}分钟内重新读取 / 核对')
            except (ValueError, TypeError):
                issues.append('缺少可用价格采集时间')
        if claim.kind == 'historical_low':
            if not d.get('historical_evidence') or not d.get('history_scope'):
                issues.append('历史低价需提供同商店 / 地区 / SKU / 币种的历史证据与覆盖范围')
    if claim.kind == 'rating':
        for key in ('platform','scope','observed_at'):
            if not d.get(key): issues.append('评分缺少 '+key)
        if d.get('platform') == 'steam':
            n, p, neg = d.get('total_reviews'),d.get('positive'),d.get('negative')
            if any(type(x) is not int or x < 0 for x in (n,p,neg)) or n != p + neg or n == 0:
                issues.append('评论分子分母无效、无评价或不一致；不可标0分')
            filters = d.get('filters',{})
            if not isinstance(filters,dict): filters={}
            if not all(k in filters for k in ('language','review_type','purchase_type','filter_offtopic_activity')):
                issues.append('缺Steam查询过滤口径')
            if filters.get('review_type') != 'all':
                issues.append('正负分子分母必须来自 review_type=all 同一查询摘要')
            if '30' in str(d.get('scope')) or 'recent' in str(d.get('scope','')).lower():
                issues.append('本版本不从一页评论或day_range推断官方最近30天好评率')
        elif d.get('platform') not in ('heybox','metacritic','other'):
            issues.append('未知评分平台')
        elif d.get('sample_size') is None or not d.get('scale'):
            issues.append('非Steam评分需标样本量与量表，不能跨平台求平均')
    if claim.kind == 'quote':
        if d.get('quote_mode') not in ('direct','translation','paraphrase'):
            issues.append('标明直引 / 译文 / 概述')
        if not d.get('original_text') or not d.get('original_date'):
            issues.append('缺原文或原始访谈日期')
    if claim.kind == 'role':
        if not all(d.get(x) for x in ('person','work','role','as_of')):
            issues.append('人物角色需具体作品、职务和资料日期')
        if d.get('role') in ('开发商','发行商','集团'):
            issues.append('人物职务不能等同开发商 / 发行商 / 集团')
    if claim.kind == 'detail':
        if not all(d.get(x) for x in ('platform','version','conditions','steps')):
            issues.append('细节缺平台 / 版本 / 条件 / 复现步骤')
        evidence = [a for a in brief.assets if a.id in d.get('asset_ids',[]) and a.purpose == 'evidence' and (a.local_file or a.url)]
        if not evidence:
            issues.append('细节需要关联真实画面 / 原始演示素材')
        if evidence and not all(a.local_file or a.timecode for a in evidence):
            issues.append('外部演示需填写时间码')
    if claim.kind == 'free_offer':
        if d.get('offer_type') not in ('free_to_keep','trial','f2p'):
            issues.append('需区分领取保留 / 限时试玩 / F2P')
        if d.get('offer_type') in ('free_to_keep','trial'):
            try:
                if parse_time(d.get('end_at','')) <= now: issues.append('免费活动已结束')
            except (ValueError, TypeError):
                issues.append('免费活动缺结束时间')
        if not d.get('platform') or not d.get('region'):
            issues.append('免费活动缺平台 / 地区')
    if claim.kind == 'ranking':
        if not all(d.get(x) for x in ('universe','metric','sort_rule','dedupe_rule','as_of','entity_kind')) or not isinstance(d.get('sample_size'),int) or d.get('sample_size',0) < 1:
            issues.append('榜单缺纳入范围、指标、样本、排序、去重、统计日期或排名对象')
    return issues


def draft_gate(brief: Brief, settings: Settings, *, publishing: bool = False) -> list[str]:
    problems = []
    if brief.status in ('out_of_scope','blocked','expired','archived'):
        problems.append('当前选题不在活动队列')
    if not brief.scope_confirmed: problems.append('尚未确认适合本账号受众')
    for field, label in [('reader_question','读者问题'),('angle','独立角度'),('thesis','一句话结论'),('original_contribution','具体原创贡献'),('reader_value','读者收益')]:
        if not getattr(brief,field).strip(): problems.append('缺少'+label)
    if brief.expires_at and parse_time(brief.expires_at) <= datetime.now(timezone.utc):
        problems.append('时效选题已过截止时间')
    if brief.missing_evidence:
        problems.extend('待补证：'+x for x in brief.missing_evidence)
    required = [c for c in brief.claims if c.required]
    if not required:
        problems.append('尚未建立核心事实清单')
    for c in required:
        if c.status != 'verified' or not c.verified_by or not c.verified_at:
            problems.append(f'待人工核验：{c.text[:65]}')
        for issue in claim_problems(c,brief,settings,publishing=publishing):
            problems.append(f'{c.text[:35]}：{issue}')
    if brief.content_form == 'deals' and not any(c.kind in ('price','free_offer') for c in required):
        problems.append('选购稿须有当前价格或免费活动的结构化依据')
    if brief.content_form == 'ratings' and not any(c.kind == 'rating' for c in required):
        problems.append('评分稿须有同口径的评价统计依据')
    if brief.content_form == 'detail' and not any(c.kind == 'detail' for c in required):
        problems.append('细节稿须有已关联画面的细节主张')
    if brief.content_form == 'creator' and not any(c.kind == 'role' for c in required):
        problems.append('人物稿须核对人物在具体作品中的职务')
    if brief.content_form == 'ranking' and not any(c.kind == 'ranking' for c in required):
        problems.append('榜单稿须有明确统计口径')
    if publishing:
        if not brief.assets and not brief.media_none_reason.strip():
            problems.append('请补素材，或说明本稿不需要配图的原因')
        for a in brief.assets:
            if not a.usage_confirmed or not a.usage_note.strip():
                problems.append('素材使用条件待确认：'+(a.title or a.id))
            if a.purpose == 'cover' and a.spoiler_level == 'major_story':
                problems.append('封面不得直接泄露关键剧情')
        if brief.spoiler_level == 'major_story' and not brief.spoiler_note.strip():
            problems.append('重剧透稿缺少读者提示')
    return list(dict.fromkeys(problems))


def text_checks(brief: Brief, title: str, body: str) -> list[str]:
    """Conservative lint; never claims to replace semantic human fact-checking."""
    text = title + '\n' + body
    verified = [c for c in brief.claims if c.status == 'verified']
    kinds = {c.kind for c in verified}
    issues = []
    if re.search(r'史低|历史最低|全网最低|最低价',text) and 'historical_low' not in kinds:
        issues.append('出现未经历史证据支持的低价主张，请改为本次清单价格或补证')
    bounded_text=re.sub(r'不代表(?:全Steam|全行业|全商店)[^。；\n]*', '', text, flags=re.I)
    if re.search(r'99[%％].{0,8}(不知道|没发现)|首次发现|全球第一|全Steam|全行业最强|所有NPC',bounded_text,re.I):
        issues.append('绝对 / 全范围断言不可由候选样本证明')
    if re.search(r'我.{0,5}(亲测|实测|通关|重玩|玩了|体验了)|本人.{0,5}(实测|通关)|我.{0,4}\d+\s*(小时|周目)',text) and not brief.author_experience.strip():
        issues.append('没有作者实际体验记录，不能编造第一人称游玩经历')
    if re.search(r'最新采访|刚刚.{0,5}(表示|声称)',text):
        if not any(c.kind == 'quote' and c.data.get('original_date') == datetime.now(timezone.utc).date().isoformat() for c in verified):
            issues.append('采访的新旧时间未证实，旧访谈不能包装为最新表态')
    if re.search(r'开发者.{0,8}(故意|刻意|有意)',text) and 'design_intent' not in kinds:
        issues.append('设计意图需开发者直接依据；请区分观察与推论')
    if any(c.kind == 'free_offer' and c.data.get('offer_type') != 'free_to_keep' for c in verified) and re.search(r'永久入库|免费保留',text):
        issues.append('免费类型可能与永久入库表述冲突')
    if re.search(r'官方证实|官方确认',title) and not any(s.is_primary and s.role == 'fact' and readable(s) for s in brief.sources):
        issues.append('标题中的官方确认缺少可读的一手事实来源')
    # A numeric lint does not validate semantics; it catches unsupported high-risk tokens.
    evidence = '\n'.join(c.text+' '+json.dumps(c.data,ensure_ascii=False) for c in verified)
    for token in re.findall(r'\d+(?:\.\d+)?\s*(?:%|％|元|小时|万份)',text):
        number = re.search(r'\d+(?:\.\d+)?',token)[0]
        if number not in evidence:
            issues.append('请核对稿件新增数字：'+token)
    return list(dict.fromkeys(issues))


def compute_deal_summary(rows: list[dict]) -> dict:
    if not rows: raise ValueError('请先选入游戏')
    signatures = {(r.get('store'),r.get('region'),r.get('currency')) for r in rows}
    if len(signatures) != 1 or any(not v for v in next(iter(signatures))):
        raise ValueError('清单必须使用同商店、地区与币种')
    identities = {(r.get('sku'),r.get('edition')) for r in rows}
    if len(identities) != len(rows) or any(not a or not b for a,b in identities):
        raise ValueError('清单SKU/版本缺失或重复')
    if any(type(r.get('price_minor')) is not int or r['price_minor'] < 0 for r in rows):
        raise ValueError('价格必须使用非负整数最小货币单位')
    low = min(r['price_minor'] for r in rows)
    return {'count':len(rows), 'min_price_minor':low, 'store':rows[0]['store'], 'region':rows[0]['region'], 'currency':rows[0]['currency'], 'scope':'仅本次最终选入清单；不代表全商店或历史价格'}


def rating_percent(positive: int, negative: int, total: int) -> float | None:
    if any(type(x) is not int or x < 0 for x in (positive,negative,total)) or total != positive+negative:
        raise ValueError('评价数量口径不一致')
    if not total: return None
    return float((Decimal(positive)*100/Decimal(total)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP))


def editorial_priority(b: Brief, settings: Settings) -> dict:
    required = [c for c in b.claims if c.required]
    verified = sum(c.status=='verified' for c in required)
    components = {
        'reader_value':25 if b.reader_value.strip() and b.reader_question.strip() else None,
        'contribution':20 if b.original_contribution.strip() and b.angle.strip() else None,
        'readiness':int(20*verified/len(required)) if required else None,
        'audience_fit':15 if b.scope_confirmed else None,
        'feasibility':(10 if b.estimated_human_minutes <= settings.daily_minutes else 4) if b.estimated_human_minutes else None,
        'timing':10 if b.pool=='evergreen' else (8 if not b.expires_at or parse_time(b.expires_at)>datetime.now(timezone.utc) else 0),
    }
    gaps = draft_gate(b,settings)
    return {'total':sum(x or 0 for x in components.values()), 'components':components,
            'confidence':'high' if not gaps else 'low' if verified==0 else 'medium',
            'ready':not gaps, 'gaps':gaps, 'verified_claims':verified, 'required_claims':len(required),
            'note':'编辑优先级是按已填写证据计算的设计规则，不是爆款概率'}
