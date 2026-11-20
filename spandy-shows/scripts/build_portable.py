"""Assemble the already-tested local engines into a relocatable Windows ZIP."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

PROJECT = Path(__file__).resolve().parents[1]
EXCLUDE = {'.venv','node_modules','.runtime','__pycache__','.pytest_cache','toolchains','.git','test-results','.netlify','desktop-tools','release','build'}

def copied(source,destination,*,python=False):
    def ignore(path,names):
        skipped = {name for name in names if name=='__pycache__' or name.endswith('.pyc')}
        if python and Path(path)==source: skipped.add('Scripts')
        if python and Path(path)==source/'Lib': skipped.add('site-packages')
        return skipped
    shutil.copytree(source,destination,ignore=ignore,dirs_exist_ok=True)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--destination',type=Path,required=True)
    args = parser.parse_args()
    bundle = args.destination.resolve()/'Spandy Shows Portable'
    if bundle.exists(): raise SystemExit('Destination already exists; use a fresh destination.')
    bundle.mkdir(parents=True)
    app = bundle/'app'
    app.mkdir()
    files = 0
    for directory,folders,names in os.walk(PROJECT):
        folders[:]=[name for name in folders if name not in EXCLUDE and not (Path(directory)/name).resolve().is_relative_to(bundle)]
        for name in names:
            path=Path(directory)/name;relative=path.relative_to(PROJECT)
            if name in ('runtime.local.json','.env') or '.db' in name:continue
            destination = app/relative
            destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(path,destination)
            files += 1
    print(f'Copied {files} website/source files.',flush=True)
    runtime = bundle/'runtime'
    runtime.mkdir()
    base = Path(sys.base_prefix)
    copied(base,runtime/'python',python=True)
    copied(Path(sys.prefix)/'Lib/site-packages',runtime/'python/Lib/site-packages')
    # Pin imports to the included runtime instead of registry/PATH/user packages.
    (runtime/'python/python312._pth').write_text('.\nLib\nDLLs\nLib/site-packages\nimport site\n',encoding='ascii')
    print('Copied portable Python and backend dependencies.',flush=True)
    config = json.loads((PROJECT/'runtime.local.json').read_text(encoding='utf-8'))
    jdk = Path(config['java']).parent.parent
    mingw = Path(config['gcc']).parent.parent
    copied(jdk,runtime/'java')
    print('Copied the complete Java runtime/compiler.',flush=True)
    copied(mingw,runtime/'c')
    print('Copied the complete C compiler/debugger.',flush=True)
    # WinLibs' optional-manifest spec splits a discovered filename at spaces.
    # The manifest is included in this complete runtime, so use GCC's ordinary
    # filename lookup (%s), which preserves the argument during relocation.
    gcc = runtime/'c/bin/gcc.exe'
    def compiler_output(option):
        return subprocess.run([str(gcc),option],check=True,capture_output=True,text=True,
                              creationflags=subprocess.CREATE_NO_WINDOW).stdout.strip()
    specs = compiler_output('-dumpspecs')
    endfile = specs.split('*endfile:\n',1)[1].split('\n\n',1)[0]
    if '%:if-exists(default-manifest.o%s)' in endfile:
        assert any((runtime/'c').rglob('default-manifest.o')),'The default manifest must be included.'
        endfile = endfile.replace('%:if-exists(default-manifest.o%s)','default-manifest.o%s')
        spec_path = runtime/'c/lib/gcc'/compiler_output('-dumpmachine')/compiler_output('-dumpfullversion')/'specs'
        spec_path.write_text('*endfile:\n'+endfile+'\n',encoding='utf-8')
        print('Corrected the portable GCC manifest spec for folder names with spaces.',flush=True)
    shutil.copy2(PROJECT/'portable/launcher.py',bundle/'launcher.py')
    shutil.copy2(PROJECT/'portable/README-PORTABLE.txt',bundle/'READ ME FIRST.txt')
    for stop,name in [(False,'Start Spandy Shows.exe'),(True,'Stop Spandy Shows.exe')]:
        command = [config['gcc'],'-municode','-mwindows','-Os','-s','-static-libgcc',str(PROJECT/'portable/native_launcher.c'),'-o',str(bundle/name),'-luser32']
        if stop: command.insert(1,'-DSPANDY_STOP')
        subprocess.run(command,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
    notices = ('Spandy Shows includes unmodified third-party runtimes and Python dependencies.\n'
               'Python '+sys.version.split()[0]+': https://www.python.org/ — license: runtime/python/LICENSE.txt\n'
               'Python dependency versions and upstream license metadata: app/requirements.lock.txt and runtime/python/Lib/site-packages/*.dist-info/\n'
               'Eclipse Temurin JDK: https://adoptium.net/temurin/releases/ — licenses: runtime/java/legal/ and runtime/java/NOTICE\n'
               'WinLibs GCC/MinGW/GDB: https://winlibs.com/ and https://github.com/brechtsanders/winlibs_mingw\n'
               'Corresponding upstream source/build information and component licenses are supplied by the WinLibs project. All original toolchain files and available license notices are retained in runtime/c/.\n'
               'Spandy Shows adds an endfile specs override to GCC to preserve manifest filenames when paths contain spaces. The configuration change is documented in app/scripts/build_portable.py; compiler binaries are unchanged.\n'
               'Locked vendor versions and archive checksums: app/toolchains.lock.json\n')
    (bundle/'THIRD-PARTY-NOTICES.txt').write_text(notices,encoding='utf-8')
    print('Built windowless Start and Stop launchers.',flush=True)
    print(bundle,flush=True)

if __name__=='__main__': main()
