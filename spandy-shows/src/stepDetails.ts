import type {Step,Value} from './types.ts';
import {changed,display} from './types.ts';

export function describeStep(step:Step, previous:Step|undefined, source:string){
 const changes:{name:string;before?:Value;after?:Value}[]=[];
 const globalsVisible=Object.keys(step.globals).length>0;
 const scopes=[{name:step.frames.length?'global.':'',now:step.globals,old:previous?.globals},...step.frames.map(f=>({name:step.frames.length>1||globalsVisible?`${f.name} (${f.id}).`:'',now:f.locals,old:previous?.frames.find(p=>p.id===f.id)?.locals}))];
 for(const scope of scopes)for(const [name,after] of Object.entries(scope.now)){
  const before=scope.old?.[name];if(changed(after,before))changes.push({name:scope.name+name,before,after});
 }
 for(const scope of scopes)for(const [name,before] of Object.entries(scope.old||{}))if(!(name in scope.now))changes.push({name:scope.name+name,before});
 for(const frame of previous?.frames||[])if(!step.frames.some(f=>f.id===frame.id))for(const [name,before] of Object.entries(frame.locals))changes.push({name:`${frame.name} (${frame.id}).${name}`,before});
 const lines=source.split('\n'), next=step.location?lines[step.location.line-1]?.trim()||'':'';
 const objectChanges=Object.values(step.objects).filter(o=>previous?.objects[o.id]&&changed(o,previous.objects[o.id]));
 const printed=!!previous&&step.stdout!==previous.stdout;
 let title='Ready for the next line';
 let reason='The highlighted line runs next. The values below show the program state before that line executes.';
 if(step.note==='resume'){title='Execution resumed';reason='The generator or async function continues from its saved position, keeping the same frame and local values.';}
 else if(step.event==='call'){title=`Entered ${step.frames.at(-1)?.name||'the program'}`;reason='A function call creates a stack frame. Its parameters and local variables appear in that frame.';}
 else if(step.note==='yield'){title='Generator yielded';reason=`The generator yields ${step.returnValue?display(step.returnValue):'a value'} and pauses. It can resume later with its local values preserved.`;}
 else if(step.note==='suspend'){title='Async function paused';reason='The async function pauses at a yield or await point. Its local values are preserved until execution resumes.';}
 else if(step.event==='return'){title='Function returned';reason=step.returnValue&&step.returnValue.type!=='void'?`The function returns ${display(step.returnValue)} to its caller.`:'Control returns to the caller. The remaining stack shows where execution continues.';}
 else if(step.exception){title=step.exception.type;reason=step.exception.message||'The runtime raised an exception at this point.';}
 else if(step.event==='completed'){title='Program completed';reason='All executed lines have finished. Use the arrows or timeline to replay the recorded values and output.';}
 else if(step.event==='terminated'){title='Execution stopped';reason=step.note?.replaceAll('_',' ')||'The program stopped before normal completion.';}
 else if(changes.length){title=changes.length===1?`${changes[0].name} ${!changes[0].after?'left scope':changes[0].before?'changed':'was created'}`:`${changes.length} variable values changed`;reason=previous?.location?`After line ${previous.location.line}, the recorded values changed as shown below. The highlighted line runs next.`:'These are the values available in the current scope.';}
 else if(objectChanges.length){title='Object contents changed';reason='The same object identity is preserved. Open Objects & memory to inspect the updated contents.';}
 else if(printed){title='Output written';reason=previous?.location?`Line ${previous.location.line} wrote to standard output. Output shows everything printed up to this step.`:'The program wrote to standard output.';}
 else if(previous?.location&&step.location){
  const code=lines[previous.location.line-1]?.trim()||'';
  if(/^(for|while)\b/.test(code)){title='Loop continued';reason=`The runtime moved from line ${previous.location.line} to line ${step.location.line} after evaluating the loop. The highlighted line is the next instruction.`;}
  else if(/^(if|else|switch|case)\b/.test(code)){title='Branch selected';reason=`After line ${previous.location.line}, control moved to line ${step.location.line}. This is the path chosen by the runtime.`;}
  else{title=`Reached line ${step.location.line}`;reason=`Control moved from line ${previous.location.line} to line ${step.location.line}. No displayed variable values changed between these snapshots.`;}
 }
 return {title,reason,next,changes,objectChanges};
}

