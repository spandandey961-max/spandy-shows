import asyncio, json, os, secrets, time, uuid, logging
from logging.handlers import RotatingFileHandler
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy import create_engine, text
from .schema import Program,JobRequest,InputResponse
from .runner import execute_job, stop_job, availability, ROOT, live_progress, partial_trace, respond
from .limits import MAX_STEPS, RUN_SECONDS, VISUALIZE_SECONDS, MAX_SOURCE_LINES, MAX_SOURCE_BYTES, MAX_REQUEST_BYTES, memory_limit_mib

jobs={}
logger=logging.getLogger('spandy.service')
if not logger.handlers:
    log_root=Path(os.getenv('SPANDY_JOB_ROOT',str(ROOT/'.runtime')))
    log_root.mkdir(exist_ok=True,parents=True)
    handler=RotatingFileHandler(log_root/'service.log',maxBytes=1048576,backupCount=2,encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
tasks=set()
slots=asyncio.Semaphore(2)
attempts=defaultdict(deque)
database_url=os.getenv('DATABASE_URL','sqlite:///'+str(ROOT/'spandy-shows.db'))
engine=create_engine(database_url)

def migrate():
    with engine.begin() as conn:
        conn.execute(text('CREATE TABLE IF NOT EXISTS programs (id VARCHAR(64) PRIMARY KEY, payload TEXT NOT NULL, created_at BIGINT NOT NULL, expires_at BIGINT NOT NULL, kind VARCHAR(16) NOT NULL)'))
        conn.execute(text('CREATE INDEX IF NOT EXISTS programs_expiration ON programs(expires_at)'))

@asynccontextmanager
async def lifespan(app):
    global slots
    slots=asyncio.Semaphore(2)
    migrate()
    yield
    for job in jobs.values():
        job['cancel'].set()
        await stop_job(job)
        if job['status'] in ('queued','running','waiting'):job['status']='cancelled'
    for task in tasks: task.cancel()
    await asyncio.gather(*tasks,return_exceptions=True)
    engine.dispose()

app=FastAPI(title='Spandy Shows',description='See your code, step by step.',lifespan=lifespan)
origins=os.getenv('SPANDY_ORIGINS','http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:8000').split(',')
app.add_middleware(CORSMiddleware,allow_origins=origins,allow_methods=['GET','POST','PUT','PATCH','DELETE'],allow_headers=['Content-Type','X-Spandy-Token'])
app.add_middleware(TrustedHostMiddleware,allowed_hosts=os.getenv('SPANDY_HOSTS','127.0.0.1,localhost,testserver').split(','))

@app.middleware('http')
async def boundaries(request:Request, call_next):
    desktop_token=os.getenv('SPANDY_DESKTOP_TOKEN')
    if desktop_token and request.url.path.startswith('/api/') and not secrets.compare_digest(request.headers.get('x-spandy-token',''),desktop_token):
        return JSONResponse(status_code=401,content={'error':{'code':'desktop_session','message':'Open this workspace in the Spandy Shows desktop app.'}})
    if request.headers.get('origin') and request.headers['origin'] not in origins:
        return JSONResponse(status_code=403,content={'error':{'code':'origin_denied','message':'Origin is not permitted.'}})
    if request.method in ('POST','PUT','PATCH'):
        try: content_length=int(request.headers.get('content-length','0') or '0')
        except ValueError: content_length=MAX_REQUEST_BYTES+1
        if content_length>MAX_REQUEST_BYTES or content_length<0:
            return JSONResponse(status_code=413,content={'error':{'code':'request_limit','message':'Request exceeds 2 MiB.'}})
        chunks=[];size=0
        async for chunk in request.stream():
            size+=len(chunk)
            if size>MAX_REQUEST_BYTES:return JSONResponse(status_code=413,content={'error':{'code':'request_limit','message':'Request exceeds 2 MiB.'}})
            chunks.append(chunk)
        request._body=b''.join(chunks)
        # Count all write requests and bound tracked clients.
        key=request.client.host if request.client else 'unknown'
        input_submission=request.url.path.startswith('/api/jobs/') and request.url.path.endswith('/input')
        if input_submission:key+=':input'
        now=time.time()
        if len(attempts)>2048:
            for stale in list(attempts):
                if not attempts[stale] or attempts[stale][-1]<now-60: attempts.pop(stale,None)
            if len(attempts)>2048:return JSONResponse(status_code=503,content={'error':{'code':'service_busy','message':'The service is busy.'}})
        while attempts[key] and attempts[key][0]<now-60: attempts[key].popleft()
        if len(attempts[key])>=(240 if desktop_token else 120 if input_submission else 20):
            return JSONResponse(status_code=429,content={'error':{'code':'rate_limit','message':'Please wait a minute before trying again.'}})
        attempts[key].append(now)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='same-origin'
    if desktop_token:
        response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; worker-src 'self' blob:; style-src 'self' 'unsafe-inline'; font-src 'self'; img-src 'self' data: blob:; connect-src 'self'; object-src 'none'; frame-src 'none'; base-uri 'self'"
    return response

@app.exception_handler(HTTPException)
async def errors(request, exc):
    return JSONResponse(status_code=exc.status_code,content={'error':{'code':'request_error','message':exc.detail}})

@app.exception_handler(RequestValidationError)
async def invalid(request,exc):
    return JSONResponse(status_code=422,content={'error':{'code':'invalid_request','message':'Invalid program request. Check language, source size, input and selected step.'}})

@app.get('/api/health')
async def health():
    mode=os.getenv('SPANDY_EXECUTION_MODE','docker')
    if mode=='trusted-local': available=availability()
    else:
        try:
            import subprocess
            checked=await asyncio.to_thread(subprocess.run,['docker','image','inspect','spandy-shows-worker:local'],capture_output=True,timeout=3)
            docker_ready=checked.returncode==0
        except (OSError,subprocess.TimeoutExpired): docker_ready=False
        available={x:docker_ready for x in ('python','java','c')}
    return {'name':'Spandy Shows','status':'ok','languages':available,'executionMode':mode,
            'desktop':bool(os.getenv('SPANDY_DESKTOP_DATA')),
            'persistence':'PostgreSQL' if database_url.startswith('postgres') else 'SQLite (local)',
            'limits':{'sourceBytes':MAX_SOURCE_BYTES,'sourceLines':MAX_SOURCE_LINES,'steps':MAX_STEPS,'wallSeconds':RUN_SECONDS,'visualizeWallSeconds':VISUALIZE_SECONDS,'inputIdleSeconds':180,'memoryMiB':memory_limit_mib(mode),'outputChars':8192}}

async def work(job):
    try:
        async with slots:
            if job['cancel'].is_set(): job['status']='cancelled'; return
            job['status']='running'
            job['trace']=await execute_job(job)
            job['status']=job['trace']['status']
    except Exception:
        logger.exception('Execution job %s failed (%s)',job['id'],job['program'].language)
        job['status']='failed'
        job['error']='The execution service could not complete this job.'

@app.post('/api/jobs',status_code=202)
async def submit(program:JobRequest):
    if len(program.source.encode())>MAX_SOURCE_BYTES or len(program.source.splitlines())>MAX_SOURCE_LINES:
        raise HTTPException(413,f'Programs are limited to {MAX_SOURCE_BYTES//1024} KiB and {MAX_SOURCE_LINES:,} lines.')
    now=time.time()
    for key in list(jobs):
        if now-jobs[key]['created']>3600 and jobs[key]['status'] not in ('running','queued','waiting'): jobs.pop(key)
    if sum(j['status'] in ('running','queued','waiting') for j in jobs.values())>=8:
        raise HTTPException(503,'The execution queue is full. Try again shortly.')
    if len(jobs)>=128: raise HTTPException(503,'Trace storage is full. Older jobs expire after one hour.')
    id=uuid.uuid4().hex
    jobs[id]={'id':id,'program':program,'status':'queued','cancel':asyncio.Event(),'created':now}
    task=asyncio.create_task(work(jobs[id])); tasks.add(task); task.add_done_callback(tasks.discard)
    return {'id':id,'status':'queued'}

def get_job(id):
    if id not in jobs: raise HTTPException(404,'Job not found or expired.')
    return jobs[id]

@app.get('/api/jobs/{id}')
async def status(id:str):
    job=get_job(id)
    return {'id':id,'status':job['status'],'error':job.get('error'),'live':live_progress(job)}

@app.post('/api/jobs/{id}/input')
async def input_value(id:str, response:InputResponse):
    job=get_job(id)
    if job['status'] not in ('running','waiting'):raise HTTPException(409,'This program is no longer waiting for input.')
    try:
        if not respond(job,response):raise HTTPException(409,'This input request has already been answered or is no longer current.')
    except ValueError as exc:raise HTTPException(413,str(exc))
    return {'id':id,'status':'running'}

@app.get('/api/jobs/{id}/trace')
async def trace(id:str):
    job=get_job(id)
    if 'trace' in job:return job['trace']
    partial=partial_trace(job)
    if partial:return partial
    raise HTTPException(409,'The trace is not ready.')

@app.delete('/api/jobs/{id}')
async def cancel(id:str):
    job=get_job(id)
    if job['status'] in ('queued','running','waiting'):
        job['cancel'].set()
        await stop_job(job)
    return {'id':id,'status':'cancelling' if job['cancel'].is_set() else job['status']}

def persist(program,kind):
    id=secrets.token_urlsafe(24)
    now=int(time.time())
    with engine.begin() as conn:
        conn.execute(text('DELETE FROM programs WHERE expires_at < :now'),{'now':now})
        count=conn.execute(text('SELECT count(*) FROM programs')).scalar()
        if count>=10000: raise HTTPException(503,'Saved program storage is full.')
        conn.execute(text('INSERT INTO programs (id,payload,created_at,expires_at,kind) VALUES (:id,:payload,:now,:expires,:kind)'),
            {'id':id,'payload':program.model_dump_json(),'now':now,'expires':now+30*86400,'kind':kind})
    return {'id':id,'expiresAt':now+30*86400,'access':'Anyone with the unguessable link can read the source; 30-day retention.'}

@app.post('/api/programs',status_code=201)
async def save(program:Program): return persist(program,'saved')
@app.post('/api/shares',status_code=201)
async def share(program:Program): return persist(program,'share')

def retrieve(id):
    with engine.connect() as conn:
        row=conn.execute(text('SELECT payload,expires_at FROM programs WHERE id=:id'),{'id':id}).first()
    if not row or row[1]<time.time(): raise HTTPException(404,'This program link is missing or has expired.')
    return Program.model_validate_json(row[0]).model_dump()

@app.get('/api/programs/{id}')
async def saved(id:str): return retrieve(id)
@app.get('/api/shares/{id}')
async def shared(id:str): return retrieve(id)

from .library import router as library_router
app.include_router(library_router)

@app.post('/api/desktop/shutdown')
async def desktop_shutdown():
    shutdown=getattr(app.state,'desktop_shutdown',None)
    if not os.getenv('SPANDY_DESKTOP_TOKEN') or not shutdown:raise HTTPException(404,'Desktop session not found.')
    shutdown()
    return {'closing':True}

# Serve the built browser application for one-command private local startup.
if (ROOT/'dist').exists():
    from fastapi.staticfiles import StaticFiles
    app.mount('/',StaticFiles(directory=ROOT/'dist',html=True),name='Spandy Shows')
