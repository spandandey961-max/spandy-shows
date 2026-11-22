import {memoryLayout, memoryTarget, referenceLabel} from './memoryLayout.ts';
import {changed, display} from './types.ts';
import type {Step, Value} from './types.ts';

export interface MemoryAccess {
 key: string;
 label: string;
 kind: 'read' | 'written';
 value: Value;
 before?: Value;
 anchor?: string;
 assignedTo?: string;
 pass?: number;
}

const observed = (value?: Value): value is Value =>
 !!value && !['unavailable','uninitialized','optimized-out'].includes(value.kind);

export function variableAnchor(step:Step,name:string){
 const frame=step.frames.at(-1);
 return memoryTarget(frame&&Object.hasOwn(frame.locals,name)?frame.id:'$global',[name]);
}

/** Describes captured changes and resolves simple operands from the pre-line snapshot. */
export function memoryAccesses(step: Step, previous: Step | undefined, source: string): MemoryAccess[] {
 if (!previous) return [];
 const layout = memoryLayout(step);
 const accesses = new Map<string, MemoryAccess>();
 for (const object of Object.values(step.objects)) {
  const prior = previous.objects[object.id];
  if (!prior) continue;
  const addChange = (path: string | number, value: Value, before?: Value) => {
   if (!observed(value) || !before || !changed(value, before)) return;
   const key = memoryTarget(object.id, [path]);
   const label = referenceLabel({kind:'reference',type:object.type,ref:object.id,path:[path]}, layout.names);
   accesses.set('written'+key, {key, label, kind:'written', value, before});
  };
  object.items.forEach((value, index) => addChange(index, value, prior.items[index]));
  Object.entries(object.fields).forEach(([name, value]) => addChange(name, value, prior.fields[name]));
 }
 if (previous.location?.phase !== 'before' || !['line','return','completed'].includes(step.event)) return [...accesses.values()];
 if (step.location?.phase==='before' && step.location.line===previous.location.line &&
     step.location.file===previous.location.file && step.stdout===previous.stdout) return [...accesses.values()];
 const frame = previous.frames.at(-1);
 if (step.event === 'line' && frame?.id !== step.frames.at(-1)?.id) return [...accesses.values()];
 const line = source.split('\n')[previous.location.line - 1] || '';
 if (line.length>2048) return [...accesses.values()];
 const python=previous.location.file==='main.py';
 const code = line.replace(/("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')|\/\/.*$|#.*$/g,
  (text,literal) => literal || (text.startsWith('#')!==python ? text : '')
 ).trim().replace(/;$/,'');
 const assignment = /^(?:(?:[A-Za-z_]\w*\s+)+\*?\s*)?([\w*][^=]*?)\s*([+\-*/%]?=)(?!=)\s*(.+)$/.exec(code);
 const output = /^(?:print|printf|System\.out\.print(?:ln|f)?)\s*\((.*)\)$/.exec(code);
 const condition = /^(?:if|while)\s*\(?(.+?)\)?\s*[:{]\s*$/.exec(code);
 const update = /^(?:\+\+|--)(\w+\s*\[.+\])$|^(\w+\s*\[.+\])(?:\+\+|--)$/.exec(code);
 const expression = assignment?.[3] || output?.[1] || condition?.[1] || update?.[1] || update?.[2];
 if (!expression) return [...accesses.values()];
 const operands = /(?:\b\w+(?:\s*\[[^()[\];]+\])+|\*\s*(?:\(\s*\w+\s*[+-]\s*\w+\s*\)|\w+)|\b\w+(?:(?:->|\.)\s*\w+)+)/g;
 const expressionCode=expression.replace(/"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'/g,'0');
 // Resolve only simple operands that are evaluated without short-circuiting,
 // additional calls, or changes to an index during the same expression.
 if (/\+\+|--|\b(?:and|or|if|else|for|in)\b/.test(expressionCode) ||
     !/^[\s\w,.+\-*/%<>=!]*$/.test(expressionCode.replace(operands,'0'))) return [...accesses.values()];
 const values = {...previous.globals, ...frame?.locals};
 const integer = (part: string) => {
  const value = /^-?\d+$/.test(part) ? Number(part) : values[part]?.value;
  return typeof value === 'number' && Number.isSafeInteger(value) ? value : undefined;
 };
 const names = {...memoryLayout(previous).names, ...layout.names};
 const resolve = (operand:string, kind:MemoryAccess['kind'], assignedTo?:string) => {
  const indexed = /^(\w+)((?:\s*\[[^\]]+\])+)$/.exec(operand);
  const pointer = /^\*\s*(?:(\w+)|\(\s*(\w+)\s*([+-])\s*(\w+)\s*\))$/.exec(operand);
  const member = /^(\w+)((?:\s*(?:->|\.)\s*\w+)+)$/.exec(operand);
  let id: string | null | undefined, path: (string | number)[] = [];
  let anchor:string|undefined;
  if (indexed) {
   let value = values[indexed[1]];
   if (value?.kind !== 'reference') return;
   for (const [,subscript] of indexed[2].matchAll(/\[([^\]]+)\]/g)) {
    const calculation = /^\s*(-?\w+)(?:\s*([+-])\s*(\w+))?\s*$/.exec(subscript);
    if (!calculation || !value?.ref) return;
    const left=integer(calculation[1]), right=calculation[3]?integer(calculation[3]):0;
    if(left===undefined||right===undefined)return;
    const index=left+(calculation[2]==='-'?-right:right);
    const name=[calculation[1],calculation[3],indexed[1]].find(name=>name && Object.hasOwn(values,name))!;
    anchor=value.type.includes('*')&&name===indexed[1]?undefined:variableAnchor(previous,name);
    const offset=value.path?.[0];
    if(value.path?.length&&(value.path.length!==1||typeof offset!=='number'))return;
    const sequence=previous.objects[value.ref];
    const targetIndex=index+(typeof offset==='number'?offset:index<0&&previous.location?.file==='main.py'?sequence?.length||0:0);
    if(targetIndex<0)return;
    id = value.ref;
    path = [targetIndex];
    value = sequence?.items[targetIndex];
   }
  } else if (member) {
   let value=values[member[1]];
   for(const [,name] of member[2].matchAll(/(?:->|\.)\s*(\w+)/g)){
    if(value?.kind!=='reference'||!value.ref)return;
    if(value.path?.length===1&&typeof value.path[0]==='number'){
     value=previous.objects[value.ref]?.items[value.path[0]];
    }
    if(value?.kind!=='reference'||!value.ref||value.path?.length)return;
    id=value.ref;
    path=[name];
    value=previous.objects[id]?.fields[name];
   }
  } else if (pointer) {
   const value = values[pointer[1] || pointer[2]];
   if (value?.kind !== 'reference' || !value.type.includes('*')) return;
   id = value.ref;
   path = [...(value.path || [])];
   if (pointer[2]) {
    const offset = integer(pointer[4]);
    const index = path.at(-1);
    if (offset === undefined || typeof index !== 'number') return;
    path[path.length - 1] = index + (pointer[3] === '-' ? -offset : offset);
   }
  }
  if (!id || path.length !== 1) return;
  const key = memoryTarget(id, path);
  const object = (kind==='read'?previous:step).objects[id];
  const part = path[0];
  const value = typeof part === 'number' ? object?.items[part] : object?.fields[part];
  if (observed(value) && step.objects[id]) {
   const label = referenceLabel({kind:'reference',type:'',ref:id,path}, names);
   const before = typeof part==='number'?previous.objects[id]?.items[part]:previous.objects[id]?.fields[part];
   accesses.set(kind+key, {key,label,kind,value,anchor,assignedTo,before});
  }
 };
 const reads=[...expressionCode.matchAll(operands)];
 const assignedTo=reads.length===1&&expressionCode.trim()===reads[0][0]&&assignment?.[2]==='='&&/^\w+$/.test(assignment[1])
  ?assignment[1]:undefined;
 for(const [read] of reads)resolve(read,'read',assignedTo);
 const target=assignment?.[1] || update?.[1] || update?.[2];
 if (target && [...target.matchAll(operands)].some(match=>match[0]===target)) {
  if (assignment && assignment[2]!=='=') resolve(target,'read');
  resolve(target,'written');
 }
 return [...accesses.values()];
}

export function explainMemoryAccess(access: MemoryAccess) {
 const value = display(access.value);
 if (access.pass) return `Pass ${access.pass}. The loop read ${value} from ${access.label} and assigned it to ${access.assignedTo}.`;
 if (access.kind === 'read') return `Read ${value} from ${access.label}${access.assignedTo?' and assigned it to '+access.assignedTo:''}.`;
 if (observed(access.before)&&changed(access.value,access.before)) return `${access.label} changed from ${display(access.before)} to ${value}.`;
 return `${access.label} now holds ${value}.`;
}
