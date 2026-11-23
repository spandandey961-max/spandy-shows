"""Real GCC/GDB-MI adapter with bounded observation of declared and allocated storage."""
import hashlib,importlib.util,inspect,json,os,queue,re,shutil,signal,subprocess,sys,threading,time
from pathlib import Path

# Compiler, debugger and program processes must not open Windows consoles.
_PROCESS_FLAGS = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
_input_spec=importlib.util.spec_from_file_location('spandy_c_input',Path(__file__).with_name('c_input.py'))
_input_module=importlib.util.module_from_spec(_input_spec);_input_spec.loader.exec_module(_input_module)
input_targets=_input_module.input_targets
_live_spec=importlib.util.spec_from_file_location('spandy_interactive',Path(__file__).with_name('interactive.py'))
_live=importlib.util.module_from_spec(_live_spec);_live_spec.loader.exec_module(_live)
_limits_spec=importlib.util.spec_from_file_location('spandy_limits',Path(__file__).with_name('limits.py'))
_limits=importlib.util.module_from_spec(_limits_spec);_limits_spec.loader.exec_module(_limits)

class MI:
    def __init__(self,cwd,interactive=False):
        from pygdbmi.gdbmiparser import parse_response
        self.interactive=interactive
        self.proc=subprocess.Popen(creationflags=_PROCESS_FLAGS, args=[os.getenv('SPANDY_GDB','gdb'),'--quiet','--nx','--interpreter=mi3'],cwd=cwd,
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',bufsize=1)
        self.queue=queue.Queue(maxsize=2048);self.token=0;self.pending=[];self.observations=[]
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
            self.collect_observation(data)
            if time.monotonic()>deadline and len(results)<len(tokens):raise TimeoutError('GDB command timed out.')
        if errors:raise RuntimeError('; '.join(errors))
        return [results[token] for token in tokens]
    def stopped(self):
        if self.pending:return self.pending.pop(0)
        deadline=time.monotonic()+_limits.VISUALIZE_SECONDS
        while True:
            try:data=self.queue.get(timeout=5)
            except queue.Empty:
                if self.proc.poll() is None and (self.interactive or time.monotonic()<deadline):continue
                raise RuntimeError(f'GDB stopped without an execution event (exit code {self.proc.poll()}).') from None
            if data.get('message')=='stopped':return data.get('payload') or {}
            self.collect_observation(data)

    def collect_observation(self, message):
        if message.get('type') == 'console':
            line = message.get('payload') or ''
            if line.startswith('SPANDY_OBSERVATION='):
                self.observations.append(line.split('=', 1)[1])

    def observation(self):
        # Depending on the MI version, the stop notification may come first.
        deadline = time.monotonic() + 4
        while not self.observations:
            try:
                message = self.queue.get(timeout=max(0, deadline - time.monotonic()))
            except queue.Empty:
                raise RuntimeError('The C memory observer did not report the debugger stop.') from None
            self.collect_observation(message)
        return json.loads(self.observations.pop(0))
    def record_user_lines(self, source_file):
        """Stop at actual user line-table addresses without stepping library code.

        GDB software stepping on Windows otherwise repeatedly enters the OS
        debugger for library instructions that never become displayed states.
        Line entries retain calls, returns, loop edges and variable changes.
        """
        try:
            rows=self.command('-symbol-list-lines '+q(source_file)).get('lines',[])
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
    def __init__(self,mi,source,source_file):
        self.mi,self.source_file=mi,source_file
        self.previous = {}
        self.output = {name: b'' for name in ('stdout', 'stderr')}
        self.output_text = dict.fromkeys(self.output, '')
        observer=inspect.getsource(_live.step_delta)+'\n'+Path(__file__).with_name('c_observer.py').read_text(encoding='utf-8')
        self.mi.command('-interpreter-exec console '+q('python exec('+repr(observer)+')'))
        settings=f'_spandy_storage.input_targets={input_targets(source)!r}; _spandy_storage.source_file={source_file!r}'
        self.mi.command('-interpreter-exec console '+q('python '+settings))
    def snapshot(self,stop,index,workspace):
        payload = self.mi.observation()
        if 'error' in payload:
            raise RuntimeError('C memory observation failed: ' + payload['error'])
        data = self.previous = _live.apply_delta(self.previous, payload)
        event=data['event'];f=stop.get('frame',{})
        exc={'type':stop.get('signal-name','signal'),'message':stop.get('signal-meaning','Runtime signal')} if stop.get('reason')=='signal-received' else None
        return {'index':index,'event':'exception' if exc else event,'location':{'file':self.source_file,'line':int(f.get('line','1')),'phase':'before'},
                'frames':data['frames'],'globals':data['globals'],'objects':data['objects'],
                **self.read_streams(workspace),'exception':exc,'returnValue':None,
                'thread':data.get('thread'),
                'note':'A function returned. The caller is suspended before the highlighted line.' if event=='return' else None}

    def read_streams(self, workspace):
        # Capture files append during execution. Inspect only bytes that
        # arrived since the previous stop, within the existing replay preview.
        for name, previous in self.output.items():
            path = workspace/(name+'.txt')
            try:
                size = min(path.stat().st_size, 8192)
                if size == len(previous):
                    continue
                if size < len(previous):
                    previous = b''
                with path.open('rb') as stream:
                    stream.seek(len(previous))
                    current = previous + stream.read(size-len(previous))
            except FileNotFoundError:
                current = b''
            self.output[name] = current
            self.output_text[name] = current.decode('utf-8',errors='replace').replace('\r\n','\n')
        return self.output_text

def read_output(path, limit=8192):
    try:
        with path.open('rb') as stream:
            return stream.read(limit).decode('utf-8',errors='replace').replace('\r\n','\n')
    except FileNotFoundError:
        return ''

def exit_diagnostic(code):
    if os.name=='nt':
        status=code & 0xffffffff
        name={3:'abort (SIGABRT)',0x40000015:'abort (SIGABRT)',0xc0000005:'access violation',0xc000001d:'illegal instruction',
              0xc0000094:'division by zero',0xc00000fd:'stack overflow'}.get(status)
        if name:return f'C program crashed with {name} (0x{status:08X}).'
    elif code<0:
        try:return f'C program was terminated by {signal.Signals(-code).name}.'
        except ValueError:pass
    return f'C program exited with status {code}.'

def execute(request,workspace):
    source=request['source']
    cpp=request.get('nativeMode')=='cpp'
    source_file='main.cpp' if cpp else 'main.c'
    result={'schemaVersion':1,'language':'c','runtimeVersion':'GCC / GDB','sourceFile':source_file,
            'sourceHash':hashlib.sha256(source.encode()).hexdigest(),'status':'completed','terminationReason':'completed','steps':[],'diagnostics':[],
            'limitations':['C initialization is generally unknown. Direct stdin destination observations are hidden until an instrumented real read succeeds.',
            'Pointers link to observed symbols, array elements and bounded allocations made through instrumented calls. Unknown addresses are not dereferenced.',
            'GNU C17. Statements sharing a line are one debugger step. Arrays include runtime-sized and nested dimensions; the active union member is unknown.',
            'Undefined behavior beyond debugger signals is not comprehensively diagnosed; sanitizers are not enabled in this development adapter.',
            'Instrumented stdin reads return standard C results, including EOF and partial conversions.']}
    code_tokens=re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|//[^\n]*|/\*.*?\*/',' ',source,flags=re.S)
    if cpp:result['limitations']=['C++17 with G++. Standard input comes from the preset input box and ends at EOF. Local values and declared storage are recorded; C++ allocation and STL internals may be unavailable.']
    (workspace/source_file).write_text(source,encoding='utf-8')
    (workspace/'stdin.txt').write_bytes((_live.initial_input(request.get('stdin','')) if request.get('interactive') and not cpp else request.get('stdin','')).encode('utf-8'))
    # Separate helper; source file and its line mappings remain unchanged.
    adapter=Path(__file__).parent
    (workspace/'capture.c').write_text((adapter/'c_capture.c').read_text(encoding='utf-8'),encoding='utf-8')
    (workspace/'spandy_input.h').write_text((adapter/'c_input.h').read_text(encoding='utf-8'),encoding='utf-8')
    target=workspace/('program.exe' if os.name=='nt' else 'program')
    flags=['-fsanitize=address,undefined','-fno-sanitize-recover=all'] if os.getenv('SPANDY_C_SANITIZERS')=='1' else []
    if flags:result['limitations'].append('AddressSanitizer and UBSan cover a subset of memory errors; leak checking under ptrace is disabled.')
    gcc=os.getenv('SPANDY_GCC','gcc')
    compiler=[gcc,'-std=gnu17','-g','-O0','-fno-omit-frame-pointer','-Wall','-Wextra','-Werror=implicit-function-declaration',*flags]
    if cpp:
        sibling=Path(gcc).with_name('g++.exe' if os.name=='nt' else 'g++')
        gxx=str(sibling) if sibling.is_file() else shutil.which('g++')
        if not gxx:
            result.update(status='failed',terminationReason='worker_unavailable')
            result['diagnostics']=[{'severity':'error','message':'G++ is required for C++ mode.'}]
            return result
        compiler=[gxx,'-std=c++17','-g','-O0','-fno-omit-frame-pointer','-Wall','-Wextra',*flags]
    normalized=source if cpp else _input_module.normalize_void_main(source)
    instrumented=None if cpp else _input_module.instrument(normalized,capture_heap=request.get('execution')!='run',windows=os.name=='nt')
    program_file=source_file
    validation_file=None
    if instrumented or normalized!=source:
        validation=_input_module.instrument(normalized,capture_heap=False,windows=os.name=='nt',validate=True)
        validation_file=source_file
        if validation is not None:
            validation_file='validate.c'
            (workspace/validation_file).write_text(validation,encoding='utf-8')
        program_file='instrumented.c'
        (workspace/program_file).write_text(instrumented or '#line 1 "main.c"\n'+normalized,encoding='utf-8')
    helper_object=None
    if not flags and os.getenv('SPANDY_C_HELPERS'):
        try:
            directory=Path(os.environ['SPANDY_C_HELPERS']);metadata=json.loads((directory/'helpers.json').read_text(encoding='utf-8'))
            if all(metadata['sources'][name]==hashlib.sha256((adapter/name).read_bytes()).hexdigest() for name in ('c_capture.c','c_input.h')) and (directory/'capture.o').is_file():helper_object=directory/'capture.o'
        except (OSError,ValueError,KeyError):pass
    extensions=('*.cpp','*.cc','*.cxx') if cpp else ('*.c',)
    sources=[path.relative_to(workspace).as_posix() for extension in extensions
             for path in sorted((workspace/'files').glob(extension))]
    options=dict(cwd=workspace, creationflags=_PROCESS_FLAGS, capture_output=True,
                 text=True, timeout=_limits.COMPILE_SECONDS)
    includes=['-I','files']
    compile_entry=record=None
    if not cpp and helper_object and os.getenv('SPANDY_C_CACHE'):
        # -E resolves the actual include graph and time-dependent macros. Keep
        # job directories out of debug paths so a hit can be stepped in a new job.
        compiler.extend(['-fno-working-directory', f'-fdebug-prefix-map={workspace.as_posix()}=.'])
        spec=importlib.util.spec_from_file_location('spandy_c_cache',adapter/'c_cache.py')
        cache=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cache)
        expanded=workspace/'cache-preprocessed.i'
        names=list(dict.fromkeys([source_file, validation_file or source_file, program_file,*sources]))
        try:
            with expanded.open('wb') as stream:
                preprocessed=subprocess.run([*compiler,*includes,'-E',*names], cwd=workspace,
                    creationflags=_PROCESS_FLAGS, stdout=stream,stderr=subprocess.DEVNULL,timeout=_limits.COMPILE_SECONDS)
            if not preprocessed.returncode:
                key=cache.key(cache.toolchain_key(gcc,helper_object), [*compiler[1:-1], request.get('execution')],
                              workspace,names,expanded,adapter)
                if key:
                    compile_entry=Path(os.environ['SPANDY_C_CACHE'])/(key+'.zip')
                    record=cache.restore(compile_entry,target)
        except (OSError,subprocess.TimeoutExpired):
            pass  # A cache failure leaves normal compilation available.
        finally:
            expanded.unlink(missing_ok=True)
    if record is None:
        validation_result=(subprocess.run([*compiler,*includes,'-fsyntax-only',validation_file],**options)
                           if validation_file else None)
        compile_=validation_result
        if cpp and helper_object is None and (compile_ is None or not compile_.returncode):
            helper_object=workspace/'capture.o'
            helper=subprocess.run([gcc,'-std=gnu17','-g',*flags,'-c','capture.c','-o',str(helper_object)],**options)
            if helper.returncode:
                compile_=helper
        if compile_ is None or not compile_.returncode:
            compile_=subprocess.run([*compiler,*includes,program_file,*sources,str(helper_object or 'capture.c'),
                                     '-o',target.name,'-lm'],**options)
            if not compile_.stderr and validation_result:
                compile_.stderr=validation_result.stderr
            if normalized!=source and not compile_.returncode:
                compile_.stderr+='Legacy void main() is treated as int main() with a default exit status of zero.\n'
    else:
        compile_=subprocess.CompletedProcess([],0,stderr=record['warnings'])
    if compile_.returncode:
        result.update(status='failed',terminationReason='compilation_error');text=compile_.stderr[:8192];line=re.search(re.escape(source_file)+r':(\d+):(\d+)',text)
        if not re.search(r'\bmain\s*\(',code_tokens) and re.search(r'(?m)^\s*\{',code_tokens):
            text='C statements must be inside a function. Add int main(void) before the opening { and return 0; before its closing }.\n\n'+text[:7900]
        result['diagnostics']=[{'severity':'error','message':text,'line':int(line[1]) if line else None,'column':int(line[2]) if line else None}];return result
    if compile_.stderr:result['diagnostics']=[{'severity':'warning','message':compile_.stderr[:8192]}]
    if record is not None:
        result['runtimeVersion']=record['version']
    else:
        version=subprocess.run([gcc,'--version'],creationflags=_PROCESS_FLAGS,capture_output=True,text=True,timeout=3)
        if version.stdout:
            result['runtimeVersion']=version.stdout.splitlines()[0][:256]
        if compile_entry is not None:
            try:
                cache.save(compile_entry,target,compile_.stderr[:8192],result['runtimeVersion'])
            except OSError:
                pass
    live=request.get('interactive',False)
    publisher=_live.TracePublisher(workspace, early_batch=8) if live else None
    broker=_live.NativeInputBroker(workspace,lambda:publisher.publish(result,force=True)) if live and not cpp else None
    if request.get('execution')=='run':
        # The same real GCC output and stdin guard, without debugger step limits.
        with (workspace/'native.log').open('wb') as log:
            try:completed=subprocess.run(creationflags=_PROCESS_FLAGS, args=[str(target),*request.get('arguments',[])],cwd=workspace,stdout=log,stderr=log,timeout=None if live else _limits.RUN_SECONDS)
            finally:
                if broker:broker.close()
        if completed.returncode:
            result.update(status='failed',terminationReason='runtime_error')
            result['diagnostics'].append({'severity':'error','message':read_output(workspace/'stderr.txt') or exit_diagnostic(completed.returncode)})
        if any((workspace/name).exists() and (workspace/name).stat().st_size>_limits.RUN_OUTPUT_BYTES for name in ('stdout.txt','stderr.txt')):
            result['diagnostics'].append({'severity':'warning','message':'The output preview is limited to the first 64 KiB per stream.'})
        result['steps']=[{'index':0,'event':'completed' if result['status']=='completed' else 'terminated','location':None,'frames':[],
            'globals':{},'objects':{},'stdout':read_output(workspace/'stdout.txt',_limits.RUN_OUTPUT_BYTES),'stderr':read_output(workspace/'stderr.txt',_limits.RUN_OUTPUT_BYTES),'exception':None,'note':result['terminationReason']}]
        result['limitations'].append('Run code does not record memory or frames. Use Visualize to inspect execution.')
        return result
    mi=MI(workspace,live);line_breakpoints=False;configured=False
    try:
        obs=Observer(mi,source,source_file)
        mi.batch(['-gdb-set pagination off', '-gdb-set confirm off', '-gdb-set auto-load off',
                  '-gdb-set print elements 40', '-gdb-set breakpoint always-inserted on'])
        mi.command('-file-exec-and-symbols '+q(target))
        if request.get('arguments'):
            if os.name!='nt':mi.command('-gdb-set startup-with-shell off')
            mi.command('-exec-arguments '+' '.join(q(arg) for arg in request['arguments']))
        mi.command('-break-insert main');mi.command('-exec-run');stop=mi.stopped()
        while True:
            if stop.get('reason','').startswith('exited'):
                if stop.get('reason')=='exited-signalled':
                    result.update(status='failed',terminationReason='runtime_error')
                    result['diagnostics'].append({'severity':'error','message':'C program was terminated by '+stop.get('signal-name','a signal')+'.'})
                elif stop.get('reason')=='exited' and stop.get('exit-code','0')!='0':
                    result.update(status='failed',terminationReason='runtime_error')
                    result['diagnostics'].append({'severity':'error','message':'C program exited with status '+stop['exit-code']+'.'})
                break
            if len(result['steps'])>=_limits.MAX_STEPS-1:result.update(status='truncated',terminationReason='step_limit');break
            file=Path(stop.get('frame',{}).get('fullname',stop.get('frame',{}).get('file',''))).name
            if stop.get('reason')=='signal-received' and file!=source_file:
                result.update(status='failed',terminationReason='runtime_error')
                result['diagnostics'].append({'severity':'error','message':stop.get('signal-name','Signal')+': '+stop.get('signal-meaning','The native runtime stopped outside the submitted source.')})
                break
            if file==source_file:
                state=obs.snapshot(stop,len(result['steps']),workspace);result['steps'].append(state)
                if publisher:publisher.publish(result)
                if state['exception']:result.update(status='failed',terminationReason='runtime_error');result['diagnostics'].append({'severity':'error','message':state['exception']['type']+': '+state['exception']['message'],'line':state['location']['line']});break
                if not configured:line_breakpoints=mi.record_user_lines(source_file);configured=True
                mi.command('-exec-continue' if line_breakpoints else '-exec-step')
            else:mi.command('-exec-continue' if line_breakpoints else '-exec-finish')
            stop=mi.stopped()
    finally:
        mi.close()
        if broker:broker.close()
    last=result['steps'][-1] if result['steps'] else {'globals':{},'objects':{}}
    stopped_objects={key:{**obj,'allocation':'unknown','note':'Last debugger observation; storage lifetime is unknown after execution stops.'} for key,obj in last['objects'].items()}
    if any((workspace/name).exists() and (workspace/name).stat().st_size>_limits.RUN_OUTPUT_BYTES for name in ('stdout.txt','stderr.txt')):
        result['diagnostics'].append({'severity':'warning','message':'The output preview is limited to the first 64 KiB per stream.'})
    result['steps'].append({'index':len(result['steps']),'event':'completed' if result['status']=='completed' else 'terminated','location':None,
        'frames':[],'globals':last['globals'],'objects':stopped_objects,'stdout':read_output(workspace/'stdout.txt',_limits.RUN_OUTPUT_BYTES),'stderr':read_output(workspace/'stderr.txt',_limits.RUN_OUTPUT_BYTES),'exception':None,'note':result['terminationReason']})
    return result

if __name__=='__main__':
    request_path,result_path=map(Path,sys.argv[1:3])
    try:result=execute(json.loads(request_path.read_text(encoding='utf-8')),request_path.parent)
    except Exception as e:print(f'{type(e).__name__}: {e}'[:2000],file=sys.stderr);sys.exit(1)
    result_path.write_text(json.dumps(result),encoding='utf-8')
