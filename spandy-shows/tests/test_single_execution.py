"""Single-choice source, normal menu loops and exactly-once live responses."""
from pathlib import Path
import pytest
from backend.app import jobs
from tests.test_compiler import run
from tests.test_interactive import client, waiting, answer, done

ROOT = Path(__file__).resolve().parents[1]
ONCE = (ROOT/'public/examples/java-utility-once.java').read_text(encoding='utf-8')
MENU = (ROOT/'tests/fixtures/utility-menu.java').read_text(encoding='utf-8-sig')
TITLE = 'SIMPLE JAVA UTILITY PROGRAM'

@pytest.mark.parametrize('choice,value,expected',[
    ('1','121','121 is a Palindrome number.'),
    ('2','153','153 is an Armstrong number.'),
    ('3','29','29 is a Prime number.'),
    ('4','6','0, 1, 1, 2, 3, 5'),
    ('5','5','Factorial of 5 = 120'),
    ('6','Spandy','ydnapS'),
    ('7','123','Sum of digits of 123 is 6'),
    ('8','2024','2024 is a Leap Year.'),
    ('9','10','Binary equivalent of 10 is: 1010'),
    ('0','','Exiting program. Goodbye!'),
])
def test_one_choice_java_utility_completes_once(choice,value,expected):
    trace = run('java',ONCE,choice+'\n'+value+'\n')
    assert trace['status']=='completed',trace['diagnostics']
    stdout = trace['steps'][-1]['stdout']
    assert stdout.count(TITLE)==1
    assert stdout.count(expected)==1

@pytest.mark.parametrize('mode',['run','visualize'])
def test_factorial_live_reads_complete_same_process_once(client,mode):
    response = client.post('/api/jobs',json={'language':'java','source':ONCE,'execution':mode,'interactive':True})
    assert response.status_code==202,response.text
    id = response.json()['id']
    state = waiting(client,id,1)
    assert state['live']['input']['type']=='integer' # hasNextInt, before nextInt
    pid = jobs[id]['process'].pid
    answer(client,id,1,'5')
    state = waiting(client,id,2)
    assert jobs[id]['process'].pid==pid
    assert state['live']['stdout'].count(TITLE)==1
    assert state['live']['stdout'].endswith('Enter an integer to find its factorial: ')
    assert client.post('/api/jobs/'+id+'/input',json={'id':1,'text':'5'}).status_code==409
    answer(client,id,2,'5')
    trace = done(client,id)
    assert trace['status']=='completed',trace['diagnostics']
    assert trace['steps'][-1]['stdout'].count(TITLE)==1
    assert trace['steps'][-1]['stdout'].count('Factorial of 5 = 120')==1
    if mode=='visualize':
        assert len(trace['steps'])>20
        assert any(f['name']=='findFactorial' for s in trace['steps'] for f in s['frames'])

def test_original_menu_loop_is_a_single_process_not_a_second_execution(client):
    id = client.post('/api/jobs',json={'language':'java','source':MENU,'execution':'run','interactive':True}).json()['id']
    waiting(client,id,1)
    pid = jobs[id]['process'].pid
    answer(client,id,1,'5');waiting(client,id,2);answer(client,id,2,'5')
    state = waiting(client,id,3)
    assert jobs[id]['process'].pid==pid
    assert state['live']['stdout'].count(TITLE)==2
    assert state['live']['stdout'].count('Factorial of 5 = 120')==1
    answer(client,id,3,'0')
    trace = done(client,id)
    assert trace['status']=='completed',trace['diagnostics']
    assert trace['steps'][-1]['stdout'].count('Goodbye!')==1

@pytest.mark.parametrize('mode',['run','visualize'])
def test_one_choice_reverse_string_retains_scanner_newline_semantics(client,mode):
    id = client.post('/api/jobs',json={'language':'java','source':ONCE,'execution':mode,'interactive':True}).json()['id']
    waiting(client,id,1);answer(client,id,1,'6')
    state = waiting(client,id,2)
    assert state['live']['input']['type']=='text'
    answer(client,id,2,'Spandy')
    trace = done(client,id)
    assert trace['status']=='completed',trace['diagnostics']
    assert trace['steps'][-1]['stdout'].count(TITLE)==1
    assert trace['steps'][-1]['stdout'].count('ydnapS')==1

def test_invalid_menu_choice_is_handled_without_restarting(client):
    id = client.post('/api/jobs',json={'language':'java','source':ONCE,'execution':'run','interactive':True}).json()['id']
    waiting(client,id,1);answer(client,id,1,'oops')
    trace = done(client,id)
    assert trace['status']=='completed',trace['diagnostics']
    assert trace['steps'][-1]['stdout'].count(TITLE)==1
    assert trace['steps'][-1]['stdout'].count('Invalid input. Exiting...')==1
