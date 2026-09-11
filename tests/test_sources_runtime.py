import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
import pytest
from heybox_content_studio.collectors.reviews import SteamReviewsClient
from heybox_content_studio.collectors.steam import SteamNewsCollector, SteamStoreCollector
from heybox_content_studio.collectors.epic import EpicFreeGamesCollector
from heybox_content_studio.collection import collect_run
from heybox_content_studio.http import HttpClient, FetchError
from heybox_content_studio.models import Settings, SourceItem
from heybox_content_studio.storage import Store
from heybox_content_studio.jobs import Jobs
from heybox_content_studio.runtime import start,stop,health,belongs
from heybox_content_studio.legacy import migrate,available_archives
from conftest import iso

class JsonHTTP:
    def __init__(self,data):self.data=data;self.calls=[]
    def get_json(self,url,**kwargs):self.calls.append((url,kwargs));return self.data


def test_review_query_summary_and_privacy():
    data={'success':1,'query_summary':{'total_positive':90,'total_negative':10,'total_reviews':100,'review_score':8},'reviews':[{'review':'测试评论','author':{'steamid':'secret-user-id'},'voted_up':True}]}
    h=JsonHTTP(data);r=SteamReviewsClient(h).collect(620)
    assert r['recommended_percent']==90 and r['total_reviews']==100 and len(h.calls)==3
    assert 'author' not in json.dumps(r['samples']) and 'secret-user-id' not in json.dumps(r)
    assert r['filters']['review_type']=='all' and r['scope']=='matching_query_summary'
    assert r['samples'][0]['sample_only'] is True


def test_news_not_all_official():
    h=JsonHTTP({'appnews':{'newsitems':[{'title':'news','contents':'test','gid':'1','feedname':'pcgamer','url':'https://example.com/news'},{'title':'update','contents':'patch','gid':'2','feedname':'steam_community_announcements','url':'https://store.steampowered.com/news/1'}]}})
    r=SteamNewsCollector(h,{620:'Portal 2'}).collect()
    assert r.items[0].source_type=='media' and r.items[1].source_type=='official'


def test_current_deal_is_not_historical():
    row={'id':620,'name':'Game','discount_percent':50,'original_price':2000,'final_price':1000,'currency':'CNY'}
    h=JsonHTTP({'specials':{'items':[row]},'top_sellers':{'items':[row]}})
    r=SteamStoreCollector(h).collect()
    assert len(r.items)==1 and not r.items[0].metrics['historical_low_verified']


def test_epic_free_to_keep_not_f2p():
    offers={'promotionalOffers':[{'promotionalOffers':[{'startDate':iso(-24),'endDate':iso(24),'discountSetting':{'discountPercentage':0}}]}]}
    h=JsonHTTP({'data':{'Catalog':{'searchStore':{'elements':[{'id':'paid','title':'Paid','promotions':offers,'price':{'totalPrice':{'originalPrice':1000,'discountPrice':0}},'productSlug':'paid'},{'id':'f2p','title':'F2P','promotions':offers,'price':{'totalPrice':{'originalPrice':0,'discountPrice':0}}}]}}}})
    items=EpicFreeGamesCollector(h).collect().items
    assert len(items)==1 and items[0].game_name=='Paid'


def test_private_networks_blocked():
    for url in ['file:///etc/passwd','http://127.0.0.1/test','http://169.254.169.254/','http://localhost/','http://10.0.0.1/']:
        with pytest.raises(FetchError):HttpClient.validate_url(url)


def test_collection_single_source_failure_is_soft(tmp_path,monkeypatch):
    from heybox_content_studio import collection
    from heybox_content_studio.collectors.base import CollectorResult
    store=Store(tmp_path);store.save_settings(Settings(enabled_sources={'steam_store':True,'epic':True}))
    def bad(self):raise FetchError('429 rate limit','rate_limited')
    def good(self):return CollectorResult(source='epic',items=[SourceItem(id='1',source='epic',source_url='https://example.com/game',source_type='official',game_name='游戏',title='限免线索',category='free_game')])
    monkeypatch.setattr(collection.SteamStoreCollector,'collect',bad);monkeypatch.setattr(collection.EpicFreeGamesCollector,'collect',good)
    r=collect_run(store)
    assert r['status']=='partial' and r['created']==1
    assert not store.list('live')[0].drafts
    again=collect_run(store);assert again['created']==0
    assert store.latest('live')['run_id']!=r['run_id']


def test_jobs_interrupted_recovery_and_conflict(tmp_path):
    j=Jobs(tmp_path)
    from heybox_content_studio.storage import atomic_json,ConflictError
    running=j.start('test',lambda progress:time.sleep(.2))
    with pytest.raises(ConflictError):j.start('duplicate',lambda p:None)
    time.sleep(.25)
    assert j.get(running['id'])['status']=='done'
    atomic_json(j.directory/'orphan.json',{'id':'orphan','status':'running','name':'old'})
    j2=Jobs(tmp_path);assert j2.get('orphan')['status']=='interrupted'


def test_legacy_dryrun_copy_hash_and_no_deletion(tmp_path):
    source=tmp_path/'old';target=tmp_path/'new';p=source/'reports/2026-09-11/xhh/edited/reach-pick.md';p.parent.mkdir(parents=True);p.write_text('人工修改稿')
    (source/'data').mkdir();(source/'data/radar.db').write_bytes(b'old sqlite placeholder')
    before={r['path']:r['sha256'] for r in migrate(source,target)['files']}
    assert not (target/'legacy').exists()
    result=migrate(source,target,copy=True)
    assert result['copied'] and p.read_text()=='人工修改稿'
    assert {r['path']:r['sha256'] for r in result['files']}==before
    assert len(available_archives(target))==2


def freeport():
    with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]


def test_detached_service_survives_launcher_and_isolation(tmp_path,monkeypatch):
    root=tmp_path/'service';root.mkdir();port=freeport()
    src=str(Path(__file__).resolve().parents[1]/'src');monkeypatch.setenv('PYTHONPATH',src)
    cmd=[sys.executable,'-m','heybox_content_studio','--root',str(root),'start','--port',str(port),'--no-browser']
    subprocess.run(cmd,check=True,capture_output=True,timeout=20)
    # The launcher is gone; the separate session still answers real HTTP.
    try:
        info=health(port);assert belongs(info,root)
        assert start(root,port,False)['pid']==info['pid']
        with pytest.raises(RuntimeError):start(tmp_path/'other',port,False)
        with pytest.raises(RuntimeError):stop(tmp_path/'other',port)
        assert belongs(health(port),root)
    finally:stop(root,port)
    assert health(port) is None
