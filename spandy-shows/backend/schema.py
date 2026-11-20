"""Spandy Shows schema v1: independent, bounded observations from real engines."""
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator
from .limits import MAX_STEPS, MAX_SOURCE_BYTES, MAX_SOURCE_LINES

class Record(BaseModel):
    model_config = ConfigDict(extra='forbid')

class Value(Record):
    kind: Literal['primitive','reference','null','uninitialized','unavailable','optimized-out']
    type: str = Field(max_length=256)
    value: str | int | float | bool | None = None
    ref: str | None = Field(default=None, max_length=256)
    path: list[int | str] = Field(default_factory=list, max_length=6)
    truncated: bool = False
    note: str | None = Field(default=None, max_length=1024)

class ObjectRecord(Record):
    id: str = Field(max_length=256)
    type: str = Field(max_length=256)
    kind: Literal['sequence','mapping','instance','set','memory']
    items: list[Value] = Field(default_factory=list, max_length=40)
    entries: list[tuple[Value, Value]] = Field(default_factory=list, max_length=40)
    fields: dict[str, Value] = Field(default_factory=dict, max_length=40)
    length: int | None = None
    address: str | None = Field(default=None, max_length=128)
    allocation: Literal['unknown','allocated','freed','stack','static'] | None = None
    truncated: bool = False
    note: str | None = Field(default=None, max_length=1024)

class Location(Record):
    file: str = Field(max_length=256)
    line: int = Field(ge=1, le=MAX_SOURCE_LINES)
    phase: Literal['before','after']

class Frame(Record):
    id: str = Field(max_length=256)
    name: str = Field(max_length=256)
    line: int = Field(ge=1, le=MAX_SOURCE_LINES)
    locals: dict[str, Value] = Field(default_factory=dict, max_length=100)

class Diagnostic(Record):
    severity: Literal['error','warning','info'] = 'error'
    message: str = Field(max_length=8192)
    line: int | None = Field(default=None, ge=1, le=MAX_SOURCE_LINES)
    column: int | None = Field(default=None, ge=1)

class ExceptionRecord(Record):
    type: str = Field(max_length=256)
    message: str = Field(max_length=4096)

class Step(Record):
    index: int = Field(ge=0, lt=MAX_STEPS)
    event: Literal['line','call','return','exception','completed','terminated']
    location: Location | None = None
    frames: list[Frame] = Field(default_factory=list, max_length=50)
    globals: dict[str, Value] = Field(default_factory=dict, max_length=100)
    objects: dict[str, ObjectRecord] = Field(default_factory=dict, max_length=80)
    stdout: str = Field(default='', max_length=8192)
    stderr: str = Field(default='', max_length=8192)
    exception: ExceptionRecord | None = None
    returnValue: Value | None = None
    note: str | None = Field(default=None, max_length=1024)

class Trace(Record):
    schemaVersion: Literal[1] = 1
    language: Literal['python','java','c']
    runtimeVersion: str = Field(max_length=256)
    sourceFile: str = Field(max_length=256)
    sourceHash: str = Field(pattern=r'^[a-f0-9]{64}$')
    status: Literal['completed','failed','truncated','cancelled']
    terminationReason: str = Field(max_length=256)
    steps: list[Step] = Field(max_length=MAX_STEPS)
    diagnostics: list[Diagnostic] = Field(default_factory=list, max_length=40)
    limitations: list[str] = Field(default_factory=list, max_length=20)

class Program(Record):
    language: Literal['python','java','c']
    source: str = Field(min_length=1, max_length=MAX_SOURCE_BYTES)
    stdin: str = Field(default='', max_length=4096)
    title: str = Field(default='Untitled program', min_length=1, max_length=80)
    selectedStep: int = Field(default=0, ge=0, lt=MAX_STEPS)

    @field_validator('source')
    @classmethod
    def source_bounds(cls,value):
        if len(value.encode('utf-8'))>MAX_SOURCE_BYTES or len(value.splitlines())>MAX_SOURCE_LINES:
            raise ValueError(f'Source is limited to {MAX_SOURCE_LINES} lines and {MAX_SOURCE_BYTES//1024} KiB.')
        return value

class JobRequest(Program):
    execution: Literal['visualize','run'] = 'visualize'
    interactive: bool = False

class InputRequest(Record):
    id: int = Field(ge=1, le=128)
    line: int = Field(ge=1, le=MAX_SOURCE_LINES)
    type: Literal['integer','number','character','text']

class InputResponse(Record):
    id: int = Field(ge=1, le=128)
    text: str = Field(max_length=4096)

