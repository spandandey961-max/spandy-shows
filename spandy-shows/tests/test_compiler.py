"""Compiler mode executes to completion independently of the visualization step cap."""
import asyncio, os
import pytest
from backend.runner import execute_job, availability
from backend.schema import JobRequest, Trace

def run(language, source, stdin=''):
    os.environ['SPANDY_EXECUTION_MODE']='trusted-local'
    os.environ['SPANDY_TRUST_LOCAL_CODE']='1'
    if not availability()[language]:
        pytest.skip('Required engine is unavailable.')
    result=asyncio.run(execute_job({'id':'compiler-check','program':JobRequest(language=language,source=source,stdin=stdin,execution='run'),'cancel':asyncio.Event()}))
    Trace.model_validate(result)
    return result

@pytest.mark.parametrize('language,source',[
 ('python','total = 0\nfor n in range(5000):\n    total += n\nprint(total)'),
 ('java','public class Main { public static void main(String[] args) { int total=0; for(int n=0;n<5000;n++) total+=n; System.out.println(total); } }'),
 ('c','#include <stdio.h>\nint main(void) { int total=0; for(int n=0;n<5000;n++) total+=n; printf("%d\\n",total); return 0; }')
])
def test_runs_past_visualization_step_limit(language,source):
    result=run(language,source)
    assert result['status']=='completed',result['diagnostics']
    assert len(result['steps'])==1
    assert result['steps'][0]['stdout'].replace('\r\n','\n')=='12497500\n'

@pytest.mark.parametrize('language,source',[
 ('python','a = int(input())\nb = int(input())\nprint(a + b)'),
 ('java','import java.util.Scanner; public class Main { public static void main(String[] args) { Scanner s = new Scanner(System.in); System.out.println(s.nextInt()+s.nextInt()); } }'),
 ('c','#include <stdio.h>\nint main(void) { int a,b; scanf("%d%d",&a,&b); printf("%d\\n",a+b); return 0; }')
])
def test_compiler_uses_real_stdin(language,source):
    result=run(language,source,'17\n25')
    assert result['status']=='completed',result['diagnostics']
    assert result['steps'][0]['stdout'].replace('\r\n','\n')=='42\n'

@pytest.mark.parametrize('stdin,expected',[('121','Palindrome'),('123','Not a palindrome')])
def test_palindrome_compiler(stdin,expected):
    from tests.test_input import PALINDROME
    result=run('c',PALINDROME,stdin)
    assert result['status']=='completed',result['diagnostics']
    assert result['steps'][0]['stdout']=='Enter an integer: '+expected

@pytest.mark.parametrize('stdin,expected',[('','EOF'),('abc','Invalid')])
def test_c_compiler_returns_failed_input_to_program(stdin,expected):
    source='#include <stdio.h>\nint main(void) { int n; int read = scanf("%d",&n); puts(read == EOF ? "EOF" : "Invalid"); return 0; }'
    result=run('c',source,stdin)
    assert result['status']=='completed',result['diagnostics']
    assert result['steps'][0]['stdout']==expected+'\n'

def test_python_compiler_imports_and_complete_pattern():
    result=run('python','import math\nprint(math.isqrt(81))\nfor row in range(1,31):\n    print("*" * row)')
    assert result['status']=='completed'
    assert result['steps'][0]['stdout']=='9\n'+''.join('*'*n+'\n' for n in range(1,31))

@pytest.mark.parametrize('language,source',[
 ('python','print("before")\n1/0'),
 ('java','public class Main { public static void main(String[] args) { System.out.println("before"); int zero=0; System.out.println(1/zero); } }'),
 ('c','#include <stdio.h>\nint main(void) { puts("before"); return 1; }')
])
def test_compiler_preserves_output_on_runtime_failure(language,source):
    result=run(language,source)
    assert result['status']=='failed'
    assert result['terminationReason']=='runtime_error'
    assert result['steps'][0]['stdout'].replace('\r\n','\n')=='before\n'
    assert result['diagnostics']
