import type {Language} from './types';

// Detection guides the form only. Runtimes still read the supplied stream and
// report EOF/type errors; the UI never invents input or evaluates user code.
export function inputInfo(source:string,language:Language){
 const tokens=source.replace(language==='python'?/#[^\n]*|(?:"""[\s\S]*?"""|'''[\s\S]*?'''|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')/g:/\/\*[\s\S]*?\*\/|\/\/[^\n]*|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'/g,m=>' '.repeat(m.length));
 const pattern=language==='python'?/\binput\s*\(/:language==='c'?/\b(?:scanf|vscanf|getchar)\s*\(|\b(?:fscanf|vfscanf|fgetc|getc)\s*\(\s*stdin\b|\bfgets\s*\([^;]*,\s*stdin\s*\)/:/\.(?:next|nextLine|nextInt|nextLong|nextDouble|nextFloat|nextBoolean|nextShort|nextByte|readLine|read)\s*\(/;
 const match=pattern.exec(tokens);
 if(!match)return {required:false,prompt:''};
 let prompt='';
 if(language==='python')prompt=source.slice(match.index).match(/^input\s*\(\s*["']([^"']*)["']/)?.[1]||'';
 else {
  const outputs=[...source.slice(0,match.index).matchAll(language==='c'?/\bprintf\s*\(\s*"((?:\\.|[^"\\])*)"/g:/\bSystem\.out\.print(?:ln)?\s*\(\s*"((?:\\.|[^"\\])*)"/g)];
  prompt=outputs.at(-1)?.[1]||'';
 }
 return {required:true,prompt:prompt.replace(/\\n/g,' ').replace(/\\t/g,' ').replace(/\\"/g,'"').trim().slice(0,160)};
}
