"""Bounded observations inside GDB's Python interpreter (Python 3.9 compatible).

Read declared storage only. In particular, do not construct a GDB var object for
a VLA before its declaration, fetch an entire array, or dereference an arbitrary
pointer. Array rows have distinct typed identities even when their addresses
overlap the containing array. Pointer destinations are resolved after the
bounded storage walk, so aliases can target an individual element or field.
"""
import json
import math
import re
import gdb


class SpandyStorageObserver:
    def __init__(self):
        self.identities = {}
        self.globals = None
        self.signatures = []
        self.frame_ids = []
        self.next_frame = 0
        self.input_targets = {}
        self.input_reads = set()
        self.input_cursor = 0
        self.input_assignments = []

    def type_key(self, type_):
        return str(type_.strip_typedefs().unqualified())

    def address(self, value):
        try:
            return int(value.address) if value.address is not None else None
        except (gdb.error, ValueError, OverflowError):
            return None

    def identity(self, addr, type_):
        key = (addr, self.type_key(type_))
        if key not in self.identities:
            self.identities[key] = 'm' + str(len(self.identities) + 1)
        return self.identities[key]

    def unavailable(self, type_, note):
        return {'kind': 'unavailable', 'type': str(type_)[:256], 'note': note[:1024]}

    def register(self, value, destination=None, rendered=None, allocation='stack'):
        addr = self.address(value)
        if addr is not None:
            self.storage.setdefault(addr, []).append({
                'type': value.type, 'destination': destination,
                'value': rendered, 'allocation': allocation,
            })

    def observe(self, value, depth=0, destination=None, allocation='stack'):
        type_ = value.type
        name = str(type_)[:256]
        try:
            if value.is_optimized_out:
                return {'kind': 'optimized-out', 'type': name}
            base = type_.strip_typedefs()
            code = base.code
            if code == gdb.TYPE_CODE_UNION:
                return self.unavailable(type_, 'The active union member is unknown.')
            if code in (gdb.TYPE_CODE_ARRAY, gdb.TYPE_CODE_STRUCT):
                addr = self.address(value)
                if addr is None:
                    return self.unavailable(type_, 'Storage address is unavailable.')
                oid = self.identity(addr, type_)
                reference = {'kind': 'reference', 'type': name, 'ref': oid}
                self.register(value, (oid, []), allocation=allocation)
                if oid in self.objects:
                    return reference
                if len(self.objects) >= 80:
                    return self.unavailable(type_, 'The memory view contains at most 80 objects per step.')
                array = code == gdb.TYPE_CODE_ARRAY
                record = {'id': oid, 'type': name, 'kind': 'sequence' if array else 'instance',
                          'items': [], 'entries': [], 'fields': {}, 'address': hex(addr),
                          'allocation': allocation, 'truncated': False,
                          'note': 'Observed declared storage. Initialization is not generally verified.'}
                self.objects[oid] = record
                if depth >= 6:
                    record.update(truncated=True, note='Memory traversal stops after six nested objects.')
                    return reference
                if array:
                    low, high = base.range()
                    length = max(0, int(high) - int(low) + 1)
                    record['length'] = length
                    record['truncated'] = length > 40
                    for index in range(int(low), min(int(high) + 1, int(low) + 40)):
                        if self.cells >= 512:
                            record['truncated'] = True
                            break
                        self.cells += 1
                        child = value[index]
                        rendered = self.observe(child, depth + 1, (oid, [index - int(low)]), allocation)
                        record['items'].append(rendered)
                else:
                    for field in base.fields():
                        if not field.name or not re.match(r'^[A-Za-z_]\w*$', field.name):
                            continue
                        if len(record['fields']) >= 40 or self.cells >= 512:
                            record['truncated'] = True
                            break
                        self.cells += 1
                        try:
                            record['fields'][field.name] = self.observe(
                                value[field.name], depth + 1, (oid, [field.name]), allocation)
                        except gdb.error:
                            record['fields'][field.name] = self.unavailable(field.type, 'Field is unavailable.')
                if record['truncated']:
                    record['note'] += ' The view is limited to 40 items per collection and 512 cells per step; execution uses the complete array.'
                return reference
            if code == gdb.TYPE_CODE_PTR:
                addr = int(value)
                if addr == 0:
                    rendered = {'kind': 'null', 'type': name, 'value': None}
                else:
                    rendered = {'kind': 'primitive', 'type': name, 'value': hex(addr),
                                'note': 'This address is outside the displayed declared storage. It is not dereferenced by the visualizer.'}
                    self.pointers.append((rendered, addr, base.target()))
            elif code == gdb.TYPE_CODE_BOOL:
                rendered = {'kind': 'primitive', 'type': name, 'value': bool(value)}
            elif code in (gdb.TYPE_CODE_INT, gdb.TYPE_CODE_ENUM, gdb.TYPE_CODE_CHAR):
                number = int(value)
                scalar = chr(number & 255) if self.type_key(base) in ('char', 'signed char', 'unsigned char') else number
                rendered = {'kind': 'primitive', 'type': name, 'value': str(number) if isinstance(scalar, int) and abs(number) > 9007199254740991 else scalar}
            elif code == gdb.TYPE_CODE_FLT:
                number = float(value)
                rendered = {'kind': 'primitive', 'type': name, 'value': number if math.isfinite(number) else str(number)}
            else:
                rendered = {'kind': 'primitive', 'type': name, 'value': str(value)[:300]}
            self.register(value, destination, rendered, allocation)
            return rendered
        except (gdb.error, ValueError, TypeError, OverflowError) as error:
            return self.unavailable(type_, 'Debugger observation unavailable: ' + str(error))

    def symbols(self, frame):
        found = {}
        block = frame.block()
        while block is not None and not block.is_global and not block.is_static:
            for symbol in block:
                if (symbol.is_variable or symbol.is_argument) and re.match(r'^[A-Za-z_]\w*$', symbol.name or ''):
                    found.setdefault(symbol.name, symbol)
            block = block.superblock
        if self.globals is None:
            self.globals = {}
            while block is not None:
                for symbol in block:
                    if (symbol.is_variable and symbol.symtab is not None
                            and symbol.symtab.filename.replace('\\', '/').split('/')[-1] == 'main.c'
                            and re.match(r'^[A-Za-z_]\w*$', symbol.name or '')):
                        self.globals.setdefault(symbol.name, symbol)
                block = block.superblock
        return found

    def snapshot(self, request=None):
        self.objects = {}
        self.storage = {}
        self.pointers = []
        self.cells = 0
        frames = []
        selected = gdb.selected_frame()
        frame = gdb.newest_frame()
        level = 0
        contexts = []
        while frame is not None:
            try:
                sal = frame.find_sal()
                if sal.symtab is not None and sal.symtab.filename.replace('\\', '/').split('/')[-1] == 'main.c':
                    contexts.append({'frame': frame, 'level': level, 'name': frame.name() or '?', 'line': sal.line})
            except gdb.error:
                pass
            frame = frame.older()
            level += 1
        contexts = list(reversed(contexts))[-50:]
        signatures = [item['name'] for item in contexts]
        common = 0
        while common < min(len(signatures), len(self.signatures)) and signatures[common] == self.signatures[common]:
            common += 1
        event = 'call' if len(signatures) > len(self.signatures) else 'return' if len(signatures) < len(self.signatures) else 'line'
        self.frame_ids = self.frame_ids[:common]
        for _ in range(common, len(signatures)):
            self.next_frame += 1
            self.frame_ids.append('f' + str(self.next_frame))
        self.signatures = signatures
        lines = {self.frame_ids[index]: item['line'] for index, item in enumerate(contexts)}
        for frame_id, name, line in self.input_assignments:
            if frame_id in lines and lines[frame_id] != line:
                self.input_reads.add((frame_id, name))
        self.input_assignments = [item for item in self.input_assignments if item[0] in lines and lines[item[0]] == item[2]]
        try:
            with open('input-events.txt', encoding='utf-8') as stream:
                events = stream.read(65536).splitlines()
        except OSError:
            events = []
        for event_line in events[self.input_cursor:]:
            target = self.input_targets.get(int(event_line))
            if target:
                index = next((i for i in reversed(range(len(contexts))) if signatures[i] == target['function']), None)
                if index is not None:
                    frame_id = self.frame_ids[index]
                    if target.get('assignment') and lines[frame_id] == int(event_line):
                        self.input_assignments.extend((frame_id, name, int(event_line)) for name in target['names'])
                    else:
                        self.input_reads.update((frame_id, name) for name in target['names'])
        self.input_cursor = len(events)
        try:
            for index, context in enumerate(contexts):
                frame = context['frame']
                frame.select()
                line = context['line']
                hidden = {name for target in self.input_targets.values() if target['function'] == context['name']
                          for name in target['names'] if (self.frame_ids[index], name) not in self.input_reads}
                variables = {}
                for name, symbol in list(self.symbols(frame).items())[:100]:
                    type_ = str(symbol.type)[:256]
                    if name in hidden:
                        variables[name] = self.unavailable(type_, 'Awaiting program input. The pre-read debugger value is hidden because initialization is not verified.')
                    elif (not symbol.is_argument and symbol.addr_class != gdb.SYMBOL_LOC_STATIC
                          and symbol.line and line <= symbol.line):
                        # A VLA's debugger bounds/pointer are uninitialized before
                        # this instruction. Reading it can exhaust GDB memory.
                        variables[name] = {'kind': 'uninitialized', 'type': type_, 'note': 'The declaration on line %d has not executed yet.' % symbol.line}
                    else:
                        try:
                            variables[name] = self.observe(frame.read_var(symbol))
                        except gdb.error as error:
                            variables[name] = self.unavailable(type_, str(error))
                frames.append({'id': self.frame_ids[index], 'name': context['name'], 'line': line, 'locals': variables})
            globals_ = {}
            for name, symbol in list((self.globals or {}).items())[:100]:
                try:
                    globals_[name] = self.observe(symbol.value(), allocation='static')
                except gdb.error as error:
                    globals_[name] = self.unavailable(symbol.type, str(error))
            for rendered, addr, target_type in self.pointers:
                candidates = self.storage.get(addr, [])
                matching = [item for item in candidates if self.type_key(item['type']) == self.type_key(target_type)]
                if not matching and target_type.strip_typedefs().code == gdb.TYPE_CODE_VOID:
                    matching = candidates
                if not matching:
                    continue
                target = matching[0]
                destination = target['destination']
                if destination is None and target['value'] is not None:
                    oid = self.identity(addr, target['type'])
                    if oid not in self.objects:
                        if len(self.objects) >= 80:
                            continue
                        self.objects[oid] = {'id': oid, 'type': str(target['type'])[:256], 'kind': 'memory',
                            'items': [], 'entries': [], 'fields': {'value': target['value']}, 'address': hex(addr),
                            'allocation': target['allocation'], 'truncated': False, 'note': 'Observed symbol storage.'}
                    destination = (oid, ['value'])
                if destination is not None:
                    rendered.update(kind='reference', ref=destination[0], path=destination[1],
                                    note='Pointer matches observed declared storage at ' + hex(addr) + '.')
                    rendered.pop('value', None)
            return {'event': event, 'frames': frames, 'globals': globals_, 'objects': self.objects}
        finally:
            selected.select()


_spandy_storage = SpandyStorageObserver()


def spandy_observe(request):
    print('SPANDY_OBSERVATION=' + json.dumps(_spandy_storage.snapshot(request), ensure_ascii=True, allow_nan=False))
