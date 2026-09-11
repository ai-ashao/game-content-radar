import json
from pathlib import Path
import pytest
from heybox_content_studio.webapp import ImportPack


@pytest.mark.parametrize('filename',[
    '01-buy-smart-review-scope.json',
    '02-classic-portal2-coop.json',
    '03-creator-miyazaki-bloodborne.json',
])
def test_reference_packs_import_but_do_not_auto_approve(client,filename):
    raw=json.loads((Path('examples')/filename).read_text(encoding='utf-8'))
    ImportPack.model_validate(raw)
    response=client.post('/api/import-pack',json=raw)
    assert response.status_code==201,response.text
    brief=response.json()
    assert brief['approval'] is None
    assert not brief['priority']['ready']
    assert all(c['status']=='pending' for c in brief['claims'])
    assert not brief['drafts']
