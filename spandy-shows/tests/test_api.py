import asyncio,json,os,time
import pytest
os.environ['SPANDY_EXECUTION_MODE']='trusted-local'
os.environ['SPANDY_TRUST_LOCAL_CODE']='1'
from fastapi.testclient import TestClient
from backend.app import app,attempts
from backend.runner import execute_job
from backend.schema import Program,Trace
from backend.limits import MAX_SOURCE_BYTES, MAX_REQUEST_BYTES

@pytest.fixture
def client():
    attempts.clear()
    with TestClient(app) as c:yield c

def wait(client,id):
    for _ in range(300):
        state=client.get('/api/jobs/'+id).json()
        if state['status'] not in ('queued','running'):return state
        time.sleep(.03)
    raise AssertionError('Job never finished')

def test_submit_trace_and_persistence(client):
    payload={'language':'python','source':'x = 1\nprint(x)','title':'API verification','stdin':'','selectedStep':2}
    response=client.post('/api/jobs',json=payload)
    assert response.status_code==202
    id=response.json()['id'];assert wait(client,id)['status']=='completed'
    trace=client.get('/api/jobs/'+id+'/trace').json()
    Trace.model_validate(trace)
    assert trace['steps'][-1]['stdout']=='1\n'
    for endpoint in ('programs','shares'):
        saved=client.post('/api/'+endpoint,json=payload)
        assert saved.status_code==201
        got=client.get('/api/'+endpoint+'/'+saved.json()['id'])
        assert got.json()==payload

def test_validation_and_origins(client):
    assert client.post('/api/jobs',json={'language':'ruby','source':'x'}).status_code==422
    assert client.post('/api/jobs',json={'language':'python','source':'x'*(MAX_SOURCE_BYTES+1)}).status_code==422
    assert client.post('/api/jobs',content='x'*(MAX_REQUEST_BYTES+1)).status_code==413
    assert client.post('/api/jobs',json={'language':'python','source':'x'},headers={'Origin':'https://untrusted.example'}).status_code==403
    assert client.get('/api/jobs/missing').status_code==404

def test_rate_limit(client):
    for _ in range(20):assert client.post('/api/shares',json={'language':'python','source':'x=1'}).status_code==201
    assert client.post('/api/shares',json={'language':'python','source':'x=1'}).status_code==429

def test_cancel_and_tree(client):
    # This deliberate trusted-local test blocks before any trace line can complete.
    response=client.post('/api/jobs',json={'language':'python','source':'__import__("time").sleep(20)'})
    id=response.json()['id'];time.sleep(.2)
    assert client.delete('/api/jobs/'+id).status_code==200
    assert wait(client,id)['status']=='cancelled'

def test_resource_limits(client):
    for source,reason in [('while True:\n    pass','step_limit')]:
        id=client.post('/api/jobs',json={'language':'python','source':source}).json()['id']
        assert wait(client,id)['status']=='truncated'
        assert client.get('/api/jobs/'+id+'/trace').json()['terminationReason']==reason

def test_default_does_not_enable_local_execution(monkeypatch):
    monkeypatch.setenv('SPANDY_EXECUTION_MODE','trusted-local');monkeypatch.delenv('SPANDY_TRUST_LOCAL_CODE',raising=False)
    t=asyncio.run(execute_job({'id':'boundary-check','program':Program(language='python',source='x=1'),'cancel':asyncio.Event()}))
    assert t['terminationReason']=='worker_unavailable'

def test_schema_rejects_worker_injection():
    with pytest.raises(ValueError):Trace.model_validate({'schemaVersion':99,'html':'<script>bad()</script>'})

def test_rapid_submissions_and_queued_cancellation(client):
    ids=[client.post('/api/jobs',json={'language':'python','source':'__import__("time").sleep(0.4)\nprint("done")'}).json()['id'] for _ in range(3)]
    client.delete('/api/jobs/'+ids[-1])
    assert wait(client,ids[-1])['status']=='cancelled'
    for id in ids[:2]:
        assert wait(client,id)['status']=='completed'
        assert client.get('/api/jobs/'+id+'/trace').json()['steps'][-1]['stdout']=='done\n'

def test_compiler_api(client):
    payload={'language':'python','source':'print(sum(range(5000)))','execution':'run'}
    response=client.post('/api/jobs',json=payload)
    assert response.status_code==202
    id=response.json()['id']
    assert wait(client,id)['status']=='completed'
    result=client.get('/api/jobs/'+id+'/trace').json()
    assert len(result['steps'])==1
    assert result['steps'][0]['stdout']=='12497500\n'
    assert client.post('/api/jobs',json={**payload,'execution':'guess'}).status_code==422
