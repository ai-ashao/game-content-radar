from __future__ import annotations

import hashlib
from collections import Counter
from datetime import datetime, timezone
from .collectors.steam import SteamStoreCollector, SteamNewsCollector
from .collectors.epic import EpicFreeGamesCollector
from .collectors.reddit import RedditRSSCollector
from .collectors.rss import GenericRSSCollector
from .collectors.xiaoheihe import XiaoheihePublicCollector
from .http import HttpClient
from .models import Brief, SourceItem, SourceRecord, now_iso, uid
from .storage import Store


def normalize_error(warnings: list[str]) -> str:
    text=' '.join(warnings).lower()
    if '429' in text or '限流' in text: return 'rate_limited'
    if '403' in text or '401' in text or '权限' in text: return 'needs_access'
    return 'failed'


def collect_run(store: Store,mode: str='live',progress=None) -> dict:
    start=now_iso(); run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uid()[:8]
    settings=store.settings()
    sources=[]; items=[]; ids=[]; created=0
    def notify(message):
        if progress: progress(message)
    if mode=='offline':
        run={'run_id':run_id,'mode':'offline','started_at':start,'finished_at':now_iso(),'status':'empty','sources':[], 'items':[], 'created':0,'message':'无网络测试：未执行采集，未改动真实或示例选题库'}
        store.write_run(mode,run); return run
    if mode=='example':
        from .demo import create_demo
        before=len(store.list('example'))
        ids=create_demo(store)
        new_count=len(store.list('example'))-before
        run={'run_id':run_id,'mode':mode,'started_at':start,'finished_at':now_iso(),'status':'ok','sources':[{'name':'example','status':'ok','count':len(ids),'warnings':['人工构造示例，不可发布']}], 'items':[], 'brief_ids':ids,'created':new_count,'message':'示例数据已加载；与真实资料库完全隔离'}
        store.write_run(mode,run); return run
    http=HttpClient(timeout=settings.request_timeout,max_requests=settings.max_requests)
    specs=[('steam_store', lambda:SteamStoreCollector(http,country=settings.country)),
           ('steam_news',lambda:SteamNewsCollector(http,settings.watched_apps)),
           ('epic',lambda:EpicFreeGamesCollector(http,country=settings.country)),
           ('reddit',lambda:RedditRSSCollector(http,settings.subreddits)),
           ('official_rss',lambda:GenericRSSCollector(http,settings.official_rss)),
           ('xiaoheihe',lambda:XiaoheihePublicCollector(http))]
    try:
        for name,factory in specs:
            if not settings.enabled_sources.get(name) or (name=='steam_news' and not settings.watched_apps) or (name=='official_rss' and not settings.official_rss):
                sources.append({'name':name,'status':'not_configured','count':0,'warnings':[]}); continue
            notify('正在读取 '+name)
            try:
                r=factory().collect()
                status='partial' if r.items and r.warnings else 'ok' if r.items else normalize_error(r.warnings) if r.warnings else 'empty'
                sources.append({'name':name,'status':status,'count':len(r.items),'warnings':r.warnings})
                items.extend(r.items)
            except Exception as exc:
                sources.append({'name':name,'status':getattr(exc,'status','failed'),'count':0,'warnings':[str(exc)[:500]]})
    finally:
        http.close()
    unique={}
    for item in items:
        key=(item.source,item.source_url or item.id)
        unique.setdefault(key,item)
    notify('正在归并线索并更新选题池，不自动生成全文')
    for item in unique.values():
        b=signal_to_brief(item)
        saved,is_new=store.create_once(b)
        ids.append(saved.id); created+=is_new
    ok=any(s['status'] in ('ok','partial') for s in sources)
    problems=any(s['status'] in ('failed','needs_access','rate_limited','partial') for s in sources)
    run={'run_id':run_id,'mode':mode,'started_at':start,'finished_at':now_iso(), 'status':'partial' if ok and problems else 'ok' if ok else 'failed' if problems else 'empty',
         'sources':sources,'items':[x.to_dict() for x in unique.values()],'brief_ids':ids,'created':created,'raw_count':len(items),'unique_count':len(unique), 'message':'仅收集线索；核心事实需逐条核验'}
    store.write_run(mode,run)
    return run


def signal_to_brief(item: SourceItem) -> Brief:
    form='deals' if item.category in ('sale','free_game') else 'new_game'
    name=item.game_name or item.title
    origin=hashlib.sha256((item.source+'|'+item.source_url+'|'+form).encode()).hexdigest()
    source=SourceRecord(title=item.title,url=item.source_url,source_type=item.source_type if item.source_type in ('official','community','media') else 'unknown',
                        role='discovery',publisher=str(item.metrics.get('feedlabel') or item.source),original_date=item.published_at,
                        read_at=item.collected_at,read_status='partial',summary=item.summary[:16000],provenance='collector',
                        access_note='采集得到列表/摘要，不代表原文核查完毕')
    question=f'{name}适合什么玩家，现在有哪些确定信息和限制？'
    expires=item.metrics.get('free_until')
    return Brief(title=item.title[:200],column='buy_smart',content_form=form,pool='timely',mode='live',reader_question=question,
                 origin_key=origin,sources=[source],status='needs_research',expires_at=expires,
                 missing_evidence=['选择一个明确角度并确认受众','读取核心来源，建立事实与素材清单'],
                 notes='候选入口：'+item.source+'；原始快照见运行记录。不代表全站热点排名。')
