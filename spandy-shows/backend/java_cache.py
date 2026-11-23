"""Disposable local compiler artifacts. Program input and results are never cached."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

MAX_CACHE_BYTES = 256 * 1024 * 1024

def fingerprint(command):
    executable = Path(shutil.which(command) or command).resolve()
    digest = hashlib.sha256(str(executable).encode())
    for path in (executable, executable.parent.parent / 'release', executable.parent.parent / 'lib' / 'modules'):
        if path.is_file():
            info = path.stat()
            digest.update(f'{info.st_size}:{info.st_mtime_ns}'.encode())
    return digest.hexdigest()

def read_record(directory, name):
    try:
        return json.loads((directory / name).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None

def write_record(directory, name, record):
    directory.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=directory, suffix='.tmp')
    try:
        with os.fdopen(handle, 'w', encoding='utf-8') as stream:
            json.dump(record, stream)
        os.replace(temporary, directory / name)
    finally:
        Path(temporary).unlink(missing_ok=True)

def compilation_key(toolchain, release, sources, libraries):
    digest = hashlib.sha256(f'v1:debug:utf8:jdi:{toolchain}:{release}'.encode())
    for path in [*sources, *libraries]:
        digest.update(path.name.encode())
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()

def restore(directory, key, workspace):
    entry = directory / key
    record = read_record(entry, 'manifest.json')
    if not record:
        return None
    try:
        for name, expected in record['classes'].items():
            path = Path(name)
            if path.is_absolute() or '..' in path.parts or path.suffix != '.class':
                return None
            if hashlib.sha256((entry / path).read_bytes()).hexdigest() != expected:
                return None
        for name in record['classes']:
            target = workspace / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(entry / name, target)
        os.utime(entry, None)
        return record
    except (OSError, KeyError, TypeError):
        return None

def save(directory, key, workspace, preview, warnings):
    directory.mkdir(parents=True, exist_ok=True)
    incoming=sum(path.stat().st_size for path in workspace.rglob('*.class'))
    if incoming>MAX_CACHE_BYTES:return
    # Evict old entries before staging a new one. Concurrent readers can always compile again.
    entries = sorted((path for path in directory.iterdir() if path.is_dir() and not path.name.startswith('.')), key=lambda path: path.stat().st_mtime)
    sizes = [(path, sum(file.stat().st_size for file in path.rglob('*') if file.is_file())) for path in entries]
    total = sum(size for _, size in sizes)
    for path, size in sizes:
        if total+incoming <= MAX_CACHE_BYTES:
            break
        shutil.rmtree(path, ignore_errors=True)
        total -= size
    with tempfile.TemporaryDirectory(prefix='.staging-', dir=directory) as temporary:
        staging = Path(temporary)
        classes = {}
        for file in workspace.rglob('*.class'):
            relative = file.relative_to(workspace)
            if relative.parts[0] == 'files':
                continue
            data = file.read_bytes()
            classes[relative.as_posix()] = hashlib.sha256(data).hexdigest()
            target = staging / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        if not classes:
            return
        write_record(staging, 'manifest.json', dict(classes=classes, preview=preview, warnings=warnings))
        try:
            staging.rename(directory / key)
        except OSError:
            pass  # Another worker may have published this exact compilation already.
