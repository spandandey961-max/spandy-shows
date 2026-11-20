import {test} from 'node:test';
import assert from 'node:assert/strict';
import {retainedStep,playbackOutput} from '../src/playback.ts';

test('background recording and completion preserve the manually selected step',()=>{
 assert.equal(retainedStep(0,205),0);
 assert.equal(retainedStep(12,205),12);
 assert.equal(retainedStep(12,13),12);
 assert.equal(retainedStep(12,205,40),40);
 assert.equal(retainedStep(12,5),4);
});
test('visual replay never exposes future output during preparation',()=>{
 assert.equal(playbackOutput('visualize',true,false,'first\n','first\nsecond\n'),'first\n');
 assert.equal(playbackOutput('visualize',false,false,'','complete\n'),'');
 assert.equal(playbackOutput('visualize',true,true,'','Name: '),'Name: ');
 assert.equal(playbackOutput('run',true,false,'','actual output\n'),'actual output\n');
 assert.equal(playbackOutput('run',false,false,'complete\n','old\n'),'complete\n');
});
