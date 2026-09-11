from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from .models import (Approval, Brief, BriefInput, Claim, DraftInput, DraftRevision, MediaAsset, MetricSnapshot,
                     Mode, PublicationRecord, SourceRecord, now_iso, parse_time)
from .storage import Store, fingerprint
from .validation import claim_problems, draft_gate, editorial_priority, text_checks


def invalidate(b: Brief, *, claims: bool = False) -> None:
    b.approval = None
    b.scheduled_at = None
    if claims:
        for c in b.claims:
            if c.kind != 'opinion':
                c.status = 'pending'
                c.verified_by = None
                c.verified_at = None
    if b.status not in ('out_of_scope','archived'):
        b.status = 'in_review' if b.drafts else 'needs_research'


def current_fingerprint(b: Brief) -> str:
    data = b.model_dump(mode='json')
    # Publication, metrics and UI/status changes do not rewrite approved content.
    for k in ('approval','scheduled_at','publications','metrics','audit','version','updated_at','status','actual_human_minutes'):
        data.pop(k,None)
    return fingerprint(data)

class StudioService:
    def __init__(self, store: Store):
        self.store = store

    def create(self, mode: Mode, data: BriefInput) -> Brief:
        return self.store.create(Brief(**data.model_dump(),mode=mode))

    def update(self, mode: Mode, bid: str, expected: int, data: BriefInput) -> Brief:
        def op(b):
            # Validate column/form together, not halfway through an assignment.
            merged = Brief.model_validate({**b.model_dump(), **data.model_dump()})
            changed = {k for k, value in data.model_dump().items() if getattr(b, k) != value}
            delta = data.actual_human_minutes - b.actual_human_minutes
            b.__dict__.update(merged.__dict__)
            if delta:
                b.audit.append({'at':now_iso(), 'action':'human_time_adjustment', 'minutes_delta':delta})
            if changed - {'actual_human_minutes'}:
                invalidate(b, claims=True)
        return self.store.mutate(mode,bid,expected,op,'brief_updated_approval_invalidated')

    def source(self, mode: Mode, bid: str, expected: int, source: SourceRecord) -> Brief:
        def op(b):
            source.read_at = now_iso() if source.read_status == 'read' else source.read_at
            b.sources = [s for s in b.sources if s.id != source.id] + [source]
            for c in b.claims:
                if source.id in c.source_ids:
                    c.status='pending'; c.verified_at=None; c.verified_by=None
            invalidate(b)
        return self.store.mutate(mode,bid,expected,op,'source_saved')

    def claim(self, mode: Mode, bid: str, expected: int, claim: Claim) -> Brief:
        def op(b):
            claim.status='pending'; claim.verified_by=None; claim.verified_at=None
            b.claims = [c for c in b.claims if c.id != claim.id]+[claim]
            invalidate(b)
        return self.store.mutate(mode,bid,expected,op,'claim_saved_needs_verification')

    def verify(self, mode: Mode, bid: str, expected: int, cid: str, reviewer: str, confirmed: bool) -> Brief:
        if not reviewer.strip() or not confirmed:
            raise ValueError('请阅读原始来源后，勾选已核对并填写审核人')
        def op(b):
            c=next((c for c in b.claims if c.id==cid),None)
            if c is None: raise FileNotFoundError('主张不存在')
            issues=claim_problems(c,b,self.store.settings())
            if issues: raise ValueError('；'.join(issues))
            c.status='verified'; c.verified_by=reviewer.strip(); c.verified_at=now_iso()
            b.approval=None; b.scheduled_at=None
            if not b.drafts:
                b.status='brief_ready' if not draft_gate(b,self.store.settings()) else 'needs_research'
        return self.store.mutate(mode,bid,expected,op,'claim_verified_by_human')

    def asset(self, mode: Mode, bid: str, expected: int, asset: MediaAsset) -> Brief:
        def op(b):
            b.assets=[a for a in b.assets if a.id != asset.id]+[asset]
            # A change to visual evidence requires rechecking claims depending on it.
            for c in b.claims:
                if asset.id in c.data.get('asset_ids',[]):
                    c.status='pending'; c.verified_at=None; c.verified_by=None
            invalidate(b)
        return self.store.mutate(mode,bid,expected,op,'asset_saved')

    def remove(self, mode: Mode, bid: str, expected: int, kind: str, item_id: str) -> Brief:
        if kind not in ('sources','claims','assets'): raise ValueError('仅能移除来源 / 主张 / 素材')
        def op(b):
            setattr(b,kind,[i for i in getattr(b,kind) if i.id != item_id])
            invalidate(b,claims=True)
        return self.store.mutate(mode,bid,expected,op,'removed_'+kind)

    def save_draft(self, mode: Mode, bid: str, expected: int, draft: DraftInput) -> Brief:
        def op(b):
            valid_ids={c.id for c in b.claims}
            if set(draft.used_claim_ids)-valid_ids:
                raise ValueError('草稿引用了不存在的主张')
            changed = bool(b.drafts and any(getattr(b.drafts[-1],k)!=getattr(draft,k) for k in ('title','body_markdown','comment_hook','used_claim_ids')))
            invalidate(b,claims=changed)
            r=DraftRevision(**draft.model_dump(),revision=len(b.drafts)+1)
            r.fingerprint=fingerprint(draft.model_dump())
            r.check_notes=text_checks(b,r.title,r.body_markdown+'\n'+r.comment_hook)
            b.drafts.append(r)
            b.status='draft_ready'
        return self.store.mutate(mode,bid,expected,op,'new_draft_revision')

    def publishing_problems(self,b: Brief) -> list[str]:
        problems=draft_gate(b,self.store.settings(),publishing=True)
        if not b.drafts:
            problems.append('尚无稿件')
        else:
            d=b.drafts[-1]
            if d.assistance=='outline': problems.append('资料大纲不能视作完成稿')
            problems+=text_checks(b,d.title,d.body_markdown+'\n'+d.comment_hook)
            for t in d.title_candidates:
                problems+=text_checks(b,t,'')
            if not d.used_claim_ids:
                problems.append('请勾选本稿引用的已核验事实')
            for cid in d.used_claim_ids:
                c=next((c for c in b.claims if c.id==cid),None)
                if c is None or c.status!='verified': problems.append('稿件含待核验的引用主张')
                elif not c.required: problems+=claim_problems(c,b,self.store.settings(),publishing=True)
        return list(dict.fromkeys(problems))

    def approve(self,mode: Mode,bid: str,expected: int,reviewer: str,checks: dict) -> Brief:
        required=('facts_checked','media_checked','spoiler_checked','policy_checked')
        if not reviewer.strip() or not all(checks.get(k) is True for k in required):
            raise ValueError('需人工确认事实、素材、剧透和平台规则检查；系统不能代替审核')
        def op(b):
            problems=self.publishing_problems(b)
            if problems: raise ValueError('；'.join(problems))
            b.approval=Approval(reviewer=reviewer,checked_at=now_iso(),draft_revision=b.drafts[-1].revision,
                                fingerprint=current_fingerprint(b),**{k:True for k in required})
            b.status='approved'
        return self.store.mutate(mode,bid,expected,op,'human_approved')

    def require_approved(self,b: Brief):
        problems=self.publishing_problems(b)
        if not b.approval or b.approval.fingerprint!=current_fingerprint(b):
            problems.append('当前版本尚未通过人工审核，或审核后已修改')
        if problems: raise ValueError('；'.join(problems))

    def schedule(self,mode: Mode,bid: str,expected: int,at: str) -> Brief:
        dt=parse_time(at)
        if dt <= datetime.now(timezone.utc): raise ValueError('排期须在未来；不自动发布')
        def op(b):
            self.require_approved(b)
            b.scheduled_at=dt.isoformat(); b.status='scheduled'
        return self.store.mutate(mode,bid,expected,op,'scheduled_manual_posting')

    def publication(self,mode: Mode,bid: str,expected: int,url: str,published_at: str) -> Brief:
        import re
        if mode=='example':
            raise ValueError('示例工作区不能登记真实发布；请在真实工作区研究并审核')
        if not re.fullmatch(r'https://(?:www\.)?xiaoheihe\.cn/app/bbs/link/\d+(?:\?[^\s]*)?',url):
            raise ValueError('请填写小黑盒帖子分享网址：https://www.xiaoheihe.cn/app/bbs/link/数字')
        when=parse_time(published_at)
        if (when-datetime.now(timezone.utc)).total_seconds()>300:
            raise ValueError('发布时间不能在未来')
        def op(b):
            self.require_approved(b)
            if any(p.url.split('?')[0]==url.split('?')[0] for p in b.publications):
                raise ValueError('该帖子已经登记')
            b.publications.append(PublicationRecord(url=url,published_at=when.isoformat(),draft_revision=b.drafts[-1].revision,title=b.drafts[-1].title))
            b.status='published'; b.scheduled_at=None
        return self.store.mutate(mode,bid,expected,op,'publication_recorded_not_automated')

    def metric(self,mode: Mode,bid: str,expected: int,metric: MetricSnapshot) -> Brief:
        def op(b):
            p=next((p for p in b.publications if p.id==metric.publication_id),None)
            if not p: raise ValueError('发布记录不存在')
            age=(parse_time(metric.observed_at)-parse_time(p.published_at)).total_seconds()/3600
            if age < 0: raise ValueError('观察时间早于发布时间')
            if (parse_time(metric.observed_at)-datetime.now(timezone.utc)).total_seconds()>300:
                raise ValueError('观察时间不能在未来')
            metric.post_age_hours=round(age,2)
            b.metrics.append(metric)
        return self.store.mutate(mode,bid,expected,op,'metric_snapshot_recorded')

    def status(self,mode: Mode,bid: str,expected: int,status: str) -> Brief:
        if status not in ('needs_research','in_review','out_of_scope','blocked','archived'):
            raise ValueError('该状态需通过相应的审核 / 排期流程设置')
        def op(b):
            invalidate(b); b.status=status
        return self.store.mutate(mode,bid,expected,op,'editor_state_'+status)

    def view(self,b: Brief) -> dict:
        result=b.model_dump(mode='json')
        result['priority']=editorial_priority(b,self.store.settings())
        result['publish_gaps']=self.publishing_problems(b)
        result['approval_valid']=bool(b.approval and b.approval.fingerprint==current_fingerprint(b) and not result['publish_gaps'])
        return result

    def dashboard(self,mode: Mode) -> dict:
        bs=self.store.list(mode); settings=self.store.settings()
        rows=[self.view(b) for b in bs]
        rows.sort(key=lambda b:b['priority']['total'],reverse=True)
        now=datetime.now(timezone.utc)
        def costs(window_hours):
            return max(0,sum(record.get('minutes_delta',0) for b in bs for record in b.audit
                if record.get('action')=='human_time_adjustment'
                and 0 <= (now-parse_time(record['at'])).total_seconds()/3600 <= window_hours))
        daily_remaining=max(0,settings.daily_minutes-costs(24))
        weekly_remaining=max(0,settings.weekly_minutes-costs(168))
        publications=[(b,p) for b in bs for p in b.publications]
        recent=[(b,p) for b,p in publications if 0 <= (now-parse_time(p.published_at)).total_seconds()/3600<=24*30]
        counts={c:sum(b.column==c for b,p in recent) for c in settings.column_mix}
        heavy_week=sum(1 for b,p in publications if (b.estimated_human_minutes or 0)>=45
                       and 0 <= (now-parse_time(p.published_at)).total_seconds()/3600<=168)
        published_day=sum(1 for b,p in publications if 0 <= (now-parse_time(p.published_at)).total_seconds()/3600<=24)
        limit=max(0,min(2,settings.daily_posts_max)-published_day)
        recommended=[]
        for pool in ('timely','evergreen'):
            eligible=[b for b in rows if b['pool']==pool and b['priority']['ready']
                      and b['status'] not in ('published','archived','scheduled')
                      and b['estimated_human_minutes'] is not None
                      and b['estimated_human_minutes']<=min(daily_remaining,weekly_remaining)
                      and (b['estimated_human_minutes']<45 or heavy_week<settings.heavy_posts_per_week)]
            # The mix is a scheduling preference, never a claim about platform algorithms.
            eligible.sort(key=lambda b:(settings.column_mix[b['column']]/100*(len(recent)+len(recommended)+1)-counts[b['column']],b['priority']['total']),reverse=True)
            if eligible and len(recommended)<limit:
                chosen=eligible[0]; recommended.append(chosen['id']); counts[chosen['column']]+=1
                daily_remaining-=chosen['estimated_human_minutes']; weekly_remaining-=chosen['estimated_human_minutes']
                if chosen['estimated_human_minutes']>=45: heavy_week+=1
        return {'briefs':rows,'recommended_ids':recommended,'latest_run':self.store.latest(mode),
                'policy':self.store.policy().model_dump(),'settings':settings.model_dump(),
                'budget_note':'按人工分钟变更记录的最近24h/7d预算；45分钟以上视为重型稿，栏目配比用于排期偏好',
                'stats':{'total':len(bs),'needs_research':sum(not b['priority']['ready'] for b in rows if b['status'] not in ('archived','published','out_of_scope')),
                         'ready':sum(b['priority']['ready'] for b in rows if b['status'] not in ('published','archived','scheduled')),
                         'scheduled':sum(b.status=='scheduled' for b in bs),'published':sum(len(b.publications) for b in bs)}}

    def analytics(self,mode: Mode) -> dict:
        items=[]; counts={}; windows={w:[] for w in ('24h','72h','7d','custom')}
        for b in self.store.list(mode):
            counts[b.column]=counts.get(b.column,0)+len(b.publications)
            for p in b.publications:
                snapshots=[m for m in b.metrics if m.publication_id==p.id]
                rows=[]
                for m in snapshots:
                    v=m.model_dump(); target={'24h':24,'72h':72,'7d':168}.get(m.window)
                    v['window_mismatch']=bool(target and abs(m.post_age_hours-target)> {'24h':6,'72h':12,'7d':24}[m.window])
                    # Unknown is null, including missing exposure denominators.
                    numer=[m.likes,m.comments,m.favorites,m.shares]
                    v['interaction_per_view']=(sum(numer)/m.views) if m.views and all(x is not None for x in numer) else None
                    rows.append(v)
                items.append({'brief_id':b.id,'title':p.title,'column':b.column,'url':p.url,'publication_id':p.id,'published_at':p.published_at,'human_minutes':b.actual_human_minutes,'metrics':rows})
        return {'publications':items,'column_counts':counts,'insight':'样本不足时继续观察；不跨帖子年龄比较累计互动，不预测收入。'}
