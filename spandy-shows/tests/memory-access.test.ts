import assert from 'node:assert/strict';
import {test} from 'node:test';
import {loopAccesses} from '../src/loopAccess.ts';
import {memoryAccesses} from '../src/memoryAccess.ts';
import {memoryTarget} from '../src/memoryLayout.ts';
import type {MemoryObject, Step, Trace, Value} from '../src/types.ts';

const number=(value:number):Value=>({kind:'primitive',type:'int',value});
const ref=(id:string,type='list',path?:number[]):Value=>({kind:'reference',type,ref:id,path});
const array=(id:string,items:Value[],type='list'):MemoryObject=>
 ({id,kind:'sequence',type,items,length:items.length,entries:[],fields:{},truncated:false});
const step=(index:number,line:number,globals:Step['globals'],objects:Step['objects'],file='main.py'):Step=>
 ({index,event:'line',location:{file,line,phase:'before'},frames:[],globals,objects,stdout:'',stderr:'',exception:null,returnValue:null,note:null});

test('duplicate loop values land on separate cells and clear when the loop exits',()=>{
 for(const language of ['python','java'] as const){
  const type=language==='python'?'list':'int[]';
  const source=language==='python'?'for item in A:\n    print(item)\nprint("done")':
   'for (int item : A) {\n    System.out.println(item);\n}\nSystem.out.println("done");';
  const A=ref('a',type),objects={a:array('a',[number(7),number(7)],type)};
  const steps=[
   step(0,1,{A},objects),step(1,2,{A,item:number(7)},objects),
   step(2,1,{A},objects),step(3,2,{A,item:number(7)},objects),
   step(4,1,{A},objects),step(5,language==='python'?3:4,{A},objects)
  ];
  const passes=loopAccesses({language,steps} as Trace,source);
  assert.deepEqual([...passes].map(([index,[access]])=>[index,access.label,access.pass]),
   [[1,'A[0]',1],[3,'A[1]',2]]);
  assert.equal(passes.get(1)?.[0].anchor,memoryTarget('$global',['item']));
 }
});

test('indexed and pointer reads identify the exact nested or offset cell',()=>{
 const globals={grid:ref('g'),i:number(1),p:ref('a','int *',[1])};
 const objects={
  g:array('g',[ref('a'),ref('b')]),a:array('a',[number(5),number(6),number(7)]),
  b:array('b',[number(8),number(9),number(10)])
 };
 const before=step(0,1,globals,objects,'main.c'),after=step(1,2,globals,objects,'main.c');
 const [cell]=memoryAccesses(after,before,'int x = grid[i][i+1];');
 assert.equal(cell.label,'grid[1][2]');
 assert.equal(cell.anchor,memoryTarget('$global',['i']));
 assert.equal(cell.assignedTo,'x');
 const [read]=memoryAccesses(after,before,'printf("%d", *(p + 1));');
 assert.equal(read.key,memoryTarget('a',[2]));
 assert.equal(read.anchor,undefined);
 assert.deepEqual(globals.p.path,[1]);
 assert.equal(memoryAccesses(after,before,'if (flag && grid[i][0]) {').length,0);
});
