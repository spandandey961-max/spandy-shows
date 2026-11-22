"""Bounded observations inside GDB's Python interpreter (Python 3.9 compatible).

Read declared storage only. In particular, do not construct a GDB var object for
a VLA before its declaration, fetch an entire array, or dereference an arbitrary
pointer. Array rows have distinct typed identities even when their addresses
overlap the containing array. Pointer destinations are resolved after the
bounded storage walk, so aliases can target an individual element or field.
"""
import json
import bisect
import math
import re
import gdb

MAX_ITEMS = 128
MAX_CELLS = 1024


def array_bounds(array_type):
    low, high = array_type.range()
    low = 0 if low is None else int(low)
    # GDB can report an unspecified DWARF upper bound as zero even
    # while printing the type as T []. A genuine T [1] keeps its bound.
    if re.search(r'\[\s*\]', str(array_type)) or high is None or int(high) < low:
        return low, None
    return low, int(high)


class SpandyStorageObserver:
    def __init__(self):
        self.identities = {}
        self.globals = None
        self.next_frame = 0
        self.input_targets = {}
        self.input_cursor = 0
        self.thread_state={}
        self.heap_epoch = None
        self.heap = {}
        self.heap_starts = []
        self.source_file = 'main.c'

    def read_heap(self):
        try:
            epoch = int(gdb.parse_and_eval('spandy_heap_epoch'))
            if epoch == self.heap_epoch:return
            table = gdb.parse_and_eval('spandy_heap')
            count = min(512, int(gdb.parse_and_eval('spandy_heap_used')))
            heap = {}
            for index in range(max(0,count)):
                entry = table[index]
                start = int(entry['address'])
                heap[start] = (int(entry['size']), int(entry['generation']), bool(int(entry['live'])))
            self.heap = heap
            self.heap_starts = sorted(heap)
            self.heap_epoch = epoch
        except (gdb.error, ValueError, TypeError):
            self.heap, self.heap_starts = {}, []

    def allocation(self, address):
        index = bisect.bisect_right(self.heap_starts,address)-1
        if index < 0:return None
        start = self.heap_starts[index]
        size,generation,live = self.heap[start]
        return (start,size,generation,live) if address<=start+size else None

    def type_key(self, type_):
        return str(type_.strip_typedefs().unqualified())

    def address(self, value):
        try:
            return int(value.address) if value.address is not None else None
        except (gdb.error, ValueError, OverflowError):
            return None

    def identity(self, addr, type_):
        allocation = self.allocation(addr)
        generation = allocation[2] if allocation and allocation[3] and addr < allocation[0]+allocation[1] else None
        key = (addr, self.type_key(type_), generation)
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
            if code in (gdb.TYPE_CODE_ARRAY, gdb.TYPE_CODE_STRUCT, gdb.TYPE_CODE_UNION):
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
                          'note': 'Live heap storage. Initialization is not verified.' if allocation=='allocated'
                                  else 'Observed declared storage. Initialization is not generally verified.'}
                if code == gdb.TYPE_CODE_UNION:
                    record['note']='Members overlap. The active member is unknown.'
                self.objects[oid] = record
                if depth >= 6:
                    record.update(truncated=True, note='Memory traversal stops after six nested objects.')
                    return reference
                if array:
                    low, high = array_bounds(base)
                    if high is None:
                        storage=self.allocation(addr) if allocation=='allocated' else None
                        width=base.target().sizeof
                        length=max(0,(storage[0]+storage[1]-addr)//width) if storage and storage[3] and width else 0
                        high=low+length-1
                        if length:
                            bounded=base.target().array(low,high)
                            value=value.address.cast(bounded.pointer()).dereference()
                    length = max(0, int(high) - int(low) + 1)
                    record['length'] = length
                    record['truncated'] = length > MAX_ITEMS
                    for index in range(int(low), min(int(high) + 1, int(low) + MAX_ITEMS)):
                        if self.cells >= MAX_CELLS:
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
                        if len(record['fields']) >= 40 or self.cells >= MAX_CELLS:
                            record['truncated'] = True
                            break
                        self.cells += 1
                        try:
                            if code == gdb.TYPE_CODE_UNION and field.type.strip_typedefs().code not in (gdb.TYPE_CODE_BOOL,gdb.TYPE_CODE_INT,gdb.TYPE_CODE_ENUM,gdb.TYPE_CODE_CHAR,gdb.TYPE_CODE_FLT):
                                record['fields'][field.name] = self.unavailable(field.type,'The active union member is unknown.')
                                continue
                            record['fields'][field.name] = self.observe(
                                value[field.name], depth + 1, (oid, [field.name]), allocation)
                        except gdb.error:
                            record['fields'][field.name] = self.unavailable(field.type, 'Field is unavailable.')
                if record['truncated']:
                    record['note'] += f' The view is limited to {MAX_ITEMS} array elements and {MAX_CELLS} cells per step.'
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
                            and symbol.symtab.filename.replace('\\', '/').split('/')[-1] == self.source_file
                            and re.match(r'^[A-Za-z_]\w*$', symbol.name or '')):
                        self.globals.setdefault(symbol.name, symbol)
                block = block.superblock
        return found

    def snapshot(self, request=None):
        self.objects = {}
        self.storage = {}
        self.pointers = []
        self.cells = 0
        self.read_heap()
        frames = []
        selected = gdb.selected_frame()
        thread = gdb.selected_thread()
        thread_number=thread.global_num if thread else 1
        context=self.thread_state.setdefault(thread_number,{
            'signatures':[],'ids':[],'reads':set(),'assignments':[],'declarations':set()
        })
        frame = gdb.newest_frame()
        level = 0
        contexts = []
        while frame is not None and len(contexts)<50:
            try:
                sal = frame.find_sal()
                if sal.symtab is not None and sal.symtab.filename.replace('\\', '/').split('/')[-1] == self.source_file:
                    contexts.append({'frame': frame, 'level': level, 'name': frame.name() or '?', 'line': sal.line})
            except gdb.error:
                pass
            frame = frame.older()
            level += 1
        contexts = list(reversed(contexts))[-50:]
        signatures=[]
        for item in contexts:
            try:
                caller=item['frame'].older()
                base_pointer=(int(caller.read_register('sp')),caller.pc()) if caller is not None else None
            except (gdb.error,ValueError,OverflowError):base_pointer=None
            signatures.append((item['name'],base_pointer))
        previous=context['signatures']
        common = 0
        while common < min(len(signatures),len(previous)) and signatures[common]==previous[common]:
            common += 1
        event = 'call' if len(signatures)>len(previous) else 'return' if len(signatures)<len(previous) else 'line'
        ids=context['ids'][:common]
        known={key:frame_id for key,frame_id in zip(previous,context['ids']) if key[1] is not None}
        for key in signatures[common:]:
            frame_id=known.get(key)
            if frame_id is None or frame_id in ids:
                self.next_frame += 1
                frame_id='f'+str(self.next_frame)
            ids.append(frame_id)
        context.update(signatures=signatures,ids=ids)
        lines = {ids[index]: item['line'] for index, item in enumerate(contexts)}
        declarations=context['declarations']={item for item in context['declarations'] if item[0] in lines}
        reads=context['reads']={item for item in context['reads'] if item[0] in lines}
        for frame_id, name, line in context['assignments']:
            if frame_id in lines and lines[frame_id] != line:
                reads.add((frame_id, name))
        assignments=context['assignments']=[item for item in context['assignments'] if item[0] in lines and lines[item[0]]==item[2]]
        try:
            with open('input-events.txt', encoding='utf-8') as stream:
                events = stream.read(65536).splitlines()
        except OSError:
            events = []
        for event_line in events[self.input_cursor:]:
            target = self.input_targets.get(int(event_line))
            if target:
                index = next((i for i in reversed(range(len(contexts))) if signatures[i][0] == target['function']), None)
                if index is not None:
                    frame_id = ids[index]
                    if target.get('assignment') and lines[frame_id] == int(event_line):
                        assignments.extend((frame_id, name, int(event_line)) for name in target['names'])
                    else:
                        reads.update((frame_id, name) for name in target['names'])
        self.input_cursor = len(events)
        try:
            for index, context in enumerate(contexts):
                frame = context['frame']
                frame.select()
                line = context['line']
                hidden = {name for target in self.input_targets.values() if target['function'] == context['name']
                          for name in target['names'] if (ids[index],name) not in reads}
                variables = {}
                for name, symbol in list(self.symbols(frame).items())[:100]:
                    type_ = str(symbol.type)[:256]
                    key=(ids[index],name,symbol.line)
                    if symbol.line and line>symbol.line:
                        declarations.add(key)
                    if name in hidden:
                        variables[name] = self.unavailable(type_, 'Awaiting program input. The pre-read debugger value is hidden because initialization is not verified.')
                    elif (not symbol.is_argument and symbol.addr_class != gdb.SYMBOL_LOC_STATIC
                          and symbol.line and line <= symbol.line and key not in declarations):
                        # A VLA's debugger bounds/pointer are uninitialized before
                        # this instruction. Reading it can exhaust GDB memory.
                        variables[name] = {'kind': 'uninitialized', 'type': type_, 'note': 'The declaration on line %d has not executed yet.' % symbol.line}
                    else:
                        try:
                            variables[name] = self.observe(frame.read_var(symbol))
                        except gdb.error as error:
                            variables[name] = self.unavailable(type_, str(error))
                frames.append({'id': ids[index], 'name': context['name'], 'line': line, 'locals': variables})
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
                    self.link_heap(rendered, addr, target_type)
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
            return {'event': event,'thread':'Main thread' if thread_number==1 else 'Thread '+str(thread_number),
                    'frames': frames, 'globals': globals_, 'objects': self.objects}
        finally:
            selected.select()

    def link_heap(self, rendered, address, target):
        allocation = self.allocation(address)
        if not allocation:return
        base, size, generation, live = allocation
        if not live:
            rendered['note']='This address matches a freed allocation. Its contents are unavailable.'
            return
        if address==base+size:
            rendered['note']='This address is one past an observed allocation.'
            return
        try:
            element=target.strip_typedefs()
            if element.code in (gdb.TYPE_CODE_VOID, gdb.TYPE_CODE_FUNC):
                return
            width=element.sizeof
            offset=address-base
            if not width or offset+width>size or offset%width:
                return
            length=size//width
            if element.code==gdb.TYPE_CODE_STRUCT:
                fields=element.fields()
                if fields and fields[-1].type.strip_typedefs().code==gdb.TYPE_CODE_ARRAY:
                    _,high=array_bounds(fields[-1].type.strip_typedefs())
                    if high is None:
                        if offset:return
                        length=1
            # Keep the type provided by the pointer. Never read across the
            # live allocation and never call functions in the debuggee.
            storage_type=target.array(length-1) if length>1 else target
            view=gdb.Value(base).cast(storage_type.pointer()).dereference()
            result=self.observe(view,allocation='allocated')
            if result['kind']=='reference':
                oid=result['ref']
                path=[offset//width] if length>1 else []
            else:
                if len(self.objects)>=80:return
                oid=self.identity(base,target)
                self.objects[oid]={
                    'id':oid,'type':str(target)[:256],'kind':'memory','items':[],'entries':[],
                    'fields':{'value':result},'address':hex(base),'allocation':'allocated','truncated':False,
                    'note':'Live heap storage. Initialization is not verified.'
                }
                path=['value']
            if path and isinstance(path[0],int) and path[0]>=len(self.objects[oid]['items']):
                rendered['note']=f'The pointer targets heap element {path[0]}, outside the displayed slice.'
                return
            rendered.update(kind='reference', ref=oid, path=path,
                            note=f'Address in live allocation {generation} at {hex(base)}.')
            rendered.pop('value',None)
        except (gdb.error,ValueError,TypeError,OverflowError):
            return


_spandy_storage = SpandyStorageObserver()


def spandy_observe(request):
    print('SPANDY_OBSERVATION=' + json.dumps(_spandy_storage.snapshot(request), ensure_ascii=True, allow_nan=False))
