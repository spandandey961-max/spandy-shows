const {contextBridge,ipcRenderer}=require('electron');
const token=process.argv.find(arg=>arg.startsWith('--spandy-token='))?.slice('--spandy-token='.length)||'';
contextBridge.exposeInMainWorld('spandyDesktop',{
 token,
 openProgram:()=>ipcRenderer.invoke('spandy:open'),
 showProgramsFolder:()=>ipcRenderer.invoke('spandy:folder'),
 setDocumentTitle:title=>ipcRenderer.send('spandy:title',title),
 onCommand:callback=>{const listener=(_event,command)=>callback(command);ipcRenderer.on('spandy:command',listener);return()=>ipcRenderer.removeListener('spandy:command',listener);}
});
