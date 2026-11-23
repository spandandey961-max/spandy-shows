"""Package the complete app source and verify every archived file."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DIRECTORIES = ('src', 'backend', 'desktop', 'portable', 'public', 'scripts', 'tests', 'docs', 'migrations')
ROOT_FILES = (
    'README.md', 'LICENSE', 'VERIFICATION.md', 'PLAN.md', 'package.json',
    'pnpm-lock.yaml', 'pnpm-workspace.yaml', 'tsconfig.json', 'vite.config.ts',
    'index.html', 'requirements.txt', 'requirements.lock.txt', 'toolchains.lock.json',
    'Dockerfile', 'Dockerfile.worker', 'compose.yaml', 'netlify.toml',
    'launch.ps1', 'launch.sh', '.gitignore', '.dockerignore', '.env.example',
)
SKIP_DIRECTORIES = {'__pycache__', 'node_modules', '.pytest_cache', '.git', 'test-results'}

def package(destination):
    version = json.loads((ROOT / 'package.json').read_text(encoding='utf-8'))['version']
    desktop_version = json.loads((ROOT / 'desktop/package.json').read_text(encoding='utf-8'))['version']
    if version != desktop_version:
        raise ValueError('Frontend and desktop versions must agree before packaging.')
    paths = [ROOT / name for name in ROOT_FILES]
    for name in DIRECTORIES:
        paths.extend(path for path in (ROOT / name).rglob('*')
                     if path.is_file() and not SKIP_DIRECTORIES.intersection(path.relative_to(ROOT).parts)
                     and path.suffix not in {'.pyc', '.class', '.db', '.log', '.tmp'}
                     and path.name != '.env')
    manifest = {'name': 'Spandy Shows', 'version': version, 'publisher': 'Spandan', 'files': {}}
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination / f'Spandy-Shows-{version}-Full-Source.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for path in sorted(paths):
            relative = path.relative_to(ROOT).as_posix()
            data = path.read_bytes()
            manifest['files'][relative] = hashlib.sha256(data).hexdigest()
            bundle.writestr('spandy-shows/' + relative, data)
        bundle.writestr('spandy-shows/PACKAGE-MANIFEST.json', json.dumps(manifest, indent=2))
    with zipfile.ZipFile(archive) as bundle:
        if bundle.testzip() is not None:
            raise ValueError('Source archive failed its CRC check.')
        for relative, expected in manifest['files'].items():
            if hashlib.sha256(bundle.read('spandy-shows/' + relative)).hexdigest() != expected:
                raise ValueError('Source archive content mismatch for ' + relative)
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix('.sha256').write_text(f'{checksum}  {archive.name}\n', encoding='utf-8')
    print(json.dumps({'archive': str(archive), 'version': version, 'files': len(manifest['files']),
                      'bytes': archive.stat().st_size, 'sha256': checksum}, indent=2))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, default=ROOT.parent)
    package(parser.parse_args().destination.resolve())
