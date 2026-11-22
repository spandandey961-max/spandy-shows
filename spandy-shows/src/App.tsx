import {useEffect,useMemo,useRef,useState} from 'react';
import {ArrowUpRight,BookOpen,Check,ChevronDown,ChevronLeft,ChevronRight,Copy,Download,FileCode2,FolderOpen,HelpCircle,Link,LoaderCircle,Moon,Pause,Pencil,Play,Save,SkipBack,SkipForward,Sun,Terminal,Trash2,X} from 'lucide-react';
import CodeEditor from './Editor';
import Diagram from './Diagram';
import Output from './Output';
import type {InputEcho} from './Output';
import StepExplanation from './StepExplanation';
import {examples} from './examples';
import {inspectorTrace} from './inspector';
import {memoryAccesses} from './memoryAccess';
import {loopAccesses} from './loopAccess';
import {memoryLayout} from './memoryLayout';
import {retainedStep,playbackOutput} from './playback';
import {sourceFile} from './sourceFile';
import {detectLanguage,executionLanguage} from './detectLanguage';
import {languageName} from './types';
import type {Example,Language,Trace} from './types';
import {desktop,desktopHeaders,readDraft} from './desktop';

async function api(path:string,options?:RequestInit){
 const res=await fetch('/api'+path,{...options,headers:{'Content-Type':'application/json',...desktopHeaders(),...options?.headers}});
 const data=await res.json();if(!res.ok)throw Object.assign(new Error(data.error?.message||data.detail?.[0]?.msg||(typeof data.detail==='string'?data.detail:'The service could not complete this request.')),{status:res.status});return data;
}
function diagnosticText(message:string){return message.replace(/^\s*at SpandyRun(?:\$[\w$]+)?\.[^\n]*(?:\n|$)/gm,'').trimEnd();}
type Execution='run'|'visualize';
type PendingInput={id:number;line:number;type:'integer'|'number'|'character'|'text'};
type Saved={id:string;title:string;language:Language;nativeMode?:'c'|'cpp';source?:string;stdin?:string;selectedStep:number;created:number;updated?:number};
function readSaved():Saved[]{try{return JSON.parse(localStorage.getItem('spandy-shows-programs')||'[]')}catch{return []}}
export default function App(){
 const draft=useRef(readDraft());
 const [language,setLanguage]=useState<Language>(draft.current?.language||'python'),[source,setSource]=useState(draft.current?.source??examples.python[0].source),[stdin,setStdin]=useState(''),[title,setTitle]=useState(draft.current?.title||examples.python[0].title);
 const [activeSaved,setActiveSaved]=useState<string|null>(draft.current?.id||null),[saveName,setSaveName]=useState(''),[renaming,setRenaming]=useState<Saved|null>(null),[saving,setSaving]=useState(false);
 const [programArgs,setProgramArgs]=useState('');
 const [nativeMode,setNativeMode]=useState<'c'|'cpp'>(draft.current?.nativeMode==='cpp'?'cpp':'c');
 const [programFiles,setProgramFiles]=useState<Record<string,string>>({}),[generatedFiles,setGeneratedFiles]=useState<Record<string,string>>({});
 const fileName=useMemo(()=>language==='c'&&nativeMode==='cpp'?'main.cpp':sourceFile(language,source),[language,source,nativeMode]);
 const [trace,setTrace]=useState<Trace|null>(null),[traceSource,setTraceSource]=useState(''),[step,setStep]=useState(0),[playing,setPlaying]=useState(false),[speed,setSpeed]=useState(1),[execution,setExecution]=useState<Execution>('visualize');
 const [running,setRunning]=useState(false),[health,setHealth]=useState<{languages:Record<Language,boolean>;executionMode:string;persistence:string;limits?:{memoryMiB:number}}|null>(null),[error,setError]=useState('');
 const [modal,setModal]=useState<'examples'|'help'|'saved'|'share'|'copy'|'save'|null>(null),[search,setSearch]=useState(''),[saved,setSaved]=useState<Saved[]>(desktop?[]:readSaved),[toast,setToast]=useState(''),[shareUrl,setShareUrl]=useState(''),[sharing,setSharing]=useState(false);
 const [theme,setTheme]=useState(()=>localStorage.getItem('spandy-shows-theme')||(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light')),[showObjects,setShowObjects]=useState(false),[inputIssue,setInputIssue]=useState('');
 const inputField=useRef<HTMLInputElement>(null);
 const [pending,setPending]=useState<PendingInput|null>(null),[response,setResponse]=useState(''),[sending,setSending]=useState(false),[liveOutput,setLiveOutput]=useState(''),[echoes,setEchoes]=useState<InputEcho[]>([]);
 const echoesRef=useRef<InputEcho[]>([]),frontier=useRef(0),latestOutput=useRef('');
 const job=useRef<string|null>(null),runSerial=useRef(0),initial=useRef(false),dialog=useRef<HTMLDialogElement>(null),modalOpener=useRef<HTMLElement|null>(null),requestedStep=useRef<number|null>(null);
 const executing=useRef(false),inputSubmitting=useRef(false);
 const stale=!!trace&&(source!==traceSource||language!==trace.language);
 const displayTrace=useMemo(()=>inspectorTrace(trace,traceSource),[trace,traceSource]);
 const current=!stale?displayTrace?.steps[step]:undefined,prior=!stale?displayTrace?.steps[step-1]:undefined;
 const previous=current?.thread===prior?.thread?prior:undefined;
 const iterations=useMemo(()=>loopAccesses(displayTrace,traceSource),[displayTrace,traceSource]);
 const accesses=useMemo(()=>{
  if(!current)return [];
  const loop=iterations.get(step)||[];
  return [...loop,...memoryAccesses(current,previous,traceSource).filter(access=>
   access.kind==='written'||!loop.some(item=>item.key===access.key))];
 },[current,previous,traceSource,iterations,step]);
 const names=useMemo(()=>memoryLayout(current).names,[current]);
 const [memoryFocus,setMemoryFocus]=useState<{key:string;step:typeof current}>();
 const max=(trace?.steps.length||1)-1;
 const objectOrder=useMemo(()=>Object.keys(current?.objects||{}),[current]);
 const hasObjects=!stale&&Object.keys(current?.objects||{}).length>0;
 const playbackReady=execution==='visualize'&&!!trace&&!stale&&trace.steps.length>0;
 const disabled=!playbackReady;
 const atInput=!!pending&&(execution==='run'||step===max);
 const recordingState=useRef({max,running,waiting:!!pending});
 recordingState.current={max,running,waiting:!!pending};
 const tell=(message:string)=>setToast(message);
 async function attachFiles(files:File[]){
  if(files.length>8||files.reduce((total,file)=>total+file.size,0)>256*1024){tell('Choose up to eight files totaling 256 KiB.');return;}
  const names=files.map(file=>file.name.toLowerCase());
  if(new Set(names).size!==names.length||files.some(file=>!(/^[A-Za-z0-9][A-Za-z0-9._ -]{0,79}$/).test(file.name)||/[. ]$/.test(file.name)||/^(con|prn|aux|nul|com\d|lpt\d)(\.|$)/i.test(file.name))){tell('Use distinct file names with letters, numbers, spaces, dots, underscores or hyphens.');return;}
  try{
   const entries=await Promise.all(files.map(async file=>{
    const bytes=new Uint8Array(await file.arrayBuffer());
    let data='';
    for(let offset=0;offset<bytes.length;offset+=8192)data+=String.fromCharCode(...bytes.subarray(offset,offset+8192));
    return [file.name,btoa(data)] as const;
   }));
   setProgramFiles(Object.fromEntries(entries));
  }catch{tell('Could not read an input file.');}
 }
 function downloadResult(name:string,data:string){
  const url=URL.createObjectURL(new Blob([Uint8Array.from(atob(data),c=>c.charCodeAt(0))]));
  const link=document.createElement('a');link.href=url;link.download=name;link.click();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
 }
 const nativeActions=useRef<(command:string)=>void>(()=>{});
 nativeActions.current=command=>{
  if(command==='save')saveLocal();
  else if(command==='open')void openNative();
  else if(command==='programs'){setSearch('');setModal('saved');}
  else if(command==='export')download();
  else if(command==='new')load({id:'new',title:'Untitled program',source:'',category:'Your code',description:''});
  else if(command==='run'&&!running)void execute('run');
  else if(command==='visualize'&&!running)void execute('visualize');
  else if(command==='help')setModal('help');
  else if(command==='undo'||command==='redo')window.dispatchEvent(new CustomEvent('spandy-editor-edit',{detail:command}));
 };
 useEffect(()=>window.spandyDesktop?.onCommand(command=>nativeActions.current(command)),[]);
 useEffect(()=>{
  if(!desktop)return;
  window.spandyDesktop?.setDocumentTitle(title);
  const flush=()=>{try{localStorage.setItem('spandy-shows-draft',JSON.stringify({source,language,title,nativeMode,id:activeSaved}));}catch{}};
  const timer=setTimeout(flush,200);
  window.addEventListener('beforeunload',flush);
  return()=>{clearTimeout(timer);window.removeEventListener('beforeunload',flush);};
 },[source,language,title,activeSaved,nativeMode]);
 useEffect(()=>{
  document.documentElement.dataset.theme=theme;document.documentElement.style.colorScheme=theme;
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content',theme==='dark'?'#161c19':'#f4f2ee');
  localStorage.setItem('spandy-shows-theme',theme);
 },[theme]);
 useEffect(()=>{if(!toast)return;const timer=setTimeout(()=>setToast(''),3500);return()=>clearTimeout(timer)},[toast]);
 useEffect(()=>{
  if(modal){modalOpener.current=document.activeElement as HTMLElement;dialog.current?.showModal();}
  else {dialog.current?.close();modalOpener.current?.focus();}
 },[modal]);
 useEffect(()=>{
  if(!playing||stale)return;
  // New checkpoints must not reset this clock before its next tick.
  const timer=setInterval(()=>setStep(n=>{const state=recordingState.current;if(n>=state.max){if(!state.running||state.waiting)setPlaying(false);return n}return n+1}),1000/speed);
  return()=>clearInterval(timer);
 },[playing,speed,stale]);
 useEffect(()=>{if(pending&&(execution==='run'||step===max))requestAnimationFrame(()=>inputField.current?.focus());},[pending?.id,step,max,execution]);
 async function submitInput(eof=false){
  if(!pending||!job.current||inputSubmitting.current)return;
  inputSubmitting.current=true;
  const request=pending,id=job.current,serial=runSerial.current,value=response,outputOffset=latestOutput.current.length,requestStep=frontier.current;
  setSending(true);setInputIssue('');
  try{
   await api('/jobs/'+id+'/input',{method:'POST',body:JSON.stringify({id:request.id,text:eof?'':value,eof})});
   if(serial!==runSerial.current)return;
   if(!eof){
    const next=[...echoesRef.current,{id:request.id,offset:outputOffset,text:value,stepIndex:requestStep}];
    echoesRef.current=next;setEchoes(next);
   }
   setPending(null);setResponse('');setPlaying(false);
  }catch(e){if(serial===runSerial.current)setInputIssue((e as Error).message)}
  finally{if(serial===runSerial.current){inputSubmitting.current=false;setSending(false)}}
 }
 async function execute(mode:Execution='visualize',code=source,lang=language,initialInput=stdin,initialTitle=title,compilerMode=nativeMode){
  if(executing.current)return;
  executing.current=true;
  const correctLanguage=lang==='c'&&compilerMode==='cpp'?'c':executionLanguage(code,lang);
  if(correctLanguage!==lang){setLanguage(correctLanguage);tell(`${languageName[correctLanguage]} detected. Using the ${languageName[correctLanguage]} compiler.`);lang=correctLanguage;}
  const serial=++runSerial.current;
  if(job.current){void api('/jobs/'+job.current,{method:'DELETE'}).catch(()=>{});job.current=null;}
  setPlaying(false);setRunning(true);setExecution(mode);setShowObjects(mode==='visualize');setError('');setInputIssue('');setTrace(null);setTraceSource(code);setStep(0);setGeneratedFiles({});
  setPending(null);setResponse('');setSending(false);inputSubmitting.current=false;setLiveOutput('');setEchoes([]);echoesRef.current=[];latestOutput.current='';frontier.current=0;
  try{
   const submitted=await api('/jobs',{method:'POST',body:JSON.stringify({language:lang,source:code,stdin:initialInput,title:initialTitle,selectedStep:0,execution:mode,interactive:true,nativeMode:lang==='c'?compilerMode:'c',arguments:programArgs.replace(/\r\n/g,'\n').split('\n').filter(arg=>arg.length>0),files:programFiles})});
   if(serial!==runSerial.current){void api('/jobs/'+submitted.id,{method:'DELETE'});return;}
   job.current=submitted.id;
   let state=submitted,lastRequest=0,lastTraceCount=0,lastTraceFetch=0;
   while(['queued','running','waiting'].includes(state.status)){
    await new Promise(resolve=>setTimeout(resolve,100));if(serial!==runSerial.current)return;
    state=await api('/jobs/'+submitted.id);if(serial!==runSerial.current)return;
    if(state.live){setLiveOutput(state.live.stdout);latestOutput.current=state.live.stdout;}
    const request:PendingInput|null=state.live?.input||null;
    const newRequest=!!request&&request.id!==lastRequest;
    if(mode==='visualize'&&(((state.live?.traceSteps||0)>lastTraceCount&&performance.now()-lastTraceFetch>300)||newRequest)&&['queued','running','waiting'].includes(state.status)){
     lastTraceFetch=performance.now();
     const partial:Trace|undefined=await api('/jobs/'+submitted.id+'/trace').catch(e=>{if(e.status!==409)throw e;});
     if(serial!==runSerial.current)return;
     if(partial){lastTraceCount=partial.steps.length;setTrace(partial);frontier.current=Math.max(0,lastTraceCount-1);}
    }
    if(request&&request.id!==lastRequest){
     lastRequest=request.id;
     setPending(request);setResponse('');setInputIssue('');
    }
   }
   if(state.status==='cancelled'&&!state.error){if(serial===runSerial.current)tell('Execution cancelled.');return;}
   if(state.error)throw new Error(state.error);
   const result:Trace=await api('/jobs/'+submitted.id+'/trace');if(serial!==runSerial.current)return;
   setTrace(result);setTraceSource(code);setGeneratedFiles(state.files||{});
   const requested=requestedStep.current;
   setStep(n=>mode==='run'?Math.max(0,result.steps.length-1):retainedStep(n,result.steps.length,requested));requestedStep.current=null;
  }catch(e){if(serial===runSerial.current)setError((e as Error).message)}
  finally{if(serial===runSerial.current){executing.current=false;inputSubmitting.current=false;setRunning(false);setPending(null);setSending(false);job.current=null;}}
 }
 useEffect(()=>{
  const key=(e:KeyboardEvent)=>{
   if(e.defaultPrevented||e.isComposing||modal||(e.key==='Enter'&&e.repeat))return;
   const target=e.target instanceof HTMLElement?e.target:null;
   if(target?.closest('.monaco-editor'))return;
   if(e.key==='Enter'&&(e.ctrlKey||e.metaKey)){e.preventDefault();if(!running)void execute(e.shiftKey?'visualize':'run');return;}
   if(e.key==='Enter'&&target===inputField.current){e.preventDefault();void submitInput();return;}
   if(target?.closest('input,textarea,select,[contenteditable="true"]'))return;
   if(e.key==='Enter'&&!target?.closest('button,a')&&!running){e.preventDefault();void execute();return;}
   if(!trace||stale||execution!=='visualize')return;
   if(e.key==='ArrowRight'){e.preventDefault();setPlaying(false);setStep(n=>e.ctrlKey||e.metaKey?max:Math.min(max,n+1));}
   if(e.key==='ArrowLeft'){e.preventDefault();setPlaying(false);setStep(n=>e.ctrlKey||e.metaKey?0:Math.max(0,n-1));}
   if(e.code==='Space'){if(target?.closest('button,a'))return;e.preventDefault();if(step===max&&!running)setStep(0);setPlaying(x=>!x);}
   if(e.key==='Home'){e.preventDefault();setPlaying(false);setStep(0);}
   if(e.key==='End'){e.preventDefault();setPlaying(false);setStep(max);}
  };window.addEventListener('keydown',key);return()=>window.removeEventListener('keydown',key);
 },[trace,stale,running,modal,max,step,source,language,stdin,execution,title,pending,response,sending,programArgs,programFiles,nativeMode]);
 useEffect(()=>{
  if(initial.current)return;initial.current=true;
  void (async()=>{
   try{
    const service=await api('/health');setHealth(service);
    if(desktop)setSaved(await api('/library/programs'));
    const params=new URLSearchParams(location.search),id=params.get('share')||params.get('program');
    if(id){const program=await api(`/${params.has('share')?'shares':'programs'}/${encodeURIComponent(id)}`);setLanguage(program.language);setSource(program.source);setStdin(program.stdin);setTitle(program.title);setNativeMode(program.nativeMode==='cpp'?'cpp':'c');requestedStep.current=program.selectedStep;await execute('visualize',program.source,program.language,program.stdin,program.title,program.nativeMode==='cpp'?'cpp':'c');}
    else if(params.has('example')){const lang=params.get('language') as Language;if(['python','java','c'].includes(lang)){const example=examples[lang].find(ex=>ex.id===params.get('example'));if(example)load(example,lang);}}
   }catch(e){setError((e as Error).message)}
  })();
  return()=>{++runSerial.current;if(job.current)void api('/jobs/'+job.current,{method:'DELETE'}).catch(()=>{});};
 },[]);
 function edit(text:string){setSource(text);if(!activeSaved&&title===examples[language][0].title)setTitle(`Your ${languageName[language]} program`);setInputIssue('');setPlaying(false);if(running)void cancel();}
 async function cancel(){++runSerial.current;executing.current=false;inputSubmitting.current=false;setRunning(false);setPlaying(false);setPending(null);setSending(false);if(job.current){const id=job.current;job.current=null;await api('/jobs/'+id,{method:'DELETE'}).catch(()=>{});}tell('Execution cancelled.');}
 function load(example:Example,lang=language,compilerMode:'c'|'cpp'='c'){setNativeMode(compilerMode);if(running)void cancel();setActiveSaved(null);setLanguage(lang);setSource(example.source);setStdin(example.stdin||'');setTitle(example.title);setTrace(null);setEchoes([]);setPending(null);setLiveOutput('');setStep(0);setPlaying(false);setShowObjects(false);setError('');setInputIssue('');requestedStep.current=null;setModal(null);}
 function selectLanguage(lang:Language){if(lang!==language){if(detectLanguage(source)===lang)load({id:'your-code',title:`Your ${languageName[lang]} program`,source,stdin,category:'Your code',description:''},lang);else load(examples[lang][0],lang);}}
 function saveLocal(){setSaveName(title);setRenaming(null);setModal('save');}
 async function commitSave(){
  if(saving)return;const name=saveName.trim();if(!name){tell('Enter a program name.');return;}if(!renaming&&!source.trim()){tell('Write some code before saving.');return;}
  setSaving(true);
  try{
   if(desktop){
    if(renaming){await api('/library/programs/'+renaming.id,{method:'PATCH',body:JSON.stringify({title:name})});if(activeSaved===renaming.id)setTitle(name);}
    else{const record=await api('/library/programs'+(activeSaved?'/'+activeSaved:''),{method:activeSaved?'PUT':'POST',body:JSON.stringify({title:name,language,source,stdin,nativeMode,selectedStep:stale?0:step})});setActiveSaved(record.id);setTitle(name);}
    setSaved(await api('/library/programs'));
   }else{
    let items:Saved[];
    if(renaming){items=saved.map(s=>s.id===renaming.id?{...s,title:name}:s);if(activeSaved===renaming.id)setTitle(name);}
    else{const id=activeSaved||crypto.randomUUID();const item:Saved={id,title:name,language,source,stdin,nativeMode,selectedStep:stale?0:step,created:saved.find(s=>s.id===id)?.created||Date.now()};items=[item,...saved.filter(s=>s.id!==id)].slice(0,30);setActiveSaved(id);setTitle(name);}
    localStorage.setItem('spandy-shows-programs',JSON.stringify(items));setSaved(items);
   }
   setModal(null);tell(desktop?'Saved on this device.':'Saved in this browser.');
  }catch(e){tell((e as Error).message);}finally{setSaving(false);}
 }
 async function openSaved(item:Saved){try{const record=desktop?await api('/library/programs/'+item.id):item;load({id:record.id,title:record.title,source:record.source!,stdin:record.stdin,category:'Saved',description:''},record.language,record.nativeMode==='cpp'?'cpp':'c');setActiveSaved(record.id);requestedStep.current=record.selectedStep;}catch(e){tell((e as Error).message);}}
 async function deleteSaved(item:Saved){
  if(!confirm(`Delete “${item.title}” from ${desktop?'this device':'this browser'}?`))return;
  try{if(desktop){await api('/library/programs/'+item.id,{method:'DELETE'});setSaved(await api('/library/programs'));}else{const next=saved.filter(s=>s.id!==item.id);localStorage.setItem('spandy-shows-programs',JSON.stringify(next));setSaved(next);}if(activeSaved===item.id)setActiveSaved(null);}catch(e){tell((e as Error).message);}
 }
 async function openNative(){try{const file=await window.spandyDesktop?.openProgram();if(!file)return;
  if(file.name.endsWith('.spandy.json')){const p=JSON.parse(file.source);if(p.format!=='spandy-shows-program'||!['python','java','c'].includes(p.language)||typeof p.source!=='string')throw new Error('This is not a Spandy Shows program file.');load({id:'imported',title:String(p.title||'Imported program').slice(0,80),source:p.source,stdin:typeof p.stdin==='string'?p.stdin:'',category:'Imported',description:''},p.language,p.nativeMode==='cpp'?'cpp':'c');requestedStep.current=Math.max(0,Math.min(19999,Number(p.selectedStep)||0));}
  else{const cpp=/\.(cpp|cc|cxx)$/i.test(file.name);const lang:Language=file.name.endsWith('.java')?'java':cpp||file.name.endsWith('.c')?'c':file.name.endsWith('.py')?'python':detectLanguage(file.source)||language;load({id:'opened',title:file.name.replace(/\.[^.]+$/,'').slice(0,80),source:file.source,category:'Your code',description:''},lang,cpp?'cpp':'c');}
 }catch(e){tell((e as Error).message);}}
 function exportProgram(){const blob=new Blob([JSON.stringify({format:'spandy-shows-program',version:1,title,language,source,stdin,nativeMode,selectedStep:stale?0:step},null,2)],{type:'application/json'}),url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=title.replace(/[^\p{L}\p{N} _-]/gu,'').slice(0,60)+'.spandy.json';a.click();URL.revokeObjectURL(url);}
 function download(){const blob=new Blob([source],{type:'text/plain'}),url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=fileName;a.click();URL.revokeObjectURL(url);}
 async function copyCode(){try{await navigator.clipboard.writeText(source);tell('Code copied.');}catch{setModal('copy');}}
 async function makeShare(){setModal('share');if(desktop)return;setSharing(true);setShareUrl('');try{const record=await api('/shares',{method:'POST',body:JSON.stringify({language,source,stdin,nativeMode,title,selectedStep:stale?0:step})});setShareUrl(`${location.origin}/?share=${record.id}`);}catch(e){tell((e as Error).message)}finally{setSharing(false)}}
 const status=inputIssue?'Input issue':stale?'Edited':atInput?'Waiting for input':error?'Unavailable':execution==='visualize'&&playbackReady?(playing?'Playing':'Paused'):running?(execution==='visualize'?'Preparing steps':'Running'):trace?.status==='completed'?'Completed':trace?'Stopped':'Ready';
 return <>
 <a href="#workspace" className="skip-link">Skip to workspace</a>
 <header className="app-header">
  <a href="/" className="brand" aria-label="Spandy Shows home"><img src="/spandy-shows-icon.png" alt="" width="44" height="44"/><span>Spandy Shows<small>See your code, step by step.</small></span></a>
  <nav className="header-nav" aria-label="Workspace actions">
   <button className="nav-action" aria-label="Examples" onClick={()=>{setSearch('');setModal('examples')}}><BookOpen size={17}/><span>Examples</span></button>
   <button className="nav-action" aria-label="My programs" onClick={()=>{setSearch('');setModal('saved')}}><Save size={17}/><span>My programs</span></button>
   <button className="icon-button" aria-label={`Switch to ${theme==='light'?'dark':'light'} theme`} onClick={()=>setTheme(theme==='light'?'dark':'light')}>{theme==='light'?<Moon size={19}/>:<Sun size={19}/>}</button>
   <button className="icon-button" aria-label="Help and keyboard shortcuts" onClick={()=>setModal('help')}><HelpCircle size={19}/></button>
  </nav>
 </header>
 <main id="workspace">
  <h1 className="sr-only">Spandy Shows code compiler and visualizer</h1>
  <div className="workspace-toolbar">
   <div className="language-tabs" role="tablist" aria-label="Programming language">{(['python','java','c'] as Language[]).map(l=><button key={l} role="tab" aria-selected={language===l} className={language===l?'selected':''} onClick={()=>selectLanguage(l)}>{languageName[l]}</button>)}</div>
   <div className="document-actions">{desktop&&<><span className="program-title" title={title}>{title}</span><button className="small-button" aria-label="Open program file" onClick={()=>void openNative()}><FolderOpen size={16}/><span>Open</span></button></>}<button className="small-button" aria-label="Save" title={desktop?'Save on this device':'Save in this browser'} onClick={saveLocal}><Save size={16}/><span>Save</span></button><button className="small-button" aria-label="Share" title="Share program" onClick={()=>void makeShare()}><Link size={16}/><span>Share</span></button></div>
  </div>
  <div className="workspace-grid">
   <section className="code-panel" aria-label="Source code">
    <div className="panel-top code-top"><div className="file-label"><FileCode2 size={16}/><span>{fileName}</span></div><div className="code-tools"><button className="copy-code" onClick={()=>void copyCode()} aria-label="Copy code" title="Copy code"><Copy size={15}/><span>Copy code</span></button><button className="icon-button" aria-label="Download source code" title="Download source code" onClick={download}><Download size={17}/></button></div></div>
    <div className="editor-wrapper"><CodeEditor source={source} language={language} onChange={edit} line={execution==='visualize'?pending&&step===max?pending.line:current?.location?.line||(current?.event==='terminated'?trace?.diagnostics.find(d=>d.severity==='error'&&d.line)?.line:undefined):pending?.line} trace={stale?null:trace} theme={theme} onRun={()=>{if(!running)void execute('run')}} onVisualize={()=>{if(!running)void execute('visualize')}}/></div>
    <details className="program-options">
     <summary>Program options</summary>
     <div className="program-options-grid">
      {language==='c'&&<label>Compiler<select value={nativeMode} disabled={running} onChange={e=>{
       setNativeMode(e.target.value as 'c'|'cpp');setTrace(null);setPlaying(false);
      }}><option value="c">GNU C17</option><option value="cpp">C++17</option></select></label>}
      <label>Arguments, one per line<textarea rows={2} maxLength={4096} value={programArgs} disabled={running} onChange={e=>setProgramArgs(e.target.value)}/></label>
      <label>{language==='c'&&nativeMode==='cpp'?'Input, followed by EOF':'Input before the first prompt'}<textarea rows={2} maxLength={65536} value={stdin} disabled={running} onChange={e=>setStdin(e.target.value)}/></label>
      <label className="option-files">Program files<input type="file" multiple disabled={running} onChange={e=>{
       void attachFiles(Array.from(e.currentTarget.files||[]));e.currentTarget.value='';
      }}/></label>
     </div>
     <p>Use <code>files/</code> for data your program opens. You can attach up to eight files totaling 256 KiB.</p>
     {!!Object.keys(programFiles).length&&<div className="program-file-list">{Object.keys(programFiles).map(name=><button type="button" className="small-button" key={name} disabled={running} onClick={()=>setProgramFiles(files=>Object.fromEntries(Object.entries(files).filter(([file])=>file!==name)))} aria-label={`Remove ${name}`}>{name} <X size={13}/></button>)}</div>}
    </details>
    <div className="run-section">{running?<button className="run-button" onClick={e=>{if(e.detail<=1)void cancel()}} onKeyDown={e=>{if(e.repeat&&(e.key==='Enter'||e.key===' '))e.preventDefault()}}>{!pending&&<LoaderCircle className="spin" size={17}/>}Stop execution<X size={16}/></button>:<><button className="run-button" onClick={()=>void execute('visualize')} title="Visualize (Ctrl + Shift + Enter)"><Play fill="currentColor" size={15}/>Visualize</button><button className="visualize-button" onClick={()=>void execute('run')} title="Run code (Ctrl + Enter)">Run code<ArrowUpRight size={16}/></button></>}</div>
   </section>
   <section className="visual-panel" aria-label="Execution visualization">
    <div className="panel-top visual-top"><h2>Inside your program</h2>{hasObjects&&<button className="memory-toggle" aria-expanded={showObjects} aria-controls="program-inspector" onClick={()=>setShowObjects(x=>!x)}>Objects &amp; memory<ChevronDown size={15} className={showObjects?'expanded':''}/></button>}</div>
    <div className="visual-content" tabIndex={0} role="region" aria-label="Output and execution details">
    <div className="execution-meta"><span className={`status-pill ${error||inputIssue?'status-error':''}`}>{running&&!pending&&<LoaderCircle size={13} className="spin"/>}<span className="status-dot"/>{status}</span>{pending&&(execution==='run'||step===max)?<code>Line {pending.line} · input</code>:execution==='visualize'&&current?.location&&<code>Line {current.location.line} · {current.location.phase}</code>}</div>
    {error&&<div className="diagnostics service-error" role="alert"><h3>Execution service</h3><p>{error}</p><button className="small-button" onClick={()=>void api('/health').then(h=>{setHealth(h);void execute(execution);}).catch(e=>setError(e.message))}>Try again</button></div>}
    <Output text={playbackOutput(execution,running,atInput,current?.stdout||'',liveOutput)} inputs={echoes.filter(e=>execution==='run'||step>e.stepIndex)}/>
    {!stale&&!!Object.keys(generatedFiles).length&&<section className="diagnostics" aria-label="Generated files">
     <h3>Generated files</h3>
     <div className="generated-files">{Object.entries(generatedFiles).map(([name,data])=>{
      const image=/\.png$/i.test(name)&&data.startsWith('iVBORw0KGgo')?'png':/\.jpe?g$/i.test(name)&&data.startsWith('/9j/')?'jpeg':null;
      return <div key={name} className="generated-file">
       {image&&<img src={`data:image/${image};base64,${data}`} alt={name} loading="lazy"/>}
       <button type="button" className="small-button" onClick={()=>downloadResult(name,data)}><Download size={14}/>{name}</button>
      </div>;
     })}</div>
    </section>}
    {pending&&(execution==='run'||step===max)&&<form className="runtime-input" onSubmit={e=>{e.preventDefault();void submitInput()}} aria-label="Runtime program input">
     <div className="input-heading"><label htmlFor="runtime-input"><Terminal size={15}/>Program input</label><span>Line {pending.line} · {pending.type==='text'?'text':pending.type}</span></div>
     <div className="runtime-input-row"><input ref={inputField} id="runtime-input" aria-label="Program input" aria-describedby="runtime-input-help" autoComplete="off" spellCheck={false} maxLength={4096} inputMode={pending.type==='integer'?'numeric':pending.type==='number'?'decimal':'text'} placeholder={`Enter ${pending.type==='integer'?'an integer':pending.type==='number'?'a number':pending.type==='character'?'a character':'text'}…`} value={response} disabled={sending} onChange={e=>{setResponse(e.target.value);setInputIssue('')}}/><button type="submit" className="small-button" disabled={sending}>{sending?<LoaderCircle size={16} className="spin"/>:<ArrowUpRight size={16}/>}Continue</button></div>
     <div className="input-actions"><p id="runtime-input-help" className="input-help">Enter to continue. Send EOF when there is no more input.</p><button type="button" className="small-button" disabled={sending} onClick={()=>void submitInput(true)}>Send EOF</button></div>
     {inputIssue&&<p className="input-issue" role="alert">{inputIssue}</p>}
    </form>}
    {pending&&execution==='visualize'&&step!==max&&<div className="waiting-replay"><span>Program waiting for input at line {pending.line}.</span><button className="small-button" onClick={()=>{setPlaying(false);setStep(max)}}>Go to input line<ArrowUpRight size={14}/></button></div>}
    {execution==='visualize'&&current&&<StepExplanation step={current} previous={previous} source={traceSource} diagnostics={trace?.diagnostics} accesses={accesses} names={names} reveal={key=>{setPlaying(false);setShowObjects(true);setMemoryFocus({key,step:current});}}/>}

    {!stale&&!!trace?.diagnostics.length&&<section className="diagnostics" aria-label="Compiler and runtime diagnostics"><h3>{trace.diagnostics.some(d=>d.severity==='error')?'Errors':'Warnings'}</h3>{trace.diagnostics.map((d,i)=><p key={i} className={d.severity}>{d.line&&<code>Line {d.line}: </code>}{diagnosticText(d.message)}</p>)}</section>}
    {current?.stderr&&!trace?.diagnostics.some(d=>d.message.includes(current.stderr))&&<section className="diagnostics" aria-label="Standard error"><h3>Standard error</h3><pre>{current.stderr}</pre></section>}
    {!stale&&trace?.status==='truncated'&&!trace.diagnostics.length&&<section className="diagnostics" role="alert"><h3>Execution limit reached</h3><p>{trace.terminationReason==='step_limit'?'Visualize records up to 20,000 steps. Use Run code for longer executions.':`Execution stopped: ${trace.terminationReason.replaceAll('_',' ')}.`}</p></section>}
    {current&&(execution==='visualize'||showObjects)&&<Diagram step={current} previous={previous} objectOrder={objectOrder} showObjects={showObjects} accesses={accesses} focus={memoryFocus?.step===current?memoryFocus:undefined}/>}
    </div>
   </section>
  </div>
  <section className="playback" aria-label="Execution playback">
   <div className="step-counter"><span>Step</span><strong>{playbackReady?step+1:'—'}<span> / {playbackReady?max+1:'—'}</span></strong></div>
   <div className="playback-buttons">
    <button disabled={disabled||step===0} onClick={()=>{setPlaying(false);setStep(0)}} aria-label="First step" title="First step (Home / Ctrl + ←)"><SkipBack size={18}/></button>
    <button disabled={disabled||step===0} onClick={()=>{setPlaying(false);setStep(x=>Math.max(0,x-1))}} aria-label="Previous step" title="Previous step (←)"><ChevronLeft size={22}/></button>
    <button className="play-pause" disabled={disabled} aria-label={playing?'Pause playback':'Play execution'} title="Play / pause (Space)" onClick={()=>{if(step===max&&!running)setStep(0);setPlaying(x=>!x)}}>{playing?<Pause size={17} fill="currentColor"/>:<Play size={17} fill="currentColor"/>}</button>
    <button disabled={disabled||step===max} onClick={()=>{setPlaying(false);setStep(x=>Math.min(max,x+1))}} aria-label="Next step" title="Next step (→)"><ChevronRight size={22}/></button>
    <button disabled={disabled||step===max} onClick={()=>{setPlaying(false);setStep(max)}} aria-label="Last step" title="Last step (End / Ctrl + →)"><SkipForward size={18}/></button>
   </div>
   <div className="timeline"><input type="range" aria-label="Execution step" aria-valuetext={playbackReady?`Step ${step+1} of ${max+1}`:'Visualize a program to inspect its steps'} min={0} max={playbackReady?max:1} value={playbackReady?step:0} disabled={disabled} onChange={e=>{setPlaying(false);setStep(Number(e.target.value))}}/></div>
   <div className="speed-control"><label htmlFor="speed">Speed</label><select id="speed" aria-label="Playback speed" value={speed} onChange={e=>setSpeed(Number(e.target.value))}><option value={.5}>0.5×</option><option value={1}>1×</option><option value={2}>2×</option><option value={4}>4×</option></select></div>
  </section>
  <footer className="workspace-footer"><span>Python · Java · C</span><span className="shortcut-hint"><kbd>Ctrl</kbd> + <kbd>Enter</kbd> run <span>·</span> <kbd>←</kbd><kbd>→</kbd> step</span><button onClick={()=>setModal('help')}>Help<ArrowUpRight size={13}/></button></footer>
 </main>
 <dialog ref={dialog} className={`modal modal-${modal}`} onCancel={()=>setModal(null)} onClick={e=>{if(e.target===e.currentTarget)setModal(null)}} aria-label={modal==='help'?'About Spandy Shows':modal==='examples'?'Example library':modal==='share'?'Share program':modal==='copy'?'Copy source code':modal==='save'?'Save program':'Saved programs'}>
  <div className="modal-inner"><div className="modal-heading"><div><span className="eyebrow">SPANDY SHOWS</span><h2>{modal==='examples'?'Examples':modal==='saved'?'My programs':modal==='share'?'Share program':modal==='copy'?'Copy code':modal==='save'?(renaming?'Rename program':'Save program'):'Help & shortcuts'}</h2></div><button className="icon-button" aria-label="Close dialog" onClick={()=>setModal(null)}><X size={20}/></button></div>
   {modal==='examples'&&<><p className="modal-description">Choose a program to run or explore.</p><div className="example-controls"><div className="language-tabs">{(['python','java','c']as Language[]).map(l=><button key={l} className={language===l?'selected':''} onClick={()=>{selectLanguage(l);setModal('examples')}}>{languageName[l]}</button>)}</div><input type="search" aria-label="Search examples" placeholder="Find a concept…" value={search} onChange={e=>setSearch(e.target.value)}/></div><div className="example-list">{examples[language].filter(x=>(x.title+x.category+x.description).toLowerCase().includes(search.toLowerCase())).map((ex,i)=><button className="example-card" key={ex.id} onClick={()=>load(ex)}><span className="example-number">{String(i+1).padStart(2,'0')}</span><div><small>{ex.category}</small><h3>{ex.title}</h3><p>{ex.description}</p></div><ArrowUpRight size={17}/></button>)}</div></>}
   {modal==='saved'&&<><p className="modal-description">{desktop?'Named programs saved on this device. They remain here after closing the app.':'Up to 30 named programs, saved in this browser.'}</p><div className="library-tools"><input type="search" aria-label="Search saved programs" placeholder="Find a program…" value={search} onChange={e=>setSearch(e.target.value)}/>{desktop&&<button className="small-button" onClick={()=>void window.spandyDesktop?.showProgramsFolder()}><FolderOpen size={16}/>Device folder</button>}</div>{saved.length?<div className="saved-list">{saved.filter(s=>(s.title+languageName[s.language]).toLowerCase().includes(search.toLowerCase())).map(s=><div className="saved-item" key={s.id}><button onClick={()=>void openSaved(s)}><FileCode2 size={20}/><div><strong>{s.title}</strong><small>{languageName[s.language]} · {new Date(s.updated||s.created).toLocaleDateString()}</small></div><ArrowUpRight size={15}/></button><button className="icon-button" aria-label={`Rename ${s.title}`} onClick={()=>{setSaveName(s.title);setRenaming(s);setModal('save')}}><Pencil size={15}/></button><button className="icon-button" aria-label={`Delete ${s.title}`} onClick={()=>void deleteSaved(s)}><Trash2 size={15}/></button></div>)}</div>:<p className="saved-empty">Use Save to name and keep a program here.</p>}</>}
   {modal==='save'&&<form className="save-form" onSubmit={e=>{e.preventDefault();void commitSave();}}><p className="modal-description">{renaming?'Choose a new name for this program.':desktop?'Name your program and save it on this device.':'Name your program and save it in this browser.'}</p><label htmlFor="program-name">Program name</label><input id="program-name" value={saveName} onChange={e=>setSaveName(e.target.value)} maxLength={80} required autoFocus/><div className="save-actions"><button type="button" className="small-button" onClick={()=>setModal(null)}>Cancel</button><button type="submit" className="run-button" disabled={saving}>{saving?<LoaderCircle size={16} className="spin"/>:<Save size={16}/>} {renaming?'Rename program':'Save program'}</button></div></form>}
   {modal==='copy'&&<><p className="modal-description">Select the source below and copy it.</p><textarea className="copy-source" aria-label="Source code to copy" value={source} readOnly onFocus={e=>e.target.select()}/></>}
   {modal==='share'&&(desktop?<><p className="modal-description">Export a program file to send to another device. It includes your code, language, name and input. Open it through File → Open in Spandy Shows.</p><div className="save-actions"><button className="small-button" onClick={()=>void copyCode()}><Copy size={16}/>Copy code</button><button className="run-button" onClick={exportProgram}><Download size={16}/>Export program</button></div></>:<><p className="modal-description">Shares your code, language, input and selected step.</p>{sharing?<div className="share-loading"><LoaderCircle className="spin" size={20}/>Creating a link…</div>:shareUrl?<><label className="share-label" htmlFor="share-url">Program link</label><div className="share-link"><input id="share-url" value={shareUrl} readOnly onFocus={e=>e.target.select()}/><button aria-label="Copy share link" onClick={()=>void navigator.clipboard.writeText(shareUrl).then(()=>tell('Link copied.')).catch(()=>tell('Select the link to copy it.'))}><Copy size={18}/></button></div><p className="share-note">Anyone with the link can read the source. Links expire in 30 days.{location.hostname==='127.0.0.1'||location.hostname==='localhost'?' This local link works on this computer.':''}</p></>:<p>Could not create a link. Try again when the execution service is available.</p>}</>)}
   {modal==='help'&&<div className="help-content">
    <p>Spandy Shows. <strong>See your code, step by step.</strong></p>
    {desktop&&<><h3>Your device</h3><p>Your named programs are stored permanently in the local device library. Save updates the current saved program; Rename changes its name. File → Open reads Python, Java, C and exported Spandy Shows program files. Share exports a file that you can transfer yourself. Your draft and theme are restored on reopening. Closing the app also stops its compiler service.</p></>}
    <h3>Run or visualize</h3><p><strong>Run code</strong> compiles and executes your program, then shows the complete output. <strong>Visualize</strong> records execution so you can inspect variables, read each step explanation and move between steps. While waiting for input you can replay the recorded prefix, then return to the input line to continue. Open <strong>Objects & memory</strong> when relevant data is available. It starts closed.</p>
    <h3>Input</h3><p>Run or visualize your program. When it reaches an input read, Program input appears below Output. Enter one response and press Enter or Continue. The same execution resumes until its next read. Type hints follow the input statement; the real runtime validates conversions and reports errors. Submitted responses appear in blue in Output.</p>
    <h3>Keyboard shortcuts</h3><dl className="shortcut-list"><dt>Ctrl / ⌘ + Enter</dt><dd>Run code from the editor</dd><dt>Ctrl / ⌘ + Shift + Enter</dt><dd>Visualize</dd><dt>← / →</dt><dd>Previous / next step</dd><dt>Home / End</dt><dd>First / last step</dd><dt>Ctrl / ⌘ + ← / →</dt><dd>First / last step</dd><dt>Space</dt><dd>Play / pause</dd></dl><p>Typing and normal button keyboard controls keep their usual behavior.</p>
    <h3>Supported programs</h3><p>Run Python, Java, GNU C17 or C++17. To use C++, choose it under the C tab in Program options and supply input before running. Attach helper source files in Program options. The trace follows the code in the editor.</p><p>Python and Java record user threads. C pointers can link to declared storage and supported heap allocations. The memory panel labels observed freed addresses and preserves array indexes during playback. C values can include uninitialized bytes when the debugger cannot determine whether the program wrote them.</p><p>Save visual output as a PNG or JPEG under <code>files/</code> to see a preview. Native GUI windows need a desktop environment. Java <code>System.console()</code> needs a real terminal.</p>
    <h3>Limits</h3><p>10,000 source lines, 1 MiB source, 64 KiB interactive input, 60 seconds for Run code and 300 seconds for Visualize preparation including compilation, up to three minutes waiting per input, {health?.limits?.memoryMiB??768} MiB memory for this device and 64 KiB of preview output per stream in Run code. Intermediate Visualize snapshots retain up to 8 KiB per stream and the final step shows up to 64 KiB. Visualize records up to 20,000 snapshots and 64 MiB of trace data. Run code has no snapshot limit. Memory views show up to 6 levels, 80 objects and 40 items per collection; C arrays show up to 128 elements each and 1,024 cells per step. Programs use their complete arrays during execution.</p>
    <h3>Connected engines</h3><div className="engine-list">{(['python','java','c']as Language[]).map(l=><div key={l}><span className={`connection-dot ${health?.languages[l]?'connected':''}`}/>{languageName[l]}<span>{health?.languages[l]?'available':'unavailable'}</span></div>)}</div>
    <p className="help-fine">{health?.executionMode==='trusted-local'?'Private local execution: run your own code. Process limits do not isolate untrusted programs.':'Public hosting requires a verified hardened sandbox.'} {health?.persistence&&`Persistence: ${health.persistence}.`}</p>
   </div>}
  </div>
 </dialog>
 {toast&&<div className="toast" role="status"><Check size={16}/>{toast}</div>}
 </>;
}
