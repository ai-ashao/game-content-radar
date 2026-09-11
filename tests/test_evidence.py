from copy import deepcopy
from datetime import datetime, timezone
import pytest
from heybox_content_studio.models import Claim, MediaAsset, Settings
from heybox_content_studio.validation import claim_problems, draft_gate, text_checks, rating_percent, compute_deal_summary
from conftest import basic_brief, iso, verify_all, save_and_approve


def price(): return {'store':'steam','region':'CN','currency':'CNY','sku':'app-1','edition':'base','observed_at':iso(),'price_minor':1234}

def rating(): return {'platform':'steam','scope':'matching_query_summary','observed_at':iso(),'positive':90,'negative':10,'total_reviews':100,'filters':{'language':'all','review_type':'all','purchase_type':'steam','filter_offtopic_activity':1}}

def make(kind='fact',data=None): return Claim(text='测试主张',kind=kind,source_ids=['source-test'],locator='第1段',data=data or {})


def test_source_discovery_is_not_fact():
    b=basic_brief();b.sources[0].role='discovery'
    assert claim_problems(b.claims[0],b,Settings())


def test_url_only_not_evidence():
    b=basic_brief();b.sources[0].read_status='unread';b.sources[0].summary=''
    assert any('来源' in x for x in claim_problems(b.claims[0],b,Settings()))


def test_no_eligible_no_recommendation(service):
    service.store.create(basic_brief(scope_confirmed=False))
    assert service.dashboard('live')['recommended_ids']==[]


def test_evergreen_old_source_ok_and_expired_deal_block(service):
    b=verify_all(service,service.store.create(basic_brief()))
    assert not draft_gate(b,Settings())
    b.expires_at=iso(-1)
    assert any('截止' in x for x in draft_gate(b,Settings()))


def test_unsupported_history_claim(ready):
    assert text_checks(ready,'史低来啦','')
    assert text_checks(ready,'全网最低价','')
    assert not text_checks(ready,'从具体场景看线索','不代表全Steam排名。')


def test_current_price_needs_context_and_publishing_freshness():
    b=basic_brief();p=make('price',price())
    assert not claim_problems(p,b,Settings(),publishing=True)
    p.data['observed_at']=iso(-1)
    assert any('30分钟' in i for i in claim_problems(p,b,Settings(),publishing=True))
    p.data['observed_at']='bad'
    assert claim_problems(p,b,Settings())


def test_historical_low_requires_actual_history():
    b=basic_brief();p=make('historical_low',price())
    assert any('历史证据' in x for x in claim_problems(p,b,Settings()))


def test_prices_scope_count_duplicate_and_min():
    a=price();b={**price(),'sku':'app-2','price_minor':500}
    r=compute_deal_summary([a,b]);assert r['count']==2 and r['min_price_minor']==500
    with pytest.raises(ValueError):compute_deal_summary([a,a])
    with pytest.raises(ValueError):compute_deal_summary([a,{**b,'region':'US'}])
    with pytest.raises(ValueError):compute_deal_summary([a,{**b,'currency':'USD'}])


def test_rating_ratio_is_not_rating_out_of_ten():
    assert rating_percent(90,10,100)==90
    assert rating_percent(1,2,3)==33.33
    assert rating_percent(0,0,0) is None
    with pytest.raises(ValueError):rating_percent(90,20,100)

@pytest.mark.parametrize('patch',[{'scope':'recent_30_days'},{'total_reviews':101},{'positive':0,'negative':0,'total_reviews':0},{'filters':{'review_type':'positive'}},{'filters':'bad'}])
def test_invalid_review_scope(patch):
    b=basic_brief();c=make('rating',{**rating(),**patch});assert claim_problems(c,b,Settings())


def test_quote_original_date_and_source_required():
    b=basic_brief();c=make('quote',{'original_text':'原话','quote_mode':'translation'})
    assert claim_problems(c,b,Settings())
    c.data['original_date']='2019-01-01'; assert not claim_problems(c,b,Settings())
    b.sources[0].is_primary=False; assert claim_problems(c,b,Settings())


def test_role_is_work_specific():
    b=basic_brief();c=make('role',{'person':'某人','work':'某作','role':'发行商','as_of':'2020-01-01'})
    assert claim_problems(c,b,Settings())
    c.data['role']='总监'; assert not claim_problems(c,b,Settings())


def test_detail_needs_visual_location():
    b=basic_brief();c=make('detail',{'platform':'PC','version':'1.0','conditions':'测试场景','steps':'观察灯光','asset_ids':['asset-test']})
    assert claim_problems(c,b,Settings())
    b.assets=[MediaAsset(id='asset-test',url='https://example.com/video',purpose='evidence')]
    assert any('时间码' in x for x in claim_problems(c,b,Settings()))
    b.assets[0].timecode='01:10'; assert not claim_problems(c,b,Settings())


def test_unfounded_experience_design_intent_and_old_quote(ready):
    for title in ('我玩了1000小时才知道','开发者故意让玩家迷路','最新采访公开','99%的玩家不知道'):
        assert text_checks(ready,title,'')


def test_free_types_not_interchangeable():
    b=basic_brief();c=make('free_offer',{'platform':'steam','region':'CN','offer_type':'trial','end_at':iso(24)});c.status='verified';b.claims=[c]
    assert not claim_problems(c,b,Settings())
    assert text_checks(b,'永久入库','')
    c.data['end_at']=iso(-1);assert claim_problems(c,b,Settings())


def test_spoilers_and_media_confirmation(service):
    b=verify_all(service,service.store.create(basic_brief(spoiler_level='major_story')))
    assert any('剧透' in x for x in draft_gate(b,Settings(),publishing=True))
    b.assets=[MediaAsset(purpose='cover',spoiler_level='major_story')]
    issues=draft_gate(b,Settings(),publishing=True)
    assert any('封面' in x for x in issues) and any('使用条件' in x for x in issues)
