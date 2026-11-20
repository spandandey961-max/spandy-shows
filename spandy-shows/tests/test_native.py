import asyncio,json,os
from pathlib import Path
import pytest
from backend.schema import Program
from backend.runner import execute_job,availability

FIXTURES=Path(__file__).parent/'examples.json'

def run(language,source,stdin=''):
    os.environ['SPANDY_EXECUTION_MODE']='trusted-local'
    os.environ['SPANDY_TRUST_LOCAL_CODE']='1'
    return asyncio.run(execute_job({'id':'adapter-check','program':Program(language=language,source=source,stdin=stdin),'cancel':asyncio.Event()}))

@pytest.mark.parametrize('language',['java','c'])
def test_native_assignment_output(language):
    if not availability()[language]:pytest.skip('Required compiler/debugger not installed.')
    data=json.loads(FIXTURES.read_text(encoding='utf-8'))
    ex=next(e for e in data[language] if e['id']=='variables')
    t=run(language,ex['source'])
    assert t['status']=='completed',t['diagnostics']
    assert t['steps'][-1]['stdout'].strip()=='15'
    assert any(v.get('value')==10 for s in t['steps'] for f in s['frames'] for v in f['locals'].values())
    assert any(v.get('value')==15 for s in t['steps'] for f in s['frames'] for v in f['locals'].values())

@pytest.mark.parametrize('language',['java','c'])
def test_native_recursion_and_identity(language):
    if not availability()[language]:pytest.skip('Required compiler/debugger not installed.')
    data=json.loads(FIXTURES.read_text(encoding='utf-8'))
    ex=next(e for e in data[language] if e['id']=='recursion')
    t=run(language,ex['source'])
    assert t['status']=='completed',t['diagnostics']
    assert t['steps'][-1]['stdout'].strip()=='24'
    assert max(len(s['frames']) for s in t['steps'])>=5

def test_c_pointer():
    if not availability()['c']:pytest.skip('C engine missing.')
    data=json.loads(FIXTURES.read_text(encoding='utf-8'))
    ex=next(e for e in data['c'] if e['id']=='pointers')
    t=run('c',ex['source'])
    assert t['status']=='completed',t['diagnostics']
    assert t['steps'][-1]['stdout'].strip()=='7'
    assert any(f['locals'].get('pointer',{}).get('kind')=='reference' for s in t['steps'] for f in s['frames'])

@pytest.mark.parametrize('language',['java','c'])
def test_native_errors(language):
    if not availability()[language]:pytest.skip('Required compiler/debugger not installed.')
    data=json.loads(FIXTURES.read_text(encoding='utf-8'))
    ex=next(e for e in data[language] if e['id']=='error')
    t=run(language,ex['source'])
    assert t['status']=='failed',t['diagnostics']
    assert t['terminationReason']=='runtime_error'
    assert any(s['event']=='exception' for s in t['steps'])

@pytest.mark.parametrize('language',['java','c'])
def test_native_compilation_failure(language):
    if not availability()[language]:pytest.skip('Required compiler/debugger not installed.')
    t=run(language,'this is not a program')
    assert t['terminationReason']=='compilation_error'
    assert not t['steps'] and t['diagnostics']

def test_java_shared_array_mutation_and_cycle():
    if not availability()['java']:pytest.skip('Java engine missing.')
    source='''public class Main {
 public static void main(String[] args) {
  Object[] original = {null};
  Object[] alias = original;
  alias[0] = original;
  System.out.println(original.length);
 }
}'''
    t=run('java',source)
    assert t['status']=='completed',t['diagnostics']
    states=[s for s in t['steps'] if s['frames'] and 'alias' in s['frames'][-1]['locals']]
    before,after=states[0],states[-1]
    oid=after['frames'][-1]['locals']['original']['ref']
    assert after['frames'][-1]['locals']['alias']['ref']==oid
    assert before['objects'][oid]['items'][0]['kind']=='null'
    assert after['objects'][oid]['items'][0]['ref']==oid

def test_c_struct_and_array_values():
    if not availability()['c']:pytest.skip('C engine missing.')
    source='''#include <stdio.h>
struct Point { int x; int y; };
int main(void) {
 struct Point point = {2, 3};
 int values[2] = {1, 2};
 point.x = 5;
 values[1] = 7;
 printf("%d %d", point.x, values[1]);
 return 0;
}'''
    t=run('c',source)
    assert t['status']=='completed',t['diagnostics']
    s=[s for s in t['steps'] if s['frames']][-1]
    frame=s['frames'][-1]['locals']
    assert s['objects'][frame['point']['ref']]['fields']['x']['value']==5
    assert s['objects'][frame['values']['ref']]['items'][1]['value']==7
