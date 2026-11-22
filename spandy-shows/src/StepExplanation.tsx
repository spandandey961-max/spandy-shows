import type {Step,Trace} from './types';
import {display} from './types';
import {describeStep} from './stepDetails';
import {explainMemoryAccess} from './memoryAccess';
import type {MemoryAccess} from './memoryAccess';
import {referenceLabel} from './memoryLayout';

export default function StepExplanation({step,previous,source,diagnostics=[],accesses,names,reveal}:{step:Step;previous?:Step;source:string;diagnostics?:Trace['diagnostics'];accesses:MemoryAccess[];names:Record<string,string>;reveal:(key:string)=>void}){
 const description=describeStep(step,previous,source);
 if(accesses.some(access=>access.pass)&&previous?.location&&/^\s*for\b/.test(source.split('\n')[previous.location.line-1]||'')){
  description.title='Loop advanced';
  description.reason='The highlighted line runs next.';
 }
 const failure=step.event==='terminated'?diagnostics.find(d=>d.severity==='error'):undefined;
 if(failure){description.title=['runtime_error','input_invalid','input_required'].includes(step.note||'')?'Runtime error':'Execution stopped';description.reason=failure.message.split('\n')[0];}
 const valueText=(value?:Parameters<typeof display>[0])=>value?.kind==='reference'?`↗ ${referenceLabel(value,names)}`:display(value);
 const detail=(access:MemoryAccess)=><li key={access.kind+access.key+access.anchor}><button type="button" className="memory-jump" onClick={()=>reveal(access.key)} aria-label={`Show ${access.label} in memory`}>{access.label}</button><span>{explainMemoryAccess(access)}</span></li>;
 return <section className="step-explanation" aria-label="Step explanation" aria-live="polite">
  <div className="explanation-heading"><h3>{description.title}</h3><span>{step.thread&&step.thread!=='Main thread'?`${step.thread} · `:''}Step {step.index+1}</span></div>
  {step.note?.startsWith('Dynamic code ·')&&<p className="step-context">{step.note}</p>}
  <p>{description.reason}</p>
  {!!accesses.length&&<ul className="memory-accesses">{accesses.slice(0,3).map(detail)}</ul>}
  {accesses.length>3&&<details className="memory-more"><summary>{accesses.length-3} more memory changes</summary><ul className="memory-accesses">{accesses.slice(3).map(detail)}</ul></details>}
  {!!description.changes.length&&<ul className="value-changes">{description.changes.map(change=><li key={change.name}><code>{change.name}</code><span>{change.before?<><del>{valueText(change.before)}</del><span aria-label="changed to"> → </span></>:<span className="created-label">created · </span>}<strong>{change.after?valueText(change.after):'out of scope'}</strong></span></li>)}</ul>}
  {description.next&&<div className="next-instruction"><span>Next · line {step.location!.line}</span><code>{description.next}</code></div>}
 </section>;
}
