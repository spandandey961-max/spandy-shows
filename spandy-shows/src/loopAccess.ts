import {memoryTarget} from './memoryLayout.ts';
import {variableAnchor} from './memoryAccess.ts';
import type {MemoryAccess} from './memoryAccess.ts';
import type {Trace} from './types.ts';

/** Follow recorded loop header and body visits, including equal adjacent items. */
export function loopAccesses(trace: Trace | null, source: string): Map<number, MemoryAccess[]> {
 const result = new Map<number, MemoryAccess[]>();
 if (!trace || trace.language === 'c') return result;
 const python = trace.language === 'python';
 const masked = source.replace(/"""[\s\S]*?"""|'''[\s\S]*?'''|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|\/\*[\s\S]*?\*\//g, text => text.replace(/[^\n]/g, ' '));
 const lines = masked.split('\n').map(line => line.replace(python ? /#.*$/ : /\/\/.*$/, ''));
 const loops = new Map<number, {end:number; item:string; sequence:string}>();
 const indent = (text:string) => text.match(/^[ \t]*/)![0].replace(/\t/g,'        ').length;
 lines.forEach((line, index) => {
  const match = python
   ? /^\s*for\s+(\w+)\s+in\s+(\w+)\s*:\s*$/.exec(line)
   : /^\s*for\s*\(\s*(?:final\s+)?[\w.$<>, ?[\]]+\s+(\w+)\s*:\s*(\w+)\s*\)\s*(\{)?\s*$/.exec(line);
  if (!match) return;
  let end = index + 1;
  if (python) {
   while (end < lines.length && (!lines[end].trim() || indent(lines[end]) > indent(line))) end++;
  } else {
   if (!match[3]) while (end < lines.length && !lines[end].trim()) end++;
   let depth = match[3] ? 1 : 0;
   do {
    for (const brace of lines[end] || '') depth += brace === '{' ? 1 : brace === '}' ? -1 : 0;
    end++;
   } while (depth > 0 && end < lines.length);
  }
  loops.set(index+1, {end, item:match[1], sequence:match[2]});
 });
 if (!loops.size) return result;
 const ordered = (type:string) => python
  ? ['list','tuple','bytes','bytearray','array','deque'].includes(type)
  : /\[\]$|^java\.util\.(?:ArrayList|LinkedList|Vector|Stack|Arrays\$ArrayList|ImmutableCollections\$List(?:12|N))$/.test(type);
 type Pass = {index:number; ref:string; valid:boolean};
 const histories = new Map<string,{line?:number; passes:Map<number,Pass>}>();
 const framesByThread = new Map<string,Set<string>>();
 trace.steps.forEach((step, index) => {
  if (!step.location || step.location.phase !== 'before') return;
  const thread = step.thread || '';
  const key = (id:string) => JSON.stringify([thread,id]);
  const active = new Set(['$global',...step.frames.map(frame=>frame.id)].map(key));
  for (const prior of framesByThread.get(thread) || []) if (!active.has(prior)) histories.delete(prior);
  framesByThread.set(thread,active);
  if (step.event !== 'line') return;
  const frame = step.frames.at(-1);
  const id = key(frame?.id || '$global');
  if (!histories.has(id)) histories.set(id,{passes:new Map()});
  const history = histories.get(id)!;
  const line = step.location.line;
  const values = {...step.globals,...frame?.locals};
  const header = history.line;
  const loop = header === undefined ? undefined : loops.get(header);
  if (header !== undefined && loop && line > header && line <= loop.end) {
   const ref = values[loop.sequence]?.ref;
   const object = ref ? step.objects[ref] : undefined;
   const previous = history.passes.get(header);
   if (object && ordered(object.type)) {
    history.passes.set(header, {index:(previous?.index ?? -1)+1, ref:object.id,
     valid:(!previous || previous.valid && previous.ref===ref)});
   } else if (previous) previous.valid=false;
  }
  const accesses:MemoryAccess[] = [];
  for (const [start, pass] of history.passes) {
   const current = loops.get(start)!;
   if (line < start || line > current.end) {history.passes.delete(start);continue;}
   if (!pass.valid) continue;
   const value = step.objects[pass.ref]?.items[pass.index];
   const item = values[current.item];
   if (!value || !['primitive','null','reference'].includes(value.kind) || !item ||
       item.kind!==value.kind || item.ref!==value.ref || item.value!==value.value) continue;
   accesses.push({key:memoryTarget(pass.ref,[pass.index]), label:current.sequence+'['+pass.index+']',
    kind:'read',value,anchor:variableAnchor(step,current.item),assignedTo:current.item,pass:pass.index+1});
  }
  if (accesses.length) result.set(index,accesses);
  history.line=line;
 });
 return result;
}
