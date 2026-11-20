import json,sqlite3
import pytest
from fastapi.testclient import TestClient
from backend.app import app,attempts

@pytest.fixture
def device(tmp_path,monkeypatch):
    monkeypatch.setenv('SPANDY_DESKTOP_DATA',str(tmp_path))
    monkeypatch.setenv('SPANDY_DESKTOP_TOKEN','test-desktop-session')
    attempts.clear()
    with TestClient(app,headers={'X-Spandy-Token':'test-desktop-session'}) as client:yield client,tmp_path

def payload(**values):return dict(language='python',source='import math\nprint(math.isqrt(81))',title='Square root',stdin='',selectedStep=2,**values)

def test_named_program_roundtrip_and_reopen(device):
    client,folder=device
    created=client.post('/api/library/programs',json=payload()).json()
    id=created['id'];assert created['source']==payload()['source']
    listing=client.get('/api/library/programs').json()
    assert listing[0]['title']=='Square root' and 'source' not in listing[0]
    assert (folder/'programs.sqlite3').is_file()
    assert client.patch('/api/library/programs/'+id,json={'title':'  Maths homework  '}).json()['title']=='Maths homework'
    updated=payload();updated.update(title='Maths homework',source='print(10)',selectedStep=0)
    assert client.put('/api/library/programs/'+id,json=updated).status_code==200
    with TestClient(app,headers={'X-Spandy-Token':'test-desktop-session'}) as reopened:
        stored=reopened.get('/api/library/programs/'+id).json()
        assert stored['source']=='print(10)' and stored['created']==created['created']
    assert len(client.get('/api/library/programs').json())==1
    assert client.get('/api/library/backup').json()['programs'][0]['source']=='print(10)'
    assert client.delete('/api/library/programs/'+id).status_code==200
    assert client.get('/api/library/programs').json()==[]

def test_device_library_requires_own_session(device):
    client,_=device
    assert client.get('/api/library/programs',headers={'X-Spandy-Token':'wrong'}).status_code==401
    assert client.post('/api/jobs',headers={'X-Spandy-Token':'wrong'},json={'language':'python','source':'print(1)'}).status_code==401
    assert client.get('/api/library/programs',headers={'Origin':'https://foreign.example'}).status_code==403

def test_invalid_names_do_not_overwrite_saved_code(device):
    client,_=device
    item=client.post('/api/library/programs',json=payload()).json();id=item['id']
    for name in ('   ','x'*81,'Name\nnext'):
        assert client.patch('/api/library/programs/'+id,json={'title':name}).status_code==422
    assert client.get('/api/library/programs/'+id).json()['source']==payload()['source']
    assert client.put('/api/library/programs/missing',json=payload()).status_code==404

def test_names_are_data_and_programs_have_no_expiry(device):
    client,folder=device
    program=payload();program['title']='../CON: My program'
    item=client.post('/api/library/programs',json=program).json()
    with sqlite3.connect(folder/'programs.sqlite3') as db:db.execute('UPDATE library SET created=1,updated=1')
    assert client.get('/api/library/programs/'+item['id']).status_code==200
    assert len(client.get('/api/library/programs').json())==1

def test_web_edition_has_no_desktop_library(monkeypatch):
    monkeypatch.delenv('SPANDY_DESKTOP_DATA',raising=False)
    monkeypatch.delenv('SPANDY_DESKTOP_TOKEN',raising=False)
    with TestClient(app) as client:assert client.get('/api/library/programs').status_code==404
