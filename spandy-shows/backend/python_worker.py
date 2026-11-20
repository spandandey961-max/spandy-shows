"""CPython tracing worker. This is observation, NOT a security sandbox."""
import ast, builtins, hashlib, io, json, math, sys, types, itertools, importlib.util, dis, inspect
from pathlib import Path
_live_spec=importlib.util.spec_from_file_location('spandy_interactive',Path(__file__).with_name('interactive.py'))
_live=importlib.util.module_from_spec(_live_spec);_live_spec.loader.exec_module(_live)

_limits_spec=importlib.util.spec_from_file_location('spandy_limits',Path(__file__).with_name('limits.py'))
_limits=importlib.util.module_from_spec(_limits_spec);_limits_spec.loader.exec_module(_limits)
MAX_STEPS, MAX_OUTPUT = _limits.MAX_STEPS, 8192
class TraceLimit(BaseException): pass
class OutputLimit(BaseException): pass

class Capture(io.StringIO):
    def __init__(self, path=None):
        super().__init__();self.path=path
        if path:path.write_text('',encoding='utf-8')
    def write(self, s):
        remaining = MAX_OUTPUT - self.tell()
        super().write(s[:remaining])
        if self.path:self.path.write_bytes(self.getvalue().encode('utf-8'))
        if len(s) > remaining: raise OutputLimit()
        return len(s)

class Serializer:
    def __init__(self):
        self.identities, self.retained = {}, []
        self.objects = {}

    def reset(self): self.objects = {}

    def value(self, v, depth=0):
        t = type(v)
        if v is None: return {'kind':'null','type':'NoneType','value':None}
        if t in (bool, int, float, str):
            value, truncated = v, False
            if t is str and len(v)>300: value, truncated = v[:300]+'…', True
            if t is int and v.bit_length()>1024: value, truncated = '<large integer>', True
            elif t is int and abs(v)>9007199254740991: value = str(v)
            if t is float and not math.isfinite(v): value = str(v)
            return {'kind':'primitive','type':t.__name__,'value':value,'truncated':truncated}
        if t is types.FunctionType:
            return {'kind':'primitive','type':'function','value':v.__name__+'()'}
        if t in (types.ModuleType, type):
            return {'kind':'unavailable','type':t.__name__,'note':'Module and class internals are not inspected.'}
        if t not in (list, tuple, dict, set, frozenset) and self.fields(v) is None:
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
        if t in (list, tuple, set, frozenset):
            record.update(kind='set' if t in (set,frozenset) else 'sequence',length=len(v))
            record['items'] = [self.value(x, depth+1) for x in itertools.islice(v,40)]
            record['truncated'] = len(v)>40
        elif t is dict:
            record.update(kind='mapping',length=len(v))
            record['entries'] = [[self.value(k,depth+1),self.value(x,depth+1)] for k,x in itertools.islice(v.items(),40)]
            record['truncated'] = len(v)>40
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
                              'Only the main execution thread is traced. Native/library object internals may be unavailable.']}
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
    out, err = Capture(workspace/'stdout.txt' if live else None), Capture(workspace/'stderr.txt' if live else None)
    namespace = {'__name__':'__main__', '__file__':str(workspace/'main.py') if workspace else 'main.py', '__builtins__':dict(vars(builtins))}
    if workspace:(workspace/'main.py').write_text(source,encoding='utf-8')
    frames, frame_ids, suspended = [], {}, set()
    next_frame=itertools.count(1)
    def exception_info(e):
        args = BaseException.args.__get__(e)
        message = ', '.join(str(x)[:300] for x in args if type(x) in (str,int,float,bool))
        return {'type':type.__getattribute__(type(e),'__name__')[:256],'message':message[:4096]}
    def snapshot(frame, event, arg=None, note=None):
        if len(result['steps']) >= MAX_STEPS-1: raise TraceLimit()
        serializer.reset()
        globals_ = serializer.variables(namespace)
        stack=[]
        for f in frames[-50:]:
            if f.f_code.co_name != '<module>':
                stack.append({'id':frame_ids[id(f)],'name':f.f_code.co_name,'line':f.f_lineno,'locals':serializer.variables(f.f_locals)})
        step={'index':len(result['steps']),'event':event,'location':{'file':'main.py','line':max(1,frame.f_lineno),'phase':'after' if event=='return' else 'before'},
              'frames':stack,'globals':globals_,'stdout':out.getvalue(),'stderr':err.getvalue(), 'exception':None,'returnValue':None}
        if len(namespace)>100 or any(len(f.f_locals)>100 for f in frames):step['note']='Variable display is truncated to 100 names per scope.'
        if note:step['note']=note
        if event=='return': step['returnValue']=serializer.value(arg)
        if event=='exception': step['exception']=exception_info(arg[1])
        step['objects'] = serializer.objects
        result['steps'].append(step)
        if publisher:publisher.publish(result)
    def tracer(frame,event,arg):
        if frame.f_code.co_filename != 'main.py': return None
        if event=='call':
            if len(frames)>=50: raise TraceLimit()
            frames.append(frame)
            resumed=id(frame) in suspended
            suspended.discard(id(frame))
            if id(frame) not in frame_ids:frame_ids[id(frame)]=f'f{next(next_frame)}'
            if frame.f_code.co_name!='<module>': snapshot(frame,'call',note='resume' if resumed else None)
        elif event in ('line','return','exception'):
            paused=event=='return' and frame.f_lasti>=0 and dis.opname[frame.f_code.co_code[frame.f_lasti]]=='YIELD_VALUE'
            note=('suspend' if frame.f_code.co_flags & (inspect.CO_COROUTINE|inspect.CO_ASYNC_GENERATOR) else 'yield') if paused else None
            snapshot(frame,event,arg,note)
            if event=='return':
                if frame in frames: frames.remove(frame)
                if paused:suspended.add(id(frame))
                else:frame_ids.pop(id(frame),None);suspended.discard(id(frame))
        return tracer
    prev_out,prev_err,prev_in,prev_argv = sys.stdout,sys.stderr,sys.stdin,sys.argv
    try:
        input_=_live.PythonInput(_live.InputClient(workspace,lambda:publisher.publish(result,force=True)),source) if live else io.StringIO(request.get('stdin',''))
        sys.stdout,sys.stderr,sys.stdin = out,err,input_
        sys.argv=[namespace['__file__']]
        sys.settrace(tracer if request.get('execution')!='run' else None)
        exec(code, namespace, namespace)
    except (TraceLimit,OutputLimit) as e:
        result.update(status='truncated',terminationReason='step_limit' if type(e) is TraceLimit else 'output_limit')
    except SystemExit as e:
        if e.code not in (None,0):
            result.update(status='failed',terminationReason='runtime_error')
            result['diagnostics']=[{'severity':'error','message':f'SystemExit: {e.code}'[:8192]}]
    except BaseException as e:
        result.update(status='failed',terminationReason='runtime_error')
        result['diagnostics']=[{'severity':'error','message':exception_info(e)['type']+': '+exception_info(e)['message']}]
    finally:
        sys.settrace(None)
        sys.stdout,sys.stderr,sys.stdin = prev_out,prev_err,prev_in
        sys.argv=prev_argv
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
