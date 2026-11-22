import {test} from 'node:test';
import assert from 'node:assert/strict';
import {sourceFile} from '../src/sourceFile.ts';

test('Java filename follows the actual top-level public class',()=>{
 assert.equal(sourceFile('java','public class UtilityProgram {}'),'UtilityProgram.java');
 assert.equal(sourceFile('java','class Box { public class Nested {} }\npublic final class Example {}'),'Example.java');
 assert.equal(sourceFile('java','// public class Fake {}\npublic class Actual { String s="public class Other {}"; }'),'Actual.java');
 assert.equal(sourceFile('java','package example; public record RecordApp(int value) {}'),'RecordApp.java');
 assert.equal(sourceFile('java','class Helper {} class App { static void main(String[] args) {} }'),'App.java');
 assert.equal(sourceFile('java','class Helper { class Inner { void main() {} } } class App { void main() {} }'),'App.java');
 assert.equal(sourceFile('java','package demo; public class Helper {} class App { void main() {} }'),'Helper.java');
 assert.equal(sourceFile('java','@Example(type=Other.class) public class App {}'),'App.java');
 assert.equal(sourceFile('python','import math'),'main.py');
 assert.equal(sourceFile('c','#include <stdio.h>'),'main.c');
});
