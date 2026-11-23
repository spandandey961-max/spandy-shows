import { useEffect,useLayoutEffect,useRef } from 'react';
import * as monaco from 'monaco-editor/editor/editor.api.js';
import {language as pythonGrammar,conf as pythonConfiguration} from 'monaco-editor/languages/definitions/python/python.js';
import {language as javaGrammar,conf as javaConfiguration} from 'monaco-editor/languages/definitions/java/java.js';
import {language as cppGrammar,conf as cppConfiguration} from 'monaco-editor/languages/definitions/cpp/cpp.js';
import 'monaco-editor/editor/contrib/bracketMatching/browser/bracketMatching.js';
import 'monaco-editor/editor/contrib/indentation/browser/indentation.js';
import EditorWorker from 'monaco-editor/editor/editor.worker.js?worker';
import type { Language, Trace } from './types';
// Install grammar and editing rules before the first model requests its language.
for(const [id,grammar,configuration] of [
 ['python',pythonGrammar,pythonConfiguration],
 ['java',javaGrammar,javaConfiguration],
 ['cpp',cppGrammar,cppConfiguration],
] as const){
 monaco.languages.register({id});
 monaco.languages.setMonarchTokensProvider(id,grammar);
 monaco.languages.setLanguageConfiguration(id,configuration);
}
(globalThis as unknown as {MonacoEnvironment:unknown}).MonacoEnvironment={getWorker:()=>new EditorWorker()};
monaco.editor.defineTheme('spandy-ink',{base:'vs-dark',inherit:true,rules:[{token:'comment',foreground:'88958D',fontStyle:'italic'},{token:'keyword',foreground:'E6A381'},{token:'string',foreground:'ACCCAD'},{token:'number',foreground:'D9BA7E'},{token:'identifier',foreground:'E5E6E2'},{token:'type',foreground:'8DC0D1'}],colors:{'editor.background':'#202521','editor.foreground':'#e6e8e2','editorLineNumber.foreground':'#96a08f','editorLineNumber.activeForeground':'#e6b48b','editor.lineHighlightBackground':'#ffffff04','editor.selectionBackground':'#52665360','editorCursor.foreground':'#e6b48b','editorGutter.background':'#202521','editorIndentGuide.background1':'#39433a'}});
monaco.editor.defineTheme('spandy-paper',{base:'vs',inherit:true,rules:[{token:'comment',foreground:'70796D',fontStyle:'italic'},{token:'keyword',foreground:'A43C28'},{token:'string',foreground:'44704A'},{token:'number',foreground:'986225'},{token:'type',foreground:'326986'}],colors:{'editor.background':'#fffefa','editor.foreground':'#303831','editorLineNumber.foreground':'#858D80','editorLineNumber.activeForeground':'#a43c28','editor.selectionBackground':'#dce8ed','editorCursor.foreground':'#a43c28','editorGutter.background':'#fffefa','editorIndentGuide.background1':'#e1e4db'}});
export default function CodeEditor({source,documentVersion,language,onChange,line,trace,theme,onRun,onVisualize}:{source:string;documentVersion:number;language:Language;onChange:(s:string)=>void;line?:number;trace:Trace|null;theme:string;onRun:()=>void;onVisualize:()=>void}){
 const host=useRef<HTMLDivElement>(null),editor=useRef<monaco.editor.IStandaloneCodeEditor|null>(null),callback=useRef(onChange),decorations=useRef<monaco.editor.IEditorDecorationsCollection|null>(null),replacing=useRef(false);
 const activeLine=useRef(line);activeLine.current=line;
 const appliedVersion=useRef(documentVersion);
 callback.current=onChange;
 const actions=useRef({onRun,onVisualize});actions.current={onRun,onVisualize};
 useEffect(()=>{
  if(!host.current)return;
  const e=monaco.editor.create(host.current,{value:source,language:language==='c'?'cpp':language,theme:theme==='dark'?'spandy-ink':'spandy-paper',fontFamily:'"IBM Plex Mono", "Consolas", monospace',fontSize:13,lineHeight:24,minimap:{enabled:false},automaticLayout:true,scrollBeyondLastLine:false,padding:{top:18,bottom:18},lineNumbersMinChars:3,glyphMargin:true,folding:false,renderLineHighlight:'none',overviewRulerLanes:0,hideCursorInOverviewRuler:true,wordWrap:'on',tabSize:4,insertSpaces:true,detectIndentation:false,
   autoIndent:'full',autoIndentOnPaste:true,autoClosingBrackets:'languageDefined',autoClosingQuotes:'languageDefined',autoSurround:'languageDefined',autoClosingOvertype:'auto',autoClosingDelete:'auto',matchBrackets:'always',
   accessibilitySupport:'on',ariaLabel:'Spandy Shows code editor',stickyScroll:{enabled:false},scrollbar:{verticalScrollbarSize:6,horizontalScrollbarSize:6}});
  e.addCommand(monaco.KeyMod.CtrlCmd|monaco.KeyCode.Enter,()=>actions.current.onRun());
  e.addCommand(monaco.KeyMod.CtrlCmd|monaco.KeyMod.Shift|monaco.KeyCode.Enter,()=>actions.current.onVisualize());
  e.addCommand(monaco.KeyMod.CtrlCmd|monaco.KeyCode.KeyZ,()=>void e.getModel()?.undo(),'editorTextFocus');
  e.addCommand(monaco.KeyMod.CtrlCmd|monaco.KeyCode.KeyY,()=>void e.getModel()?.redo(),'editorTextFocus');
  e.addCommand(monaco.KeyMod.CtrlCmd|monaco.KeyMod.Shift|monaco.KeyCode.KeyZ,()=>void e.getModel()?.redo(),'editorTextFocus');
  editor.current=e; decorations.current=e.createDecorationsCollection();
  const nativeEdit=(event:Event)=>{
   const action=(event as CustomEvent).detail;
   if(action!=='undo'&&action!=='redo')return;
   if(host.current?.contains(document.activeElement)){const model=e.getModel();if(action==='undo')void model?.undo();else void model?.redo();}
   else if(document.activeElement?.matches('input,textarea,[contenteditable="true"]'))document.execCommand(action);
   else {e.focus();e.trigger("desktop",action,null);}
  };
  window.addEventListener('spandy-editor-edit',nativeEdit);
  const subscription=e.onDidChangeModelContent(()=>{if(!replacing.current)callback.current(e.getValue());});
  // Monaco initially measures the fallback font. Refresh when the web font arrives.
  let disposed=false,fontFrame=0;
  const refreshFontMetrics=()=>{
   if(disposed)return;
   cancelAnimationFrame(fontFrame);
   fontFrame=requestAnimationFrame(()=>{if(!disposed){monaco.editor.remeasureFonts();e.layout();}});
  };
  const fonts=document.fonts;
  fonts?.addEventListener('loadingdone',refreshFontMetrics);
  fonts?.addEventListener('loadingerror',refreshFontMetrics);
  fonts?.load('13px "IBM Plex Mono"').then(refreshFontMetrics,refreshFontMetrics);
  let layoutFrame=0;
  const layout=e.onDidLayoutChange(()=>{cancelAnimationFrame(layoutFrame);layoutFrame=requestAnimationFrame(()=>{if(activeLine.current)e.revealLineInCenterIfOutsideViewport(activeLine.current);});});
  return ()=>{window.removeEventListener('spandy-editor-edit',nativeEdit);disposed=true;cancelAnimationFrame(fontFrame);fonts?.removeEventListener('loadingdone',refreshFontMetrics);fonts?.removeEventListener('loadingerror',refreshFontMetrics);cancelAnimationFrame(layoutFrame);layout.dispose();subscription.dispose();e.getModel()?.dispose();e.dispose();editor.current=null;};
 },[]);
 useEffect(()=>{monaco.editor.setTheme(theme==='dark'?'spandy-ink':'spandy-paper')},[theme]);
 useLayoutEffect(()=>{
  // React's echo of a keystroke must never replace a newer Monaco buffer.
  // Only opening another document explicitly requests a model replacement.
  if(appliedVersion.current===documentVersion)return;
  appliedVersion.current=documentVersion;
  const e=editor.current;
  if(e&&e.getValue()!==source){replacing.current=true;try{e.setValue(source);}finally{replacing.current=false;}}
 },[source,documentVersion]);
 useEffect(()=>{const m=editor.current?.getModel();if(m)monaco.editor.setModelLanguage(m,language==='c'?'cpp':language);},[language]);
 useEffect(()=>{
  decorations.current?.set(line?[{range:new monaco.Range(line,1,line,1),options:{isWholeLine:true,className:'executing-line',glyphMarginClassName:'executing-glyph',linesDecorationsClassName:'executing-border'}}]:[]);
  if(line)editor.current?.revealLineInCenterIfOutsideViewport(line);
 },[line]);
 useEffect(()=>{const m=editor.current?.getModel();if(m)monaco.editor.setModelMarkers(m,'execution',(trace?.diagnostics||[]).filter(d=>d.line).map(d=>({startLineNumber:d.line!,endLineNumber:d.line!,startColumn:d.column||1,endColumn:(d.column||1)+1,message:d.message,severity:d.severity==='error'?monaco.MarkerSeverity.Error:monaco.MarkerSeverity.Warning})));},[trace]);
 return <div ref={host} className="monaco-host"/>;
}
