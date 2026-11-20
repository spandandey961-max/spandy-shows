"""Exercise the real portable EXEs with installed runtimes absent from PATH."""
import argparse
import json
import os
from pathlib import Path
import struct
import subprocess
import time
import urllib.error
import urllib.request

def request(base,path,data=None,method=None):
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(base+path,data=body,method=method,
                                 headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=5) as response:
        return json.load(response)

def until(action,predicate,seconds=45):
    deadline = time.monotonic()+seconds
    while time.monotonic()<deadline:
        try:
            value = action()
            if predicate(value): return value
        except (OSError,ValueError): pass
        time.sleep(.05)
    raise AssertionError('Portable execution did not reach the expected state.')

def subsystem(path):
    data = path.read_bytes()
    pe = struct.unpack_from('<I',data,0x3c)[0]
    return struct.unpack_from('<H',data,pe+24+68)[0]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('bundle',type=Path)
    args = parser.parse_args()
    root = args.bundle.resolve()
    environment = dict(os.environ)
    environment.update(PATH=os.path.join(os.environ['SYSTEMROOT'],'System32'),
                       PYTHONHOME='Z:\\missing-python',PYTHONPATH='Z:\\missing-modules')
    flags = subprocess.CREATE_NO_WINDOW
    start = root/'Start Spandy Shows.exe'
    stop = root/'Stop Spandy Shows.exe'
    assert subsystem(start)==subsystem(stop)==2,'Launchers must use the GUI subsystem.'
    result = subprocess.run([str(root/'runtime/python/python.exe'),'-I','-c',
                             'import sys,json,ssl,sqlite3,psutil,pydantic,fastapi; print(json.dumps({"prefix":sys.prefix,"version":sys.version,"paths":sys.path}))'],
                            env=environment,capture_output=True,text=True,creationflags=flags,check=True)
    runtime = json.loads(result.stdout)
    assert Path(runtime['prefix']).resolve()==(root/'runtime/python').resolve(),runtime
    assert all(Path(path).resolve().is_relative_to(root) for path in runtime['paths']),runtime
    print('Isolated portable Python imports and GUI launchers passed.',flush=True)
    subprocess.run([str(start),'--no-browser'],env=environment,creationflags=flags,check=True)
    state_path = root/'.portable/state.json'
    state = until(lambda:json.loads(state_path.read_text()),lambda s:'port' in s)
    base = f"http://127.0.0.1:{state['port']}"
    try:
        health = until(lambda:request(base,'/api/health'),lambda h:all(h['languages'].values()))
        assert health['executionMode']=='trusted-local',health
        print('Portable server ready:',base,flush=True)
        for _ in range(3):
            subprocess.run([str(start),'--no-browser'],env=environment,creationflags=flags,check=True)
        time.sleep(.5)
        assert json.loads(state_path.read_text())['pid']==state['pid'],'Repeated Start must reuse the process.'
        print('Repeated Start reuses one server.',flush=True)
        sources = {
            'python':'import math\nclass Box:\n    def __init__(self,n): self.value=math.isqrt(n)\ndef calculate():\n    n=int(input("Number: "))\n    box=Box(n)\n    print(box.value)\ncalculate()',
            'java':'import java.util.Scanner;\npublic class PortableExample {\n static int doubled(int n) {return n*2;}\n public static void main(String[] args) {\n Scanner scanner=new Scanner(System.in);\n System.out.print("Number: ");\n int n=scanner.nextInt();\n System.out.println(doubled(n));\n }\n}',
            'c':'#include <stdio.h>\n#include <math.h>\nint main(void) {\n int n;\n printf("Number: ");\n scanf("%d", &n);\n printf("%.0f\\n",sqrt(n));\n return 0;\n}',
        }
        for mode in ('run','visualize'):
            for language,source in sources.items():
                created = request(base,'/api/jobs',{'language':language,'source':source,'execution':mode,'interactive':True})
                id = created['id']
                state = until(lambda:request(base,'/api/jobs/'+id),lambda s:s['status'] in ('waiting','failed','completed'))
                assert state['status']=='waiting',request(base,'/api/jobs/'+id+'/trace')
                assert state['live']['stdout']=='Number: ',state
                assert state['live']['input']['type']=='integer',state
                request(base,'/api/jobs/'+id+'/input',{'id':1,'text':'81'})
                state = until(lambda:request(base,'/api/jobs/'+id),lambda s:s['status'] not in ('queued','running','waiting'))
                trace = request(base,'/api/jobs/'+id+'/trace')
                assert trace['status']=='completed',trace
                assert trace['steps'][-1]['stdout']=='Number: '+('162' if language=='java' else '9')+'\n',trace
                if mode=='visualize': assert len(trace['steps'])>5
                print(language,mode,'passed:',len(trace['steps']),'steps.',flush=True)
        utility = (root/'app/public/examples/java-utility-once.java').read_text(encoding='utf-8')
        id = request(base,'/api/jobs',{'language':'java','source':utility,'execution':'visualize','interactive':True})['id']
        for sequence in (1,2):
            state = until(lambda:request(base,'/api/jobs/'+id),lambda s:(s.get('live',{}).get('input') or {}).get('id')==sequence)
            request(base,'/api/jobs/'+id+'/input',{'id':sequence,'text':'5'})
        until(lambda:request(base,'/api/jobs/'+id),lambda s:s['status'] not in ('queued','running','waiting'))
        trace = request(base,'/api/jobs/'+id+'/trace')
        assert trace['status']=='completed',trace
        assert trace['steps'][-1]['stdout'].count('SIMPLE JAVA UTILITY PROGRAM')==1
        assert trace['steps'][-1]['stdout'].count('Factorial of 5 = 120')==1
        print('Single-choice menu, two live inputs and visual playback passed.',flush=True)
        # Stop must cancel a blocked worker as well as the server.
        id = request(base,'/api/jobs',{'language':'python','source':'input("Waiting: ")','interactive':True})['id']
        until(lambda:request(base,'/api/jobs/'+id),lambda s:s['status']=='waiting')
    finally:
        subprocess.run([str(stop),'--no-browser'],env=environment,creationflags=flags,check=True)
        until(lambda:state_path.exists(),lambda exists:not exists,seconds=20)
    try:
        request(base,'/api/health')
    except (OSError,urllib.error.URLError): pass
    else: raise AssertionError('Portable server is still running after Stop.')
    print('Stop shuts down the portable server and active worker. All portable checks passed.',flush=True)

if __name__=='__main__': main()
