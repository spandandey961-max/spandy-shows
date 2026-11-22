"""CPython tracing worker. This is observation, NOT a security sandbox."""
import ast, builtins, hashlib, io, json, math, os, sys, types, itertools, importlib.util, dis, inspect
import array
import collections
import datetime
import decimal
import fractions
import re
import threading
from pathlib import Path
_live_spec=importlib.util.spec_from_file_location('spandy_interactive',Path(__file__).with_name('interactive.py'))
_live=importlib.util.module_from_spec(_live_spec);_live_spec.loader.exec_module(_live)

_limits_spec=importlib.util.spec_from_file_location('spandy_limits',Path(__file__).with_name('limits.py'))
_limits=importlib.util.module_from_spec(_limits_spec);_limits_spec.loader.exec_module(_limits)
MAX_STEPS, MAX_OUTPUT = _limits.MAX_STEPS, 8192
class TraceLimit(BaseException): pass

class Capture(io.StringIO):
    def __init__(self, path=None, limit=MAX_OUTPUT):
        super().__init__();self.path=path;self.limit=limit;self.truncated=False
        self.lock=threading.Lock()
        if path:path.write_text('',encoding='utf-8')
    def write(self, s):
        with self.lock:
            remaining = max(0,self.limit - self.tell())
            captured = s[:remaining]
            super().write(captured)
            if self.path and captured:
                with self.path.open('ab') as stream:
                    stream.write(captured.encode('utf-8', errors='replace'))
            if len(s) > remaining:self.truncated = True
        return len(s)

class Serializer:
    def __init__(self):
        self.identities, self.retained = {}, []
        self.objects = {}

    def reset(self): self.objects = {}

    def value(self, v, depth=0):
        t = type(v)
        hierarchy = type.__getattribute__(t,'__mro__')
        sequence = next((base for base in (list,tuple,set,frozenset,collections.deque,bytes,bytearray,array.array,memoryview)
                         if base in hierarchy),None)
        mapping = next((base for base in (collections.OrderedDict,dict) if base in hierarchy),None)
        if v is None: return {'kind':'null','type':'NoneType','value':None}
        if t in (bool, int, float, str):
            value, truncated = v, False
            if t is str and len(v)>300: value, truncated = v[:300]+'…', True
            if t is int and v.bit_length()>4096: value, truncated = '<large integer>', True
            elif t is int and abs(v)>9007199254740991: value = str(v)
            if t is float and not math.isfinite(v): value = str(v)
            return {'kind':'primitive','type':t.__name__,'value':value,'truncated':truncated}
        if t is types.FunctionType:
            return {'kind':'primitive','type':'function','value':v.__name__+'()'}
        if t is decimal.Decimal:
            return {'kind':'primitive','type':'Decimal','value':str(v)[:300]}
        if t is fractions.Fraction:
            return {'kind':'primitive','type':'Fraction','value':str(v)[:300]}
        if t in (datetime.date,datetime.datetime,datetime.time) and (t is datetime.date or v.tzinfo is None):
            return {'kind':'primitive','type':t.__name__,'value':v.isoformat()}
        if t is re.Match:
            return {'kind':'primitive','type':'Match','value':f'[{v.start()}:{v.end()}] {str(v.group())[:260]}'}
        if t is types.GeneratorType:
            return {'kind':'primitive','type':'generator','value':v.gi_code.co_name+' · '+inspect.getgeneratorstate(v).removeprefix('GEN_').lower()}
        if t is memoryview:
            try:
                if v.ndim != 1:return {'kind':'unavailable','type':'memoryview','note':'Only one-dimensional memoryviews are displayed.'}
                if len(v):v[0]
            except (ValueError,NotImplementedError):return {'kind':'unavailable','type':'memoryview','note':'This memoryview cannot be read.'}
        if t in (types.ModuleType, type):
            return {'kind':'unavailable','type':t.__name__,'note':'Module and class internals are not inspected.'}
        if sequence is None and mapping is None and self.fields(v) is None:
            return {'kind':'unavailable','type':type.__getattribute__(t,'__name__')[:256], 'note':'Unsupported value; no user representation was invoked.'}
        key = id(v)
        if key not in self.identities:
            self.identities[key] = f'o{len(self.identities)+1}'
            self.retained.append(v)
        oid = self.identities[key]
        result = {'kind':'reference','type':type.__getattribute__(t,'__name__')[:256], 'ref':oid}
        if oid in self.objects: return result
        if len(self.objects)>=80:
            return {'kind':'unavailable','type':result['type'],'truncated':True,'note':'Object limit reached.'}
        record = {'id':oid,'type':result['type'],'kind':'instance','fields':{},'items':[],'entries':[],'truncated':False}
        self.objects[oid] = record
        if depth>=6:
            record.update(truncated=True, note='Maximum traversal depth reached.')
            return result
        if sequence:
            length=sequence.__len__(v)
            record.update(kind='set' if sequence in (set,frozenset) else 'sequence',length=length)
            values=(sequence.__getitem__(v,i) for i in range(min(length,40))) if sequence is memoryview else sequence.__iter__(v)
            record['items'] = [self.value(x, depth+1) for x in itertools.islice(values,40)]
            record['truncated'] = length>40
        elif mapping:
            length=mapping.__len__(v)
            record.update(kind='mapping',length=length)
            record['entries'] = [[self.value(k,depth+1),self.value(x,depth+1)] for k,x in itertools.islice(mapping.items(v),40)]
            record['truncated'] = length>40
        else:
            fields = self.fields(v) or {}
            record['fields'] = {k[:256]:self.value(x,depth+1) for k,x in itertools.islice(fields.items(),40) if type(k) is str}
            record['truncated'] = len(fields)>40
        return result

    @staticmethod
    def fields(v):
        # Builtin storage descriptors only: never properties or user getters.
        fields=None
        for cls in type.__getattribute__(type(v),'__mro__'):
            descriptors=type.__getattribute__(cls,'__dict__')
            desc = descriptors.get('__dict__')
            if type(desc) is types.GetSetDescriptorType:
                try:fields={**desc.__get__(v, type(v)),**(fields or {})}
                except (TypeError, AttributeError):pass
            for name,desc in descriptors.items():
                if type(desc) is types.MemberDescriptorType:
                    if fields is None:fields={}
                    if len(fields)>=40:continue
                    try:fields[name]=desc.__get__(v,type(v))
                    except (TypeError,AttributeError):pass
        return fields

    def variables(self, values):
        return {k[:256]:self.value(v) for k,v in itertools.islice(((k,v) for k,v in values.items() if type(k) is str and not k.startswith('__')),100)}

def execute(request, workspace=None):
    source = request['source']
    result = {'schemaVersion':1,'language':'python','runtimeVersion':sys.version.split()[0],
              'sourceFile':'main.py','sourceHash':hashlib.sha256(source.encode()).hexdigest(),
              'status':'completed','terminationReason':'completed','steps':[],'diagnostics':[],
              'limitations':['Snapshots precede the highlighted line; returns and completion are after execution.',
                              'Standard-library calls execute normally; their internal lines are not traced.',
                              'User Python threads have separate recorded stacks. Native/library object internals may be unavailable.']}
    try:
        tree = ast.parse(source, filename='main.py')
        if request.get('execution')=='run':
            result['limitations']=['Run code does not record intermediate states. Final globals and object inspection remain bounded.']
        for node in ast.walk(tree):
            name=getattr(node,'id',getattr(node,'name',getattr(node,'attr','')))
            if isinstance(name,str) and len(name)>256:
                result.update(status='failed',terminationReason='unsupported_feature')
                result['diagnostics']=[{'severity':'error','line':node.lineno,'message':'Identifiers longer than 256 characters are unsupported.'}]
                return result
        code = compile(tree,'main.py','exec')
    except SyntaxError as e:
        result.update(status='failed',terminationReason='syntax_error')
        result['diagnostics']=[{'severity':'error','message':e.msg[:8192],'line':e.lineno or 1,'column':e.offset or 1}]
        return result
    serializer = Serializer()
    live=bool(request.get('interactive') and workspace)
    publisher=_live.TracePublisher(workspace) if live else None
    run_only = request.get('execution') == 'run'
    output_limit = _limits.RUN_OUTPUT_BYTES
    out = Capture(workspace/'stdout.txt' if live else None, output_limit)
    err = Capture(workspace/'stderr.txt' if live else None, output_limit)
    module=types.ModuleType('__main__')
    namespace=vars(module)
    namespace.update(__file__=str(workspace/'main.py') if workspace else 'main.py',__builtins__=dict(vars(builtins)))
    if workspace:(workspace/'main.py').write_text(source,encoding='utf-8')
    frame_state=threading.local()
    snapshot_lock=threading.Lock()
    threads={}
    main_thread=threading.get_ident()
    trace_stop=None
    trace_bytes=0
    trace_budget=48*1024*1024
    next_frame=itertools.count(1)
    def exception_info(e):
        args = BaseException.args.__get__(e)
        message = ', '.join(str(x)[:300] for x in args if type(x) in (str,int,float,bool))
        return {'type':type.__getattribute__(type(e),'__name__')[:256],'message':message[:4096]}
    def snapshot(frame, frames, frame_ids, event, arg=None, note=None):
        thread=threading.get_ident()
        if thread not in threads:threads[thread]='Main thread' if thread==main_thread else f'Thread {len(threads)+1}'
        serializer.reset()
        globals_ = serializer.variables(namespace)
        stack=[]
        for f in frames[-50:]:
            if f.f_code.co_name != '<module>':
                stack.append({'id':frame_ids[id(f)],'name':f.f_code.co_name,'line':f.f_lineno,'locals':serializer.variables(f.f_locals)})
        location={'file':'main.py','line':max(1,frame.f_lineno),'phase':'after' if event=='return' else 'before'}
        if frame.f_code.co_filename=='<string>':
            location=None
            note='Dynamic code · line '+str(frame.f_lineno)
        step={'index':len(result['steps']),'event':event,'location':location,'thread':threads[thread],
              'frames':stack,'globals':globals_,'stdout':out.getvalue()[:MAX_OUTPUT],'stderr':err.getvalue()[:MAX_OUTPUT], 'exception':None,'returnValue':None}
        if len(frames)>50:step['note']=f'Showing the 50 most recent calls of {len(frames)} active frames.'
        elif len(namespace)>100 or any(len(f.f_locals)>100 for f in frames[-50:]):step['note']='Variable display is truncated to 100 names per scope.'
        if note:step['note']=note
        if event=='return': step['returnValue']=serializer.value(arg)
        if event=='exception': step['exception']=exception_info(arg[1])
        step['objects'] = serializer.objects
        nonlocal trace_bytes
        trace_bytes+=len(json.dumps(step,ensure_ascii=True,allow_nan=False)) + 2
        result['steps'].append(step)
        if publisher:publisher.publish(result)
    def tracer(frame,event,arg):
        nonlocal trace_stop
        filename=frame.f_code.co_filename
        if filename!='main.py' and not (filename=='<string>' and frame.f_globals is namespace):return None
        with snapshot_lock:
            if trace_stop:return None
            if len(result['steps'])>=MAX_STEPS-1 or trace_bytes>=trace_budget:
                trace_stop='trace_limit' if trace_bytes>=trace_budget else 'step_limit'
                if workspace:
                    _live.checkpoint(workspace,result)
                    (workspace/'step-limit.flag').write_text(trace_stop,encoding='utf-8')
                raise TraceLimit()
            if not hasattr(frame_state,'frames'):
                frame_state.frames,frame_state.ids,frame_state.suspended=[],{},set()
            frames,frame_ids,suspended=frame_state.frames,frame_state.ids,frame_state.suspended
            if event=='call':
                frames.append(frame)
                resumed=id(frame) in suspended
                suspended.discard(id(frame))
                if id(frame) not in frame_ids:frame_ids[id(frame)]=f'f{next(next_frame)}'
                if frame.f_code.co_name!='<module>':snapshot(frame,frames,frame_ids,'call',note='resume' if resumed else None)
            elif event in ('line','return','exception'):
                paused=event=='return' and frame.f_lasti>=0 and dis.opname[frame.f_code.co_code[frame.f_lasti]]=='YIELD_VALUE'
                note=('suspend' if frame.f_code.co_flags & (inspect.CO_COROUTINE|inspect.CO_ASYNC_GENERATOR) else 'yield') if paused else None
                snapshot(frame,frames,frame_ids,event,arg,note)
                if event=='return':
                    if frames and frames[-1] is frame:frames.pop()
                    elif frame in frames:frames.remove(frame)
                    if paused:suspended.add(id(frame))
                    else:frame_ids.pop(id(frame),None);suspended.discard(id(frame))
        return tracer
    prev_out,prev_err,prev_in,prev_argv = sys.stdout,sys.stderr,sys.stdin,sys.argv
    prev_path,prev_module,prev_thread_trace=sys.path[:],sys.modules['__main__'],threading.gettrace()
    try:
        initial=request.get('stdin','')
        input_=io.TextIOWrapper(io.BufferedReader(_live.PythonInput(
            _live.InputClient(workspace,lambda:publisher.publish(result,force=True)),
            source,_live.initial_input(initial))),encoding='utf-8',newline=None) if live else io.TextIOWrapper(io.BytesIO(initial.encode('utf-8')),encoding='utf-8')
        sys.stdout,sys.stderr,sys.stdin = out,err,input_
        sys.argv=[namespace['__file__'],*request.get('arguments',[])]
        if workspace:sys.path[:0]=[str(workspace),str(workspace/'files')]
        sys.path.extend(path for path in os.getenv('SPANDY_PYTHON_MODULES','').split(os.pathsep) if path and Path(path).is_absolute())
        sys.modules['__main__']=module
        if not run_only:threading.settrace(tracer)
        sys.settrace(tracer if request.get('execution')!='run' else None)
        exec(code, namespace, namespace)
    except TraceLimit:
        result.update(status='truncated',terminationReason=trace_stop or 'step_limit')
    except SystemExit as e:
        if e.code not in (None,0):
            result.update(status='failed',terminationReason='runtime_error')
            result['diagnostics']=[{'severity':'error','message':f'SystemExit: {e.code}'[:8192]}]
    except BaseException as e:
        result.update(status='failed',terminationReason='runtime_error')
        result['diagnostics']=[{'severity':'error','message':exception_info(e)['type']+': '+exception_info(e)['message']}]
    finally:
        sys.settrace(None)
        threading.settrace(prev_thread_trace)
        with snapshot_lock:
            if not run_only:
                if trace_stop and result['status']=='completed':result.update(status='truncated',terminationReason=trace_stop)
                trace_stop=trace_stop or 'finished'
        sys.modules['__main__']=prev_module
        sys.path[:]=prev_path
        sys.stdout,sys.stderr,sys.stdin = prev_out,prev_err,prev_in
        sys.argv=prev_argv
    if out.truncated or err.truncated:
        result['diagnostics'].append({'severity':'warning','message':'The output preview is limited to the first 64 KiB per stream.'})
    serializer.reset()
    final = {'index':len(result['steps']),'event':'completed' if result['status']=='completed' else 'terminated',
             'location':None,'frames':[], 'globals':serializer.variables(namespace),
             'stdout':out.getvalue(),'stderr':err.getvalue(),'exception':None,'note':result['terminationReason']}
    final['objects']=serializer.objects
    result['steps'].append(final)
    return result

if __name__=='__main__':
    from pathlib import Path
    request = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    result = execute(request,Path(sys.argv[1]).parent)
    Path(sys.argv[2]).write_text(json.dumps(result,ensure_ascii=True,allow_nan=False),encoding='utf-8')
