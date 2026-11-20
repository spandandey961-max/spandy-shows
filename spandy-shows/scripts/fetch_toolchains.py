"""Download locked project-local Windows engines. No system installation or PATH changes."""
import hashlib,json,os,urllib.request,zipfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
if os.name!='nt':raise SystemExit('On Linux/macOS install JDK 21, GCC and GDB through your package manager.')
tools=root/'toolchains';tools.mkdir(exist_ok=True)
lock=json.loads((root/'toolchains.lock.json').read_text())
for name,item in lock.items():
    archive=tools/(name+'.zip')
    if not archive.exists():
        print('Downloading',item['version'],flush=True)
        req=urllib.request.Request(item['url'],headers={'User-Agent':'Spandy-Shows-setup'})
        with urllib.request.urlopen(req,timeout=180) as inp,archive.open('wb') as out:
            while chunk:=inp.read(1024*1024):out.write(chunk)
    sha=hashlib.sha256()
    with archive.open('rb') as f:
        while chunk:=f.read(1024*1024):sha.update(chunk)
    if sha.hexdigest()!=item['sha256']:raise SystemExit('Toolchain checksum mismatch; remove the archive and retry.')
    if not (tools/item['directory']).exists():
        with zipfile.ZipFile(archive) as z:
            for entry in z.infolist():
                dest=(tools/entry.filename).resolve()
                if not dest.is_relative_to(tools.resolve()):raise SystemExit('Unsafe archive entry rejected.')
            z.extractall(tools)
runtime={}
for key,name in [('java','jdk'),('javac','jdk'),('gcc','c'),('gdb','c')]:
    runtime[key]=str(tools/lock[name]['directory']/'bin'/(key+'.exe'))
(root/'runtime.local.json').write_text(json.dumps(runtime,indent=2))
print('Spandy Shows toolchain paths saved to runtime.local.json.')
