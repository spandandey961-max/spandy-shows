import {useLayoutEffect,useRef,useState} from 'react';

export interface InputEcho {id:number;offset:number;text:string;stepIndex:number}
export default function Output({text,inputs=[]}:{text:string;inputs?:InputEcho[]}){
 const visible=inputs.filter(input=>input.offset<=text.length);
 const parts:(string|{id:number;text:string})[]=[];
 let cursor=0;
 for(const input of visible){parts.push(text.slice(cursor,input.offset),{id:input.id,text:input.text+'\n'});cursor=input.offset;}
 parts.push(text.slice(cursor));
 const displayed=parts.map(part=>typeof part==='string'?part:part.text).join('');
 const host=useRef<HTMLDivElement>(null),[fontSize,setFontSize]=useState(14);
 useLayoutEffect(()=>{
  const element=host.current;if(!element)return;
  const measure=()=>{
   // Preserve spaces and ASCII artwork, fit ordinary banners to the panel.
   // Exceptionally long lines can scroll horizontally; output never clips rows.
   const columns=Math.max(1,...displayed.split('\n').map(line=>Array.from(line.replace(/\t/g,'    ')).length));
   const width=Math.max(1,element.clientWidth-40);
   setFontSize(Math.max(8,Math.min(14,width/(columns*.62))));
  };
  measure();const observer=new ResizeObserver(measure);observer.observe(element);
  return()=>observer.disconnect();
 },[displayed]);
 return <section className="output-panel" aria-label="Program output"><header className="output-header"><h3>Output</h3></header><div ref={host} className="console" role="log" aria-label="Standard output" aria-live="polite"><pre style={{fontSize}}>{parts.map((part,i)=>typeof part==='string'?part:<span className="input-echo" title="Your submitted input" key={`${part.id}-${i}`}>{part.text}</span>)}</pre></div></section>;
}
