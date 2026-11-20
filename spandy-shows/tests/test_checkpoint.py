import json
from pathlib import Path
from backend import interactive

def test_transient_windows_reader_conflict_keeps_atomic_checkpoint(tmp_path,monkeypatch):
 original=interactive.os.replace;calls=[]
 def replace(source,target):
  calls.append(1)
  if len(calls)<3:raise PermissionError('Checkpoint reader has the file open')
  original(source,target)
 monkeypatch.setattr(interactive.os,'replace',replace)
 interactive.atomic_json(tmp_path/'progress.json',{'steps':205})
 assert len(calls)==3
 assert json.loads((tmp_path/'progress.json').read_text())=={'steps':205}

def test_input_response_survives_a_reader_lock_during_cleanup(tmp_path,monkeypatch):
 interactive.atomic_json(tmp_path/'input-response-1.json',{'id':1,'text':'42'})
 (tmp_path/'input-text-1.txt').write_text('42\n')
 original=Path.unlink;conflicts=[]
 def unlink(path,*args,**kwargs):
  if path.name=='input-request.json' and len(conflicts)<2:
   conflicts.append(path);raise PermissionError('Input request is being polled')
  return original(path,*args,**kwargs)
 monkeypatch.setattr(Path,'unlink',unlink)
 client=interactive.InputClient(tmp_path)
 assert client.read(5,'integer')=='42\n'
 assert client.sequence==1
 assert not any(tmp_path.glob('input-*.json'))
 assert not (tmp_path/'input-text-1.txt').exists()
