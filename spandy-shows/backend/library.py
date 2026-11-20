"""Permanent, named program storage for the private desktop edition."""
import json, os, sqlite3, time, uuid
from pathlib import Path
from contextlib import contextmanager
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator
from .schema import Program

router=APIRouter(prefix='/api/library')

class Name(BaseModel):
    title:str=Field(min_length=1,max_length=80)
    @field_validator('title')
    @classmethod
    def clean(cls,value):
        value=value.strip()
        if not value or any(ord(c)<32 for c in value):raise ValueError('Enter a program name.')
        return value

class LibraryProgram(Program):
    @field_validator('title')
    @classmethod
    def clean(cls,value):return Name.clean(value)

@contextmanager
def database():
    location=os.getenv('SPANDY_DESKTOP_DATA')
    if not location:raise HTTPException(404,'The device library belongs to the desktop edition.')
    root=Path(location);root.mkdir(parents=True,exist_ok=True)
    connection=sqlite3.connect(root/'programs.sqlite3',timeout=10)
    connection.row_factory=sqlite3.Row
    try:
        connection.execute('PRAGMA journal_mode=WAL')
        connection.execute('CREATE TABLE IF NOT EXISTS library (id TEXT PRIMARY KEY, payload TEXT NOT NULL, created INTEGER NOT NULL, updated INTEGER NOT NULL, title TEXT NOT NULL, language TEXT NOT NULL, step INTEGER NOT NULL)')
        with connection:yield connection
    finally:connection.close()

def record(row,full=False):
    result={'title':row['title'],'language':row['language'],'selectedStep':row['step']}
    if full:
        program=json.loads(row['payload']);result.update(source=program['source'],stdin=program['stdin'])
    return dict(result,id=row['id'],created=row['created'],updated=row['updated'])

@router.get('/programs')
def listing():
    with database() as db:return [record(row) for row in db.execute('SELECT id,title,language,step,created,updated FROM library ORDER BY updated DESC,id')]

@router.get('/programs/{id}')
def retrieve(id:str):
    with database() as db:row=db.execute('SELECT * FROM library WHERE id=?',(id,)).fetchone()
    if not row:raise HTTPException(404,'Program not found.')
    return record(row,True)

@router.post('/programs',status_code=201)
def create(program:LibraryProgram):
    now=time.time_ns()//1_000_000;id=uuid.uuid4().hex
    with database() as db:
        if db.execute('SELECT count(*) FROM library').fetchone()[0]>=5000:raise HTTPException(413,'The device library has reached 5,000 programs.')
        db.execute('INSERT INTO library VALUES (?,?,?,?,?,?,?)',(id,program.model_dump_json(),now,now,program.title,program.language,program.selectedStep))
    return retrieve(id)

@router.put('/programs/{id}')
def update(id:str,program:LibraryProgram):
    with database() as db:
        changed=db.execute('UPDATE library SET payload=?,updated=?,title=?,language=?,step=? WHERE id=?',(program.model_dump_json(),time.time_ns()//1_000_000,program.title,program.language,program.selectedStep,id))
        if not changed.rowcount:raise HTTPException(404,'Program not found.')
    return retrieve(id)

@router.patch('/programs/{id}')
def rename(id:str,name:Name):
    with database() as db:
        row=db.execute('SELECT * FROM library WHERE id=?',(id,)).fetchone()
        if not row:raise HTTPException(404,'Program not found.')
        payload=json.loads(row['payload']);payload['title']=name.title
        db.execute('UPDATE library SET payload=?,updated=?,title=? WHERE id=?',(json.dumps(payload),time.time_ns()//1_000_000,name.title,id))
    return retrieve(id)

@router.delete('/programs/{id}')
def remove(id:str):
    with database() as db:db.execute('DELETE FROM library WHERE id=?',(id,))
    return {'deleted':id}

@router.get('/backup')
def backup():
    with database() as db:return {'format':'spandy-shows-programs','version':1,'programs':[record(row,True) for row in db.execute('SELECT * FROM library ORDER BY updated DESC')]}
