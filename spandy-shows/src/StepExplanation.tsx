import type {Step,Trace} from './types';
import {display} from './types';
import {describeStep} from './stepDetails';

export default function StepExplanation({step,previous,source,diagnostics=[]}:{step:Step;previous?:Step;source:string;diagnostics?:Trace['diagnostics']}){
 const description=describeStep(step,previous,source);
 const failure=step.event==='terminated'?diagnostics.find(d=>d.severity==='error'):undefined;
 if(failure){description.title=['runtime_error','input_invalid','input_required'].includes(step.note||'')?'Runtime error':'Execution stopped';description.reason=failure.message.split('\n')[0];}
 return <section className="step-explanation" aria-label="Step explanation" aria-live="polite">
  <div className="explanation-heading"><h3>{description.title}</h3><span>Step {step.index+1}</span></div>
  <p>{description.reason}</p>
  {!!description.changes.length&&<ul className="value-changes">{description.changes.map(change=><li key={change.name}><code>{change.name}</code><span>{change.before?<><del>{display(change.before)}</del><span aria-label="changed to"> → </span></>:<span className="created-label">created · </span>}<strong>{change.after?display(change.after):'out of scope'}</strong></span></li>)}</ul>}
  {description.next&&<div className="next-instruction"><span>Next · line {step.location!.line}</span><code>{description.next}</code></div>}
 </section>;
}
