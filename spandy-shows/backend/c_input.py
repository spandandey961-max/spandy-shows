"""Conservative source mapping for direct scanf destinations, never their values.

Only a real successful libc read confirms an input value. Other C initialization
states remain unknown; this mapping hides pending scalar input observations.
"""
import re

READERS = {name: 'spandy_'+name for name in
           ('scanf','fscanf','vscanf','vfscanf','fgets','getchar','fgetc','fread','getline','read')}
READERS['getc'] = 'spandy_fgetc'
ALLOCATORS = {name: 'spandy_'+name for name in ('malloc','calloc','realloc','free','strdup','strndup')}

def mask_source(source):
    return re.sub(r'/\*[\s\S]*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'',
                  lambda match: re.sub(r'[^\n]', ' ', match[0]), source)

def instrument(source, *, capture_heap, windows, validate=False):
    """Wrap direct calls in the submitted file while keeping user line numbers."""
    masked = mask_source(source)
    directives = re.compile(r'(?m)^[ \t]*#(?:[^\n\\]|\\[^\n]|\\\n)*(?:\n|$)')
    code = directives.sub(lambda match: re.sub(r'[^\n]', ' ', match[0]), masked)
    wrappers = {**READERS, **(ALLOCATORS if capture_heap else {})}
    if windows:
        wrappers['getline'] = 'spandy_getline'
        wrappers.pop('strndup', None)
    names = '|'.join(wrappers)
    # Keep member calls and indirect calls on their original C dispatch path.
    # A local symbol with a libc name takes precedence over instrumentation.
    struct_depths=[]
    struct_starts={match.end()-1 for match in re.finditer(r'\b(?:struct|union)(?:\s+\w+)?\s*\{',code)}
    shadowed=set()
    depth=0
    for token in re.finditer(r'[{}]|\(\s*\*\s*(' + names + r')\b',code):
        if token[0]=='{':
            depth+=1
            if token.start() in struct_starts:struct_depths.append(depth)
        elif token[0]=='}':
            if struct_depths and struct_depths[-1]==depth:struct_depths.pop()
            depth-=1
        elif not struct_depths:
            shadowed.add(token[1])
    user_definitions = re.findall(r'\b(' + names + r')\s*\([^();{}]*\)\s*\{', code)
    shadowed.update(user_definitions)
    edits = []
    cursor, depth = 0, 0
    for call in re.finditer(r'\b(' + names + r')\s*\(', code):
        name = call[1]
        segment = code[cursor:call.start()]
        depth += segment.count('{') - segment.count('}')
        cursor = call.start()
        if name in shadowed or segment.rstrip().endswith(('.', '->')):
            continue
        # A prototype is outside function bodies. Leave declarations alone.
        if depth <= 0 or (validate and name!='getline'):
            continue
        callee = wrappers[name]
        edits.append((call.start(1),call.end(1),callee))
        if name in READERS:
            line = masked.count('\n',0,call.start())+1
            edits.append((call.end(),call.end(),str(line)+('' if name=='getchar' else ', ')))
    if not edits:
        return None
    # Inject declarations after the initial preprocessor directives, so user
    # feature-test macros run before libc headers. GCC checks the original too.
    position = re.search(r'\S',code).start()
    position = source.rfind('\n',0,position)+1
    line = source.count('\n',0,position)+1
    if validate:
        if not windows:return None
        edits = []
        # Use FILE from the program's includes so this does not hide a missing
        # stdio.h. MinGW does not ship POSIX getline.
        declaration = 'extern __INTPTR_TYPE__ getline(char **, __SIZE_TYPE__ *, FILE *);'
    else:
        declaration = '#include "spandy_input.h"'
    edits.append((position,position,f'{declaration}\n#line {line} "main.c"\n'))
    for start,end,value in sorted(edits,reverse=True):
        source = source[:start]+value+source[end:]
    return '#line 1 "main.c"\n'+source

def normalize_void_main(source):
    masked=mask_source(source)
    main=re.search(r'\bvoid(\s+main\s*\([^;{}]*\)\s*\{)',masked)
    if not main:
        return source
    depth,end=1,main.end()
    while end<len(masked) and depth:
        depth+=(masked[end]=='{')-(masked[end]=='}')
        end+=1
    start=main.end()
    replacements=list(re.finditer(r'\breturn(?=\s*;)',masked[start:end]))
    for result in reversed(replacements):
        position=start+result.end()
        source=source[:position]+' 0'+source[position:]
    return source[:main.start()]+'int '+source[main.start()+4:]

def input_targets(source):
    masked = mask_source(source)
    functions = []
    for match in re.finditer(r'\b([A-Za-z_]\w*)\s*\([^;{}]*\)\s*\{', masked):
        if match[1] in ('if', 'while', 'for', 'switch'): continue
        depth = 1; end = match.end()
        while end < len(masked) and depth:
            depth += (masked[end] == '{') - (masked[end] == '}'); end += 1
        functions.append((match.start(), end, match[1]))
    targets = {}
    for match in re.finditer(r'\b(scanf|fscanf|fgets|getchar|fgetc|getc)\s*\(', masked):
        depth = 1; end = match.end(); start = end; arguments = []
        while end < len(masked) and depth:
            char = masked[end]
            if char == ',' and depth == 1: arguments.append(masked[start:end]); start = end + 1
            depth += (char == '(') - (char == ')'); end += 1
        arguments.append(masked[start:end-1])
        stream_index=2 if match[1]=='fgets' else 0 if match[1] in ('fscanf','fgetc','getc') else None
        if stream_index is not None and (len(arguments)<=stream_index or arguments[stream_index].strip()!='stdin'):continue
        names = [m[1] for arg in arguments if (m := re.fullmatch(r'\s*&\s*([A-Za-z_]\w*)\s*', arg))]
        if match[1]=='fgets':
            names=[arguments[0].strip()] if re.fullmatch(r'\s*[A-Za-z_]\w*\s*',arguments[0]) else []
        elif match[1] in ('getchar','fgetc','getc'):
            assignment=re.search(r'\b([A-Za-z_]\w*)\s*=\s*$',masked[:match.start()])
            names=[assignment[1]] if assignment else []
        function = next((name for a, b, name in functions if a <= match.start() < b), None)
        if names and function:
            line = source.count('\n', 0, match.start()) + 1
            targets.setdefault(line, {'function': function, 'names': []})['names'].extend(names)
            if match[1] in ('getchar','fgetc','getc'):targets[line]['assignment']=True
    return targets
