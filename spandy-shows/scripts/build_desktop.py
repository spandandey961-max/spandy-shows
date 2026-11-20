"""Build the offline Windows desktop folder from the tested bundled runtimes."""
import argparse,hashlib,json,os,shutil,subprocess,sys
from pathlib import Path
from brand_windows import brand

PROJECT=Path(__file__).resolve().parents[1]
EXCLUDE={'.venv','node_modules','.runtime','__pycache__','.pytest_cache','.git','test-results','.netlify','toolchains','desktop-tools','release','build'}
def link_or_copy(source,dest):
    try:os.link(source,dest)
    except OSError:shutil.copy2(source,dest)
    return dest
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--runtimes',type=Path,required=True)
    parser.add_argument('--electron',type=Path,required=True)
    parser.add_argument('--destination',type=Path,required=True)
    args=parser.parse_args();dest=args.destination.resolve()
    if dest.exists():raise SystemExit('Use a new desktop build destination.')
    shutil.copytree(args.electron,dest)
    (dest/'electron.exe').rename(dest/'Spandy Shows.exe')
    shutil.copytree(args.runtimes,dest/'runtime',copy_function=link_or_copy,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    print('Desktop shell and bundled compilers assembled.',flush=True)
    for directory,folders,files in os.walk(PROJECT):
        folders[:]=[name for name in folders if name not in EXCLUDE and not (Path(directory)/name).resolve().is_relative_to(dest)]
        for name in files:
            path=Path(directory)/name;relative=path.relative_to(PROJECT)
            if name in ('.env','runtime.local.json') or '.db' in name:continue
            target=dest/'app'/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
    shell=dest/'resources/app';shutil.copytree(PROJECT/'desktop',shell)
    shutil.copy2(PROJECT/'public/spandy-shows-icon.png',shell/'icon.png')
    icon=dest/'Spandy Shows.ico'
    shutil.copy2(PROJECT/'public/spandy-shows.ico',icon)
    brand(dest/'Spandy Shows.exe',icon)
    helpers=dest/'app/backend/java/classes';helpers.mkdir(exist_ok=True)
    source=dest/'app/backend/java'
    javac=dest/'runtime/java/bin/javac.exe'
    subprocess.run([str(javac),'-J-Xmx128m','--add-modules','jdk.jdi','-d',str(helpers),str(source/'SpandyRun.java'),str(source/'SpandyTracer.java')],check=True,creationflags=subprocess.CREATE_NO_WINDOW)
    (helpers/'helpers.json').write_text(json.dumps({'sources':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [source/'SpandyRun.java',source/'SpandyTracer.java']}}),encoding='utf-8')
    c_helpers=dest/'app/backend/c/classes';c_helpers.mkdir(parents=True,exist_ok=True)
    subprocess.run([str(dest/'runtime/c/bin/gcc.exe'),'-std=c17','-g3','-O0','-fno-omit-frame-pointer','-Wall','-Wextra','-c',str(dest/'app/backend/c_capture.c'),'-o',str(c_helpers/'capture.o')],check=True,creationflags=subprocess.CREATE_NO_WINDOW)
    (c_helpers/'helpers.json').write_text(json.dumps({'sources':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [PROJECT/'backend/c_capture.c',PROJECT/'backend/c_input.h']}}),encoding='utf-8')
    shutil.copy2(PROJECT/'desktop/README-DESKTOP.txt',dest/'READ ME FIRST.txt')
    tools=PROJECT/'desktop/tools.lock.json'
    shutil.copy2(tools,dest/'DESKTOP-TOOLS.lock.json')
    notices=args.runtimes.parent/'THIRD-PARTY-NOTICES.txt'
    shutil.copy2(notices,dest/'THIRD-PARTY-NOTICES.txt')
    with (dest/'THIRD-PARTY-NOTICES.txt').open('a',encoding='utf-8') as output:
        output.write('\nElectron: https://www.electronjs.org/ — LICENSE and LICENSES.chromium.html in this folder. The EXE icon and Windows version resources are branded for Spandy Shows; runtime code is unchanged. Official release archive SHA-256 is recorded in DESKTOP-TOOLS.lock.json.\n')
    print('Logo, metadata and precompiled Java helpers ready:',dest,flush=True)
if __name__=='__main__':main()
