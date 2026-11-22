import copy
from backend.python_worker import execute
from backend.schema import Trace

def run(source, stdin=''):
    trace=execute({'source':source,'stdin':stdin})
    Trace.model_validate(trace)
    return trace

def test_before_line_and_output():
    t=run('x = 1\nx = 2\nprint(x)')
    lines=[s for s in t['steps'] if s['event']=='line']
    assert 'x' not in lines[0]['globals']
    assert lines[1]['globals']['x']['value']==1
    assert lines[2]['globals']['x']['value']==2 and lines[2]['stdout']==''
    assert t['steps'][-1]['stdout']=='2\n'

def test_shared_cycle_immutable():
    t=run('a = []\nb = a\na.append(a)\na.append(7)')
    before=[s for s in t['steps'] if s['event']=='line' and s['location']['line']==4][0]
    final=t['steps'][-1]
    ref=final['globals']['a']['ref']
    assert final['globals']['b']['ref']==ref
    assert before['objects'][ref]['items']==[{'kind':'reference','type':'list','ref':ref}]
    assert len(final['objects'][ref]['items'])==2

def test_recursion_arguments_returns():
    t=run('def factorial(n):\n    if n <= 1: return 1\n    return n * factorial(n-1)\nanswer = factorial(4)')
    assert max(len(s['frames']) for s in t['steps'])==4
    assert t['steps'][-1]['globals']['answer']['value']==24
    ids=[f['id'] for s in t['steps'] if s['event']=='call' for f in s['frames'][-1:]]
    assert len(set(ids))==4
    assert any(s.get('returnValue',{}).get('value')==24 for s in t['steps'] if s.get('returnValue'))

def test_class_and_no_user_inspection():
    t=run('class Box:\n    def __init__(self): self.value = 3\n    def __repr__(self): raise Exception("do not call")\nb = Box()')
    assert t['status']=='completed'
    ref=t['steps'][-1]['globals']['b']['ref']
    assert t['steps'][-1]['objects'][ref]['fields']['value']['value']==3

def test_loops_input_exception():
    t=run('n = int(input())\ntotal = 0\nfor i in range(n):\n    total += i\nprint(total)\n1/0','4\n')
    assert t['status']=='failed'
    assert t['steps'][-1]['stdout']=='6\n'
    assert any(s['event']=='exception' for s in t['steps'])

def test_limits_and_syntax():
    assert run('while True:\n    pass')['terminationReason']=='step_limit'
    assert len(run('print("x"*9000)')['steps'][-1]['stdout'])==9001
    assert run('def broken(')['terminationReason']=='syntax_error'
    assert run('import math\nprint(math.sqrt(81))')['steps'][-1]['stdout']=='9.0\n'

def test_truncated_values():
    t=run('values = list(range(100))\ns = "x" * 1000')
    s=t['steps'][-1]
    assert s['objects'][s['globals']['values']['ref']]['truncated']
    assert s['globals']['s']['truncated']

def test_integer_precision_and_unsupported():
    t=run('x = 9007199254740993')
    assert t['steps'][-1]['globals']['x']['value']=='9007199254740993'
    t=run('x = object()')
    assert t['steps'][-1]['globals']['x']['kind']=='unavailable'
