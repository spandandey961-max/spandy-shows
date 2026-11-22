"""Regression cases for the reported C, Python and Java compatibility gaps."""
import asyncio
import base64
import os

import pytest

from backend.runner import availability, execute_job
from backend.schema import JobRequest


def run(monkeypatch, language, source, *, mode='visualize', stdin='', files=None, native_mode='c'):
    if not availability()[language]:
        pytest.skip(f'{language} runtime unavailable')
    monkeypatch.setenv('SPANDY_EXECUTION_MODE', 'trusted-local')
    monkeypatch.setenv('SPANDY_TRUST_LOCAL_CODE', '1')
    program = JobRequest(language=language, source=source, execution=mode,
                         stdin=stdin, files=files or {}, nativeMode=native_mode)
    job = {'id': 'compatibility', 'program': program, 'cancel': asyncio.Event()}
    trace = asyncio.run(execute_job(job))
    return trace


def final_output(trace):
    assert trace['status'] == 'completed', trace['diagnostics']
    return trace['steps'][-1]['stdout']


def test_c_heap_links_aliases_and_lifetime(monkeypatch):
    trace = run(monkeypatch, 'c', r'''#include <stdio.h>
#include <stdlib.h>
struct Node { int value; struct Node *next; };
int main(void) {
    struct Node *head = calloc(1, sizeof *head);
    struct Node *tail = calloc(1, sizeof *tail);
    head->value = 5;
    tail->value = 9;
    head->next = tail;
    int *values = malloc(3 * sizeof *values);
    values[1] = 42;
    int *middle = values + 1;
    printf("%d %d\n", head->next->value, *middle);
    free(tail);
    head->next = NULL;
    free(values);
    free(head);
    return 0;
}''')
    assert final_output(trace) == '9 42\n'
    state = next(step for step in trace['steps'] if step['location'] and step['location']['line']==13)
    locals_ = state['frames'][-1]['locals']
    objects = state['objects']
    head = objects[locals_['head']['ref']]
    assert head['allocation'] == 'allocated'
    assert head['fields']['next']['ref'] == locals_['tail']['ref']
    assert objects[locals_['middle']['ref']]['items'][1]['value']==42
    assert locals_['middle']['path']==[1]
    assert any('freed allocation' in (frame['locals'].get('tail',{}).get('note') or '')
               for step in trace['steps'] for frame in step['frames'])


def test_c_preserves_headers_and_member_calls(monkeypatch):
    source = r'''#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <string.h>
#include <strings.h>
int local_read(void) { return 4; }
struct Reader { int (*fgets)(void); };
void main() {
    struct Reader r = {local_read};
    char *line = 0;
    size_t size = 0;
    if (getline(&line, &size, stdin) > 0)
        printf("%d %d %d\n", r.fgets(), (int)M_PI, strcasecmp(line, "HELLO\n"));
    free(line);
}'''
    assert final_output(run(monkeypatch, 'c', source, mode='run', stdin='hello\n')) == '4 3 0\n'
    missing=run(monkeypatch,'c','int main(void) { int x; return scanf("%d", &x); }',mode='run')
    assert missing['terminationReason']=='compilation_error'
    assert 'stdio.h' in missing['diagnostics'][0]['message']


def test_python_main_identity_and_windows_spawn(monkeypatch):
    source = '''import __main__, multiprocessing, pickle
class Example: pass
def double(x): return 2*x
if __name__ == "__main__":
    assert __main__.Example is Example
    assert isinstance(pickle.loads(pickle.dumps(Example())), Example)
    with multiprocessing.get_context("spawn").Pool(1) as pool:
        print(pool.map(double, [2, 4]))
'''
    assert final_output(run(monkeypatch, 'python', source, mode='run')) == '[4, 8]\n'


def test_python_threads_deep_calls_and_exec(monkeypatch):
    source = '''import threading
def factorial(n):
    return 1 if n<2 else n*factorial(n-1)
def worker():
    global outcome
    outcome = [[i*j for j in range(3)] for i in range(3)]
t=threading.Thread(target=worker)
t.start()
t.join()
exec("x = 7")
print(factorial(60) == 8320987112741390144276341183223364380754172606361245952449277696409600000000000000, outcome[2][2], x)
'''
    trace=run(monkeypatch,'python',source)
    assert final_output(trace)=='True 4 7\n'
    assert any((step.get('thread') or '').startswith('Thread ') for step in trace['steps'])
    assert any((step.get('note') or '').startswith('Dynamic code') for step in trace['steps'])
    assert max(len(step['frames']) for step in trace['steps'])==50


def test_java_preview_entry_threads_and_output(monkeypatch):
    source = '''void main() throws Exception {
    var threads = new Thread(() -> {
        var items = new java.util.TreeMap<Integer, String>();
        items.put(5, "five");
        items.put(3, "three");
        System.out.println(items.firstKey());
    }, "student");
    threads.start();
    threads.join();
    System.out.println("x".repeat(9000));
    System.out.println("finished");
}'''
    trace=run(monkeypatch,'java',source)
    assert final_output(trace).startswith('3\n')
    assert final_output(trace).endswith('\nfinished\n')
    assert any(step['thread']=='student' for step in trace['steps'])
    assert any(o['type']=='java.util.TreeMap' and len(o['entries'])==2
               for step in trace['steps'] for o in step['objects'].values())

def test_java_named_instance_entry_and_collections(monkeypatch):
    source = '''package demo;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
public class Helper { static class Nested { void main() {} } }
class App {
    void main() {
        var lists = List.of(List.of(), List.of(1), List.of(2, 3), Arrays.asList(4, 5, null));
        var sets = List.of(Set.of(), Set.of(1), Set.of(2, 3), Set.of(4, 5, 6));
        var maps = List.of(Map.of(), Map.of("a", 1), Map.of("b", 2, "c", 3));
        var concurrent = new ConcurrentHashMap<String, Integer>();
        concurrent.put("key", 7);
        concurrent.put("key", 8);
        System.out.println(concurrent.get("key"));
    }
}'''
    for mode in ('run', 'visualize'):
        trace = run(monkeypatch, 'java', source, mode=mode)
        assert final_output(trace) == '8\n'
        assert trace['sourceFile'] == 'Helper.java'
    objects = [obj for step in trace['steps'] for obj in step['objects'].values()]
    assert {0, 1, 2, 4} <= {o['length'] for o in objects if o['kind']=='sequence' and '$List' in o['type']}
    assert {0, 1, 2, 3} <= {len(o['items']) for o in objects if o['kind']=='set'}
    maps = [{key['value']: value['value'] for key, value in o['entries']} for o in objects if o['kind']=='mapping']
    assert all(expected in maps for expected in ({}, {'a': 1}, {'b': 2, 'c': 3}, {'key': 7}, {'key': 8}))
    assert any(o['type']=='java.util.Arrays$ArrayList' and [i['value'] for i in o['items']]==[4,5,None] for o in objects)

@pytest.mark.skipif(os.name == 'nt', reason='Uses the Linux libc getline branch')
def test_linux_getline_tracks_growth_and_eof(monkeypatch):
    source = '''#include <stdio.h>
#include <stdlib.h>
int main(void) {
    char *line = NULL;
    size_t capacity = 0;
    int first = getline(&line, &capacity, stdin);
    int second = getline(&line, &capacity, stdin);
    int last = getline(&line, &capacity, stdin);
    free(line);
    printf("%d %d %d\\n", first, second, last);
}'''
    trace = run(monkeypatch, 'c', source, stdin='x\n'+'b'*700+'\n')
    assert final_output(trace) == '2 701 -1\n'
    states = [s for s in trace['steps'] if s['location'] and s['frames']]
    def buffer_at(line):
        state = next(s for s in states if s['location']['line'] == line)
        pointer = state['frames'][-1]['locals']['line']
        return state['objects'][pointer['ref']]
    small, large, eof = (buffer_at(line) for line in (6, 7, 8))
    assert small['allocation'] == large['allocation'] == 'allocated'
    assert large['length'] >= 702 > small['length']
    assert eof['id'] == large['id']
    assert any('freed allocation' in (s['frames'][-1]['locals'].get('line',{}).get('note') or '') for s in states)


def test_cpp_standard_input_and_trace(monkeypatch):
    trace=run(monkeypatch,'c','''#include <iostream>
int main() {
    int number;
    std::cin >> number;
    std::cout << number * 2 << std::endl;
}''',native_mode='cpp',stdin='7')
    assert final_output(trace)=='14\n'
    assert any(step['location'] and step['location']['file']=='main.cpp' for step in trace['steps'])


def test_c_flexible_member_and_bitfield(monkeypatch):
    trace=run(monkeypatch,'c',r'''#include <stdio.h>
#include <stdlib.h>
struct Packet { unsigned flag : 1; int values[]; };
int main(void) {
    struct Packet *packet = calloc(1, sizeof *packet + 5 * sizeof(int));
    packet->flag = 1;
    packet->values[4] = 23;
    printf("%u %d\n", packet->flag, packet->values[4]);
    free(packet);
}''')
    assert final_output(trace)=='1 23\n'
    for step in trace['steps']:
        for obj in step['objects'].values():
            values=obj['fields'].get('values',{})
            if values.get('kind')=='reference':
                items=step['objects'][values['ref']]['items']
                if len(items)==5 and items[4].get('value')==23:
                    assert obj['fields']['flag']['value']==1
                    return
    pytest.fail('The fifth element of the flexible array was not visible.')


@pytest.mark.parametrize(('language','source','name','helper'),[
    ('c','#include <stdio.h>\n#include "helper.h"\nint main(void) { printf("%d", number()); }','helper.h','static int number(void) { return 42; }'),
    ('python','from helper import number\nprint(number(), end="")','helper.py','def number(): return 42'),
    ('java','class Main { public static void main(String[] args) { System.out.print(Helper.number()); } }','Helper.java','class Helper { static int number() { return 42; } }'),
])
def test_uploaded_helper_source(monkeypatch,language,source,name,helper):
    files={name:base64.b64encode(helper.encode()).decode()}
    assert final_output(run(monkeypatch,language,source,files=files,mode='run'))=='42'


def test_java_exit_and_deep_recursion(monkeypatch):
    source='''class Main {
    static int count(int n) {
        if (n == 0) return 0;
        return 1 + count(n-1);
    }
    public static void main(String[] args) {
        System.out.println(count(65));
        System.exit(0);
    }
}'''
    trace=run(monkeypatch,'java',source)
    assert final_output(trace)=='65\n'
    assert max(len(step['frames']) for step in trace['steps'])==50
