"""Relocatable Windows start/stop controller for the complete portable bundle."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parent
APP = ROOT/'app'
STATE = ROOT/'.portable'
PYTHON = ROOT/'runtime/python/pythonw.exe'
FLAGS = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0

def configure():
    STATE.mkdir(exist_ok=True)
    engines = {name:str(ROOT/f'runtime/{group}/bin/{name}.exe')
               for name,group in [('java','java'),('javac','java'),('gcc','c'),('gdb','c')]}
    for path in [PYTHON, APP/'dist/index.html', *map(Path,engines.values())]:
        if not path.is_file():
            raise RuntimeError('The package is incomplete. Extract the entire ZIP first. Missing: '+str(path.relative_to(ROOT)))
    temporary = APP/'runtime.local.json.tmp'
    temporary.write_text(json.dumps(engines,indent=2),encoding='utf-8')
    temporary.replace(APP/'runtime.local.json')

def identity():
    import psutil
    try:
        state = json.loads((STATE/'state.json').read_text(encoding='utf-8'))
        process = psutil.Process(state['pid'])
        same_path = lambda a,b: os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))
        args = process.cmdline()
        if (abs(process.create_time()-state['created'])>.01
            or not same_path(process.exe(),PYTHON)
            or '--serve' not in args
            or not any(same_path(arg,ROOT/'launcher.py') for arg in args)):
            return None
        return process,state
    except (OSError,ValueError,KeyError,psutil.Error):
        return None

def healthy(port):
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/health',timeout=.5) as response:
            health = json.load(response)
        return (health.get('name')=='Spandy Shows' and health.get('executionMode')=='trusted-local'
                and all(health.get('languages',{}).get(language) for language in ('python','java','c')))
    except (OSError,ValueError):
        return False

def free_port(preferred=None):
    for port in ([preferred] if preferred else range(8000,8100)):
        try:
            with socket.socket() as sock:
                sock.bind(('127.0.0.1',port))
            return port
        except OSError:
            continue
    raise RuntimeError('No free local port was found. Stop other Spandy Shows copies and try again.')

def ready(process,port):
    deadline = time.monotonic()+45
    while time.monotonic()<deadline:
        if not process.is_running():
            raise RuntimeError('The server stopped during startup. See .portable/server.log for details.')
        if healthy(port):
            return
        time.sleep(.1)
    raise RuntimeError('The local server did not become ready. See .portable/server.log for details.')

def start(args):
    import psutil
    existing = identity()
    if existing:
        process,state = existing
        port = state['port']
    else:
        configure()
        (STATE/'stop').unlink(missing_ok=True)
        port = free_port(args.port)
        environment = dict(os.environ)
        for key in ('PYTHONHOME','PYTHONPATH','VIRTUAL_ENV','DATABASE_URL','SPANDY_JOB_ROOT'):
            environment.pop(key,None)
        with (STATE/'bootstrap.log').open('ab') as log:
            child = subprocess.Popen([str(PYTHON),'-I',str(ROOT/'launcher.py'),'--serve','--port',str(port)],
                                     cwd=ROOT,env=environment,stdout=log,stderr=log,creationflags=FLAGS)
        process = psutil.Process(child.pid)
        state = {'pid':child.pid,'created':process.create_time(),'port':port}
        (STATE/'state.json').write_text(json.dumps(state),encoding='utf-8')
    ready(process,port)
    if not args.no_browser:
        # Use Windows' normal browser association; no browser is installed here.
        webbrowser.open(f'http://127.0.0.1:{port}/',new=2)
    return state

def stop():
    import psutil
    existing = identity()
    if not existing:
        return
    process,state = existing
    (STATE/'stop').write_text('stop',encoding='ascii')
    try:
        process.wait(timeout=10)
    except psutil.TimeoutExpired:
        # Identity is checked above: stop only this bundle's server and workers.
        for child in reversed(process.children(recursive=True)):
            try: child.kill()
            except psutil.Error: pass
        try: process.kill()
        except psutil.Error: pass
        process.wait(timeout=5)
    (STATE/'state.json').unlink(missing_ok=True)

def serve(port):
    configure()
    os.chdir(APP)
    sys.path.insert(0,str(APP))
    os.environ.update(SPANDY_EXECUTION_MODE='trusted-local',SPANDY_TRUST_LOCAL_CODE='1',
                      SPANDY_ORIGINS=f'http://127.0.0.1:{port},http://localhost:{port}',
                      SPANDY_HOSTS='127.0.0.1,localhost',
                      DATABASE_URL='sqlite:///'+str(APP/'spandy-shows.db'),
                      SPANDY_JOB_ROOT=str(APP/'.runtime'))
    for key in ('SPANDY_ACTIVE_SECONDS','SPANDY_INPUT_IDLE_SECONDS'):
        os.environ.pop(key,None)
    log = (STATE/'server.log').open('a',encoding='utf-8',buffering=1)
    sys.stdout = sys.stderr = log
    import uvicorn
    server = uvicorn.Server(uvicorn.Config('backend.app:app',host='127.0.0.1',port=port,access_log=False))
    def monitor():
        while not server.should_exit:
            if (STATE/'stop').exists():
                server.should_exit = True
                break
            time.sleep(.1)
    threading.Thread(target=monitor,daemon=True).start()
    server.run()

class SingleController:
    def __enter__(self):
        # Handles are pointer-sized on 64-bit Windows.
        self.api = ctypes.WinDLL('kernel32',use_last_error=True)
        self.api.CreateMutexW.argtypes = [ctypes.c_void_p,ctypes.c_int,ctypes.c_wchar_p]
        self.api.CreateMutexW.restype = ctypes.c_void_p
        self.api.WaitForSingleObject.argtypes = [ctypes.c_void_p,ctypes.c_uint32]
        self.api.ReleaseMutex.argtypes = [ctypes.c_void_p]
        self.api.CloseHandle.argtypes = [ctypes.c_void_p]
        name = 'Local\\SpandyShowsPortable_'+hashlib.sha256(os.path.normcase(str(ROOT)).encode()).hexdigest()[:24]
        self.handle = self.api.CreateMutexW(None,False,name)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        result = self.api.WaitForSingleObject(self.handle,60000)
        if result not in (0,0x80):
            self.api.CloseHandle(self.handle)
            raise RuntimeError('Another launch is still in progress. Please try again shortly.')
        return self
    def __exit__(self,*exc):
        self.api.ReleaseMutex(self.handle)
        self.api.CloseHandle(self.handle)

def main():
    parser = argparse.ArgumentParser(description='Spandy Shows portable launcher')
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--start',action='store_true')
    action.add_argument('--stop',action='store_true')
    action.add_argument('--serve',action='store_true')
    parser.add_argument('--no-browser',action='store_true')
    parser.add_argument('--port',type=int)
    args = parser.parse_args()
    try:
        STATE.mkdir(exist_ok=True)
        if args.serve:
            serve(args.port)
        else:
            with SingleController():
                if args.start:
                    state = start(args)
                    if sys.stdout is not None: print(json.dumps(state))
                else:
                    stop()
    except Exception as error:
        import traceback
        with (STATE/'launcher.log').open('a',encoding='utf-8') as log:
            traceback.print_exc(file=log)
        if not args.no_browser:
            ctypes.windll.user32.MessageBoxW(None,str(error),'Spandy Shows',0x10)
        if sys.stderr is not None: print(str(error),file=sys.stderr)
        raise SystemExit(1)

if __name__=='__main__': main()
