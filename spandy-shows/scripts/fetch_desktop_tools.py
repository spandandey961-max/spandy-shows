"""Fetch the pinned desktop build tools locally; nothing is installed system-wide."""
import hashlib,json,urllib.request,zipfile
from pathlib import Path

project=Path(__file__).resolve().parents[1]
directory=project/'desktop-tools';directory.mkdir(exist_ok=True)
lock=json.loads((project/'desktop/tools.lock.json').read_text(encoding='utf-8'))
for name,item in lock.items():
    archive=directory/(name+'.zip')
    if not archive.exists():
        request=urllib.request.Request(item['url'],headers={'User-Agent':'Spandy-Shows-build'})
        with urllib.request.urlopen(request,timeout=180) as response,archive.open('wb') as output:
            while chunk:=response.read(1024*1024):output.write(chunk)
    with archive.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
    if digest!=item['sha256']:raise SystemExit('Checksum mismatch: '+str(archive))
    target=directory/'electron' if name=='electron' else directory
    if name=='electron' and (target/'electron.exe').exists():continue
    if name=='nsis' and (target/('nsis-'+item['version'])/'makensis.exe').exists():continue
    target.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive) as source:
        for member in source.infolist():
            if not (target/member.filename).resolve().is_relative_to(target.resolve()):raise SystemExit('Unsafe archive entry rejected.')
        source.extractall(target)
    print(name,item['version'],'checksum verified and extracted.',flush=True)
