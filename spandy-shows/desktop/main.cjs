const {app,BrowserWindow,Menu,dialog,ipcMain,shell,screen,protocol,net}=require('electron');
const {spawn}=require('node:child_process');
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const http=require('node:http');
const ROOT=path.resolve(__dirname,'../..');
const option=name=>process.argv.find(arg=>arg.startsWith(`--${name}=`))?.slice(name.length+3);
const DATA=path.resolve(option('data-dir')||path.join(process.env.LOCALAPPDATA||app.getPath('appData'),'Spandy Shows'));
const TOKEN=crypto.randomBytes(32).toString('hex');
const ORIGIN='spandy://app';
protocol.registerSchemesAsPrivileged([{scheme:'spandy',privileges:{standard:true,secure:true,supportFetchAPI:true,stream:true,codeCache:true}}]);
const ICON=path.join(ROOT,'Spandy Shows.ico');
fs.mkdirSync(DATA,{recursive:true});fs.mkdirSync(path.join(DATA,'Logs'),{recursive:true});
app.setName('Spandy Shows');app.setAppUserModelId('SpandyShows.Desktop');
app.setPath('userData',path.join(DATA,'BrowserProfile'));
app.commandLine.appendSwitch('disable-background-networking');
app.commandLine.appendSwitch('disable-component-update');
let window,backend,connection,quitting=false,loaded=false;
const log=message=>fs.appendFileSync(path.join(DATA,'Logs/desktop.log'),new Date().toISOString()+' '+message+'\n');
const writeJSON=(file,value)=>{const temporary=file+'.tmp';fs.writeFileSync(temporary,JSON.stringify(value));fs.renameSync(temporary,file);};
const statePath=path.join(DATA,'window.json');
function bounds(){
 const area=screen.getPrimaryDisplay().workArea;
 let saved={};try{saved=JSON.parse(fs.readFileSync(statePath,'utf8'));}catch{}
 const width=Math.min(area.width,Math.max(760,Number(saved.width)||Math.min(1440,area.width*.94)));
 const height=Math.min(area.height,Math.max(540,Number(saved.height)||Math.min(900,area.height*.94)));
 const position={x:Number(saved.x),y:Number(saved.y),width:Math.round(width),height:Math.round(height)};
 if(!Number.isFinite(position.x)||!Number.isFinite(position.y)||!screen.getAllDisplays().some(d=>position.x<d.workArea.x+d.workArea.width-100&&position.x+width>d.workArea.x+100&&position.y<d.workArea.y+d.workArea.height-60&&position.y>=d.workArea.y-20)){
  position.x=Math.round(area.x+(area.width-width)/2);position.y=Math.round(area.y+(area.height-height)/2);
 }
 return {...position,maximized:!!saved.maximized,zoom:Math.min(2,Math.max(.75,Number(saved.zoom)||1))};
}
function persistWindow(){
 if(window&&!window.isDestroyed())writeJSON(statePath,{...window.getNormalBounds(),maximized:window.isMaximized(),zoom:window.webContents.getZoomFactor()});
}
function command(name){if(loaded&&window&&!window.isDestroyed())window.webContents.send('spandy:command',name);}
function integrate(){
 if(process.argv.includes('--no-integration'))return;
 const custom=option('shortcut-root');
 const locations=custom?[path.join(custom,'Desktop'),path.join(custom,'Start Menu')]:[app.getPath('desktop'),path.join(app.getPath('appData'),'Microsoft/Windows/Start Menu/Programs')];
 for(const location of locations){
  try{fs.mkdirSync(location,{recursive:true});const target=path.join(location,'Spandy Shows.lnk');
   let existing;try{existing=shell.readShortcutLink(target);}catch{}
   if(!existing||existing.target!==process.execPath||existing.icon!==ICON||existing.appUserModelId!=='SpandyShows.Desktop')shell.writeShortcutLink(target,fs.existsSync(target)?'replace':'create',{target:process.execPath,cwd:ROOT,description:'See your code, step by step.',icon:ICON,iconIndex:0,appUserModelId:'SpandyShows.Desktop'});
  }catch(error){log('Shortcut: '+error.message);}
 }
}
function requestShutdown(){
 return new Promise(resolve=>{
  if(!backend||backend.exitCode!==null)return resolve();
  let finished=false;const done=()=>{if(!finished){finished=true;resolve();}};
  backend.once('exit',done);
  const timeout=setTimeout(()=>{
   if(backend.exitCode===null){const killer=spawn(path.join(process.env.SYSTEMROOT||'C:/Windows','System32/taskkill.exe'),['/PID',String(backend.pid),'/T','/F'],{windowsHide:true,stdio:'ignore'});killer.on('error',done);killer.on('exit',done);}else done();
  },4500);timeout.unref();
  if(connection){const request=http.request({hostname:'127.0.0.1',port:connection.port,path:'/api/desktop/shutdown',method:'POST',headers:{'X-Spandy-Token':TOKEN,'Content-Type':'application/json','Content-Length':2}},res=>res.resume());request.on('error',()=>{});request.end('{}');}
  else backend.kill();
 });
}
function startBackend(){
 return new Promise((resolve,reject)=>{
  const environment={...process.env,SPANDY_DESKTOP_TOKEN:TOKEN,PYTHONIOENCODING:'utf-8',PYTHONUNBUFFERED:'1'};
  for(const key of ['PYTHONHOME','PYTHONPATH','VIRTUAL_ENV','DATABASE_URL','SPANDY_JOB_ROOT','SPANDY_CONFIG_PATH'])delete environment[key];
  backend=spawn(path.join(ROOT,'runtime/python/python.exe'),['-I',path.join(ROOT,'app/desktop/service.py'),'--root',ROOT,'--data',DATA,'--parent',String(process.pid)],{cwd:ROOT,env:environment,windowsHide:true,stdio:['ignore','pipe','pipe']});
  let buffer='',ready=false;
  const timer=setTimeout(()=>reject(new Error('The local engines did not start. See the device Logs folder.')),45000);
  backend.stdout.on('data',chunk=>{buffer+=chunk.toString();let split;while((split=buffer.indexOf('\n'))>=0){const line=buffer.slice(0,split);buffer=buffer.slice(split+1);try{const event=JSON.parse(line);if(event.ready&&!ready){ready=true;clearTimeout(timer);connection=event;writeJSON(path.join(DATA,'session.json'),{...event,appPid:process.pid,root:ROOT});resolve(event);}}catch{log(line);}}});
  backend.stderr.on('data',chunk=>log('Backend: '+chunk.toString()));
  backend.on('error',error=>{clearTimeout(timer);reject(error);});
  backend.on('exit',code=>{clearTimeout(timer);if(!ready)reject(new Error('The local engines stopped during startup. See the device Logs folder.'));else if(!quitting){dialog.showErrorBox('Spandy Shows','The local compiler stopped. Your saved programs are safe. Close and reopen the app.');app.quit();}log('Backend exited '+code);});
 });
}
function trusted(event){return !!window&&event.sender===window.webContents&&!!connection&&event.senderFrame?.url.startsWith(ORIGIN+'/');}
ipcMain.handle('spandy:open',async event=>{
 if(!trusted(event))throw new Error('Workspace is not ready.');
 const chosen=await dialog.showOpenDialog(window,{title:'Open a program',properties:['openFile'],filters:[{name:'Programs',extensions:['py','java','c','json','txt']},{name:'All files',extensions:['*']}]});
 if(chosen.canceled)return null;const file=chosen.filePaths[0];
 if(fs.statSync(file).size>2*1024*1024)throw new Error('Choose a program file smaller than 2 MB.');
 return {name:path.basename(file),source:await fs.promises.readFile(file,'utf8')};
});
ipcMain.handle('spandy:folder',event=>{if(!trusted(event))throw new Error('Workspace is not ready.');return shell.openPath(DATA);});
ipcMain.on('spandy:title',(event,title)=>{if(trusted(event)&&typeof title==='string')window.setTitle('Spandy Shows — '+title.slice(0,80));});
if(!app.requestSingleInstanceLock()){app.quit();}
else{
 app.on('second-instance',()=>{if(window){if(window.isMinimized())window.restore();window.show();window.focus();}});
 app.whenReady().then(async()=>{
  protocol.handle('spandy',async request=>{
   const url=new URL(request.url);
   if(url.hostname!=='app'||!connection||request.initiatorOrigin&&request.initiatorOrigin!==ORIGIN)return new Response('Workspace unavailable',{status:403});
   const headers=new Headers(request.headers);headers.set('X-Spandy-Token',TOKEN);headers.delete('host');
   const body=['GET','HEAD'].includes(request.method)?undefined:await request.arrayBuffer();
   return net.fetch(`http://127.0.0.1:${connection.port}${url.pathname}${url.search}`,{method:request.method,headers,body,bypassCustomProtocolHandlers:true});
  });
  const saved=bounds();
  window=new BrowserWindow({...saved,title:'Spandy Shows',icon:ICON,minWidth:760,minHeight:540,backgroundColor:'#161c19',show:true,webPreferences:{preload:path.join(__dirname,'preload.cjs'),nodeIntegration:false,contextIsolation:true,sandbox:true,webSecurity:true,webviewTag:false,additionalArguments:['--spandy-token='+TOKEN]}});
  if(saved.maximized)window.maximize();
  window.webContents.setZoomFactor(saved.zoom);
  let debounce;for(const event of ['resize','move','maximize','unmaximize'])window.on(event,()=>{clearTimeout(debounce);debounce=setTimeout(persistWindow,200);});
  window.on('close',persistWindow);
  window.webContents.setWindowOpenHandler(()=>({action:'deny'}));
  window.webContents.on('will-navigate',(event,url)=>{if(!url.startsWith(ORIGIN+'/'))event.preventDefault();});
  window.webContents.session.setPermissionRequestHandler((contents,permission,callback)=>callback(permission==='clipboard-sanitized-write'&&contents.getURL().startsWith(ORIGIN+'/')));
  window.webContents.session.setPermissionCheckHandler((_contents,permission,origin)=>permission==='clipboard-sanitized-write'&&origin===ORIGIN);
  window.webContents.session.webRequest.onBeforeRequest((details,callback)=>{
   const base=connection?`http://127.0.0.1:${connection.port}`:'';
   const allowed=details.url.startsWith('file://')&&details.url.includes('/resources/app/')||details.url.startsWith(ORIGIN+'/')||details.url.startsWith('blob:'+ORIGIN+'/')||base&&details.url.startsWith(base+'/');
   callback({cancel:!allowed});
  });
  window.webContents.session.on('will-download',(_event,item)=>item.setSaveDialogOptions({title:'Export program',defaultPath:path.join(app.getPath('documents'),path.basename(item.getFilename()))}));
  const menu=Menu.buildFromTemplate([
   {label:'File',submenu:[{label:'New program',accelerator:'CmdOrCtrl+N',click:()=>command('new')},{label:'Open…',accelerator:'CmdOrCtrl+O',click:()=>command('open')},{label:'Save program…',accelerator:'CmdOrCtrl+S',click:()=>command('save')},{label:'Export code…',accelerator:'CmdOrCtrl+Shift+S',click:()=>command('export')},{type:'separator'},{label:'My programs',accelerator:'CmdOrCtrl+P',click:()=>command('programs')},{label:'Show device folder',click:()=>shell.openPath(DATA)},{type:'separator'},{role:'quit',label:'Exit Spandy Shows'}]},
   {label:'Edit',submenu:[{label:'Undo',accelerator:'CmdOrCtrl+Z',click:()=>command('undo')},{label:'Redo',accelerator:'CmdOrCtrl+Y',click:()=>command('redo')},{type:'separator'},{role:'cut'},{role:'copy'},{role:'paste'},{role:'selectAll'}]},
   {label:'Run',submenu:[{label:'Run code',accelerator:'F5',click:()=>command('run')},{label:'Visualize',accelerator:'F6',click:()=>command('visualize')}]},
   {label:'View',submenu:[{role:'resetZoom'},{role:'zoomIn'},{role:'zoomOut'},{type:'separator'},{role:'togglefullscreen'}]},
   {label:'Help',submenu:[{label:'Help & shortcuts',accelerator:'F1',click:()=>command('help')},{label:'About Spandy Shows',click:()=>dialog.showMessageBox(window,{type:'info',title:'Spandy Shows',icon:ICON,message:'Spandy Shows',detail:'See your code, step by step.\nDesktop edition 1.1.0\nPython, Java and C run on this device.\nSaved programs stay on this device.'})}]}
  ]);Menu.setApplicationMenu(menu);
  await window.loadFile(path.join(__dirname,'splash.html'));
  integrate();
  try{await startBackend();if(quitting)return;await window.loadURL(ORIGIN+'/');loaded=true;window.webContents.setZoomFactor(saved.zoom);log('Workspace ready.');}
  catch(error){log(error.stack||error.message);dialog.showErrorBox('Spandy Shows',error.message);app.quit();}
 });
 app.on('window-all-closed',()=>app.quit());
 app.on('before-quit',event=>{if(quitting)return;event.preventDefault();quitting=true;persistWindow();requestShutdown().finally(()=>{try{fs.unlinkSync(path.join(DATA,'session.json'));}catch{}app.exit(0);});});
}
