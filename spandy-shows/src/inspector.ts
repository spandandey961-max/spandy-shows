import type {Trace} from './types';

// Hide only unused JVM startup arguments in the presentation. The raw trace
// stays intact, including all object identities and every user-created array.
export function inspectorTrace(trace:Trace|null,source:string):Trace|null{
 if(!trace||trace.language!=='java')return trace;
 const tokens=source.replace(/\/\*[\s\S]*?\*\/|\/\/[^\n]*|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'/g,m=>' '.repeat(m.length));
 const parameter=tokens.match(/\bmain\s*\(\s*(?:final\s+)?(?:java\.lang\.)?String\s*(?:(?:\[\s*\]|\.\.\.)\s*(\w+)|(\w+)\s*\[\s*\])\s*\)/);
 const name=parameter?.[1]||parameter?.[2];
 if(!name||Array.from(tokens.matchAll(/\b\w+\b/g)).filter(m=>m[0]===name).length!==1)return trace;
 const hidden=new Set<string>();
 for(const step of trace.steps){
  for(const frame of step.frames){
   const value=frame.locals[name];
   if(frame.name==='main'&&value?.kind==='reference'&&value.ref){
    const object=step.objects[value.ref];
    if(object?.type==='java.lang.String[]'&&object.length===0)hidden.add(value.ref);
   }
  }
 }
 if(!hidden.size)return trace;
 return {...trace,steps:trace.steps.map(step=>({...step,
  frames:step.frames.map(frame=>({...frame,locals:Object.fromEntries(Object.entries(frame.locals).filter(([key,value])=>!(frame.name==='main'&&key===name&&value.ref&&hidden.has(value.ref))))})),
  objects:Object.fromEntries(Object.entries(step.objects).filter(([id])=>!hidden.has(id)))
 }))};
}
