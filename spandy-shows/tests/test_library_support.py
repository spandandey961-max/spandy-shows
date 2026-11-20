"""Real library execution and source-only visualization, without canned traces."""
import asyncio
import pytest
from backend.python_worker import execute
from backend.runner import availability, execute_job
from backend.schema import JobRequest, Trace

PYTHON = '''import math
import json
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
from functools import reduce
import random
import statistics
@dataclass
class Box:
    value: int
    def double(self):
        return self.value * 2
def numbers():
    yield from range(1, 4)
box = Box(math.isqrt(81))
values = list(numbers())
print(box.double(), sum(x ** 2 for x in values))
print(Counter("banana")["a"], reduce(lambda a, b: a + b, values))
print(Decimal("0.1") + Decimal("0.2"), statistics.mean(values))
print(json.loads('{"value": 7}')['value'], random.Random(42).randint(1, 10))
'''
JAVA = '''import java.util.*;
import java.math.BigInteger;
import java.time.LocalDate;
class Box {
    int value;
    Box(int n) { value = n; }
    int doubleValue() { return value * 2; }
}
public class Main {
    public static void main(String[] args) {
        // Thread, Runtime, native: words in comments must not reject code.
        Box box = new Box(9);
        int sum = Arrays.stream(new int[]{1, 2, 3}).map(n -> n * n).sum();
        System.out.println(box.doubleValue() + " " + sum);
        System.out.println(new BigInteger("12").pow(2));
        System.out.println(LocalDate.of(2026, 1, 1).getYear());
        System.out.println(Runtime.getRuntime().availableProcessors() > 0);
    }
}'''
C = '''#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <math.h>
int square(int n) { return n * n; }
int main(void) {
    /* system(), socket(), exec(): comments are not calls. */
    volatile double n = 81;
    char text[20]; strcpy(text, "hello");
    int *value = malloc(sizeof(int));
    if (!value) return 1;
    *value = atoi("12");
    printf("%.0f %d %zu %c %d\\n", sqrt(n), square(3), strlen(text), toupper('a'), *value);
    free(value);
    return 0;
}'''

@pytest.mark.parametrize('language,source,output',[
    ('python',PYTHON,'18 14\n3 6\n0.3 2\n7 2\n'),
    ('java',JAVA,'18 14\n144\n2026\ntrue\n'),
    ('c',C,'9 9 5 A 12\n'),
])
@pytest.mark.parametrize('mode',['run','visualize'])
def test_libraries_functions_classes(language,source,output,mode,monkeypatch):
    if not availability()[language]:pytest.skip('Native engine not installed.')
    monkeypatch.setenv('SPANDY_EXECUTION_MODE','trusted-local')
    monkeypatch.setenv('SPANDY_TRUST_LOCAL_CODE','1')
    trace=asyncio.run(execute_job({'id':'library-check','program':JobRequest(language=language,source=source,execution=mode),'cancel':asyncio.Event()}))
    Trace.model_validate(trace)
    assert trace['status']=='completed',trace['diagnostics']
    assert trace['steps'][-1]['stdout']==output
    if mode=='visualize':
        assert len(trace['steps'])>5
        assert all(s['location'] is None or s['location']['line']<=len(source.splitlines()) for s in trace['steps'])
        if language=='java':
            assert any(f['name']=='doubleValue' for s in trace['steps'] for f in s['frames'])
            assert any(o['type']=='Box' for s in trace['steps'] for o in s['objects'].values())
        if language=='python':
            assert any(f['name']=='double' for s in trace['steps'] for f in s['frames'])

def python(source):
    trace=execute({'source':source,'stdin':''})
    Trace.model_validate(trace)
    assert trace['status']=='completed',trace['diagnostics']
    return trace

def test_generator_yield_resume_same_frame():
    trace=python('def count():\n    for n in range(3):\n        yield n\ng = count()\na = next(g)\nb = next(g)\nc = next(g)\nprint(a, b, c)')
    yielded=[s for s in trace['steps'] if s.get('note')=='yield']
    resumed=[s for s in trace['steps'] if s.get('note')=='resume']
    assert [s['returnValue']['value'] for s in yielded]==[0,1,2]
    assert len({s['frames'][-1]['id'] for s in yielded+resumed})==1
    assert trace['steps'][-1]['stdout']=='0 1 2\n'

def test_async_functions_and_await():
    trace=python('import asyncio\nasync def double(n):\n    await asyncio.sleep(0)\n    return n * 2\nanswer = asyncio.run(double(6))\nprint(answer)')
    assert trace['steps'][-1]['stdout']=='12\n'
    assert any(s.get('note')=='suspend' for s in trace['steps'])
    assert any(s.get('note')=='resume' for s in trace['steps'])
    ids={f['id'] for s in trace['steps'] for f in s['frames'] if f['name']=='double'}
    assert len(ids)==1

def test_slots_and_builtin_functions_without_user_getters():
    trace=python('class Box:\n    __slots__ = ("value",)\n    def __init__(self): self.value = 9\n    def __getattribute__(self, key):\n        raise ValueError("inspector must not call this")\nbox = Box()\nvalues = sorted(map(abs, [-3, 1, -2]))\nprint(values, all(values), max(values))')
    final=trace['steps'][-1]
    assert final['objects'][final['globals']['box']['ref']]['fields']['value']['value']==9
    assert final['stdout']=='[1, 2, 3] True 3\n'

def test_missing_library_is_a_real_runtime_error():
    trace=execute({'source':'import spandy_package_that_is_not_installed','stdin':''})
    Trace.model_validate(trace)
    assert trace['terminationReason']=='runtime_error'
    assert 'ModuleNotFoundError' in trace['diagnostics'][0]['message']

@pytest.mark.parametrize('mode',['run','visualize'])
def test_normal_python_exit_preserves_output(mode):
    trace=execute({'source':'import sys\nprint("done")\nsys.exit(0)\nprint("unreachable")','execution':mode})
    Trace.model_validate(trace)
    assert trace['status']=='completed'
    assert trace['steps'][-1]['stdout']=='done\n'
