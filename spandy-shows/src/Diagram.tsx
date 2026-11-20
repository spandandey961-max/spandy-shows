import { useLayoutEffect,useMemo,useRef,useState } from 'react';
import { ArrowUpRight, Braces, ChevronRight, Layers3 } from 'lucide-react';
import type {Value, Step, MemoryObject} from './types';
import {display,changed} from './types';
import {memoryLayout,memoryTarget,referenceLabel} from './memoryLayout';
import type {MemoryLayout} from './memoryLayout';

function ValueView({value,names}:{value:Value;names:Record<string,string>}){
 if(value.kind==='reference'){
  const key=memoryTarget(value.ref||'',value.path),label=referenceLabel(value,names);
  return <button type="button" className="reference-value" data-ref={value.ref} data-target={key} title={value.note||`Reference to ${label}`} aria-label={`Follow reference to ${label}`} onClick={event=>{
   const diagram=event.currentTarget.closest('.diagram');
   const target=diagram?.querySelector<HTMLElement>(`[data-memory-target="${CSS.escape(key)}"]`)||diagram?.querySelector<HTMLElement>(`[data-object="${CSS.escape(value.ref||'')}"]`);
   target?.scrollIntoView({block:'nearest',inline:'nearest'});target?.focus({preventScroll:true});
  }}><span>{label}</span><ArrowUpRight size={13}/><i/></button>;
 }
 return <span className={`primitive-value kind-${value.kind}`} title={value.note||value.type}>{display(value)}{value.truncated&&<small>truncated</small>}</span>;
}
function Variables({variables,previous,names,owner}:{variables:Record<string,Value>;previous?:Record<string,Value>;names:Record<string,string>;owner?:string}){
 return <div className="variables">{Object.entries(variables).length?Object.entries(variables).map(([name,value])=>{
  const updated=!!previous&&changed(value,previous[name]);
  return <div className={`variable-row ${updated?'updated':''}`} key={name} data-memory-target={owner?memoryTarget(owner,[name]):undefined} tabIndex={owner?-1:undefined}><div className="var-label"><code>{name}</code><small>{value.type}</small></div><div className="var-value"><ValueView value={value} names={names}/>{updated&&<span className="change-mark" title="Changed since the previous snapshot" aria-label="Changed">↗</span>}</div></div>;
 }):<p className="empty-variables">No variables here yet.</p>}</div>;
}
function ArrayCells({object,previous,layout,label}:{object:MemoryObject;previous?:MemoryObject;layout:MemoryLayout;label:string}){
 return <div className="array-cells" role="group" aria-label={`${label} indexed values`}>{object.items.map((value,index)=><div role="group" key={index} tabIndex={-1} className={previous&&changed(value,previous.items[index])?'changed-cell':''} data-memory-target={memoryTarget(object.id,[index])} aria-label={`${label}[${index}]: ${value.kind==='reference'?referenceLabel(value,layout.names):display(value)}`}><small aria-hidden="true">{index}</small><ValueView value={value} names={layout.names}/></div>)}</div>;
}
function ArrayContents({object,previous,layout,label}:{object:MemoryObject;previous?:Step;layout:MemoryLayout;label:string}){
 const rows=layout.children[object.id];
 if(!rows)return <ArrayCells object={object} previous={previous?.objects[object.id]} layout={layout} label={label}/>;
 const matrix=rows.every(row=>!layout.children[row.id]);
 return <div className={matrix?'array-matrix':'array-slices'} role="group" aria-label={`${label} ${matrix?'rows':'slices'}`}>{rows.map((row,index)=><div className={matrix?'array-matrix-row':'array-slice'} key={row.id} data-object={row.id} data-memory-target={memoryTarget(row.id)} tabIndex={-1}>
  <div className="array-row-label"><code>{matrix?`[${index}]`:`${label}[${index}]`}</code>{!matrix&&<small>{layout.shape(row).join(' × ')}</small>}</div>
  <ArrayContents object={row} previous={previous} layout={layout} label={`${label}[${index}]`}/>
  {row.truncated&&<div className="array-truncated">Showing {row.items.length} of {row.length??row.items.length} items</div>}
 </div>)}</div>;
}
function ObjectCard({object,previous,layout}:{object:MemoryObject;previous?:Step;layout:MemoryLayout}){
 const prior=previous?.objects[object.id],name=layout.names[object.id]||object.id;
 const subtreeChanged=(value:MemoryObject):boolean=>!!previous&&(changed(value,previous.objects[value.id])||(layout.children[value.id]||[]).some(subtreeChanged));
 const updated=!!prior&&subtreeChanged(object),shape=object.kind==='sequence'?layout.shape(object):[];
 return <article className={`object-card ${updated?'updated-object':''}`} data-object={object.id} data-memory-target={memoryTarget(object.id)} tabIndex={-1}>
 <header><div><span className="object-type">{name}</span><code>{object.type}</code></div><span>{shape.length>1?shape.join(' × '):object.length!=null?`${object.length} item${object.length===1?'':'s'}`:object.allocation||'object'}{updated&&<b className="updated-label">updated</b>}</span></header>
 {object.items.length>0?<div className="array-scroll"><ArrayContents object={object} previous={previous} layout={layout} label={name}/></div>:object.kind==='sequence'||object.kind==='set'?<div className="empty-object">empty {object.type}</div>:null}
 {object.entries.map(([k,v],i)=><div className="mapping-row" key={i}><ValueView value={k} names={layout.names}/><ChevronRight size={12}/><ValueView value={v} names={layout.names}/></div>)}
 {Object.keys(object.fields).length>0&&<Variables variables={object.fields} previous={prior?.fields} names={layout.names} owner={object.id}/>}
 {object.truncated&&<div className="array-truncated">View limited · showing {object.items.length||Object.keys(object.fields).length}{object.length!=null?` of ${object.length}`:''} items</div>}
 {object.address&&<div className="object-note">{object.address} · {object.allocation||'allocation unknown'}</div>}
 {object.note&&<details className="object-details"><summary>Observation details</summary><p>{object.note}</p></details>}
 </article>;
}
export default function Diagram({step,previous,objectOrder,showObjects=false}:{step?:Step;previous?:Step;objectOrder:string[];showObjects?:boolean}){
 const hasGlobals=Object.keys(step?.globals||{}).length>0;
 const objectsVisible=showObjects&&Object.keys(step?.objects||{}).length>0;
 const hasVariables=hasGlobals||!!step?.frames.length;
 const layout=useMemo(()=>memoryLayout(step),[step]);
 const canvas=useRef<HTMLDivElement>(null),[paths,setPaths]=useState<{d:string,id:string}[]>([]),[size,setSize]=useState({w:1,h:1});
 useLayoutEffect(()=>{
  const el=canvas.current;if(!el)return;
  let raf=0;
  const measure=()=>{cancelAnimationFrame(raf);raf=requestAnimationFrame(()=>{
   const bounds=el.getBoundingClientRect();const measured={w:Math.ceil(bounds.width),h:Math.ceil(bounds.height)};
   setSize(old=>old.w===measured.w&&old.h===measured.h?old:measured);
   const next:{d:string,id:string}[]=[];
   el.querySelectorAll<HTMLElement>('[data-ref]').forEach((anchor,i)=>{
    const target=el.querySelector<HTMLElement>(`[data-memory-target="${CSS.escape(anchor.dataset.target||'')}"]`)||el.querySelector<HTMLElement>(`[data-object="${CSS.escape(anchor.dataset.ref||'')}"]`);if(!target)return;
    const a=anchor.getBoundingClientRect(),b=target.getBoundingClientRect();
    const x1=a.right-bounds.left+el.scrollLeft,y1=a.top+a.height/2-bounds.top+el.scrollTop,x2=b.left-bounds.left+el.scrollLeft,y2=b.top+(target.matches('.object-card,.array-slice')?Math.min(23,b.height/2):b.height/2)-bounds.top+el.scrollTop;
    const self=anchor.closest('[data-object]')===target;
    const bend=self?70:Math.max(24,Math.abs(x2-x1)/2);
    next.push({id:`${anchor.dataset.ref}-${i}`,d:self?`M${x1},${y1} C${x1+bend},${y1} ${x1+bend},${y2-45} ${x2+12},${y2-45} S${x2-20},${y2} ${x2},${y2}`:`M${x1},${y1} C${x1+bend},${y1} ${x2-bend},${y2} ${x2-3},${y2}`});
   });setPaths(old=>JSON.stringify(old)===JSON.stringify(next)?old:next);
  });};
  measure();const observer=new ResizeObserver(measure);observer.observe(el);el.querySelectorAll('.frame-card,.object-card').forEach(x=>observer.observe(x));el.addEventListener('scroll',measure,true);
  return ()=>{cancelAnimationFrame(raf);observer.disconnect();el.removeEventListener('scroll',measure,true);};
 },[step,objectOrder,objectsVisible]);
 if(!hasVariables&&!objectsVisible)return null;
 return <div className="diagram-scroll" id="program-inspector"><div className={`diagram ${objectsVisible?(hasVariables?'with-objects':'objects-only'):'variables-only'}`} ref={canvas}>
 {objectsVisible&&<svg className="reference-arrows" width={size.w} height={size.h} aria-label="Arrows connect references to their observed objects or array elements" role="img"><defs><marker id="arrowhead" markerWidth="7" markerHeight="7" refX="5" refY="3.5" orient="auto"><path d="M0 0 L6 3.5 L0 7" fill="none" stroke="currentColor" strokeWidth="1.5"/></marker></defs>{paths.map(p=><path key={p.id} d={p.d} fill="none" stroke="currentColor" strokeWidth="1.5" markerEnd="url(#arrowhead)"/>)}</svg>}
 {hasVariables&&<section className="stack-column" aria-label="Variables and stack frames"><div className="column-label"><Layers3 size={14}/> Variables <span>{step?.frames.length||0}</span></div>
 {hasGlobals&&<article className="frame-card global-frame"><header><span>Global</span><span className="scope-tag">global</span></header><Variables variables={step?.globals||{}} previous={previous?.globals} names={layout.names}/></article>}
 {(step?.frames||[]).map((f,i)=><article key={f.id} className={`frame-card ${i===step!.frames.length-1?'active-frame':''}`}><header><div><span>{f.name}<span className="paren">()</span></span><small>{f.id}</small></div><span className="scope-tag">{i===step!.frames.length-1?'active':'waiting'}</span></header><Variables variables={f.locals} previous={previous?.frames.find(x=>x.id===f.id)?.locals} names={layout.names}/></article>)}
 </section>}
 {objectsVisible&&<section className="objects-column" aria-label="Objects and memory"><div className="column-label"><Braces size={14}/> Objects & memory <span>{objectOrder.filter(id=>step?.objects[id]&&!layout.embedded.has(id)).length}</span></div>
 {step&&objectOrder.filter(id=>step.objects[id]&&!layout.embedded.has(id)).map(id=><ObjectCard key={id} object={step.objects[id]} previous={previous} layout={layout}/>)}
 </section>}
 </div></div>;
}
