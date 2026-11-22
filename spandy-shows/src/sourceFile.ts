import type {Language} from './types.ts';

export function sourceFile(language:Language,source:string):string{
 if(language!=='java')return language==='python'?'main.py':'main.c';
 const code=source.replace(/"""[\s\S]*?"""|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|\/\/[^\n]*|\/\*[\s\S]*?\*\//g,m=>m.replace(/[^\n]/g,' '));
 const tokens=Array.from(code.matchAll(/[\p{L}_$][\p{L}\p{N}_$]*|[{};]/gu));
 let depth=0,memberStart=0;let modifiers:string[]=[];
 const classes:{name:string;public:boolean;main?:boolean}[]=[];
 let owner:typeof classes[number]|undefined;
 const mainSignature=/^\s*\(\s*(?:(?:final\s+)?(?:java\s*\.\s*lang\s*\.\s*)?String\s*(?:(?:\[\s*\]|\.\.\.)\s*[\w$]+|[\w$]+\s*\[\s*\]))?\s*\)\s*(?:throws\b[^{};]+)?\s*\{/;
 for(let i=0;i<tokens.length;i++){
  const word=tokens[i][0];
  if(word==='{'){depth++;modifiers=[];if(depth===1)memberStart=i+1;}
  else if(word==='}'){depth--;modifiers=[];if(depth===0)owner=undefined;else if(depth===1)memberStart=i+1;}
  else if(word===';'){modifiers=[];if(depth===1)memberStart=i+1;}
  else if(depth===0){
   if(['class','record','enum','interface'].includes(word)&&tokens[i+1]&&!code.slice(0,tokens[i].index).trimEnd().endsWith('.')){
    owner={name:tokens[i+1][0],public:modifiers.includes('public')};
    classes.push(owner);
   }
   modifiers.push(word);
  }else if(depth===1&&owner&&word==='main'&&tokens[i-1][0]==='void'&&
    mainSignature.test(code.slice(tokens[i].index!+word.length))&&!tokens.slice(memberStart,i).some(token=>token[0]==='private')){
   owner.main=true;
  }
 }
 const main=classes.find(item=>item.main);
 return (classes.find(item=>item.public)?.name||main?.name||classes[0]?.name||'Main')+'.java';
}
