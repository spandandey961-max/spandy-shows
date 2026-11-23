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


def test_growing_replay_throttles_checkpoints_but_input_forces_frontier(tmp_path,monkeypatch):
 clock=[10.0]
 monkeypatch.setattr(interactive.time,'monotonic',lambda:clock[0])
 publisher=interactive.TracePublisher(tmp_path)
 result={'steps':[{'index':i} for i in range(1000)]}
 publisher.publish(result)
 clock[0]+=2
 result['steps'] += [{'index':i} for i in range(1000,1064)]
 publisher.publish(result)
 assert json.loads((tmp_path/'progress.json').read_text())['steps']==1000
 publisher.publish(result,force=True)
 assert json.loads((tmp_path/'progress.json').read_text())['steps']==1064
 assert len((tmp_path/'steps.jsonl').read_text().splitlines())==1064

def test_deltas_restore_output_deletions_aliases_and_backward_history():
 first={'index':0,'note':'call','frames':[{'id':'f1','locals':{'n':3}}],'globals':{'a':{'ref':'m1'},'b':{'ref':'m1'}},'objects':{'m1':{'items':[1,2]}},'stdout':'Hi','stderr':''}
 second={'index':1,'globals':{'b':{'ref':'m1'}},'objects':{'m1':{'items':[1,3]}},'stdout':'Hi there','stderr':''}
 third={'index':2,'globals':{},'objects':{},'stdout':'reset','stderr':'Error'}
 previous={};restored=[]
 for step in (first,second,third):
  previous=interactive.apply_delta(previous,interactive.step_delta(previous,step))
  restored.append(previous)
 assert restored==[first,second,third]
 assert restored[0]['objects']['m1']['items']==[1,2]
