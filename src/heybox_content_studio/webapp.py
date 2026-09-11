from __future__ import annotations

import hashlib
import io
import json
import os
import re
import secrets
from pathlib import Path
from urllib.parse import urlsplit
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import Field
from PIL import Image

from . import SERVICE_ID, __version__
from .models import (Record, Mode, BriefInput, Claim, DraftInput, MediaAsset, MetricSnapshot, PolicyReview, Settings, SourceRecord, Subject, now_iso, uid)
from .storage import Store, ConflictError, safe_id, fingerprint
from .service import StudioService
from .jobs import Jobs
from .collection import collect_run
from .demo import create_seeds
from .writing import generate, research_bundle, bundle_zip, plain_publish_text, outline
from .legacy import available_archives
from .validation import compute_deal_summary, rating_percent

class Versioned(Record):
    expected_version: int = Field(ge=1)

class BriefPatch(Versioned):
    brief: BriefInput
class SourcePatch(Versioned):
    source: SourceRecord
class ClaimPatch(Versioned):
    claim: Claim
class AssetPatch(Versioned):
    asset: MediaAsset
class DraftPatch(Versioned):
    draft: DraftInput
class VerifyPatch(Versioned):
    reviewer: str = Field(min_length=1,max_length=100)
    confirmed: bool = False
class ApprovePatch(Versioned):
    reviewer: str = Field(min_length=1,max_length=100)
    facts_checked: bool = False
    media_checked: bool = False
    spoiler_checked: bool = False
    policy_checked: bool = False
class SchedulePatch(Versioned):
    scheduled_at: str
class PublishPatch(Versioned):
    url: str
    published_at: str
class MetricPatch(Versioned):
    metric: MetricSnapshot
class StatePatch(Versioned):
    status: str
class RunInput(Record):
    mode: str = Field(default='live',pattern='^(live|example|offline)$')
class SteamInput(Versioned):
    appid: int = Field(gt=0)
    reviews: bool = True
class CurationInput(Versioned):
    claim_ids: list[str] = Field(min_length=1,max_length=30)
    kind: str = Field(pattern='^(prices|ratings)$')
class ImportPack(Record):
    origin_mode: Mode | None = None
    brief: BriefInput
    sources: list[SourceRecord] = Field(default_factory=list,max_length=50)
    claims: list[Claim] = Field(default_factory=list,max_length=100)
    assets: list[MediaAsset] = Field(default_factory=list,max_length=30)


def create_app(base_dir: str|Path='.') -> FastAPI:
    root=Path(base_dir).resolve(); store=Store(root); studio=StudioService(store); jobs=Jobs(root)
    app=FastAPI(title='盒友编辑台',version=__version__)
    token=secrets.token_urlsafe(32)
    instance=hashlib.sha256(str(root).encode()).hexdigest()[:24]
    app.state.store=store; app.state.studio=studio; app.state.jobs=jobs
    app.add_middleware(TrustedHostMiddleware,allowed_hosts=['localhost','127.0.0.1','testserver'])

    @app.middleware('http')
    async def local_security(request: Request, call_next):
        if request.method not in ('GET','HEAD','OPTIONS'):
            if not secrets.compare_digest(request.headers.get('x-heybox-token',''),token):
                return JSONResponse(status_code=403,content={'detail':'本地安全会话已过期，请刷新页面后重试'})
            origin=request.headers.get('origin')
            if origin and urlsplit(origin).netloc != request.headers.get('host'):
                return JSONResponse(status_code=403,content={'detail':'拒绝跨来源写入本地编辑台'})
            try:
                if int(request.headers.get('content-length',0)) > 12_000_000:
                    return JSONResponse(status_code=413,content={'detail':'上传内容过大'})
            except ValueError:
                return JSONResponse(status_code=400,content={'detail':'错误的Content-Length'})
        response=await call_next(request)
        response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        response.headers['Referrer-Policy']='no-referrer'
        return response

    @app.exception_handler(FileNotFoundError)
    async def missing(_,exc): return JSONResponse(status_code=404,content={'detail':str(exc)})
    @app.exception_handler(ConflictError)
    async def conflict(_,exc): return JSONResponse(status_code=409,content={'detail':str(exc)})
    @app.exception_handler(ValueError)
    async def invalid(_,exc): return JSONResponse(status_code=400,content={'detail':str(exc)})

    static=Path(__file__).parent/'web_ui'
    app.mount('/static',StaticFiles(directory=static),name='static')
    @app.get('/',response_class=HTMLResponse)
    def home(): return HTMLResponse((static/'index.html').read_text(encoding='utf-8'))
    @app.get('/api/health')
    def health():
        return {'service':SERVICE_ID,'version':__version__,'instance':instance,'pid':os.getpid(),'status':'busy' if jobs.active_id else 'ready','active_job':jobs.active()}
    @app.get('/api/meta')
    def meta():
        return {'service':SERVICE_ID,'version':__version__,'instance':instance,'csrf_token':token,'time':now_iso(),'project_root':str(root),'llm_mode':store.settings().llm_mode}
    @app.get('/api/dashboard')
    def dashboard(mode: Mode='live'): return studio.dashboard(mode)
    @app.post('/api/run',status_code=202)
    def run(data: RunInput): return jobs.start('更新选题池',lambda p:collect_run(store,data.mode,p))
    @app.get('/api/jobs/active')
    def active(): return {'job':jobs.active()}
    @app.get('/api/jobs/{jid}')
    def job(jid: str): return jobs.get(jid)
    @app.post('/api/seeds')
    def seeds(mode: Mode='live'): return {'ids':create_seeds(store,mode)}

    @app.post('/api/briefs',status_code=201)
    def create(data: BriefInput,mode: Mode='live'): return studio.view(studio.create(mode,data))
    @app.get('/api/briefs/{bid}')
    def brief(bid: str,mode: Mode='live'): return studio.view(store.get(mode,bid))
    @app.put('/api/briefs/{bid}')
    def update(bid: str,data: BriefPatch,mode: Mode='live'): return studio.view(studio.update(mode,bid,data.expected_version,data.brief))
    @app.put('/api/briefs/{bid}/source')
    def source(bid: str,data: SourcePatch,mode: Mode='live'): return studio.view(studio.source(mode,bid,data.expected_version,data.source))
    @app.put('/api/briefs/{bid}/claim')
    def claim(bid: str,data: ClaimPatch,mode: Mode='live'): return studio.view(studio.claim(mode,bid,data.expected_version,data.claim))
    @app.post('/api/briefs/{bid}/claims/{cid}/verify')
    def verify(bid: str,cid: str,data: VerifyPatch,mode: Mode='live'): return studio.view(studio.verify(mode,bid,data.expected_version,cid,data.reviewer,data.confirmed))
    @app.put('/api/briefs/{bid}/asset')
    def asset(bid: str,data: AssetPatch,mode: Mode='live'):
        # File paths are server-owned, never accepted from JSON.
        b=store.get(mode,bid)
        existing=next((a for a in b.assets if a.id==data.asset.id),None)
        data.asset.local_file=existing.local_file if existing else None
        return studio.view(studio.asset(mode,bid,data.expected_version,data.asset))
    @app.delete('/api/briefs/{bid}/{kind}/{item_id}')
    def remove(bid: str,kind: str,item_id: str,data: Versioned,mode: Mode='live'):
        return studio.view(studio.remove(mode,bid,data.expected_version,kind,item_id))

    @app.post('/api/briefs/{bid}/upload')
    async def upload(bid: str,mode: Mode='live',expected_version: int=Form(...),file: UploadFile=File(...)):
        store.get(mode,bid)
        raw=await file.read(10_000_001)
        if len(raw)>10_000_000: raise HTTPException(413,'单张图片不可超过10MB')
        try:
            with Image.open(io.BytesIO(raw)) as im:
                if im.format not in ('PNG','JPEG','WEBP') or im.width*im.height>24_000_000:
                    raise ValueError('只支持PNG/JPEG/WebP，最多2400万像素')
                fmt=im.format
                im.verify()
        except Exception as exc:
            raise ValueError('无法验证图片文件；不接收SVG、HTML或伪装扩展名') from exc
        name=uid()+{'PNG':'.png','JPEG':'.jpg','WEBP':'.webp'}[fmt]
        directory=store.mode_dir(mode)/'uploads'; directory.mkdir(parents=True,exist_ok=True)
        path=directory/name; path.write_bytes(raw)
        media=MediaAsset(title=(file.filename or '截图')[:300],local_file=name,purpose='evidence',usage_note='请说明本人截图或来源使用条件，上传不等于已核验')
        try:
            b=studio.asset(mode,bid,expected_version,media)
        except Exception:
            path.unlink(missing_ok=True); raise
        return studio.view(b)

    @app.get('/api/assets/{mode}/{filename}')
    def asset_file(mode: Mode,filename: str):
        if not re.fullmatch(r'[a-f0-9]{16}\.(png|jpg|webp)',filename): raise ValueError('错误的素材ID')
        directory=store.mode_dir(mode)/'uploads'; path=directory/filename
        if not path.resolve().is_relative_to(directory.resolve()) or not path.is_file(): raise FileNotFoundError('素材不存在')
        return FileResponse(path)

    @app.post('/api/import-pack',status_code=201)
    def import_pack(data: ImportPack,mode: Mode='live'):
        from .models import Brief
        if data.origin_mode=='example' and mode=='live': raise ValueError('示例研究包不能导入真实资料库')
        for c in data.claims: c.status='pending'; c.verified_at=None; c.verified_by=None
        for a in data.assets: a.local_file=None; a.usage_confirmed=False
        for s in data.sources: s.provenance='import'
        for group in (data.claims,data.assets,data.sources):
            if len({x.id for x in group})!=len(group): raise ValueError('导入包含重复ID')
        b=Brief(**data.brief.model_dump(),sources=data.sources,claims=data.claims,assets=data.assets,mode=mode,status='needs_research')
        return studio.view(store.create(b))

    @app.post('/api/briefs/{bid}/steam',status_code=202)
    def enrich_steam(bid: str,data: SteamInput,mode: Mode='live'):
        b=store.get(mode,bid)
        if mode=='example': raise ValueError('示例工作区不请求真实游戏数据')
        if b.version!=data.expected_version: raise ConflictError('页面版本已过期')
        def task(progress):
            from .http import HttpClient
            from .collectors.details import SteamDetailsClient
            from .collectors.reviews import SteamReviewsClient
            cfg=store.settings(); http=HttpClient(timeout=cfg.request_timeout,max_requests=6)
            progress('读取Steam详情与查询口径摘要')
            try:
                detail=SteamDetailsClient(http).collect(data.appid,cfg.country)
                review=None; warning=None
                if data.reviews:
                    try: review=SteamReviewsClient(http).collect(data.appid)
                    except Exception as exc: warning=str(exc)
            finally: http.close()
            source=SourceRecord(title=str(detail['name'])+' · Steam数据快照',url=detail['source_url'],source_type='official',role='fact',publisher='Steam商店',read_status='read',read_at=detail['observed_at'],summary=json.dumps(detail,ensure_ascii=False,indent=2),is_primary=True,provenance='collector',locator='appdetails / 当前AppID返回字段')
            def op(b):
                from .service import invalidate
                invalidate(b)
                b.sources.append(source)
                if detail.get('price_minor') is not None:
                    b.claims.append(Claim(text=f"{detail['name']}：{detail['region']}区当前价格 {detail['price_minor']/100:g} {detail.get('currency') or '币种待查'}；不是历史低价证明。",kind='price',source_ids=[source.id],locator='price_overview.final',data={k:detail[k] for k in ('store','region','currency','sku','edition','observed_at','end_at','price_minor')},notes='价格是该app的商店快照，购买包与券后价需另核对。'))
                if review:
                    sr=SourceRecord(title='Steam评价查询摘要',url=review['source_url'],source_type='official',role='fact',publisher='Steam',read_status='read',read_at=review['observed_at'],summary=json.dumps(review,ensure_ascii=False,indent=2)[:16000],is_primary=True,provenance='collector',locator='query_summary + filters')
                    b.sources.append(sr)
                    ratio=review['recommended_percent']
                    text=f"在本次同口径查询中，{detail['name']}获 {review['positive']} 条推荐 / {review['total_reviews']} 条评价"+(f"（{ratio:g}%）" if ratio is not None else '，无足够评价，不计0分')
                    b.claims.append(Claim(text=text,kind='rating',source_ids=[sr.id],locator='query_summary.total_positive / total_reviews',data={k:v for k,v in review.items() if k not in ('samples','warnings')}))
                b.assets.append(MediaAsset(title=str(detail['name'])+' · 官方商店封面',url=detail.get('header_image') or '',source_id=source.id,publisher='Steam商店/发行方',usage_note='官方图片链接，使用条件需人工确认'))
            new=store.mutate(mode,bid,data.expected_version,op,'steam_evidence_added_unverified')
            return {'brief_id':bid,'version':new.version,'warning':warning,'message':'数据已读取，主张仍待人工核验'}
        return jobs.start('补充Steam资料',task)

    @app.post('/api/briefs/{bid}/curate')
    def curate(bid: str,data: CurationInput,mode: Mode='live'):
        b=store.get(mode,bid)
        selected=[c for c in b.claims if c.id in data.claim_ids]
        if len(selected)!=len(set(data.claim_ids)) or any(c.status!='verified' for c in selected): raise ValueError('请仅选择存在且已核验的事实')
        if data.kind=='prices':
            if any(c.kind!='price' for c in selected): raise ValueError('只能从价格主张计算选购清单')
            result=compute_deal_summary([c.data for c in selected])
            text=f"本次清单共{result['count']}款，当前最低 {result['min_price_minor']/100:g} {result['currency']}；限{result['region']}区{result['store']}本次清单。"
            kind='fact'; d={**result,'selected_claim_ids':data.claim_ids}
        else:
            if any(c.kind!='rating' or c.data.get('platform')!='steam' for c in selected): raise ValueError('本次仅支持同口径Steam评价排序')
            scopes={json.dumps({'filters':c.data.get('filters'),'scope':c.data.get('scope')},sort_keys=True) for c in selected}
            if len(scopes)!=1: raise ValueError('不同评价查询口径不可混排')
            accepted=[c for c in selected if c.data.get('total_reviews',0)>=store.settings().min_review_count]
            if not accepted: raise ValueError('没有达到最小评价样本量的候选')
            ranked=sorted(accepted,key=lambda c:(rating_percent(c.data['positive'],c.data['negative'],c.data['total_reviews']),c.data['total_reviews']),reverse=True)
            result={'rows':[{'claim_id':c.id,'text':c.text,'ratio':rating_percent(c.data['positive'],c.data['negative'],c.data['total_reviews'])} for c in ranked], 'excluded':len(selected)-len(accepted)}
            text=f'本次{len(ranked)}款候选的Steam推荐率筛选；不代表全Steam排名。'
            kind='ranking'; d={'universe':'人工选入的已核验候选池','metric':'Steam同口径推荐比例','sample_size':len(ranked),'sort_rule':'推荐率降序，同率按评价数降序','dedupe_rule':'按选入主张去重；同一游戏不同版本需人工筛除','as_of':now_iso(),'entity_kind':'game','computed':result}
        d['selected_claim_ids']=data.claim_ids
        d['selected_claim_fingerprints']={c.id:fingerprint({'text':c.text,'data':c.data}) for c in selected}
        claim=Claim(text=text,kind=kind,source_ids=list({i for c in selected for i in c.source_ids}),locator='根据已选主张由程序计算，详见data',data=d)
        return {'summary':result,'brief':studio.view(studio.claim(mode,bid,data.expected_version,claim))}

    @app.post('/api/briefs/{bid}/generate',status_code=202)
    def generate_draft(bid: str,data: Versioned,mode: Mode='live'):
        b=store.get(mode,bid)
        if b.version!=data.expected_version: raise ConflictError('页面版本已过期')
        def task(progress):
            progress('整理资料并生成待审稿；不会自动批准或发布')
            result=generate(b,store.settings())
            if result.get('draft'):
                new=studio.save_draft(mode,bid,data.expected_version,DraftInput.model_validate(result['draft']))
                result['brief_id']=bid; result['version']=new.version
            return result
        return jobs.start('生成待审稿',task)
    @app.put('/api/briefs/{bid}/draft')
    def save_draft(bid: str,data: DraftPatch,mode: Mode='live'): return studio.view(studio.save_draft(mode,bid,data.expected_version,data.draft))
    @app.post('/api/briefs/{bid}/approve')
    def approve(bid: str,data: ApprovePatch,mode: Mode='live'): return studio.view(studio.approve(mode,bid,data.expected_version,data.reviewer,data.model_dump()))
    @app.post('/api/briefs/{bid}/schedule')
    def schedule(bid: str,data: SchedulePatch,mode: Mode='live'): return studio.view(studio.schedule(mode,bid,data.expected_version,data.scheduled_at))
    @app.post('/api/briefs/{bid}/publish')
    def publish(bid: str,data: PublishPatch,mode: Mode='live'): return studio.view(studio.publication(mode,bid,data.expected_version,data.url,data.published_at))
    @app.post('/api/briefs/{bid}/metric')
    def metric(bid: str,data: MetricPatch,mode: Mode='live'): return studio.view(studio.metric(mode,bid,data.expected_version,data.metric))
    @app.post('/api/briefs/{bid}/state')
    def state(bid: str,data: StatePatch,mode: Mode='live'): return studio.view(studio.status(mode,bid,data.expected_version,data.status))
    @app.get('/api/briefs/{bid}/copy')
    def copy_text(bid: str,mode: Mode='live',approved: bool=False):
        b=store.get(mode,bid)
        if not b.drafts: raise ValueError('尚无稿件')
        if approved:
            if mode=='example': raise ValueError('示例不可复制为正式发布稿')
            studio.require_approved(b)
        prefix='' if approved else ('【示例，不可发布】\n\n' if mode=='example' else '【待审稿，请勿直接发布】\n\n')
        return {'text':prefix+plain_publish_text(b),'approved':approved}
    @app.get('/api/briefs/{bid}/bundle')
    def bundle(bid: str,mode: Mode='live'):
        return Response(bundle_zip(store.get(mode,bid),root),media_type='application/zip',headers={'Content-Disposition':f'attachment; filename="heybox-research-{safe_id(bid)}.zip"'})
    @app.get('/api/briefs/{bid}/prompt')
    def prompt(bid: str,mode: Mode='live'): return research_bundle(store.get(mode,bid))
    @app.get('/api/analytics')
    def analytics(mode: Mode='live'): return studio.analytics(mode)
    @app.get('/api/settings')
    def settings(): return store.settings()
    @app.put('/api/settings')
    def save_settings(data: Settings): store.save_settings(data); return {'saved':True}
    @app.put('/api/policy')
    def policy(data: PolicyReview): store.save_policy(data); return {'saved':True}
    @app.get('/api/subjects')
    def subjects(mode: Mode='live'): return store.subjects(mode)
    @app.put('/api/subjects')
    def subject(data: Subject,mode: Mode='live'): store.save_subject(mode,data); return {'saved':True}
    @app.get('/api/legacy')
    def legacy():
        records=available_archives(root)
        return {'files':[{'id':i,**r} for i,r in enumerate(records)],'note':'历史资料只读，旧SEO分不参与新流程'}
    @app.get('/api/legacy/{index}')
    def legacy_file(index: int):
        records=available_archives(root)
        if index<0 or index>=len(records): raise FileNotFoundError('归档不存在')
        p=(root/records[index]['download_path']).resolve()
        if not p.is_relative_to(root): raise ValueError('非法归档路径')
        return FileResponse(p,filename=p.name,media_type='application/octet-stream')
    return app
