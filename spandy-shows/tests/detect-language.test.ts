import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {detectLanguage,executionLanguage} from '../src/detectLanguage.ts';

test('pasted Java utility uses Java even when Python or C is selected',()=>{
 const source=readFileSync(new URL('./fixtures/utility-menu.java',import.meta.url),'utf8');
 assert.equal(executionLanguage(source,'python'),'java');
 assert.equal(executionLanguage(source,'c'),'java');
 assert.equal(source.includes('public class Main'),true);
});
test('Java declarations allow the opening brace on another line',()=>{
 assert.equal(detectLanguage('public final class UtilityProgram\n{\n public static void main(String[] args) {}\n}'),'java');
 assert.equal(detectLanguage('package example;\nimport java.util.Scanner;'),'java');
 assert.equal(detectLanguage('public enum App { READY; public static void main(String[] args) {} }'),'java');
 assert.equal(detectLanguage('enum App { READY; public static void main(String[] args) {} }'),'java');
});
test('C main and C enums stay with the C compiler',()=>{
 assert.equal(executionLanguage('#include <stdio.h>\nenum Choice { YES, NO };\nint main(void) { return 0; }','java'),'c');
 assert.equal(detectLanguage('#include "local.h"\nint main() { return 0; }'),'c');
});
test('Python declarations and imports use Python',()=>{
 assert.equal(executionLanguage('class Counter:\n    def increment(self):\n        pass','java'),'python');
 assert.equal(detectLanguage('from math import sqrt\nprint(sqrt(9))'),'python');
 assert.equal(detectLanguage('async def calculate(n) -> int:\n    return n'),'python');
 assert.equal(executionLanguage('import math\nprint(math.sqrt(9))','java'),'python');
});
test('comments and literals do not trigger language switches',()=>{
 for(const source of [
  '# public class Fake {}\nvalue = 1',
  '// public class Fake {}\nvalue = 1;',
  '/* int main() {} */\nvalue = 1;',
  'message = "public class Fake {}"',
  "message = '''\npublic class Fake {}\ndef fake():\n'''",
 ])assert.equal(detectLanguage(source),null,source);
});
test('ambiguous code retains the language selected by the user',()=>{
 for(const language of ['python','java','c'] as const)assert.equal(executionLanguage('value = 1',language),language);
});
