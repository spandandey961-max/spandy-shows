"""Performance changes must preserve fresh execution and immutable replay steps."""
import time

import pytest
from fastapi.testclient import TestClient
from backend import java_worker
from backend.app import app, attempts
from backend.runner import config

def test_java_cache_invalidates_dependencies_and_rejects_corrupt_class(tmp_path):
    from backend.java_cache import compilation_key, save, restore
    source=tmp_path/'Main.java';source.write_text('class Main {}')
    library=tmp_path/'helper.jar';library.write_bytes(b'first dependency')
    first=compilation_key('toolchain',21,[source],[library])
    library.write_bytes(b'updated dependency')
    assert compilation_key('toolchain',21,[source],[library])!=first
    assert compilation_key('new toolchain',21,[source],[library])!=first
    workspace=tmp_path/'work';workspace.mkdir();(workspace/'Main.class').write_bytes(b'class contents')
    cache=tmp_path/'cache';save(cache,first,workspace,False,'')
    target=tmp_path/'target';target.mkdir()
    assert restore(cache,first,target)
    assert (target/'Main.class').read_bytes()==b'class contents'
    (cache/first/'Main.class').write_bytes(b'broken')
    assert restore(cache,first,target) is None

def test_java_cache_compiles_once_but_executes_with_fresh_input(tmp_path, monkeypatch):
    settings=config()
    if not settings.get('javac'):pytest.skip('Java not configured')
    monkeypatch.setenv('SPANDY_JAVA',settings['java'])
    monkeypatch.setenv('SPANDY_JAVAC',settings['javac'])
    monkeypatch.setenv('SPANDY_COMPILE_CACHE',str(tmp_path/'cache'))
    original=java_worker.subprocess.run
    compilations=[]
    def run(*args,**kwargs):
        command=kwargs.get('args',args[0] if args else [])
        if command[0]==settings['javac'] and '-version' not in command:compilations.append(command)
        return original(*args,**kwargs)
    monkeypatch.setattr(java_worker.subprocess,'run',run)
    source='import java.util.Scanner; class Main { public static void main(String[] args) { System.out.println(new Scanner(System.in).nextInt()+1); } }'
    for index in range(3):
        workspace=tmp_path/str(index);workspace.mkdir()
        trace=java_worker.execute(dict(source=source,execution='run',stdin=str(index)),workspace)
        assert trace['status']=='completed',trace['diagnostics']
        assert trace['steps'][-1]['stdout']==str(index+1)+'\n'
    assert len(compilations)==1
    workspace=tmp_path/'changed';workspace.mkdir()
    trace=java_worker.execute(dict(source=source.replace('+1','+2'),execution='run',stdin='10'),workspace)
    assert trace['steps'][-1]['stdout']=='12\n'
    assert len(compilations)==2

def test_c_cache_tracks_headers_and_executes_with_fresh_input(tmp_path, monkeypatch):
    import hashlib
    import json
    import os
    from pathlib import Path
    import shutil
    import subprocess
    from backend import c_worker

    gcc = config().get('gcc') or shutil.which('gcc')
    if os.name != 'nt' or not gcc:
        pytest.skip('Windows desktop C cache requires MinGW.')
    monkeypatch.setenv('SPANDY_GCC', gcc)
    monkeypatch.setenv('PATH', str(Path(gcc).parent) + os.pathsep + os.environ['PATH'])
    helpers = tmp_path/'helpers'
    helpers.mkdir()
    backend = Path(c_worker.__file__).parent
    shutil.copyfile(backend/'c_input.h', helpers/'spandy_input.h')
    subprocess.run([gcc, '-std=gnu17', '-g', '-I', str(helpers), '-c',
                    str(backend/'c_capture.c'), '-o', str(helpers/'capture.o')], check=True)
    (helpers/'helpers.json').write_text(json.dumps({'sources':{
        name:hashlib.sha256((backend/name).read_bytes()).hexdigest()
        for name in ('c_capture.c','c_input.h')}}), encoding='utf-8')
    monkeypatch.setenv('SPANDY_C_HELPERS', str(helpers))
    cache = tmp_path/'cache'
    monkeypatch.setenv('SPANDY_C_CACHE', str(cache))
    original = c_worker.subprocess.run
    builds = []

    def run(*args, **kwargs):
        command = args[0] if args else kwargs['args']
        if '-lm' in command:
            builds.append(command)
        return original(*args, **kwargs)

    monkeypatch.setattr(c_worker.subprocess, 'run', run)
    source = '#include <stdio.h>\n#include "settings.h"\nint main(void) {\n int n;\n scanf("%d", &n);\n printf("%d\\n", n + OFFSET);\n}'
    for index, offset in enumerate((3, 3, 7, 7, 7)):
        if index == 3:
            for artifact in cache.glob('*.zip'):
                artifact.write_bytes(b'corrupt archive')
        workspace = tmp_path/f'run-{index}'
        (workspace/'files').mkdir(parents=True)
        (workspace/'files/settings.h').write_text(f'#define OFFSET {offset}\n', encoding='utf-8')
        trace = c_worker.execute(dict(source=source, execution='run', stdin=f'{index}\n'), workspace)
        assert trace['status'] == 'completed', trace['diagnostics']
        assert trace['steps'][-1]['stdout'] == f'{index+offset}\n'
        assert len(builds) == (1, 1, 2, 3, 3)[index]

def test_incremental_api_restores_exact_trace_with_eof_and_changed_cells(monkeypatch):
    monkeypatch.setenv('SPANDY_EXECUTION_MODE','trusted-local')
    monkeypatch.setenv('SPANDY_TRUST_LOCAL_CODE','1')
    attempts.clear()
    source='a=[1,2]\nfor line in __import__("sys").stdin:\n    a[1]=int(line)\n    print(a[1])\nprint("done")'
    with TestClient(app) as client:
        job=client.post('/api/jobs',json=dict(language='python',source=source,interactive=True)).json()['id']
        prefix=[];answered=set();deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            state=client.get('/api/jobs/'+job).json()
            response=client.get(f'/api/jobs/{job}/trace?offset={len(prefix)}')
            if response.status_code==200:
                chunk=response.json();assert chunk['stepOffset']==len(prefix)
                prefix.extend(chunk['steps'])
            pending=(state.get('live') or {}).get('input')
            if pending and pending['id'] not in answered:
                answered.add(pending['id'])
                answer={'id':pending['id'],'text':'7'} if len(answered)==1 else {'id':pending['id'],'eof':True}
                assert client.post('/api/jobs/'+job+'/input',json=answer).status_code==200
            if state['status'] not in ('queued','running','waiting'):break
            time.sleep(.03)
        else:pytest.fail('Interactive incremental replay did not complete')
        final=client.get('/api/jobs/'+job+'/trace').json()
        tail=client.get(f'/api/jobs/{job}/trace?offset={len(prefix)}').json()
        prefix.extend(tail['steps'])
        assert prefix==final['steps']
        assert final['status']=='completed'
        assert prefix[-1]['stdout']=='7\ndone\n'
        assert len(answered)==2
        assert client.get(f'/api/jobs/{job}/trace?offset={len(prefix)+1}').status_code==409
