"""Local desktop cache for compiled C programs, independent of execution state."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from zipfile import BadZipFile, ZipFile


MAX_ENTRIES = 128
MAX_ARTIFACT_BYTES = 2 * 1024 * 1024


def toolchain_key(gcc, helper):
    compiler = Path(shutil.which(gcc) or gcc).resolve()
    # The desktop installs the compiler and linker together. Include other
    # executable components in case its toolchain is refreshed in place.
    root = compiler.parent.parent
    tools = [compiler, *compiler.parent.glob('ld*.exe'), *compiler.parent.glob('as.exe'),
             *root.glob('lib/gcc/*/*/cc1.exe'), *root.glob('lib/gcc/*/*/collect2.exe'),
             *root.glob('*/lib/*.a'), *root.glob('*/lib/*.o'),
             *root.glob('lib/gcc/*/*/*.a'), *root.glob('lib/gcc/*/*/*.o')]
    digest = hashlib.sha256()
    for path in sorted(set(tools)):
        stat = path.stat()
        digest.update(f'{path}:{stat.st_size}:{stat.st_mtime_ns}\n'.encode())
    digest.update(hashlib.sha256(helper.read_bytes()).digest())
    return digest.hexdigest()


def key(toolchain, flags, workspace, names, expanded, adapter):
    digest = hashlib.sha256(json.dumps([toolchain, flags, names]).encode())
    for file in (adapter / 'c_worker.py', adapter / 'c_input.py',
                 *(workspace / name for name in names),
                 *sorted((workspace / 'files').iterdir())):
        if file.is_file():
            digest.update(file.name.encode())
            with file.open('rb') as stream:
                digest.update(hashlib.file_digest(stream, 'sha256').digest())
    with expanded.open('rb') as stream:
        # Inline assembly can depend on assembler directives and files which
        # the C preprocessor cannot report.
        data = stream.read(4 * 1024 * 1024 + 1)
        if len(data) > 4 * 1024 * 1024 or re.search(rb'\.(?:incbin|include)\b', data):
            return None
        digest.update(hashlib.sha256(data).digest())
    return digest.hexdigest()


def restore(entry, target):
    try:
        with ZipFile(entry) as archive:
            if (archive.getinfo('program.exe').file_size > MAX_ARTIFACT_BYTES
                    or archive.getinfo('manifest.json').file_size > 65536):
                return None
            record = json.loads(archive.read('manifest.json'))
            data = archive.read('program.exe')
        if (not isinstance(record['warnings'], str) or not isinstance(record['version'], str)
                or hashlib.sha256(data).hexdigest() != record['sha256']):
            return None
        target.write_bytes(data)
        os.utime(entry, None)
        return record
    except (BadZipFile, OSError, ValueError, TypeError, KeyError):
        return None


def save(entry, target, warnings, version):
    if target.stat().st_size > MAX_ARTIFACT_BYTES:
        return
    cache = entry.parent
    cache.mkdir(parents=True, exist_ok=True)
    entries = sorted((path for path in cache.glob('*.zip') if len(path.stem) == 64),
                     key=lambda path: path.stat().st_mtime)
    for old in entries[:max(0, len(entries) - MAX_ENTRIES + 1)]:
        try:
            old.unlink(missing_ok=True)
        except OSError:
            pass
    with tempfile.TemporaryDirectory(prefix='.staging-', dir=cache) as name:
        staging = Path(name) / 'artifact.zip'
        data = target.read_bytes()
        with ZipFile(staging, 'w') as archive:
            archive.writestr('program.exe', data)
            archive.writestr('manifest.json', json.dumps({
                'sha256': hashlib.sha256(data).hexdigest(), 'warnings': warnings, 'version': version,
            }))
        os.replace(staging, entry)
