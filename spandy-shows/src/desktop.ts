import type {Language} from './types';
export type Draft={source:string;language:Language;title:string;id:string|null;nativeMode?:'c'|'cpp'};
declare global {
 interface Window {spandyDesktop?:{
  token:string;
  openProgram:()=>Promise<{name:string;source:string}|null>;
  showProgramsFolder:()=>Promise<void>;
  setDocumentTitle:(title:string)=>void;
  onCommand:(callback:(command:string)=>void)=>()=>void;
 }}
}
export const desktop=!!window.spandyDesktop;
export function readDraft():Draft|null{
 if(!desktop)return null;
 try{const draft=JSON.parse(localStorage.getItem('spandy-shows-draft')||'null');
  return draft&&['python','java','c'].includes(draft.language)&&typeof draft.source==='string'&&typeof draft.title==='string'?draft:null;
 }catch{return null;}
}
export function desktopHeaders():Record<string,string>{return window.spandyDesktop?{'X-Spandy-Token':window.spandyDesktop.token}:{};}
