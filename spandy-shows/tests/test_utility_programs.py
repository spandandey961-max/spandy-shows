"""Regressions from the user's full utility program and compiler screenshots."""
import asyncio
from pathlib import Path
import pytest
from pydantic import ValidationError
from backend.java_source import java_source_info
from backend.python_worker import execute
from backend.runner import execute_job, availability
from backend.schema import JobRequest, Program, Trace
from backend.limits import MAX_SOURCE_LINES, MAX_SOURCE_BYTES
from tests.test_interactive import client, waiting, answer, done

UTILITY=Path(__file__).with_name('fixtures').joinpath('utility.py').read_text(encoding='utf-8-sig')
RESPONSES='1\n121\n2\n153\n3\n29\n4\n6\n5\n5\n6\nSpandy\n7\n123\n8\n2024\n9\n10\n0\n'

@pytest.mark.parametrize('mode',['run','visualize'])
def test_exact_user_python_utility_all_nine_choices(mode):
    trace=execute({'source':UTILITY,'stdin':RESPONSES,'execution':mode})
    Trace.model_validate(trace)
    assert trace['status']=='completed',trace['diagnostics']
    out=trace['steps'][-1]['stdout']
    for expected in ('121 is a Palindrome','153 is an Armstrong','29 is a Prime','0, 1, 1, 2, 3, 5','Factorial of 5 = 120','ydnapS','Sum of digits of 123 is 6','2024 is a Leap Year','Binary equivalent of 10 is: 1010','Goodbye!'):
        assert expected in out
    if mode=='visualize':assert len(trace['steps'])>300

def test_python_unnamed_handlers_and_pattern_nodes_with_caught_errors():
    trace=execute({'source':UTILITY,'stdin':'1\ninvalid\n0\n'})
    Trace.model_validate(trace)
    assert trace['status']=='completed'
    assert 'Invalid input.' in trace['steps'][-1]['stdout']

@pytest.mark.parametrize('mode',['run','visualize'])
def test_exact_python_utility_with_all_nineteen_live_responses(client,mode):
    id=client.post('/api/jobs',json={'language':'python','source':UTILITY,'execution':mode,'interactive':True}).json()['id']
    for sequence,response in enumerate(RESPONSES.splitlines(),1):
        state=waiting(client,id,sequence)
        assert state['live']['stdout']
        answer(client,id,sequence,response)
    trace=done(client,id)
    assert trace['status']=='completed',trace['diagnostics']
    assert 'Goodbye!' in trace['steps'][-1]['stdout']
    assert 'Binary equivalent of 10 is: 1010' in trace['steps'][-1]['stdout']

@pytest.mark.parametrize('mode',['run','visualize'])
@pytest.mark.parametrize('language',['python','java','c'])
def test_twenty_live_responses_in_one_execution(client,mode,language):
    source={
        'python':'total = 0\nfor i in range(20):\n    n = int(input("Number: "))\n    total += n\nprint(total)',
        'java':'import java.util.Scanner;\npublic class ManyInputs {\n public static void main(String[] args) {\n Scanner scanner = new Scanner(System.in);\n int total=0;\n for(int i=0;i<20;i++) {\n System.out.print("Number: ");\n int n=scanner.nextInt();\n total+=n;\n }\n System.out.println(total);\n }\n}',
        'c':'#include <stdio.h>\nint main(void) {\n int total=0;\n for(int i=0;i<20;i++) {\n int n;\n printf("Number: ");\n scanf("%d", &n);\n total+=n;\n }\n printf("%d\\n", total);\n return 0;\n}',
    }[language]
    id=client.post('/api/jobs',json={'language':language,'source':source,'execution':mode,'interactive':True}).json()['id']
    for sequence in range(1,21):
        state=waiting(client,id,sequence)
        assert state['live']['input']['type']=='integer'
        assert state['live']['stdout']=='Number: '*sequence
        answer(client,id,sequence,str(sequence))
    trace=done(client,id)
    assert trace['status']=='completed',trace['diagnostics']
    assert trace['steps'][-1]['stdout']=='Number: '*20+'210\n'

@pytest.mark.parametrize('source,filename,entry',[
    ('public class UtilityProgram { public static void main(String args[]) {} }','UtilityProgram.java','UtilityProgram'),
    ('class Helper {}\npublic final class App { public static void main(String... args) {} }','App.java','App'),
    ('package examples; public class App { public static void main(String[] args) {} }','App.java','examples.App'),
    ('// public class Fake {}\nclass Box {}\nclass App { public static void main(String[] args) {} }','App.java','App'),
    ('@Example(type=Other.class) public class App {}','App.java','App'),
])
def test_java_metadata_uses_declared_class(source,filename,entry):
    assert java_source_info(source)=={'sourceFile':filename,'entryClass':entry}

NAMED_JAVA='''package examples;
import java.util.Scanner;
class Box {
    int value;
    Box(int value) { this.value = value; }
    int doubled() { return value * 2; }
}
public class UtilityProgram {
    public static void main(String[] args) {
        Scanner scanner = new Scanner(System.in);
        System.out.print("Number: ");
        int n = scanner.nextInt();
        Box box = new Box(n);
        System.out.println(box.doubled() + " " + Integer.toBinaryString(n));
    }
}'''

@pytest.mark.parametrize('mode',['run','visualize'])
def test_named_java_package_functions_objects_and_live_input(client,mode):
    id=client.post('/api/jobs',json={'language':'java','source':NAMED_JAVA,'execution':mode,'interactive':True}).json()['id']
    state=waiting(client,id,1)
    assert state['live']['input']=={'id':1,'line':12,'type':'integer'}
    assert state['live']['stdout']=='Number: '
    answer(client,id,1,'12')
    trace=done(client,id)
    assert trace['status']=='completed',trace['diagnostics']
    assert trace['sourceFile']=='UtilityProgram.java'
    assert trace['steps'][-1]['stdout']=='Number: 24 1100\n'
    if mode=='visualize':
        assert any(f['name']=='doubled' for s in trace['steps'] for f in s['frames'])
        assert any(o['type']=='examples.Box' for s in trace['steps'] for o in s['objects'].values())
        assert all(s['location'] is None or s['location']['file']=='UtilityProgram.java' for s in trace['steps'])

@pytest.mark.parametrize('language',['python','java','c'])
@pytest.mark.parametrize('mode',['run','visualize'])
def test_1100_line_source_with_real_input_after_line_1000(client,language,mode):
    padding=('# padding\n' if language=='python' else '// padding\n')*1100
    body={
        'python':'n = int(input("Number: "))\nprint(n * 2)',
        'java':'import java.util.Scanner;\npublic class LongProgram {\n public static void main(String[] args) {\n Scanner scanner = new Scanner(System.in);\n System.out.print("Number: ");\n int n = scanner.nextInt();\n System.out.println(n * 2);\n }\n}',
        'c':'#include <stdio.h>\nint main(void) {\n int n;\n printf("Number: ");\n scanf("%d", &n);\n printf("%d\\n", n * 2);\n return 0;\n}',
    }[language]
    source=padding+body
    assert len(source.splitlines())>1100
    if language!='python':assert len(source.encode())>12000
    response=client.post('/api/jobs',json={'language':language,'source':source,'execution':mode,'interactive':True})
    assert response.status_code==202,response.text
    id=response.json()['id'];state=waiting(client,id,1)
    assert state['live']['input']['line']>1000
    assert state['live']['input']['type']=='integer'
    answer(client,id,1,'21');trace=done(client,id)
    assert trace['status']=='completed',trace['diagnostics']
    assert trace['steps'][-1]['stdout']=='Number: 42\n'
    if mode=='visualize':assert any(s['location'] and s['location']['line']>1000 for s in trace['steps'])

def test_1000_executed_python_lines_and_object_changes():
    source='class Box:\n    def __init__(self): self.value = 0\nbox = Box()\n'+'box.value += 1\n'*1000+'print(box.value)'
    trace=execute({'source':source})
    Trace.model_validate(trace)
    assert trace['status']=='completed'
    assert len(trace['steps'])>1000
    assert trace['steps'][-1]['stdout']=='1000\n'
    final=trace['steps'][-1]
    ref=final['globals']['box']['ref']
    assert final['objects'][ref]['fields']['value']['value']==1000
    assert any(s['objects'].get(ref,{}).get('fields',{}).get('value',{}).get('value')==0 for s in trace['steps'])

@pytest.mark.parametrize('language',['java','c'])
@pytest.mark.parametrize('mode',['run','visualize'])
def test_1000_executed_native_lines_and_object_changes(language,mode):
    if not availability()[language]:pytest.skip('Required compiler/debugger not installed.')
    source={
        'java':'class Box { int value = 0; }\npublic class ThousandLines {\n public static void main(String[] args) {\n Box box = new Box();\n'+'box.value++;\n'*1000+'System.out.println(box.value);\n}\n}',
        'c':'#include <stdio.h>\nstruct Box { int value; };\nint main(void) {\n struct Box box = {0};\n'+'box.value++;\n'*1000+'printf("%d\\n", box.value);\nreturn 0;\n}',
    }[language]
    trace=asyncio.run(execute_job({'id':'long-native-code','program':JobRequest(language=language,source=source,execution=mode),'cancel':asyncio.Event()}))
    Trace.model_validate(trace)
    assert trace['status']=='completed',trace['diagnostics']
    assert trace['steps'][-1]['stdout']=='1000\n'
    if mode=='visualize':
        assert len(trace['steps'])>1000
        assert any(obj.get('fields',{}).get('value',{}).get('value')==1000 for step in trace['steps'] for obj in step['objects'].values())

def test_source_boundaries_are_shared_by_jobs_and_saves():
    Program(language='python',source='# line\n'*1000+'print(1)')
    with pytest.raises(ValidationError):Program(language='python',source='pass\n'*(MAX_SOURCE_LINES+1))
    with pytest.raises(ValidationError):Program(language='python',source='#'+'x'*MAX_SOURCE_BYTES)
    with pytest.raises(ValidationError):Program(language='python',source='#'+'☀'*(MAX_SOURCE_BYTES//2))
