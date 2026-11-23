import {createRequire} from 'node:module';
import path from 'node:path';
import fs from 'node:fs';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url);
const {_electron}=require(process.env.SPANDY_PLAYWRIGHT_MODULE || 'playwright');
if(!process.argv[2])throw new Error('Pass the built desktop EXE path as the first argument.');
const output=path.resolve(process.argv[3] || 'test-results/editor');fs.mkdirSync(output,{recursive:true});
const report={version:'1.3.0-preview.6',checks:[],typing:[]};
const app=await _electron.launch({executablePath:path.resolve(process.argv[2]),args:['--data-dir='+path.join(output,'profile-'+process.pid),'--no-integration'],timeout:60000});
try {
 const page=await app.firstWindow();const errors=[];page.on('pageerror',error=>errors.push(error.message));
 await page.waitForURL('spandy://app/**');await page.locator('.monaco-editor .view-lines').waitFor();
 const editor=page.locator('.monaco-editor .view-lines');
 async function paste(text){await editor.click();await page.keyboard.press('Control+A');await app.evaluate(({clipboard},value)=>clipboard.writeText(value),text);await page.keyboard.press('Control+V');}
 async function value(){await page.keyboard.press('Control+A');await page.keyboard.press('Control+C');const text=(await app.evaluate(({clipboard})=>clipboard.readText())).replaceAll('\r\n','\n');return text==='\n'&&await editor.locator('.view-line').count()===1?'':text;}
 async function clear(){await editor.click();await page.keyboard.press('Control+A');await page.keyboard.press('Backspace');}
 const colors={dark:{keyword:'rgb(230, 163, 129)',string:'rgb(172, 204, 173)',number:'rgb(217, 186, 126)',comment:'rgb(136, 149, 141)'},light:{keyword:'rgb(164, 60, 40)',string:'rgb(68, 112, 74)',number:'rgb(152, 98, 37)',comment:'rgb(112, 121, 109)'}};
 const snippets={Python:'def hello():\n    # comment\n    name = "Hello"\n    return 42\n',Java:'class Main {\n    // comment\n    String name = "Hello";\n    int value = 42;\n}\n',C:'#include <stdio.h>\nint main(void) {\n    // comment\n    printf("Hello %d", 42);\n    return 0;\n}\n'};
 // The initially selected language must already have syntax colors.
 await page.waitForFunction(()=>new Set(Array.from(document.querySelectorAll('.view-lines span[class*=mtk]'),e=>getComputedStyle(e).color)).size>=3);
 report.checks.push('Startup syntax highlighting');
 console.log('Startup colors passed');
 for(const theme of ['dark','light']) {
  const current=await page.locator('html').getAttribute('data-theme');
  if(current!==theme)await page.getByRole('button',{name:`Switch to ${theme} theme`,exact:true}).click();
  for(const [language,source] of Object.entries(snippets)) {
   await page.getByRole('tab',{name:language,exact:true}).click();await paste(source);
   await page.waitForFunction(expected=>{
    const found=Array.from(document.querySelectorAll('.view-lines span[class*=mtk]'),e=>getComputedStyle(e).color);
    return Object.values(expected).every(color=>found.includes(color));
   },colors[theme]);
   report.checks.push(`${language} ${theme} keyword/string/comment/number colors`);
   console.log(language,theme,'colors passed');
  }
 }
 for(const language of ['C','Java','Python']) {
  await page.getByRole('tab',{name:language,exact:true}).click();
  for(const [open,close] of [['{','}'],['(',')'],['[',']'],['"','"']]) {
   await clear();await page.keyboard.type(open);assert.equal(await value(),open+close);
   await clear();await page.keyboard.type(open);await page.keyboard.type(close);assert.equal(await value(),open+close);
   await clear();await page.keyboard.type(open);await page.keyboard.press('Backspace');assert.equal(await value(),'');
   report.checks.push(`${language} auto-pair and overtype ${open}${close}`);
  }
  await clear();await page.keyboard.press('Tab');assert.equal(await value(),'    ');
  await page.keyboard.press('Control+End');await page.keyboard.press('Shift+Tab');assert.equal(await value(),'');
  if(language==='Python') {
   await page.keyboard.type('if True:');await page.keyboard.press('Enter');assert.equal(await value(),'if True:\n    ');
  } else {
   const prefix=language==='C'?'int main(void) ':'class Main ';
   await page.keyboard.type(prefix+'{');await page.keyboard.press('Enter');assert.equal(await value(),prefix+'{\n    \n}');
  }
  report.checks.push(`${language} indent/outdent and block indentation`);
  console.log(language,'pairs, overtype and indentation passed');
 }
 await page.getByRole('tab',{name:'Python',exact:true}).click();
 await paste('x = 1\n');await page.keyboard.press('Control+End');await page.keyboard.type('# undo');
 await page.keyboard.press('Control+z');assert.notEqual(await value(),'x = 1\n# undo');
 await page.keyboard.press('Control+Shift+z');assert.equal(await value(),'x = 1\n# undo');report.checks.push('Undo and redo');
 // Test actual key-to-paint latency with a 10,000-line editor document.
 await page.evaluate(()=>{
  window.editorTyping=[];window.draftReads=0;
  const get=Storage.prototype.getItem;window.readOriginalDraft=()=>get.call(localStorage,'spandy-shows-draft');
  Storage.prototype.getItem=function(key){if(key==='spandy-shows-draft')window.draftReads++;return get.call(this,key)};
  document.addEventListener('keydown',event=>{if(event.key.length===1&&!event.ctrlKey&&!event.metaKey){const start=performance.now();requestAnimationFrame(()=>window.editorTyping.push(performance.now()-start));}},true);
 });
 const documents={
  Python:Array.from({length:9999},(_,i)=>`number_${i} = ${i}`).join('\n')+'\n# ',
  Java:'class Main {\n'+Array.from({length:9997},(_,i)=>`    int number_${i} = ${i};`).join('\n')+'\n}\n// ',
  C:Array.from({length:9999},(_,i)=>`int number_${i} = ${i};`).join('\n')+'\n// ',
 };
 for(const [language,large] of Object.entries(documents)){
  await page.getByRole('tab',{name:language,exact:true}).click();await paste(large);await page.keyboard.press('Control+End');await page.waitForTimeout(300);
  for(let trial=0;trial<3;trial++){
   await page.evaluate(()=>{window.editorTyping=[]});
   await page.keyboard.type('smooth_typing_1234567890 ',{delay:8});await page.waitForTimeout(60);
   const timings=await page.evaluate(()=>window.editorTyping.sort((a,b)=>a-b));
   report.typing.push({language,trial,lines:10000,keys:timings.length,p95KeyToPaintMs:Math.round(timings[Math.floor(timings.length*.95)]*10)/10,maxKeyToPaintMs:Math.round(timings.at(-1)*10)/10});
  }
  assert.equal(await value(),large+'smooth_typing_1234567890 '.repeat(3));
  await page.waitForTimeout(300);assert.equal(await page.evaluate(()=>JSON.parse(window.readOriginalDraft()).source),large+'smooth_typing_1234567890 '.repeat(3));
  console.log(language,'10,000-line typing passed');
 }
 assert.equal(await page.evaluate(()=>window.draftReads),0);
 report.checks.push('10,000-line typing preserves all characters and saves the draft without re-reading it');
 assert.deepEqual(errors,[]);report.checks.push('No renderer exceptions');
 for(const [language,source] of Object.entries(snippets)){
  await page.getByRole('tab',{name:language,exact:true}).click();await paste(source);await page.waitForTimeout(300);
  await page.reload();await editor.waitFor();
  await page.waitForFunction(()=>new Set(Array.from(document.querySelectorAll('.view-lines span[class*=mtk]'),e=>getComputedStyle(e).color)).size>=4);
  report.checks.push(`${language} syntax colors after reloading the saved draft`);
 }
 await page.getByRole('tab',{name:'C',exact:true}).click();await paste(snippets.C);
 await page.getByRole('button',{name:'Switch to dark theme',exact:true}).click();await page.waitForTimeout(200);
 assert.deepEqual(errors,[]);
 await page.screenshot({path:path.join(output,'editor-verified.png')});
 fs.writeFileSync(path.join(output,'verification.json'),JSON.stringify(report,null,2));
 console.log(JSON.stringify(report,null,2));
} finally {await app.close();}
