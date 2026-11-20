import {test} from 'node:test';
import assert from 'node:assert/strict';
import {netlifyRoutes} from '../scripts/prepare-netlify.mjs';

test('Netlify preserves API paths and puts the proxy before the app fallback',()=>{
 assert.equal(netlifyRoutes('https://execution.example.com/'),'/api/* https://execution.example.com/api/:splat 200!\n/* /index.html 200\n');
});
test('deployment requires a public HTTPS origin instead of a disconnected compiler',()=>{
 for(const value of [undefined,'invalid','http://execution.example.com','https://localhost','https://127.0.0.1','https://[::1]','https://execution.example.com/api','https://user:secret@execution.example.com','https://execution.example.com?token=secret'])
  assert.throws(()=>netlifyRoutes(value));
});
