import type {Language} from './types.ts';

/** Only distinctive declarations count; prose, comments and literals do not. */
export function detectLanguage(source:string):Language|null{
 const code=source.replace(/"""[\s\S]*?"""|'''[\s\S]*?'''|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|\/\/[^\n]*|\/\*[\s\S]*?\*\//g,m=>m.replace(/[^\n]/g,' '));
 const declarations=code.replace(/^\s*#[^\n]*/gm,'');
 const cIncludes=/^\s*#\s*include\b/m.test(code);
 if(cIncludes&&/\b(?:int|void|char|double|float|long)\s+\w+\s*\([^;{}]*\)\s*\{/.test(declarations))return 'c';
 const python=code.replace(/#[^\n]*/g,'');
 if(/^\s*import\s+[a-z_][\w]*(?:\s+as\s+\w+)?[ \t]*;/m.test(python))return 'python';
 if(/^\s*(?:async\s+)?def\s+\w+\s*\([^{};]*?\)\s*(?:->[^\n]+)?\s*:/m.test(python)||/^\s*class\s+\w+(?:\s*\([^\n]*\))?\s*:/m.test(python)||/^\s*from\s+[\w.]+\s+import\s+/m.test(python)||/^\s*import\s+[\w.]+(?:\s+as\s+\w+)?(?:\s*,\s*[\w.]+(?:\s+as\s+\w+)?)*\s*$/m.test(python))return 'python';
 if(/\b(?:class|interface|public\s+enum)\s+[\p{L}_$][\p{L}\p{N}_$]*[^;:{}]*\{|\brecord\s+[\p{L}_$][\p{L}\p{N}_$]*\s*\(/u.test(python)||/^\s*import\s+(?:static\s+)?[\w.$]+(?:\.\*)?\s*;/m.test(python)||/\bvoid\s+main\s*\(\s*(?:java\s*\.\s*lang\s*\.\s*)?String\s*(?:\[|\.\.\.|\w+\s*\[)|\b(?:public|protected|private)\s+(?:static\s+)?void\s+main\s*\(/.test(python))return 'java';
 if(/\bint\s+main\s*\([^;{}]*\)\s*\{|\bvoid\s+main\s*\(\s*(?:void|int\b[^;{}]*)\)\s*\{/.test(declarations))return 'c';
 return null;
}

export function executionLanguage(source:string,selected:Language):Language{
 return detectLanguage(source)||selected;
}
