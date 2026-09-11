from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from heybox_content_studio.models import Brief, Claim, SourceRecord, DraftInput, Settings
from heybox_content_studio.storage import Store
from heybox_content_studio.service import StudioService
from heybox_content_studio.webapp import create_app


def iso(delta=0):
    return (datetime.now(timezone.utc)+timedelta(hours=delta)).isoformat()


def basic_brief(**overrides):
    s=SourceRecord(id='source-test',title='测试原始资料',url='https://example.com/research',source_type='official',role='fact',is_primary=True,read_status='read',summary='测试作品使用光线引导玩家前进。',original_date='2020-01-01',locator='原文第1段',read_at=iso())
    c=Claim(id='claim-test',text='测试作品使用光线引导前进。',source_ids=[s.id],locator='原文第1段')
    defaults=dict(title='测试：从具体场景理解无声引导',column='classic_rediscovery',content_form='classic',pool='evergreen',audience='PC玩家',reader_question='怎样用光线引导玩家？',angle='比较场景中的可见线索',thesis='可见线索能减少不必要的提示',original_contribution='对照具体情景并指出解释限制',reader_value='理解线索如何传达方向',scope_confirmed=True,estimated_human_minutes=10,media_none_reason='仅解释概念，不引用实际游戏画面',sources=[s],claims=[c])
    defaults.update(overrides)
    return Brief(**defaults)


def verify_all(service,b):
    for cid in [c.id for c in b.claims]:
        b=service.verify(b.mode,b.id,b.version,cid,'QA编辑',True)
    return b


def save_and_approve(service,b):
    draft=DraftInput(title=b.title,title_candidates=[b.title,'一个场景怎样传达方向？','从线索看游戏引导'],body_markdown='## 具体观察\n\n测试作品使用光线引导前进。 [C:claim-test]\n\n这是测试解释，需要根据实际材料判断适用范围。',used_claim_ids=[c.id for c in b.claims])
    b=service.save_draft(b.mode,b.id,b.version,draft)
    return service.approve(b.mode,b.id,b.version,'QA编辑',dict(facts_checked=True,media_checked=True,spoiler_checked=True,policy_checked=True))

@pytest.fixture
def service(tmp_path): return StudioService(Store(tmp_path))

@pytest.fixture
def ready(service):
    b=service.store.create(basic_brief())
    return verify_all(service,b)

@pytest.fixture
def client(tmp_path):
    app=create_app(tmp_path)
    with TestClient(app) as c:
        c.headers['X-Heybox-Token']=c.get('/api/meta').json()['csrf_token']
        yield c
