import asyncio, base64, hashlib, json, os, shutil, signal, stat, subprocess, sys, tempfile, time, uuid
from pathlib import Path
import psutil
from .schema import Diagnostic, Trace, InputRequest, valid_file_name
from .interactive import atomic_json
from .limits import INPUT_BYTES, MAX_STEPS, MAX_TRACE_BYTES, RUN_OUTPUT_BYTES, RUN_SECONDS, VISUALIZE_SECONDS, WORKSPACE_BYTES, memory_limit_mib
from .java_source import java_source_info

ROOT = Path(__file__).resolve().parents[1]
MAX_TRACE = MAX_TRACE_BYTES
def config():
    path=Path(os.getenv('SPANDY_CONFIG_PATH',str(ROOT/'runtime.local.json')))
    return json.loads(path.read_text()) if path.exists() else {}

def binary(name):
    return config().get(name) or shutil.which(name)

def availability():
    return {'python':True,'java':bool(binary('java') and binary('javac')),
            'c':bool(binary('gcc') and binary('gdb'))}

def empty_trace(program, reason, message, status='failed'):
    return {'schemaVersion':1,'language':program.language,'runtimeVersion':'unavailable',
            'sourceFile':java_source_info(program.source)['sourceFile'] if program.language=='java' else 'main.py' if program.language=='python' else 'main.cpp' if program.nativeMode=='cpp' else 'main.c',
            'sourceHash':hashlib.sha256(program.source.encode()).hexdigest(), 'status':status,
            'terminationReason':reason,'steps':[], 'diagnostics':[{'severity':'error','message':message}], 'limitations':[]}

def kill_tree(proc):
    try:
        parent=psutil.Process(proc.pid)
        children=parent.children(recursive=True)
        for child in reversed(children):
            try: child.kill()
            except psutil.Error: pass
        try: parent.kill()
        except psutil.Error: pass
    except psutil.Error: pass

def process_tree_memory_bytes(pid):
    """Count private memory once instead of adding duplicated working sets."""
    root=psutil.Process(pid)
    total=0;seen=set()
    for process in [root,*root.children(recursive=True)]:
        if process.pid in seen:continue
        seen.add(process.pid)
        try:
            info=process.memory_info()
            private=getattr(info,'private',None)
            if private is None:
                try:private=getattr(process.memory_full_info(),'uss',None)
                except (psutil.AccessDenied,NotImplementedError):pass
            if private is None:private=max(0,info.rss-getattr(info,'shared',0))
            total+=private
        except (psutil.NoSuchProcess,psutil.AccessDenied):pass
    return total

def pending_input(job):
    workspace=job.get('workspace')
    if not workspace or job['cancel'].is_set(): return None
    try:
        request=InputRequest.model_validate_json((workspace/'input-request.json').read_bytes())
        if request.id in job.get('answered',set()): return None
        return request.model_dump()
    except (OSError,ValueError): return None

def live_progress(job):
    workspace=job.get('workspace')
    if not workspace: return None
    limit=RUN_OUTPUT_BYTES if getattr(job['program'],'execution','visualize')=='run' else 8192
    def read(name):
        try:
            with (workspace/name).open('rb') as stream: return stream.read(limit).decode('utf-8',errors='replace').replace('\r\n','\n')
        except OSError: return ''
    try:trace_steps=json.loads((workspace/'progress.json').read_text())['steps']
    except (OSError,ValueError,KeyError):trace_steps=0
    return {'stdout':read('stdout.txt'),'stderr':read('stderr.txt'),'input':pending_input(job),'traceSteps':trace_steps}

def workspace_size(workspace):
    total=0
    data=workspace/'files'
    paths=workspace.iterdir()
    if data.is_dir() and not data.is_symlink() and data.resolve()==data:
        from itertools import chain
        paths=chain(paths,data.iterdir())
    for path in paths:
        try:
            metadata=path.lstat()
            if stat.S_ISREG(metadata.st_mode):total+=metadata.st_size
        except FileNotFoundError:pass  # IPC files are atomically replaced/consumed.
    return total

def partial_trace(job):
    workspace=job.get('workspace')
    if not workspace: return None
    try:
        path=workspace/'partial.json'
        if path.stat().st_size>MAX_TRACE: return None
        trace=Trace.model_validate_json(path.read_bytes())
        validate_trace(trace,job['program'])
        return trace.model_dump()
    except (OSError,ValueError): return None

def validate_trace(trace, program):
    if trace.language!=program.language or trace.sourceHash!=hashlib.sha256(program.source.encode()).hexdigest():
        raise ValueError('Trace source identity mismatch.')
    for i,s in enumerate(trace.steps):
        if s.index!=i:raise ValueError('Trace indices are not contiguous.')
        values=[*s.globals.values(),*[v for f in s.frames for v in f.locals.values()]]
        for key,obj in s.objects.items():
            if key!=obj.id:raise ValueError('Object identity mismatch.')
            values.extend(obj.items);values.extend(obj.fields.values());values.extend(v for entry in obj.entries for v in entry)
        if s.returnValue:values.append(s.returnValue)
        for v in values:
            if v.kind=='reference' and v.ref not in s.objects:raise ValueError('Dangling object reference.')
            if v.kind=='reference' and v.path:
                obj=s.objects[v.ref]
                for index,part in enumerate(v.path):
                    if isinstance(part,int):
                        if part<0 or part>=len(obj.items):raise ValueError('Array reference is outside the recorded view.')
                        destination=obj.items[part]
                    else:
                        if part not in obj.fields:raise ValueError('Field reference is outside the recorded view.')
                        destination=obj.fields[part]
                    if index<len(v.path)-1:
                        if destination.kind!='reference' or destination.ref not in s.objects:raise ValueError('Reference path does not identify nested storage.')
                        obj=s.objects[destination.ref]

def respond(job, response):
    pending=pending_input(job)
    if not pending or pending['id']!=response.id: return False
    data=b'' if response.eof else (response.text+'\n').encode('utf-8')
    total=job.get('inputBytes',0)+len(data)
    if total>INPUT_BYTES: raise ValueError('This execution has reached the 64 KiB interactive input limit. Send EOF to finish input.')
    # The raw file is published first; the JSON file is the readiness signal.
    (job['workspace']/f'input-text-{response.id}.txt').write_bytes(data)
    atomic_json(job['workspace']/f'input-response-{response.id}.json',response.model_dump())
    job.setdefault('answered',set()).add(response.id)
    job['inputBytes']=total
    job['status']='running'
    return True

def collect_files(folder, original):
    if folder.is_symlink() or not folder.is_dir() or folder.resolve()!=folder:
        return {}
    outputs, remaining = {}, 256*1024
    for path in sorted(folder.iterdir()):
        if len(outputs)>=8 or not valid_file_name(path.name):
            continue
        metadata=path.lstat()
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink!=1 or metadata.st_size>remaining:
            continue
        with path.open('rb') as stream:
            data=stream.read(remaining+1)
        if len(data)>remaining:
            continue
        encoded=base64.b64encode(data).decode('ascii')
        if original.get(path.name)!=encoded:
            outputs[path.name]=encoded
            remaining-=len(data)
    return outputs

async def execute_job(job):
    program=job['program']
    files=getattr(program,'files',{})
    mode=os.getenv('SPANDY_EXECUTION_MODE','docker')
    if mode=='trusted-local' and os.getenv('SPANDY_TRUST_LOCAL_CODE')!='1':
        return empty_trace(program,'worker_unavailable','Local execution requires explicit SPANDY_TRUST_LOCAL_CODE=1. Use Docker for development isolation.')
    if mode not in ('docker','trusted-local'):
        return empty_trace(program,'worker_unavailable','Unknown execution mode.')
    if mode=='docker' and not shutil.which('docker'):
        return empty_trace(program,'worker_unavailable','Docker is unavailable. Follow the local setup instructions to run your own trusted code.')
    if mode=='trusted-local' and not availability()[program.language]:
        return empty_trace(program,'worker_unavailable',f'The {program.language} compiler or debugger is not connected. No trace was generated.')
    job_root=Path(os.getenv('SPANDY_JOB_ROOT',str(ROOT/'.runtime')))
    job_root.mkdir(exist_ok=True,parents=True)
    with tempfile.TemporaryDirectory(prefix='job-',dir=job_root) as temp:
        workspace=Path(temp).resolve()
        job['workspace']=workspace
        if mode=='docker': workspace.chmod(0o777)
        file_folder=workspace/'files'
        file_folder.mkdir()
        if mode=='docker': file_folder.chmod(0o777)
        for name,data in files.items():
            path=file_folder/name
            path.write_bytes(base64.b64decode(data))
            if mode=='docker': path.chmod(0o666)
        req,result=workspace/'request.json', workspace/'trace.json'
        req.write_text(json.dumps(program.model_dump(exclude={'files'})),encoding='utf-8')
        worker=ROOT/'backend'/f'{program.language}_worker.py'
        env={k:v for k,v in os.environ.items() if k in ('SYSTEMROOT','WINDIR','COMSPEC','TEMP','TMP','LANG')}
        env.update(PYTHONIOENCODING='utf-8',PYTHONUNBUFFERED='1')
        env['SPANDY_WORKER_MEMORY_MIB']=str(memory_limit_mib(mode))
        if os.getenv('SPANDY_JAVA_HELPERS'):env['SPANDY_JAVA_HELPERS']=os.environ['SPANDY_JAVA_HELPERS']
        if os.getenv('SPANDY_C_HELPERS'):env['SPANDY_C_HELPERS']=os.environ['SPANDY_C_HELPERS']
        paths=[str(Path(binary(k)).parent) for k in ('java','javac','gcc','gdb') if binary(k)]
        env['PATH']=os.pathsep.join(paths+[os.environ.get('PATH','')])
        if mode=='trusted-local':
            # The service uses pythonw on Windows, but workers need ordinary
            # stdin/stdout/stderr for library code and captured diagnostics.
            # CREATE_NO_WINDOW below hides them without discarding those streams.
            worker_python=Path(sys.executable)
            if os.name=='nt' and worker_python.name.lower()=='pythonw.exe':
                worker_python=worker_python.with_name('python.exe')
            command=[str(worker_python),'-I',str(worker),str(req),str(result)]
            if program.language=='python' and os.getenv('SPANDY_PYTHON_MODULES'):
                env['SPANDY_PYTHON_MODULES']=os.environ['SPANDY_PYTHON_MODULES']
            for k in ('java','javac','gcc','gdb'):
                if binary(k): env[f'SPANDY_{k.upper()}']=binary(k)
        else:
            # Container creation, compilation and execution share the same limits.
            name='spandy-job-'+job['id']
            job['container']=name
            host_root=os.getenv('SPANDY_JOB_HOST_ROOT')
            host_workspace=str(Path(host_root)/workspace.name) if host_root else str(workspace)
            command=['docker','run','--rm','--name',name,'--network','none',
                     '--read-only','--cap-drop','ALL','--security-opt','no-new-privileges',
                     '--cpus','1','--memory','768m','--memory-swap','768m','--pids-limit','128',
                     '--ulimit',f'fsize={MAX_TRACE}:{MAX_TRACE}','--tmpfs','/tmp:rw,nosuid,nodev,size=64m',
                     '--mount',f'type=bind,source={host_workspace},target=/job',
                     '--user','65532:65532']
            if program.language=='c': command+=['--cap-add','SYS_PTRACE']
            if program.language=='c':command+=['--env','SPANDY_C_SANITIZERS=1','--env','ASAN_OPTIONS=detect_leaks=0:abort_on_error=1']
            command+=['--env','SPANDY_WORKER_MEMORY_MIB=768']
            command+=['spandy-shows-worker:local',program.language,'/job/request.json','/job/trace.json']
        logs=workspace/'worker.log'
        proc=None
        try:
            with logs.open('wb') as log:
                proc=subprocess.Popen(command,cwd=workspace,env=env,stdout=log,stderr=log,
                    start_new_session=os.name!='nt', creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
                job['process']=proc
                tick=time.monotonic();active_seconds=0;waiting_since=None;waiting_id=None;memory_checked=0
                memory_mib=memory_limit_mib(mode)
                default_limit=RUN_SECONDS if getattr(program,'execution','visualize')=='run' else VISUALIZE_SECONDS
                active_limit=float(os.getenv('SPANDY_ACTIVE_SECONDS',str(default_limit)))
                input_limit=float(os.getenv('SPANDY_INPUT_IDLE_SECONDS','180'))
                reason=None
                while proc.poll() is None:
                    if job['cancel'].is_set(): reason='cancelled'; break
                    now=time.monotonic();pending=pending_input(job)
                    if pending:
                        job['status']='waiting'
                        if waiting_since is None or waiting_id!=pending['id']:waiting_since=now;waiting_id=pending['id']
                        if now-waiting_since>input_limit: reason='input_timeout'; break
                    else:
                        job['status']='running'
                        active_seconds+=now-tick;waiting_since=None;waiting_id=None
                    tick=now
                    if active_seconds>active_limit: reason='timeout'; break
                    if (workspace/'step-limit.flag').is_file():
                        reason='trace_limit' if (workspace/'step-limit.flag').read_text(encoding='utf-8')=='trace_limit' else 'step_limit'
                        break
                    if any(path.exists() and path.stat().st_size>MAX_TRACE for path in (result,workspace/'partial.json')): reason='trace_limit'; break
                    if workspace_size(workspace)>WORKSPACE_BYTES: reason='disk_limit'; break
                    if mode=='trusted-local' and now-memory_checked>=.15:
                        memory_checked=now
                        try:
                            if process_tree_memory_bytes(proc.pid)>memory_mib*1024*1024:reason='memory_limit';break
                        except psutil.Error: pass
                    await asyncio.sleep(.03)
                if job['cancel'].is_set(): reason='cancelled'
                if reason:
                    await stop_job(job)
                    stopped=empty_trace(program,reason,{'cancelled':'Execution cancelled.','timeout':f'{"Trace preparation" if getattr(program,"execution","visualize")=="visualize" else "Program execution"} exceeded {active_limit:g} seconds.',
                        'input_timeout':'Input was not supplied within three minutes. Run again to start a new session.',
                        'memory_limit':f'This execution reached its {memory_mib} MiB memory budget.','trace_limit':f'Worker output or trace size exceeded the {MAX_TRACE//(1024*1024)} MiB trace limit.',
                        'step_limit':f'Visualize reached {MAX_STEPS:,} steps. Recorded states are available for replay.',
                        'disk_limit':f'The {WORKSPACE_BYTES//(1024*1024)} MiB workspace disk limit was reached.'}[reason],
                        'cancelled' if reason=='cancelled' else 'truncated')
                    partial=partial_trace(job)
                    if partial: stopped['steps']=partial['steps'][:MAX_STEPS-1]
                    progress=live_progress(job)
                    if progress:
                        stopped['steps'].append({'index':len(stopped['steps']),'event':'terminated','location':None,'frames':[],
                            'globals':{},'objects':{},'stdout':progress['stdout'],'stderr':progress['stderr'],'exception':None,'note':reason})
                    return stopped
                if not result.exists():
                    with logs.open('rb') as log:
                        log.seek(max(0,logs.stat().st_size-1000))
                        diagnostic=log.read(1000).decode('utf-8',errors='replace')
                    return empty_trace(program,'worker_error','The execution worker exited without a valid trace. '+diagnostic)
                if result.stat().st_size>MAX_TRACE: return empty_trace(program,'trace_limit',f'Trace exceeds {MAX_TRACE//(1024*1024)} MiB.','truncated')
                trace=Trace.model_validate_json(result.read_bytes())
                validate_trace(trace,program)
                try:
                    job['files']=collect_files(file_folder,files)
                except OSError:
                    trace.diagnostics.append(Diagnostic(severity='warning',message='Some generated files could not be read.'))
                return trace.model_dump()
        except (OSError,ValueError) as e:
            return empty_trace(program,'worker_error',('Worker result rejected: '+str(e))[:2000])
        finally:
            if proc and proc.poll() is None: await stop_job(job)
            job.pop('process',None)
            job.pop('workspace',None)

async def stop_job(job):
    if job.get('container'):
        try:
            p=await asyncio.create_subprocess_exec('docker','rm','-f',job['container'],stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL)
            await asyncio.wait_for(p.wait(),5)
        except (OSError,asyncio.TimeoutError): pass
    if job.get('process'): kill_tree(job['process'])

