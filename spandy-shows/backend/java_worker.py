import hashlib,importlib.util,json,os,re,shutil,subprocess,sys
from pathlib import Path

# Compiler, debugger and program processes must not open Windows consoles.
_PROCESS_FLAGS = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
_spec=importlib.util.spec_from_file_location('spandy_limits',Path(__file__).with_name('limits.py'))
_limits=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(_limits)
_source_spec=importlib.util.spec_from_file_location('spandy_java_source',Path(__file__).with_name('java_source.py'))
_source=importlib.util.module_from_spec(_source_spec);_source_spec.loader.exec_module(_source)

def runtime_diagnostic(stderr,source_file='Main.java'):
    diagnostic={'severity':'error','message':stderr or 'The JVM exited with a nonzero status.'}
    line=re.search(r'\('+re.escape(source_file)+r':(\d+)\)',stderr)
    if line:diagnostic['line']=int(line[1])
    return diagnostic

def installed_helper(workspace,name):
    """Reuse the shipped helpers only when their source fingerprints match."""
    location=os.getenv('SPANDY_JAVA_HELPERS')
    if not location:return False
    directory=Path(location)
    try:
        manifest=json.loads((directory/'helpers.json').read_text(encoding='utf-8'))
        source=Path(__file__).parent/'java'/f'{name}.java'
        if manifest['sources'][source.name]!=hashlib.sha256(source.read_bytes()).hexdigest():return False
        files=list(directory.glob(name+'*.class'))
        if not (directory/(name+'.class')).is_file():return False
        for file in files:shutil.copy2(file,workspace/file.name)
        return True
    except (OSError,KeyError,ValueError):return False

def execute(request,workspace):
    source=request['source']
    metadata=_source.java_source_info(source)
    source_file,entry=metadata['sourceFile'],metadata['entryClass']
    result={'schemaVersion':1,'language':'java','runtimeVersion':'JDK 21','sourceFile':source_file,
            'sourceHash':hashlib.sha256(source.encode()).hexdigest(),'status':'completed','terminationReason':'completed',
            'steps':[],'diagnostics':[], 'limitations':['Single source file with a static main(String[] args) entry point; single-threaded JDK 21 visualization.',
            'Standard-library object internals are unavailable. Strings are shown as values; arrays and user objects preserve identity.',
            'Local variables are visible only once initialized and in scope. Snapshots precede lines; method returns are after execution.']}
    # Run code uses the real JVM. Visualization requires one execution thread.
    code_tokens=re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|//[^\n]*|/\*.*?\*/',' ',source,flags=re.S)
    if request.get('execution')!='run' and re.search(r'\b(new\s+Thread|Executors\s*\.|ProcessBuilder\s*\(|native\s+\w+|System\s*\.\s*exit\s*\()',code_tokens):
        result.update(status='failed',terminationReason='unsupported_feature');result['diagnostics']=[{'severity':'error','message':'Use Run code for threads, native methods or process control. Visualize records single-threaded user code.'}];return result
    java=os.getenv('SPANDY_JAVA','java');javac=os.getenv('SPANDY_JAVAC','javac')
    memory=int(os.getenv('SPANDY_WORKER_MEMORY_MIB','768'))
    target_heap=max(128,min(1024,memory//4));trace_heap=max(128,min(512,memory//4))
    (workspace/source_file).write_text(source,encoding='utf-8')
    (workspace/'stdin.txt').write_text(request.get('stdin',''),encoding='utf-8')
    live=request.get('interactive',False)
    if live:(workspace/'interactive.flag').write_text('1')
    cp=subprocess.run(creationflags=_PROCESS_FLAGS, args=[javac,'-J-Xmx256m','-g','-encoding','UTF-8','-d',str(workspace),str(workspace/source_file)],capture_output=True,text=True,timeout=_limits.COMPILE_SECONDS)
    if cp.returncode:
        result.update(status='failed',terminationReason='compilation_error')
        text=cp.stderr.replace(str(workspace)+os.sep,'')[:8192];line=re.search(re.escape(source_file)+r':(\d+)',text)
        result['diagnostics']=[{'severity':'error','message':text,'line':int(line[1]) if line else None}];return result
    if live and not installed_helper(workspace,'SpandyRun'):
        bridge=Path(__file__).parent/'java'/'SpandyRun.java'
        cp=subprocess.run(creationflags=_PROCESS_FLAGS, args=[javac,'-J-Xmx128m','-cp',str(workspace),'-d',str(workspace),str(bridge)],capture_output=True,text=True,timeout=15)
        if cp.returncode:raise RuntimeError(cp.stderr[-2000:])
    if request.get('execution')=='run':
        with (workspace/'stdin.txt').open('rb') as input_,(workspace/'stdout.txt').open('wb') as out,(workspace/'stderr.txt').open('wb') as err:
            completed=subprocess.run(creationflags=_PROCESS_FLAGS, args=[java,f'-Xmx{target_heap}m','-Dfile.encoding=UTF-8',f'-Dspandy.workspace={workspace}',f'-Dspandy.source={source_file}',f'-Dspandy.entry={entry}','-cp',str(workspace),'SpandyRun' if live else entry],cwd=workspace,stdin=input_,stdout=out,stderr=err,timeout=None if live else _limits.RUN_SECONDS)
        stdout=(workspace/'stdout.txt').read_bytes()[:8192].decode('utf-8',errors='replace').replace('\r\n','\n')
        stderr=(workspace/'stderr.txt').read_bytes()[:8192].decode('utf-8',errors='replace').replace('\r\n','\n')
        if completed.returncode:
            result.update(status='failed',terminationReason='runtime_error')
            result['diagnostics']=[runtime_diagnostic(stderr,source_file)]
        result['steps']=[{'index':0,'event':'completed' if completed.returncode==0 else 'terminated','location':None,'frames':[],
            'globals':{},'objects':{},'stdout':stdout,'stderr':stderr,'exception':None,'note':result['terminationReason']}]
        result['limitations']=['Run code executes without recording stack frames or objects. Use Visualize to inspect execution.']
        return result
    tracer=Path(__file__).parent/'java'/'SpandyTracer.java'
    (workspace/'visualize.flag').write_text(str(_limits.MAX_STEPS))
    (workspace/'trace-base.json').write_text(json.dumps({k:v for k,v in result.items() if k!='steps'}),encoding='utf-8')
    if not installed_helper(workspace,'SpandyTracer'):
        cp=subprocess.run(creationflags=_PROCESS_FLAGS, args=[javac,'-J-Xmx128m','--add-modules','jdk.jdi','-d',str(workspace),str(tracer)],capture_output=True,text=True,timeout=15)
        if cp.returncode: raise RuntimeError(cp.stderr[-2000:])
    cp=subprocess.run(creationflags=_PROCESS_FLAGS, args=[java,f'-Xmx{trace_heap}m',f'-Dspandy.heapMiB={target_heap}',f'-Dspandy.source={source_file}',f'-Dspandy.entry={entry}','--add-modules','jdk.jdi','-cp',str(workspace),'SpandyTracer',str(workspace)],capture_output=True,text=True,timeout=None if live else _limits.VISUALIZE_SECONDS)
    if cp.returncode: raise RuntimeError(cp.stderr[-2000:])
    result.update(json.loads((workspace/'jdi.json').read_text(encoding='utf-8')))
    if result['status']=='failed':
        result['diagnostics']=[runtime_diagnostic(result['steps'][-1]['stderr'][:8192],source_file)]
    return result

if __name__=='__main__':
    request_path,result_path=map(Path,sys.argv[1:3])
    try: result=execute(json.loads(request_path.read_text(encoding='utf-8')),request_path.parent)
    except Exception as e:
        print(str(e)[:2000],file=sys.stderr);sys.exit(1)
    result_path.write_text(json.dumps(result),encoding='utf-8')
