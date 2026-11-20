import {test} from 'node:test';
import assert from 'node:assert/strict';
import {inputInfo} from '../src/input.ts';

test('C palindrome input and its prompt are detected',()=>{
 assert.deepEqual(inputInfo('printf("Enter an integer: ");\nscanf("%d", &n);','c'),{required:true,prompt:'Enter an integer:'});
});
test('Python and Java input readers require a supplied response',()=>{
 assert.deepEqual(inputInfo('name = input("Your name: ")','python'),{required:true,prompt:'Your name:'});
 assert.equal(inputInfo('int n = scanner.nextInt();','java').required,true);
 assert.equal(inputInfo('String text = scanner.nextLine();','java').required,true);
});
test('strings and comments never create an input requirement',()=>{
 assert.equal(inputInfo('// scanf("%d", &n);\nprintf("scanf(hello)");','c').required,false);
 assert.equal(inputInfo('# input("name")\nprint("input(")','python').required,false);
 assert.equal(inputInfo('/* scanner.nextInt(); */\nSystem.out.println(".next()");','java').required,false);
});
test('C stdin readers are detected without confusing file reads',()=>{
 for(const source of ['fscanf(stdin,"%d",&n);','fgets(text,sizeof(text),stdin);','getchar();','getc(stdin);'])
  assert.equal(inputInfo(source,'c').required,true,source);
 for(const source of ['fscanf(file,"%d",&n);','fgets(text,sizeof(text),file);'])
  assert.equal(inputInfo(source,'c').required,false,source);
});
