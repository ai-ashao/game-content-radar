import json
import pytest
from pydantic import ValidationError
from heybox_content_studio.models import BriefInput, Claim, SourceRecord, Settings, MetricSnapshot, Subject
from heybox_content_studio.storage import atomic_json, json_read, ConflictError, Store
from conftest import basic_brief


def test_form_column_guard():
    with pytest.raises(ValidationError): BriefInput(title='x',column='buy_smart',content_form='classic')

@pytest.mark.parametrize('id',['../file','bad" onmouseover="x','abc/slash',''])
def test_record_ids_not_html_or_paths(id):
    with pytest.raises(ValidationError): Claim(id=id,text='x')


def test_dates_require_timezone():
    with pytest.raises(ValidationError): BriefInput(title='x',expires_at='2026-09-11')


def test_unknown_metrics_are_not_zero():
    m=MetricSnapshot(publication_id='post',observed_at='2026-09-11T01:00:00Z')
    assert m.views is None and m.likes is None
    with pytest.raises(ValidationError): MetricSnapshot(publication_id='post',observed_at='x',likes=-1)


def test_settings_no_keyword_radar_sources():
    with pytest.raises(ValidationError): Settings(enabled_sources={'steam_players':True})
    with pytest.raises(ValidationError): Settings(column_mix={'buy_smart':100})


def test_atomic_write_and_corruption_is_visible(tmp_path):
    p=tmp_path/'data.json'; atomic_json(p,{'test':'中文'}); assert json_read(p)=={'test':'中文'}
    assert not list(tmp_path.glob('*.tmp'))
    p.write_text('bad json')
    with pytest.raises(json.JSONDecodeError): json_read(p)


def test_optimistic_concurrency_and_atomic_rollback(service):
    b=service.store.create(basic_brief())
    b2=service.status('live',b.id,b.version,'needs_research')
    with pytest.raises(ConflictError): service.status('live',b.id,b.version,'archived')
    assert service.store.get('live',b.id).version==b2.version
    def invalid(b):
        b.title='changed'; raise ValueError('stop')
    with pytest.raises(ValueError): service.store.mutate('live',b.id,b2.version,invalid,'bad')
    assert service.store.get('live',b.id).title==b2.title


def test_create_once_mode_isolation(service):
    a=basic_brief(origin_key='stable'); b,created=service.store.create_once(a)
    _,again=service.store.create_once(basic_brief(origin_key='stable'))
    _,demo=service.store.create_once(basic_brief(origin_key='stable',mode='example'))
    assert created and not again and demo
    assert len(service.store.list('live'))==1 and len(service.store.list('example'))==1


def test_subject_kind_cannot_be_guessed():
    s=Subject(name='制作人',kind='person')
    assert not s.confirmed and s.familiarity=='unknown'
