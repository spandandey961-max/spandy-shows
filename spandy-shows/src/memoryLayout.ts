import type {MemoryObject,Step,Value} from './types';

export const memoryTarget=(id:string,path:(string|number)[]=[])=>JSON.stringify([id,...path]);
export const referenceLabel=(value:Value,names:Record<string,string>)=>(names[value.ref||'']||value.ref||'?')+(value.path||[]).map(part=>typeof part==='number'?`[${part}]`:`.${part}`).join('');

/** Inline distinct array rows; shared rows and cycles keep their visible identity. */
export function memoryLayout(step?:Step){
 const objects=step?.objects||{},names:Record<string,string>={},parents:Record<string,number>={};
 const sequences=(object:MemoryObject):MemoryObject[]|null=>{
  if(object.kind!=='sequence'||!object.items.length)return null;
  const children=object.items.map(value=>value.kind==='reference'&&!value.path?.length?objects[value.ref||'']:undefined);
  return children.every(child=>child?.kind==='sequence')?children as MemoryObject[]:null;
 };
 for(const object of Object.values(objects))for(const child of sequences(object)||[])parents[child.id]=(parents[child.id]||0)+1;
 const cycle=(object:MemoryObject,ancestors:Set<string>,depth=0):boolean=>{
  if(ancestors.has(object.id))return true;
  if(depth>=6)return false;
  return (sequences(object)||[]).some(child=>cycle(child,new Set([...ancestors,object.id]),depth+1));
 };
 const children:Record<string,MemoryObject[]>={},embedded=new Set<string>();
 for(const object of Object.values(objects)){
  const rows=sequences(object);
  if(rows&&rows.every(row=>parents[row.id]===1&&!cycle(row,new Set([object.id])))){
   children[object.id]=rows;for(const row of rows)embedded.add(row.id);
  }
 }
 const roots=[...Object.entries(step?.globals||{}),...(step?.frames||[]).flatMap(frame=>Object.entries(frame.locals))];
 for(const [name,value] of roots)if(value.kind==='reference'&&value.ref&&!value.path?.length&&!value.type.includes('*'))names[value.ref]??=name;
 for(const [name,value] of roots)if(value.kind==='reference'&&value.ref&&objects[value.ref]?.allocation==='allocated'&&(!value.path?.length||value.path[0]===0||value.path[0]==='value'))names[value.ref]??=name;
 const nameChildren=(id:string,seen:Set<string>)=>{
  if(seen.has(id))return;seen.add(id);
  const object=objects[id];if(!object)return;
  object.items.forEach((value,index)=>{if(value.kind==='reference'&&value.ref&&!value.path?.length){names[value.ref]??=`${names[id]||id}[${index}]`;nameChildren(value.ref,seen);}});
  for(const [field,value] of Object.entries(object.fields))if(value.kind==='reference'&&value.ref&&!value.path?.length){names[value.ref]??=`${names[id]||id}.${field}`;nameChildren(value.ref,seen);}
 };
 for(const id of Object.keys(names))nameChildren(id,new Set());
 const shape=(object:MemoryObject,seen=new Set<string>()):number[]=>{
  const size=object.length??object.items.length;
  if(seen.has(object.id))return [size];
  const rows=children[object.id];if(!rows?.length)return [size];
  const next=new Set([...seen,object.id]),tail=shape(rows[0],next);
  return rows.every(row=>JSON.stringify(shape(row,next))===JSON.stringify(tail))?[size,...tail]:[size];
 };
 return {names,children,embedded,shape};
}

export type MemoryLayout=ReturnType<typeof memoryLayout>;
