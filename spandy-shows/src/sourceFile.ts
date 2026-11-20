import type {Language} from './types.ts';

export function sourceFile(language:Language,source:string):string{
 if(language!=='java')return language==='python'?'main.py':'main.c';
 const code=source.replace(/"""[\s\S]*?"""|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|\/\/[^\n]*|\/\*[\s\S]*?\*\//g,m=>m.replace(/[^\n]/g,' '));
 const tokens=Array.from(code.matchAll(/[\p{L}_$][\p{L}\p{N}_$]*|[{};]/gu));
 let depth=0;let modifiers:string[]=[];const classes:{name:string;public:boolean;start:number}[]=[];
 for(let i=0;i<tokens.length;i++){
  const word=tokens[i][0];
  if(word==='{'){depth++;modifiers=[]}
  else if(word==='}'){depth--;modifiers=[]}
  else if(word===';')modifiers=[];
  else if(depth===0){
   if(['class','record','enum','interface'].includes(word)&&tokens[i+1]&&!code.slice(0,tokens[i].index).trimEnd().endsWith('.')){
    classes.push({name:tokens[i+1][0],public:modifiers.includes('public'),start:tokens[i].index!});
   }
   modifiers.push(word);
  }
 }
 const main=classes.find((item,i)=>/\bstatic\s+(?:(?:final|synchronized|strictfp)\s+)*void\s+main\s*\(/.test(code.slice(item.start,classes[i+1]?.start)));
 return (classes.find(item=>item.public)?.name||main?.name||classes[0]?.name||'Main')+'.java';
}
