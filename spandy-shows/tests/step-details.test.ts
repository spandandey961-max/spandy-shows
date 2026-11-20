import {test} from 'node:test';
import assert from 'node:assert/strict';
import {describeStep} from '../src/stepDetails.ts';
import type {Step,Value} from '../src/types.ts';
const v=(value:number):Value=>({kind:'primitive',type:'int',value});
const step=(partial:Partial<Step>):Step=>({index:0,event:'line',location:{file:'main.py',line:1,phase:'before'},frames:[],globals:{},objects:{},stdout:'',stderr:'',exception:null,returnValue:null,note:null,...partial});

test('generator and async suspension is distinguished from a completed return',()=>{
 assert.equal(describeStep(step({event:'return',note:'yield',returnValue:v(3)}),undefined,'yield 3').title,'Generator yielded');
 assert.equal(describeStep(step({event:'return',note:'suspend'}),undefined,'await work()').title,'Async function paused');
 assert.equal(describeStep(step({event:'call',note:'resume'}),undefined,'await work()').title,'Execution resumed');
});

test('explanations use recorded values and attribute them to the preceding line',()=>{
 const old=step({globals:{x:v(1)},location:{file:'main.py',line:2,phase:'before'}});
 const now=step({index:1,globals:{x:v(2)},location:{file:'main.py',line:3,phase:'before'}});
 const before=JSON.stringify([old,now]);
 const detail=describeStep(now,old,'x=1\nx=999\nprint(x)');
 assert.equal(detail.title,'x changed');assert.match(detail.reason,/After line 2/);
 assert.equal(detail.changes[0].before?.value,1);assert.equal(detail.changes[0].after?.value,2);
 assert.equal(detail.next,'print(x)');assert.equal(JSON.stringify([old,now]),before);
});
test('recursive frames and globals keep distinct change labels',()=>{
 const now=step({globals:{n:v(9)},frames:[{id:'f1',name:'recurse',line:2,locals:{n:v(2)}},{id:'f2',name:'recurse',line:2,locals:{n:v(1)}}]});
 const detail=describeStep(now,undefined,'\nrecurse(n-1)');
 assert.equal(new Set(detail.changes.map(c=>c.name)).size,3);
 assert.ok(detail.changes.some(c=>c.name==='global.n'));
});
test('leaving scope is shown as removal rather than a fabricated value',()=>{
 const old=step({frames:[{id:'f1',name:'main',line:2,locals:{i:v(2),j:v(3)}}]});
 const now=step({frames:[{id:'f1',name:'main',line:3,locals:{i:v(2)}}]});
 const detail=describeStep(now,old,'\nloop\nnext');
 assert.equal(detail.title,'j left scope');assert.equal(detail.changes[0].after,undefined);
 assert.equal(detail.changes[0].before?.value,3);
});
test('object mutation is explained even when its reference does not change',()=>{
 const object={id:'o1',type:'list',kind:'sequence',items:[v(1)],entries:[],fields:{},truncated:false};
 const old=step({globals:{values:{kind:'reference',type:'list',ref:'o1'}},objects:{o1:object}});
 const now=step({globals:old.globals,objects:{o1:{...object,items:[v(1),v(2)]}}});
 const detail=describeStep(now,old,'values.append(2)');
 assert.equal(detail.title,'Object contents changed');assert.equal(detail.changes.length,0);assert.equal(detail.objectChanges.length,1);
});
