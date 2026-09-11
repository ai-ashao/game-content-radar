import io
import json
import time
import zipfile
from PIL import Image
import pytest
from conftest import basic_brief, iso
from heybox_content_studio.models import BriefInput


def create(client):
    pack=basic_brief().model_dump()
    r=client.post('/api/import-pack',json={'brief':{k:v for k,v in pack.items() if k in BriefInput.model_fields},'sources':pack['sources'],'claims':pack['claims']})
    assert r.status_code==201,r.text
    return r.json()

def verify(client,b):
    for c in b['claims']:
        r=client.post(f"/api/briefs/{b['id']}/claims/{c['id']}/verify",json={'expected_version':b['version'],'reviewer':'API QA','confirmed':True})
        assert r.status_code==200,r.text;b=r.json()
    return b


def test_health_security_and_static(client):
    assert client.get('/').status_code==200
    assert client.get('/static/app.js').status_code==200
    assert client.get('/api/health').json()['service']=='heybox-content-studio'
    assert 'frame-ancestors' in client.get('/').headers['content-security-policy']
    assert client.post('/api/run',headers={'X-Heybox-Token':'wrong'},json={'mode':'offline'}).status_code==403
    assert client.post('/api/run',headers={'Origin':'https://evil.test'},json={'mode':'offline'}).status_code==403
    assert client.get('/api/meta',headers={'Host':'evil.test'}).status_code==400


def test_import_cannot_preserve_machine_approval(client):
    b=create(client)
    assert b['status']=='needs_research' and b['approval'] is None
    assert b['claims'][0]['status']=='pending'


def test_whole_api_review_and_publication(client):
    b=verify(client,create(client))
    d={'title':b['title'],'body_markdown':'测试作品使用光线引导前进。[C:claim-test]','title_candidates':[],'used_claim_ids':['claim-test']}
    r=client.put(f"/api/briefs/{b['id']}/draft",json={'expected_version':b['version'],'draft':d});assert r.status_code==200,r.text;b=r.json()
    flags={'reviewer':'API QA','facts_checked':True,'media_checked':True,'spoiler_checked':True,'policy_checked':True}
    r=client.post(f"/api/briefs/{b['id']}/approve",json={'expected_version':b['version'],**flags});assert r.status_code==200,r.text;b=r.json()
    r=client.get(f"/api/briefs/{b['id']}/copy?approved=true");assert r.json()['approved'] and '[C:' not in r.json()['text']
    r=client.post(f"/api/briefs/{b['id']}/publish",json={'expected_version':b['version'],'url':'https://www.xiaoheihe.cn/app/bbs/link/99999','published_at':iso(-24)});assert r.status_code==200,r.text;b=r.json()
    r=client.post(f"/api/briefs/{b['id']}/metric",json={'expected_version':b['version'],'metric':{'publication_id':b['publications'][0]['id'],'observed_at':iso(),'likes':10}});assert r.status_code==200,r.text
    assert client.get('/api/analytics').json()['publications'][0]['metrics'][0]['views'] is None


def test_stale_updates_do_not_overwrite(client):
    b=create(client)
    p={'expected_version':b['version'],'status':'in_review'}
    assert client.post(f"/api/briefs/{b['id']}/state",json=p).status_code==200
    assert client.post(f"/api/briefs/{b['id']}/state",json=p).status_code==409


def test_upload_real_image_and_reject_html(client):
    b=create(client);memory=io.BytesIO();Image.new('RGB',(16,16)).save(memory,format='PNG')
    r=client.post(f"/api/briefs/{b['id']}/upload",data={'expected_version':b['version']},files={'file':('test.png',memory.getvalue(),'image/png')});assert r.status_code==200,r.text;b=r.json()
    a=b['assets'][0]
    assert not a['usage_confirmed']
    assert client.get('/api/assets/live/'+a['local_file']).status_code==200
    r=client.post(f"/api/briefs/{b['id']}/upload",data={'expected_version':b['version']},files={'file':('test.png',b'<script>alert(1)</script>','image/png')});assert r.status_code==400
    assert client.get('/api/assets/live/private.txt').status_code==400


def test_untrusted_asset_path_is_not_accepted(client):
    b=create(client)
    r=client.put(f"/api/briefs/{b['id']}/asset",json={'expected_version':b['version'],'asset':{'title':'x','local_file':'../../secret'}})
    assert r.status_code==200 and r.json()['assets'][0]['local_file'] is None


def test_export_zip_contains_audit_facts_not_unrestricted_files(client):
    b=verify(client,create(client))
    r=client.get(f"/api/briefs/{b['id']}/bundle");assert r.status_code==200
    z=zipfile.ZipFile(io.BytesIO(r.content))
    assert {'BRIEF.md','research-pack.json','WRITING_PROMPT.md','MEDIA.json'}<=set(z.namelist())
    pack=json.loads(z.read('research-pack.json'));assert pack['verified_claims'][0]['id']=='claim-test'
    assert '不执行' in pack['instructions']


def wait_job(client,jid):
    for _ in range(80):
        row=client.get('/api/jobs/'+jid).json()
        if row['status'] in ('done','error','interrupted'):return row
        time.sleep(.025)
    raise AssertionError('Job timeout')


def test_example_and_offline_cannot_change_real_workspace(client):
    create(client);before=client.get('/api/dashboard').json()['briefs']
    r=client.post('/api/run',json={'mode':'example'});assert r.status_code==202;assert wait_job(client,r.json()['id'])['status']=='done'
    assert len(client.get('/api/dashboard?mode=example').json()['briefs'])==3
    r=client.post('/api/run',json={'mode':'offline'});assert wait_job(client,r.json()['id'])['status']=='done'
    d=client.get('/api/dashboard').json();assert d['briefs']==before and d['latest_run'] is None
    assert client.get('/api/dashboard?mode=../../').status_code==422


def test_manual_generation_job_returns_outline(client):
    b=verify(client,create(client))
    r=client.post(f"/api/briefs/{b['id']}/generate",json={'expected_version':b['version']})
    result=wait_job(client,r.json()['id'])['result']
    assert result['draft'] is None and result['outline']
    assert client.get('/api/briefs/'+b['id']).json()['drafts']==[]


def test_seeds_idempotent(client):
    client.post('/api/seeds');a=client.get('/api/dashboard').json()
    client.post('/api/seeds');b=client.get('/api/dashboard').json()
    assert a['stats']['total']==b['stats']['total']==12
    assert b['recommended_ids']==[]


def test_example_import_cannot_enter_live(client):
    b=basic_brief().model_dump()
    body={'origin_mode':'example','brief':{k:v for k,v in b.items() if k in BriefInput.model_fields}}
    assert client.post('/api/import-pack',json=body).status_code==400
    assert client.post('/api/import-pack?mode=example',json=body).status_code==201


def test_curation_rechecks_changed_underlying_prices(client):
    b=create(client)
    base={'store':'Steam','region':'CN','currency':'CNY','edition':'base','observed_at':iso(),'price_minor':1200}
    ids=[]
    for i in range(2):
        cid='price-'+str(i);ids.append(cid)
        data={'id':cid,'text':f'价格测试{i}','kind':'price','source_ids':['source-test'],'locator':'测试价格字段','data':{**base,'sku':str(100+i),'price_minor':1200+i*100}}
        r=client.put(f"/api/briefs/{b['id']}/claim",json={'expected_version':b['version'],'claim':data});assert r.status_code==200,r.text;b=r.json()
    b=verify(client,b)
    r=client.post(f"/api/briefs/{b['id']}/curate",json={'expected_version':b['version'],'claim_ids':ids,'kind':'prices'});assert r.status_code==200,r.text
    assert r.json()['summary']['count']==2 and r.json()['summary']['min_price_minor']==1200
    b=r.json()['brief'];derived=b['claims'][-1]
    b=verify(client,b)
    changed=next(x for x in b['claims'] if x['id']==ids[0]);changed['data']['price_minor']=1700
    b=client.put(f"/api/briefs/{b['id']}/claim",json={'expected_version':b['version'],'claim':changed}).json()
    r=client.post(f"/api/briefs/{b['id']}/claims/{derived['id']}/verify",json={'expected_version':b['version'],'reviewer':'QA','confirmed':True})
    assert r.status_code==400 and '重新核验' in r.text


def test_subjects_are_typed_and_isolated(client):
    assert client.put('/api/subjects',json={'id':'subject-test','name':'测试游戏','kind':'game'}).status_code==200
    assert len(client.get('/api/subjects').json())==1
    assert client.get('/api/subjects?mode=example').json()==[]
    assert client.put('/api/subjects',json={'name':'游戏','kind':'CEO'}).status_code==422
