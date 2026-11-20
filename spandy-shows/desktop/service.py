"""Owned, windowless backend for one native app session."""
import argparse,json,os,socket,sys,threading,time
from pathlib import Path

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--data',type=Path,required=True)
    parser.add_argument('--parent',type=int,required=True)
    args=parser.parse_args();root=args.root.resolve();data=args.data.resolve()
    data.mkdir(parents=True,exist_ok=True);(data/'Logs').mkdir(exist_ok=True)
    (data/'Jobs').mkdir(exist_ok=True)
    ready_stream=sys.stdout
    log=(data/'Logs/backend.log').open('a',encoding='utf-8',buffering=1)
    sys.stdout=sys.stderr=log
    app_root=root/'app';os.chdir(app_root);sys.path.insert(0,str(app_root))
    config={name:str(root/f'runtime/{group}/bin/{name}.exe') for name,group in [('java','java'),('javac','java'),('gcc','c'),('gdb','c')]}
    for executable in config.values():
        if not Path(executable).is_file():raise RuntimeError('A bundled compiler is missing. Extract the whole app folder.')
    config_file=data/'runtime.json';config_file.write_text(json.dumps(config),encoding='utf-8')
    sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    os.environ.update(SPANDY_CONFIG_PATH=str(config_file),SPANDY_DESKTOP_DATA=str(data),
        SPANDY_EXECUTION_MODE='trusted-local',SPANDY_TRUST_LOCAL_CODE='1',
        SPANDY_ORIGINS=f'spandy://app,http://127.0.0.1:{port}',SPANDY_HOSTS='127.0.0.1,localhost',
        DATABASE_URL='sqlite:///'+(data/'workspace.sqlite3').as_posix(),
        SPANDY_JOB_ROOT=str(data/'Jobs'),SPANDY_JAVA_HELPERS=str(app_root/'backend/java/classes'),SPANDY_C_HELPERS=str(app_root/'backend/c/classes'))
    if not os.getenv('SPANDY_DESKTOP_TOKEN'):raise RuntimeError('Start the backend through Spandy Shows.exe.')
    for key in ('SPANDY_ACTIVE_SECONDS','SPANDY_INPUT_IDLE_SECONDS'):os.environ.pop(key,None)
    import psutil,uvicorn
    parent=psutil.Process(args.parent);parent_created=parent.create_time()
    from backend.app import app
    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=port,access_log=False,timeout_keep_alive=1,timeout_graceful_shutdown=3))
    app.state.desktop_shutdown=lambda:setattr(server,'should_exit',True)
    def monitor():
        reported=False
        while not server.should_exit:
            try:
                if not parent.is_running() or parent.create_time()!=parent_created:server.should_exit=True;break
            except psutil.Error:server.should_exit=True;break
            if server.started and not reported:
                ready_stream.write(json.dumps({'ready':True,'port':port,'pid':os.getpid()})+'\n');ready_stream.flush();reported=True
            time.sleep(.05)
    threading.Thread(target=monitor,daemon=True).start()
    try:server.run(sockets=[sock])
    finally:sock.close()

if __name__=='__main__':
    try:main()
    except Exception:
        import traceback
        traceback.print_exc();raise SystemExit(1)
