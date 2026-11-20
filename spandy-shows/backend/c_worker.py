"""Real GCC/GDB-MI adapter; does not infer allocation or dereference unknown pointers."""
import hashlib,importlib.util,json,os,queue,re,subprocess,sys,threading,time
from pathlib import Path

# Compiler, debugger and program processes must not open Windows consoles.
_PROCESS_FLAGS = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
from pygdbmi.gdbmiparser import parse_response
_input_spec=importlib.util.spec_from_file_location('spandy_c_input',Path(__file__).with_name('c_input.py'))
_input_module=importlib.util.module_from_spec(_input_spec);_input_spec.loader.exec_module(_input_module)
input_targets=_input_module.input_targets
_live_spec=importlib.util.spec_from_file_location('spandy_interactive',Path(__file__).with_name('interactive.py'))
_live=importlib.util.module_from_spec(_live_spec);_live_spec.loader.exec_module(_live)
_limits_spec=importlib.util.spec_from_file_location('spandy_limits',Path(__file__).with_name('limits.py'))
_limits=importlib.util.module_from_spec(_limits_spec);_limits_spec.loader.exec_module(_limits)

class MI:
    def __init__(self,cwd,interactive=False):
        self.interactive=interactive
        self.proc=subprocess.Popen(creationflags=_PROCESS_FLAGS, args=[os.getenv('SPANDY_GDB','gdb'),'--quiet','--nx','--interpreter=mi3'],cwd=cwd,
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',bufsize=1)
        self.queue=queue.Queue(maxsize=2048);self.token=0;self.pending=[];self.console=[]
        def read():
            for line in self.proc.stdout:
                try:self.queue.put(parse_response(line.rstrip()),timeout=1)
                except (ValueError,queue.Full): pass
        threading.Thread(target=read,daemon=True).start()
    def command(self,command):
        return self.batch([command])[0]
    def batch(self,commands):
        """One pipe flush for independent MI queries; results stay token ordered."""
        tokens=[];lines=[]
        for command in commands:
            self.token+=1;tokens.append(self.token);lines.append(str(self.token)+command+'\n')
        self.proc.stdin.write(''.join(lines));self.proc.stdin.flush()
        deadline=time.monotonic()+4
        results={};errors=[]
        while len(results)<len(tokens):
            try:data=self.queue.get(timeout=max(.001,deadline-time.monotonic()))
            except queue.Empty:raise TimeoutError('GDB command timed out.') from None
            if data.get('type')=='result' and data.get('token') in tokens:
                if data['message']=='error':errors.append(str(data.get('payload')))
                results[data['token']]=data.get('payload') or {}
            if data.get('message')=='stopped':self.pending.append(data.get('payload') or {})
            if data.get('type')=='console':self.console.append(data.get('payload',''))
            if time.monotonic()>deadline and len(results)<len(tokens):raise TimeoutError('GDB command timed out.')
        if errors:raise RuntimeError('; '.join(errors))
        return [results[token] for token in tokens]
    def stopped(self):
        if self.pending:return self.pending.pop(0)
        while True:
            try:data=self.queue.get(timeout=5)
            except queue.Empty:
                if self.interactive and self.proc.poll() is None:continue
                raise RuntimeError(f'GDB stopped without an execution event (exit code {self.proc.poll()}).') from None
            if data.get('message')=='stopped':return data.get('payload') or {}
    def record_user_lines(self):
        """Stop at actual user line-table addresses without stepping library code.

        GDB software stepping on Windows otherwise repeatedly enters the OS
        debugger for library instructions that never become displayed states.
        Line entries retain calls, returns, loop edges and variable changes.
        """
        try:
            rows=self.command('-symbol-list-lines main.c').get('lines',[])
            addresses=list(dict.fromkeys(row['pc'] for row in rows if int(row.get('line',0))>0))
            # Re-inserting thousands of software breakpoints at every stop is
            # quadratic on Windows. Large source files use ordinary line steps.
            if not addresses or len(addresses)>128:return False
            self.command('-break-delete')
            for start in range(0,len(addresses),128):self.batch(['-break-insert *'+pc for pc in addresses[start:start+128]])
            return True
        except RuntimeError:
            self.command('-break-delete')
            return False
    def close(self):
        try:self.command('-gdb-exit')
        except Exception: self.proc.kill()
        try:self.proc.wait(timeout=2)
        except subprocess.TimeoutExpired:self.proc.kill()

def q(s):return json.dumps(str(s))

class Observer:
    def __init__(self,mi,source):
        self.mi=mi
        observer=Path(__file__).with_name('c_observer.py').read_text(encoding='utf-8')
        self.mi.command('-interpreter-exec console '+q('python exec('+repr(observer)+')'))
        self.mi.command('-interpreter-exec console '+q('python _spandy_storage.input_targets='+repr(input_targets(source))))
    def snapshot(self,stop,index,workspace):
        self.mi.console=[]
        self.mi.command('-interpreter-exec console '+q('python spandy_observe(None)'))
        payload=next((line.split('SPANDY_OBSERVATION=',1)[1] for line in self.mi.console if line.startswith('SPANDY_OBSERVATION=')),None)
        if payload is None:raise RuntimeError('The bundled C memory observer did not return a snapshot.')
        data=json.loads(payload);event=data['event'];f=stop.get('frame',{})
        exc={'type':stop.get('signal-name','signal'),'message':stop.get('signal-meaning','Runtime signal')} if stop.get('reason')=='signal-received' else None
        return {'index':index,'event':'exception' if exc else event,'location':{'file':'main.c','line':int(f.get('line','1')),'phase':'before'},
                'frames':data['frames'],'globals':data['globals'],'objects':data['objects'],'stdout':read_output(workspace/'stdout.txt'),
                'stderr':read_output(workspace/'stderr.txt'),'exception':exc,'returnValue':None,
                'note':'A function returned. The caller is suspended before the highlighted line.' if event=='return' else None}

def read_output(path):
    return path.read_bytes()[:8192].decode('utf-8',errors='replace').replace('\r\n','\n') if path.exists() else ''

def execute(request,workspace):
    source=request['source']
    result={'schemaVersion':1,'language':'c','runtimeVersion':'GCC / GDB','sourceFile':'main.c',
            'sourceHash':hashlib.sha256(source.encode()).hexdigest(),'status':'completed','terminationReason':'completed','steps':[],'diagnostics':[],
            'limitations':['C initialization is generally unknown. Direct stdin destination observations are hidden until an instrumented real read succeeds.',
            'Pointers link to observed symbols, fields and individual array elements. Arbitrary addresses are not dereferenced; heap allocation and freed state are unknown.',
            'Single-threaded C17. Statements sharing a line are one debugger step. Arrays include runtime-sized and nested dimensions; the active union member is unknown.',
            'Undefined behavior beyond debugger signals is not comprehensively diagnosed; sanitizers are not enabled in this development adapter.',
            'C stdin readers stop on EOF, mismatched types or partial scanf conversions. Interactive reads use a live pipe; EOF-handling loops are outside this input workflow.']}
    code_tokens=re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|//[^\n]*|/\*.*?\*/',' ',source,flags=re.S)
    if request.get('execution')!='run' and re.search(r'\b(pthread\w*|fork|exec\w*|system|socket|__asm__|asm)\s*\(',code_tokens):
        result.update(status='failed',terminationReason='unsupported_feature');result['diagnostics']=[{'severity':'error','message':'Use Run code for threads, processes, networking or inline assembly. Visualize records single-threaded user code.'}];return result
    (workspace/'main.c').write_text(source,encoding='utf-8');(workspace/'stdin.txt').write_text(request.get('stdin',''),encoding='utf-8')
    # Separate helper; source file and its line mappings remain unchanged.
    adapter=Path(__file__).parent
    (workspace/'capture.c').write_text((adapter/'c_capture.c').read_text(encoding='utf-8'),encoding='utf-8')
    (workspace/'spandy_input.h').write_text((adapter/'c_input.h').read_text(encoding='utf-8'),encoding='utf-8')
    target=workspace/('program.exe' if os.name=='nt' else 'program')
    flags=['-fsanitize=address,undefined','-fno-sanitize-recover=all'] if os.getenv('SPANDY_C_SANITIZERS')=='1' else []
    if flags:result['limitations'][3]='AddressSanitizer and UBSan cover a subset of memory/undefined behavior errors. They do not establish initialization or allocation validity; leak checking under ptrace is disabled.'
    gcc=os.getenv('SPANDY_GCC','gcc')
    compiler=[gcc,'-std=c17','-g','-O0','-fno-omit-frame-pointer','-Wall','-Wextra',*flags]
    main_object=workspace/'main.o'
    compile_=subprocess.run(creationflags=_PROCESS_FLAGS, args=[*compiler,'-include',str(workspace/'spandy_input.h'),'-c',str(workspace/'main.c'),'-o',str(main_object)],capture_output=True,text=True,timeout=_limits.COMPILE_SECONDS)
    helper_object=None
    if not flags and os.getenv('SPANDY_C_HELPERS'):
        try:
            directory=Path(os.environ['SPANDY_C_HELPERS']);metadata=json.loads((directory/'helpers.json').read_text(encoding='utf-8'))
            if all(metadata['sources'][name]==hashlib.sha256((adapter/name).read_bytes()).hexdigest() for name in ('c_capture.c','c_input.h')) and (directory/'capture.o').is_file():helper_object=directory/'capture.o'
        except (OSError,ValueError,KeyError):pass
    if not compile_.returncode:
        link=subprocess.run(creationflags=_PROCESS_FLAGS, args=[*compiler,str(main_object),str(helper_object or workspace/'capture.c'),'-o',str(target),'-lm'],capture_output=True,text=True,timeout=_limits.COMPILE_SECONDS)
        link.stderr=compile_.stderr+link.stderr;compile_=link
    if compile_.returncode:
        result.update(status='failed',terminationReason='compilation_error');text=compile_.stderr[:8192];line=re.search(r'main\.c:(\d+):(\d+)',text)
        if not re.search(r'\bmain\s*\(',code_tokens) and re.search(r'(?m)^\s*\{',code_tokens):
            text='C statements must be inside a function. Add int main(void) before the opening { and return 0; before its closing }.\n\n'+text[:7900]
        result['diagnostics']=[{'severity':'error','message':text,'line':int(line[1]) if line else None,'column':int(line[2]) if line else None}];return result
    if compile_.stderr:result['diagnostics']=[{'severity':'warning','message':compile_.stderr[:8192]}]
    result['runtimeVersion']=subprocess.run(creationflags=_PROCESS_FLAGS, args=[os.getenv('SPANDY_GCC','gcc'),'--version'],capture_output=True,text=True,timeout=3).stdout.splitlines()[0][:256]
    live=request.get('interactive',False)
    publisher=_live.TracePublisher(workspace) if live else None
    broker=_live.NativeInputBroker(workspace,lambda:publisher.publish(result,force=True)) if live else None
    if request.get('execution')=='run':
        # The same real GCC output and stdin guard, without debugger step limits.
        with (workspace/'native.log').open('wb') as log:
            try:completed=subprocess.run(creationflags=_PROCESS_FLAGS, args=[str(target)],cwd=workspace,stdout=log,stderr=log,timeout=None if live else _limits.RUN_SECONDS)
            finally:
                if broker:broker.close()
        if (workspace/'input-failure.txt').exists():
            line,reason=read_output(workspace/'input-failure.txt').split()
            result.update(status='failed',terminationReason=reason)
            message='Program input ran out. Add all requested responses in Program input, then run again.' if reason=='input_required' else 'Program input does not match the requested type. Correct it in Program input, then run again.'
            result['diagnostics'].append({'severity':'error','message':message,'line':int(line)})
        elif completed.returncode:
            result.update(status='failed',terminationReason='runtime_error')
            result['diagnostics'].append({'severity':'error','message':read_output(workspace/'stderr.txt') or f'C program exited with status {completed.returncode}.'})
        result['steps']=[{'index':0,'event':'completed' if result['status']=='completed' else 'terminated','location':None,'frames':[],
            'globals':{},'objects':{},'stdout':read_output(workspace/'stdout.txt'),'stderr':read_output(workspace/'stderr.txt'),'exception':None,'note':result['terminationReason']}]
        result['limitations'].append('Run code does not record memory or frames. Use Visualize to inspect execution.')
        return result
    mi=MI(workspace,live);obs=Observer(mi,source);line_breakpoints=False;configured=False
    try:
        mi.command('-gdb-set pagination off');mi.command('-gdb-set confirm off');mi.command('-gdb-set auto-load off');mi.command('-gdb-set print elements 40')
        mi.command('-file-exec-and-symbols '+q(target));mi.command('-break-insert main');mi.command('-exec-run');stop=mi.stopped()
        while True:
            if (workspace/'input-failure.txt').exists():
                line,reason=read_output(workspace/'input-failure.txt').split()
                result.update(status='failed',terminationReason=reason)
                message='Program input ran out. Add all requested responses in Program input, then run again.' if reason=='input_required' else 'Program input does not match the requested type. Correct it in Program input, then run again.'
                result['diagnostics'].append({'severity':'error','message':message,'line':int(line)})
                break
            if stop.get('reason','').startswith('exited'):
                if stop.get('reason')=='exited' and stop.get('exit-code','0')!='0':result.update(status='failed',terminationReason='runtime_error')
                break
            if len(result['steps'])>=_limits.MAX_STEPS-1:result.update(status='truncated',terminationReason='step_limit');break
            if any((workspace/name).exists() and (workspace/name).stat().st_size>8192 for name in ('stdout.txt','stderr.txt')):
                result.update(status='truncated',terminationReason='output_limit');break
            file=Path(stop.get('frame',{}).get('fullname',stop.get('frame',{}).get('file',''))).name
            if stop.get('reason')=='signal-received' and file!='main.c':
                result.update(status='failed',terminationReason='runtime_error')
                result['diagnostics'].append({'severity':'error','message':stop.get('signal-name','Signal')+': '+stop.get('signal-meaning','The native runtime stopped outside the submitted source.')})
                break
            if file=='main.c':
                state=obs.snapshot(stop,len(result['steps']),workspace);result['steps'].append(state)
                if publisher:publisher.publish(result)
                if state['exception']:result.update(status='failed',terminationReason='runtime_error');result['diagnostics'].append({'severity':'error','message':state['exception']['type']+': '+state['exception']['message'],'line':state['location']['line']});break
                if not configured:line_breakpoints=mi.record_user_lines();configured=True
                mi.command('-exec-continue' if line_breakpoints else '-exec-step')
            else:mi.command('-exec-continue' if line_breakpoints else '-exec-finish')
            stop=mi.stopped()
    finally:
        mi.close()
        if broker:broker.close()
    last=result['steps'][-1] if result['steps'] else {'globals':{},'objects':{}}
    stopped_objects={key:{**obj,'allocation':'unknown','note':'Last debugger observation; storage lifetime is unknown after execution stops.'} for key,obj in last['objects'].items()}
    result['steps'].append({'index':len(result['steps']),'event':'completed' if result['status']=='completed' else 'terminated','location':None,
        'frames':[],'globals':last['globals'],'objects':stopped_objects,'stdout':read_output(workspace/'stdout.txt'),'stderr':read_output(workspace/'stderr.txt'),'exception':None,'note':result['terminationReason']})
    return result

if __name__=='__main__':
    request_path,result_path=map(Path,sys.argv[1:3])
    try:result=execute(json.loads(request_path.read_text(encoding='utf-8')),request_path.parent)
    except Exception as e:print(f'{type(e).__name__}: {e}'[:2000],file=sys.stderr);sys.exit(1)
    result_path.write_text(json.dumps(result),encoding='utf-8')
