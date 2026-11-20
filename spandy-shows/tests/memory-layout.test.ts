import {test} from 'node:test';
import assert from 'node:assert/strict';
import {memoryLayout,referenceLabel,memoryTarget} from '../src/memoryLayout.ts';
import type {MemoryObject,Step,Value} from '../src/types';

const primitive=(value:number):Value=>({kind:'primitive',type:'int',value});
const ref=(id:string,path:(number|string)[]=[]):Value=>({kind:'reference',type:'int[]',ref:id,path});
const array=(id:string,items:Value[]):MemoryObject=>({id,type:'int[]',kind:'sequence',items,fields:{},entries:[],length:items.length,truncated:false});
const state=(objects:Record<string,MemoryObject>):Step=>({index:1,event:'line',location:null,frames:[{id:'f1',name:'main',line:3,locals:{a:ref('root')}}],globals:{},objects,stdout:'',stderr:'',exception:null,returnValue:null,note:null});

test('2D arrays keep indexed rows inline with distinct destinations',()=>{
 const objects={root:array('root',[ref('r0'),ref('r1')]),r0:array('r0',[primitive(1),primitive(2)]),r1:array('r1',[primitive(3),primitive(4)])};
 const layout=memoryLayout(state(objects));
 assert.deepEqual(layout.shape(layout.children.root[0]),[2]);
 assert.deepEqual(layout.shape(objects.root),[2,2]);
 assert.deepEqual([...layout.embedded],['r0','r1']);
 assert.equal(referenceLabel(ref('r1',[1]),layout.names),'a[1][1]');
 assert.notEqual(memoryTarget('r0',[0]),memoryTarget('root',[0]));
});
test('3D arrays render planes and rows without merging identities',()=>{
 const objects={root:array('root',[ref('p0')]),p0:array('p0',[ref('r0'),ref('r1')]),r0:array('r0',[primitive(1),primitive(2)]),r1:array('r1',[primitive(3),primitive(4)])};
 const layout=memoryLayout(state(objects));
 assert.deepEqual(layout.shape(objects.root),[1,2,2]);
 assert.equal(layout.names.r1,'a[0][1]');
 assert.deepEqual(layout.children.p0.map(row=>row.id),['r0','r1']);
});
test('aliased rows stay separate so repeated references are not mistaken for copies',()=>{
 const objects={root:array('root',[ref('row'),ref('row')]),row:array('row',[primitive(1)])};
 const layout=memoryLayout(state(objects));
 assert.equal(layout.children.root,undefined);assert.equal(layout.embedded.has('row'),false);
});
test('cyclic Python-style sequences never disappear or recurse indefinitely',()=>{
 const objects={root:array('root',[ref('other')]),other:array('other',[ref('root')])};
 const layout=memoryLayout(state(objects));
 assert.equal(layout.embedded.size,0);assert.equal(Object.keys(layout.children).length,0);
});
