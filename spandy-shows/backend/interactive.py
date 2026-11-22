"""Bounded file IPC for live input. The user program remains in the same process."""
import ctypes, io, json, os, re, sys, threading, time, uuid
from pathlib import Path

def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=True, allow_nan=False), encoding='utf-8')
    # Windows readers can briefly deny replacement while polling a checkpoint.
    # Retry that sharing conflict; never expose a partially written JSON file.
    for attempt in range(50):
        try:os.replace(temporary,path);return
        except PermissionError:
            if attempt==49:raise
            time.sleep(.005)

def checkpoint(workspace, result):
    atomic_json(Path(workspace) / 'partial.json', result)

def remove_ipc(path):
    """A polling reader can briefly hold a Windows file against deletion."""
    for attempt in range(50):
        try:Path(path).unlink(missing_ok=True);return
        except PermissionError:
            if attempt==49:raise
            time.sleep(.005)

class TracePublisher:
    """Publish the first real state promptly without rewriting every prefix.

    A forced publication before input keeps that read's frontier exact. The
    lock also prevents the C input broker and debugger from sharing a temp file.
    """
    def __init__(self, workspace):
        self.workspace=Path(workspace);self.lock=threading.Lock()
        self.count=0;self.published=0.0
    def publish(self, result, force=False):
        with self.lock:
            count=len(result['steps']);now=time.monotonic()
            if not force and self.count and (count-self.count<max(64, self.count//4) or now-self.published<1.0):return
            checkpoint(self.workspace,result)
            atomic_json(self.workspace/'progress.json',{'steps':count})
            self.count=count;self.published=now

class InputClient:
    def __init__(self, workspace, before_wait=None):
        self.workspace = Path(workspace)
        self.sequence = 0
        self.before_wait = before_wait
        self.closed = threading.Event()
        self.eof = False

    def read(self, line, kind='text'):
        if self.eof: return ''
        self.sequence += 1
        if self.sequence>512:raise EOFError('The 512-response input limit was reached.')
        if self.before_wait: self.before_wait()
        request = self.workspace / 'input-request.json'
        response = self.workspace / f'input-response-{self.sequence}.json'
        atomic_json(request, {'id': self.sequence, 'line': max(1, line), 'type': kind})
        while not self.closed.wait(.025):
            if response.exists():
                record = json.loads(response.read_text(encoding='utf-8'))
                remove_ipc(request)
                remove_ipc(response)
                remove_ipc(self.workspace / f'input-text-{self.sequence}.txt')
                self.eof = record.get('eof', False)
                return '' if self.eof else record['text'] + '\n'
        raise EOFError('Input session closed.')

class PythonInput(io.RawIOBase):
    def __init__(self, client, source, initial=''):
        super().__init__()
        self.client, self.lines = client, source.splitlines()
        self.pending = initial.encode('utf-8')

    def readable(self): return True
    def readinto(self, buffer):
        if not len(buffer): return 0
        if not self.pending:
            frame = sys._getframe(1)
            while frame and frame.f_code.co_filename != 'main.py': frame = frame.f_back
            line = frame.f_lineno if frame else 1
            source_line = self.lines[line-1] if line <= len(self.lines) else ''
            # Hints only: CPython still performs the actual conversion and raises errors.
            kind = 'integer' if re.search(r'\bint\s*\(\s*input\s*\(', source_line) else 'number' if re.search(r'\bfloat\s*\(\s*input\s*\(', source_line) else 'text'
            self.pending = self.client.read(line, kind).encode('utf-8')
        count = min(len(buffer), len(self.pending))
        buffer[:count] = self.pending[:count]
        self.pending = self.pending[count:]
        return count

def initial_input(text):
    return text + '\n' if text and not text.endswith('\n') else text

class NativeInputBroker:
    """Feed a real blocking pipe while a guarded libc input call is waiting.

    A read that consumes buffered bytes finishes without requesting new input.
    A multi-conversion scanf stays inside the original libc call across responses.
    """
    def __init__(self, workspace, before_wait):
        self.workspace = Path(workspace)
        self.client = InputClient(workspace, before_wait)
        self.handle = None
        if os.name == 'nt':
            from ctypes import wintypes
            self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            self.kernel.CreateNamedPipeW.restype = wintypes.HANDLE
            self.kernel.CreateNamedPipeW.argtypes = [wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,wintypes.DWORD,wintypes.DWORD,wintypes.DWORD,wintypes.DWORD,wintypes.LPVOID]
            self.kernel.ConnectNamedPipe.argtypes = [wintypes.HANDLE,wintypes.LPVOID]
            self.kernel.WriteFile.argtypes = [wintypes.HANDLE,wintypes.LPCVOID,wintypes.DWORD,ctypes.POINTER(wintypes.DWORD),wintypes.LPVOID]
            self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            path = r'\\.\pipe\spandy-' + uuid.uuid4().hex
            self.handle = self.kernel.CreateNamedPipeW(path, 2, 0, 1, 8192, 8192, 0, None)
            if self.handle == ctypes.c_void_p(-1).value: raise OSError(ctypes.get_last_error(), 'Could not create stdin pipe.')
        else:
            path = str(self.workspace / 'stdin.pipe')
            os.mkfifo(path, 0o600)
            self.handle = os.open(path, os.O_RDWR | os.O_NONBLOCK)
        (self.workspace / 'stdin-path.txt').write_text(path, encoding='utf-8')
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def run(self):
        try:
            if os.name == 'nt':
                if not self.kernel.ConnectNamedPipe(self.handle, None) and ctypes.get_last_error() != 535: return
            initial = (self.workspace / 'stdin.txt').read_bytes()
            if initial:
                self.write(initial)
            observed, since = None, time.monotonic()
            while not self.client.closed.wait(.025):
                marker = self.workspace / 'input-call.txt'
                try: active = marker.read_text(encoding='utf-8').strip()
                except OSError: active = ''
                if active != observed:
                    observed, since = active, time.monotonic()
                if active and time.monotonic()-since > .15:
                    fields = active.split()
                    if len(fields) != 3: continue
                    value = self.client.read(int(fields[1]), fields[2]).encode('utf-8')
                    if not value:
                        self.close()
                        return
                    self.write(value)
                    # Give libc time to consume buffered bytes before another request.
                    since = time.monotonic()
        except (OSError, ValueError, EOFError): pass

    def write(self, value):
        if os.name == 'nt':
            count = ctypes.c_ulong()
            if not self.kernel.WriteFile(self.handle, value, len(value), ctypes.byref(count), None):
                raise OSError(ctypes.get_last_error(), 'Could not supply stdin.')
        else:
            pending = memoryview(value)
            while pending and not self.client.closed.is_set():
                try:
                    pending = pending[os.write(self.handle, pending):]
                except BlockingIOError:
                    self.client.closed.wait(.02)

    def close(self):
        self.client.closed.set()
        if self.handle is not None:
            if os.name == 'nt': self.kernel.CloseHandle(self.handle)
            else: os.close(self.handle)
            self.handle = None
