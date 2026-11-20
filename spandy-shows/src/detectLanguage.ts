import type {Language} from './types.ts';

/** Only distinctive declarations count; prose, comments and literals do not. */
export function detectLanguage(source:string):Language|null{
 const code=source.replace(/"""[\s\S]*?"""|'''[\s\S]*?'''|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|\/\/[^\n]*|\/\*[\s\S]*?\*\//g,m=>m.replace(/[^\n]/g,' '));
 const declarations=code.replace(/^\s*#[^\n]*/gm,'');
 if(/\b(?:(?:class|interface|record)|public\s+enum)\s+[\p{L}_$][\p{L}\p{N}_$]*[^;:{}]*\{/u.test(declarations)||/^\s*import\s+(?:static\s+)?[\w.$]+(?:\.\*)?\s*;/m.test(declarations)||/\bstatic\s+void\s+main\s*\(\s*String\b/.test(declarations))return 'java';
 if(/^\s*(?:async\s+)?def\s+\w+\s*\([^\n]*\)\s*(?:->[^\n]+)?\s*:/m.test(declarations)||/^\s*class\s+\w+(?:\s*\([^\n]*\))?\s*:/m.test(declarations)||/^\s*from\s+[\w.]+\s+import\s+/m.test(declarations)||/^\s*import\s+[\w.]+(?:\s+as\s+\w+)?(?:\s*,\s*[\w.]+(?:\s+as\s+\w+)?)*\s*$/m.test(declarations))return 'python';
 if(/\b(?:int|void)\s+main\s*\([^;{}]*\)\s*\{/.test(declarations)||(/^\s*#\s*include\s*[<"]/m.test(code)&&/\b(?:int|void|char|double|float|long)\s+\w+\s*\([^;{}]*\)\s*\{/.test(declarations)))return 'c';
 return null;
}

export function executionLanguage(source:string,selected:Language):Language{
 return detectLanguage(source)||selected;
}
