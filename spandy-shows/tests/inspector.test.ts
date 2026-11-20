import {test} from 'node:test';
import assert from 'node:assert/strict';
import {inspectorTrace} from '../src/inspector.ts';
import type {Trace} from '../src/types.ts';

const trace:Trace={schemaVersion:1,language:'java',runtimeVersion:'21',sourceFile:'Main.java',sourceHash:'a'.repeat(64),status:'completed',terminationReason:'completed',diagnostics:[],limitations:[],steps:[{
 index:0,event:'line',location:{file:'Main.java',line:3,phase:'before'},frames:[{id:'f1',name:'main',line:3,locals:{args:{kind:'reference',type:'java.lang.String[]',ref:'j1'},values:{kind:'reference',type:'int[]',ref:'j2'}}}],globals:{},objects:{
  j1:{id:'j1',type:'java.lang.String[]',kind:'sequence',length:0,items:[],fields:{},entries:[],truncated:false},
  j2:{id:'j2',type:'int[]',kind:'sequence',length:1,items:[{kind:'primitive',type:'int',value:7}],fields:{},entries:[],truncated:false}
 },stdout:'7',stderr:'',exception:null,returnValue:null,note:null
}]};

test('unused Java startup arguments do not trigger memory; user arrays remain',()=>{
 const original=JSON.stringify(trace);
 const displayed=inspectorTrace(trace,'public class Main { public static void main(String[] args) { int[] values={7}; System.out.println(values[0]); } }')!;
 assert.deepEqual(Object.keys(displayed.steps[0].objects),['j2']);
 assert.equal(displayed.steps[0].frames[0].locals.args,undefined);
 assert.equal(displayed.steps[0].frames[0].locals.values.ref,'j2');
 assert.equal(JSON.stringify(trace),original);
});
test('explicitly used Java arguments keep their actual object and reference',()=>{
 assert.equal(inspectorTrace(trace,'public class Main { public static void main(String[] args) { System.out.println(args.length); } }'),trace);
});
test('comments and printed argument names do not make startup data relevant',()=>{
 const displayed=inspectorTrace(trace,'public class Main { public static void main(String[] args) { /* args */ System.out.println("args"); } }')!;
 assert.equal(displayed.steps[0].objects.j1,undefined);
});
