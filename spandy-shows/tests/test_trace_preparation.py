"""Full real traces, early immutable prefixes, and repeated execution."""
import asyncio,os,time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from backend.app import app,attempts
from backend.runner import execute_job
from backend.schema import JobRequest,Trace
from backend.limits import MAX_STEPS

os.environ['SPANDY_EXECUTION_MODE']='trusted-local'
os.environ['SPANDY_TRUST_LOCAL_CODE']='1'
PATTERN=Path(__file__).with_name('fixtures').joinpath('pattern.c').read_text()
EXPECTED='    *\n   * *\n  * * *\n * * * *\n* * * * *\n'

def run(language,source,mode='visualize'):
 return asyncio.run(execute_job({'id':'preparation-check','program':JobRequest(language=language,source=source,execution=mode),'cancel':asyncio.Event()}))

@pytest.mark.parametrize('iteration',range(3))
def test_user_c_pattern_completes_repeatedly(iteration):
 trace=run('c',PATTERN);Trace.model_validate(trace)
 assert trace['status']=='completed',trace['diagnostics']
 assert trace['steps'][0]['stdout']==''
 assert trace['steps'][-1]['event']=='completed'
 assert trace['steps'][-1]['stdout']==EXPECTED
 assert {f['locals']['i']['value'] for s in trace['steps'] for f in s['frames'] if 'i' in f['locals']}>=set(range(1,6))
 if iteration==0:assert run('c',PATTERN,'run')['steps'][-1]['stdout']==EXPECTED

@pytest.mark.parametrize('language,source',[
 ('python','total=0\nfor i in range(1000):\n    total+=i\nprint(total)'),
 ('java','public class Main {\n public static void main(String[] args) {\n int total=0;\n for(int i=0;i<350;i++) {\n total+=i;\n }\n System.out.println(total);\n }\n}'),
 ('c','#include <stdio.h>\nint main(void) {\n int total=0;\n for(int i=0;i<350;i++) {\n total+=i;\n }\n printf("%d\\n",total);\n return 0;\n}')])
def test_real_traces_exceed_previous_step_cap(language,source):
 trace=run(language,source);Trace.model_validate(trace)
 assert trace['status']=='completed',trace['diagnostics']
 assert 600<len(trace['steps'])<MAX_STEPS
 assert int(trace['steps'][-1]['stdout'])==(499500 if language=='python' else 61075)

def test_c_global_and_local_shadow_are_distinct_observations():
 trace=run('c','#include <stdio.h>\nint value=9;\nint main(void) {\n int value=3;\n int *alias=&value;\n *alias=7;\n printf("%d",value);\n return 0;\n}')
 assert trace['status']=='completed',trace['diagnostics']
 assert trace['steps'][-1]['stdout']=='7'
 state=next(s for s in reversed(trace['steps']) if s['frames'])
 assert state['globals']['value']['value']==9
 assert state['frames'][-1]['locals']['value']['value']==7
 assert state['frames'][-1]['locals']['alias']['kind']=='reference'

def test_first_real_prefix_arrives_before_pattern_completion():
 attempts.clear()
 with TestClient(app) as client:
  id=client.post('/api/jobs',json={'language':'c','source':PATTERN,'interactive':True}).json()['id']
  deadline=time.monotonic()+30;prefix=None
  while time.monotonic()<deadline:
   state=client.get('/api/jobs/'+id).json()
   if state.get('live',{}).get('traceSteps',0):
    prefix=client.get('/api/jobs/'+id+'/trace').json();break
   assert state['status'] in ('queued','running'),state
   time.sleep(.03)
  assert prefix and state['status']=='running'
  assert prefix['steps'][0]['stdout']==''
  while time.monotonic()<deadline:
   if client.get('/api/jobs/'+id).json()['status'] not in ('queued','running'):break
   time.sleep(.05)
  trace=client.get('/api/jobs/'+id+'/trace').json()
  assert trace['status']=='completed',trace['diagnostics']
  assert trace['steps'][:len(prefix['steps'])]==prefix['steps']
  assert trace['steps'][-1]['stdout']==EXPECTED
