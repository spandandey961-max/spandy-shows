import hashlib,importlib.util,json,os,re,shutil,subprocess,sys
from pathlib import Path

# Compiler, debugger and program processes must not open Windows consoles.
_PROCESS_FLAGS = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
_spec=importlib.util.spec_from_file_location('spandy_limits',Path(__file__).with_name('limits.py'))
_limits=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(_limits)
_source_spec=importlib.util.spec_from_file_location('spandy_java_source',Path(__file__).with_name('java_source.py'))
_source=importlib.util.module_from_spec(_source_spec);_source_spec.loader.exec_module(_source)
_cache_spec=importlib.util.spec_from_file_location('spandy_java_cache',Path(__file__).with_name('java_cache.py'))
_cache=importlib.util.module_from_spec(_cache_spec);_cache_spec.loader.exec_module(_cache)

def runtime_diagnostic(stderr,source_file='Main.java'):
    diagnostic={'severity':'error','message':stderr or 'The JVM exited with a nonzero status.'}
    line=re.search(r'\('+re.escape(source_file)+r':(\d+)\)',stderr)
    if line:diagnostic['line']=int(line[1])
    return diagnostic

def installed_helper(workspace,name,release):
    """Reuse the shipped helpers only when their source fingerprints match."""
    location=os.getenv('SPANDY_JAVA_HELPERS')
    if not location:return False
    directory=Path(location)
    try:
        manifest=json.loads((directory/'helpers.json').read_text(encoding='utf-8'))
        source=Path(__file__).parent/'java'/f'{name}.java'
        if manifest['sources'][source.name]!=hashlib.sha256(source.read_bytes()).hexdigest():return False
        files=list(directory.glob(name+'*.class'))
        if not files or not (directory/(name+'.class')).is_file():return False
        for file in files:
            with file.open('rb') as stream:header=stream.read(8)
            if not header.startswith(b'\xca\xfe\xba\xbe') or len(header)!=8 or int.from_bytes(header[6:8],'big')>release+44:return False
        for file in files:shutil.copy2(file,workspace/file.name)
        return True
    except (OSError,KeyError,ValueError):return False

def execute(request,workspace):
    source=request['source']
    metadata=_source.java_source_info(source)
    source_file,entry=metadata['sourceFile'],metadata['entryClass']
    result={'schemaVersion':1,'language':'java','runtimeVersion':'unknown','sourceFile':source_file,
            'sourceHash':hashlib.sha256(source.encode()).hexdigest(),'status':'completed','terminationReason':'completed',
            'steps':[],'diagnostics':[], 'limitations':['Uploaded Java sources can be compiled together; Visualize follows the editor source.',
            'Arrays, user objects and selected JDK collections preserve identity. Strings and boxed primitives are shown as values.',
            'Local variables are visible only once initialized and in scope. Snapshots precede lines; method returns are after execution.']}
    java=os.getenv('SPANDY_JAVA','java');javac=os.getenv('SPANDY_JAVAC','javac')
    cache=Path(os.environ['SPANDY_COMPILE_CACHE']) if os.getenv('SPANDY_COMPILE_CACHE') else None
    def version(command):
        key=_cache.fingerprint(command) if cache else None
        cached=_cache.read_record(cache,'version-'+key+'.json') if cache else None
        if cached:return tuple(cached)
        process=subprocess.run([command,'-version'],creationflags=_PROCESS_FLAGS,capture_output=True,text=True,timeout=5)
        output=process.stdout+process.stderr
        match=re.search(r'\b(?:javac|(?:openjdk|java) version)\s+"?(\d+)([^\s"]*)',output)
        if process.returncode or not match:raise ValueError(f'Could not identify the Java version for {Path(command).name}.')
        value=(int(match[1]),match[1]+match[2])
        if cache:
            try:_cache.write_record(cache,'version-'+key+'.json',value)
            except OSError:pass
        return value

    def compile_error(message,line=None):
        result.update(status='failed',terminationReason='compilation_error',
                      diagnostics=[{'severity':'error','message':message[:8192],'line':line}])
        return result

    try:
        compiler,_=version(javac)
        runtime,result['runtimeVersion']=version(java)
    except (OSError,ValueError,subprocess.TimeoutExpired) as error:
        return compile_error(str(error))
    release=min(compiler,runtime)
    if release<17:return compile_error('Spandy Shows requires a Java compiler and runtime version 17 or newer.')
    memory=int(os.getenv('SPANDY_WORKER_MEMORY_MIB','768'))
    target_heap=max(128,min(1024,memory//4));trace_heap=max(128,min(512,memory//4))
    (workspace/source_file).write_text(source,encoding='utf-8')
    live=request.get('interactive',False)
    stdin=request.get('stdin','')
    if live and stdin and not stdin.endswith('\n'): stdin+='\n'
    (workspace/'stdin.txt').write_bytes(stdin.encode('utf-8'))
    (workspace/'args.txt').write_text(''.join(arg+'\n' for arg in request.get('arguments',[])),encoding='utf-8')
    if live:(workspace/'interactive.flag').write_text('1')
    run_only=request.get('execution')=='run'
    library=workspace/'files'
    classpath=os.pathsep.join([str(workspace),*(str(path) for path in sorted(library.glob('*.jar')))])
    classes=[str(workspace/source_file),*(str(path) for path in sorted(library.glob('*.java')))]
    helpers=('SpandyRun',) if run_only else ('SpandyRun','SpandyTracer')
    for helper in helpers:
        if not installed_helper(workspace,helper,release):
            classes.append(str(Path(__file__).parent/'java'/f'{helper}.java'))
    def compile_sources(preview=False):
        return subprocess.run(creationflags=_PROCESS_FLAGS, args=[javac,'-J-Xmx256m','-J-XX:+UseSerialGC',
            '-J-Duser.language=en','-J-Duser.country=US',*(('--enable-preview',) if preview else ()),
            '--release',str(release),'--add-modules','jdk.jdi','-g','-encoding','UTF-8',
            '-cp',classpath,'-d',str(workspace),*classes],capture_output=True,text=True,timeout=_limits.COMPILE_SECONDS)
    cached=None;cache_key=None
    if cache:
        try:
            fingerprints=_cache.fingerprint(javac)+_cache.fingerprint(java)
            # Include shipped helpers too, even if their classes were copied above.
            inputs=[Path(path) for path in classes]+[Path(__file__).parent/'java'/f'{name}.java' for name in helpers]
            cache_key=_cache.compilation_key(fingerprints,release,inputs,sorted(library.glob('*.jar')))
            cached=_cache.restore(cache,cache_key,workspace)
        except OSError:pass
    if cached:
        preview=cached['preview']
    else:
        cp=compile_sources()
        preview=cp.returncode!=0 and 'use --enable-preview' in cp.stderr
        if preview:
            if compiler!=runtime:
                return compile_error(f'Preview features need a matching Java compiler and runtime. javac is {compiler} and java is {runtime}.')
            cp=compile_sources(preview=True)
        if cp.returncode:
            text=cp.stderr.replace(str(workspace)+os.sep,'')[:8192];line=re.search(re.escape(source_file)+r':(\d+)',text)
            return compile_error(text,int(line[1]) if line else None)
        if cache and cache_key:
            try:_cache.save(cache,cache_key,workspace,preview,cp.stderr)
            except OSError:pass
    if run_only:
        with (workspace/'stdin.txt').open('rb') as input_,(workspace/'stdout.txt').open('wb') as out,(workspace/'stderr.txt').open('wb') as err:
            completed=subprocess.run(creationflags=_PROCESS_FLAGS, args=[java,f'-Xmx{target_heap}m','-XX:+UseSerialGC',*(('--enable-preview',) if preview else ()),
                '-Dfile.encoding=UTF-8',f'-Dspandy.workspace={workspace}',f'-Dspandy.source={source_file}',
                f'-Dspandy.entry={entry}','-cp',classpath,'SpandyRun'],cwd=workspace,stdin=input_,stdout=out,stderr=err,timeout=None if live else _limits.RUN_SECONDS)
        def read_output(name):
            with (workspace/name).open('rb') as stream:
                return stream.read(_limits.RUN_OUTPUT_BYTES).decode('utf-8',errors='replace').replace('\r\n','\n')
        stdout,stderr=read_output('stdout.txt'),read_output('stderr.txt')
        if completed.returncode:
            result.update(status='failed',terminationReason='runtime_error')
            result['diagnostics']=[runtime_diagnostic(stderr[:8192],source_file)]
        if any((workspace/name).stat().st_size>_limits.RUN_OUTPUT_BYTES for name in ('stdout.txt','stderr.txt')):
            result['diagnostics'].append({'severity':'warning','message':'The output preview is limited to the first 64 KiB per stream.'})
        result['steps']=[{'index':0,'event':'completed' if completed.returncode==0 else 'terminated','location':None,'frames':[],
            'globals':{},'objects':{},'stdout':stdout,'stderr':stderr,'exception':None,'note':result['terminationReason']}]
        result['limitations']=['Run code executes without recording stack frames or objects. Use Visualize to inspect execution.']
        return result
    (workspace/'visualize.flag').write_text(str(_limits.MAX_STEPS))
    (workspace/'trace-base.json').write_text(json.dumps({k:v for k,v in result.items() if k!='steps'}),encoding='utf-8')
    cp=subprocess.run(creationflags=_PROCESS_FLAGS, args=[java,f'-Xmx{trace_heap}m','-XX:+UseSerialGC',
        f'-Dspandy.heapMiB={target_heap}',f'-Dspandy.source={source_file}',f'-Dspandy.entry={entry}',f'-Dspandy.preview={str(preview).lower()}',
        f'-Dspandy.classpath={classpath}','--add-modules','jdk.jdi','-cp',str(workspace),'SpandyTracer',str(workspace)],
        capture_output=True,text=True,timeout=None if live else _limits.VISUALIZE_SECONDS)
    if cp.returncode: raise RuntimeError(cp.stderr[-2000:])
    result.update(json.loads((workspace/'jdi.json').read_text(encoding='utf-8')))
    if result['status']=='failed':
        result['diagnostics']=[runtime_diagnostic(result['steps'][-1]['stderr'][:8192],source_file)]
    if (workspace/'output-limited.flag').exists():
        result['diagnostics'].append({'severity':'warning','message':'The output preview is limited to the first 64 KiB per stream.'})
    return result

if __name__=='__main__':
    request_path,result_path=map(Path,sys.argv[1:3])
    try: result=execute(json.loads(request_path.read_text(encoding='utf-8')),request_path.parent)
    except Exception as e:
        print(str(e)[:2000],file=sys.stderr);sys.exit(1)
    result_path.write_text(json.dumps(result),encoding='utf-8')
