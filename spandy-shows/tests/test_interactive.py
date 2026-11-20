"""Real processes, blocking input, runtime validation and immutable replay."""
import os,time
from pathlib import Path
import pytest
os.environ['SPANDY_EXECUTION_MODE']='trusted-local'
os.environ['SPANDY_TRUST_LOCAL_CODE']='1'
from fastapi.testclient import TestClient
from backend.app import app,attempts,jobs
from backend.schema import Trace

@pytest.fixture
def client():
    attempts.clear()
    with TestClient(app) as c:yield c

def state_until(client,id,predicate):
    deadline=time.monotonic()+30
    while time.monotonic()<deadline:
        state=client.get('/api/jobs/'+id).json()
        if predicate(state):return state
        if state['status'] not in ('queued','running','waiting'):
            raise AssertionError(client.get('/api/jobs/'+id+'/trace').json())
        time.sleep(.03)
    raise AssertionError('Execution did not reach the expected state.')

def waiting(client,id,sequence):
    return state_until(client,id,lambda s:s.get('live') and (s['live'].get('input') or {}).get('id')==sequence)

def done(client,id):
    state_until(client,id,lambda s:s['status'] not in ('queued','running','waiting'))
    trace=client.get('/api/jobs/'+id+'/trace').json();Trace.model_validate(trace);return trace

def answer(client,id,sequence,text):
    response=client.post('/api/jobs/'+id+'/input',json={'id':sequence,'text':text})
    assert response.status_code==200,response.text

PYTHON='print("Started")\na = int(input("First: "))\nb = int(input("Second: "))\nprint(a + b)'

def test_python_imports_custom_function_and_generator_with_live_input(client):
    source='import math\ndef armstrong():\n    n = int(input("Number: "))\n    digits = str(n)\n    total = sum(int(digit) ** len(digits) for digit in digits)\n    print(total == n, math.isqrt(81))\narmstrong()'
    id=client.post('/api/jobs',json={'language':'python','source':source,'interactive':True}).json()['id']
    first=waiting(client,id,1)
    assert first['live']['stdout']=='Number: '
    assert first['live']['input']['line']==3
    prefix=client.get('/api/jobs/'+id+'/trace').json()
    answer(client,id,1,'153')
    trace=done(client,id)
    assert trace['status']=='completed',trace['diagnostics']
    assert trace['steps'][:len(prefix['steps'])]==prefix['steps']
    assert trace['steps'][-1]['stdout']=='Number: True 9\n'
C='#include <stdio.h>\nint main(void) {\n int a, b;\n printf("Started\\nFirst: ");\n scanf("%d", &a);\n printf("Second: ");\n scanf("%d", &b);\n printf("%d\\n", a+b);\n return 0;\n}'
JAVA='import java.util.Scanner;\npublic class Main {\n public static void main(String[] args) {\n Scanner in=new Scanner(System.in);\n System.out.println("Started");\n System.out.print("First: ");\n int a=in.nextInt();\n System.out.print("Second: ");\n int b=in.nextInt();\n System.out.println(a+b);\n }\n}'

@pytest.mark.parametrize('mode',['run','visualize'])
@pytest.mark.parametrize('language,source',[('python',PYTHON),('java',JAVA),('c',C)])
def test_two_reads_same_process(client,mode,language,source):
    id=client.post('/api/jobs',json={'language':language,'source':source,'interactive':True,'execution':mode}).json()['id']
    first=waiting(client,id,1)
    assert first['live']['stdout']=='Started\nFirst: '
    assert first['live']['input']['type']=='integer'
    pid=jobs[id]['process'].pid
    before=client.get('/api/jobs/'+id+'/trace')
    if mode=='visualize':
        assert before.status_code==200
        prefix=before.json();assert len(prefix['steps'])>0
        assert prefix['steps'][-1]['location']['line']==first['live']['input']['line']
    answer(client,id,1,'17')
    second=waiting(client,id,2)
    assert jobs[id]['process'].pid==pid
    assert second['live']['stdout']=='Started\nFirst: Second: '
    assert second['live']['input']['line']>first['live']['input']['line']
    assert client.post('/api/jobs/'+id+'/input',json={'id':1,'text':'9'}).status_code==409
    if mode=='visualize':
        middle=client.get('/api/jobs/'+id+'/trace').json()
        assert middle['steps'][:len(prefix['steps'])]==prefix['steps']
        values=[v['value'] for f in middle['steps'][-1]['frames'] for v in f['locals'].values() if v['kind']=='primitive']
        values += [v['value'] for v in middle['steps'][-1]['globals'].values() if v['kind']=='primitive']
        assert 17 in values
    answer(client,id,2,'25');trace=done(client,id)
    assert trace['status']=='completed'
    assert trace['steps'][-1]['stdout']=='Started\nFirst: Second: 42\n'
    if mode=='visualize':assert len(trace['steps'])>5

@pytest.mark.parametrize('language,source,error',[('python',PYTHON,'ValueError'),('java',JAVA,'InputMismatchException'),('c',C,'requested type')])
def test_invalid_integer_is_real_runtime_failure(client,language,source,error):
    id=client.post('/api/jobs',json={'language':language,'source':source,'interactive':True}).json()['id']
    waiting(client,id,1);answer(client,id,1,'oops');trace=done(client,id)
    assert trace['status']=='failed'
    assert error in str(trace['diagnostics'])
    assert 'Second:' not in trace['steps'][-1]['stdout']

@pytest.mark.parametrize('choice,pattern',[('a','#\n##\n###\n####\n'),('b','####\n###\n##\n#\n'),('c','####\n ###\n  ##\n   #\n'),('d','   #\n  ##\n ###\n####\n')])
def test_user_java_patterns(client,choice,pattern):
    source=Path('tests/fixtures/Main.java').read_text(encoding='utf-8-sig')
    id=client.post('/api/jobs',json={'language':'java','source':source,'interactive':True}).json()['id']
    first=waiting(client,id,1)
    assert first['live']['input']=={'id':1,'line':11,'type':'character'}
    assert first['live']['stdout'].endswith('Enter your choice: ')
    assert 'number of terms' not in first['live']['stdout']
    answer(client,id,1,choice)
    second=waiting(client,id,2)
    assert second['live']['input']=={'id':2,'line':13,'type':'integer'}
    assert '#' not in second['live']['stdout']
    answer(client,id,2,'4');trace=done(client,id)
    assert trace['status']=='completed';assert trace['steps'][-1]['stdout'].endswith(pattern)
    values=[f['locals'] for s in trace['steps'] for f in s['frames']]
    assert any(v.get('n',{}).get('value')==4 for v in values)
    assert len({v.get('i',{}).get('value') for v in values if 'i' in v})>=4
    assert any('j' in v or 'k' in v for v in values)

def test_c_partial_scanf_continues_original_read(client):
    source='#include <stdio.h>\nint main(void) {\n int a,b;\n printf("Two integers: ");\n scanf("%d %d", &a,&b);\n printf("%d",a+b);\n return 0;\n}'
    id=client.post('/api/jobs',json={'language':'c','source':source,'execution':'run','interactive':True}).json()['id']
    first=waiting(client,id,1);answer(client,id,1,'17')
    second=waiting(client,id,2);assert second['live']['input']['line']==first['live']['input']['line']
    answer(client,id,2,'25');trace=done(client,id)
    assert trace['status']=='completed';assert trace['steps'][-1]['stdout']=='Two integers: 42'

def test_c_buffered_newline_does_not_ask_again(client):
    source='#include <stdio.h>\nint main(void) {int n; scanf("%d", &n); int c=getchar(); printf("%d %d",n,c);}'
    id=client.post('/api/jobs',json={'language':'c','source':source,'execution':'run','interactive':True}).json()['id']
    waiting(client,id,1);answer(client,id,1,'12');trace=done(client,id)
    assert trace['status']=='completed',trace;assert trace['steps'][-1]['stdout']=='12 10'

def test_waiting_does_not_use_active_budget_and_cancel_works(client,monkeypatch):
    monkeypatch.setenv('SPANDY_ACTIVE_SECONDS','1')
    id=client.post('/api/jobs',json={'language':'python','source':'n=input("Name: ")\nprint(n)','interactive':True}).json()['id']
    waiting(client,id,1);time.sleep(1.2)
    assert client.get('/api/jobs/'+id).json()['status']=='waiting'
    answer(client,id,1,'Spandy');trace=done(client,id);assert trace['status']=='completed',trace
    id=client.post('/api/jobs',json={'language':'python','source':'input("Name: ")','interactive':True}).json()['id']
    waiting(client,id,1);client.delete('/api/jobs/'+id)
    assert done(client,id)['status']=='cancelled'

def test_input_bounds_and_idle_timeout(client,monkeypatch):
    id=client.post('/api/jobs',json={'language':'python','source':'input("Name: ")','interactive':True}).json()['id']
    waiting(client,id,1)
    assert client.post('/api/jobs/'+id+'/input',json={'id':1,'text':'x'*4096}).status_code==413
    answer(client,id,1,'okay');assert done(client,id)['status']=='completed'
    monkeypatch.setenv('SPANDY_INPUT_IDLE_SECONDS','0.2')
    id=client.post('/api/jobs',json={'language':'python','source':'input("Name: ")','interactive':True}).json()['id']
    waiting(client,id,1);trace=done(client,id)
    assert trace['terminationReason']=='input_timeout';assert trace['steps'][-1]['stdout']=='Name: '
@pytest.mark.parametrize('language,source',[('python','name=input("Name: ")\namount=float(input("Amount: "))\nprint(name,amount)'),('java','import java.util.Scanner;\npublic class Main {public static void main(String[] args) {\n Scanner in=new Scanner(System.in);\n System.out.print("Name: ");\n String name=in.nextLine();\n System.out.print("Amount: ");\n double amount=in.nextDouble();\n System.out.println(name+" "+amount);\n}}'),('c','#include <stdio.h>\nint main(void) {\n char name[30]; double amount;\n printf("Name: ");\n scanf("%29s",name);\n printf("Amount: ");\n scanf("%lf",&amount);\n printf("%s %.1f\\n",name,amount);\n}')])
def test_text_and_float_requests(client,language,source):
    id=client.post('/api/jobs',json={'language':language,'source':source,'interactive':True,'execution':'run'}).json()['id']
    first=waiting(client,id,1);assert first['live']['input']['type']=='text';assert first['live']['stdout']=='Name: '
    answer(client,id,1,'Ada')
    second=waiting(client,id,2);assert second['live']['input']['type']=='number';assert second['live']['stdout']=='Name: Amount: '
    answer(client,id,2,'1.5');trace=done(client,id)
    assert trace['status']=='completed';assert trace['steps'][-1]['stdout']=='Name: Amount: Ada 1.5\n'

def test_user_java_invalid_second_input(client):
    source=Path('tests/fixtures/Main.java').read_text(encoding='utf-8-sig')
    id=client.post('/api/jobs',json={'language':'java','source':source,'interactive':True}).json()['id']
    waiting(client,id,1);answer(client,id,1,'a');waiting(client,id,2);answer(client,id,2,'banana');trace=done(client,id)
    assert trace['status']=='failed';assert 'InputMismatchException' in str(trace['diagnostics'])
    assert trace['diagnostics'][0]['line']==13
    assert trace['steps'][-1]['stdout'].endswith('Enter the number of terms: ')
    assert '#' not in trace['steps'][-1]['stdout']
    assert any(f['locals'].get('ch',{}).get('value')=='a' for s in trace['steps'] for f in s['frames'])
