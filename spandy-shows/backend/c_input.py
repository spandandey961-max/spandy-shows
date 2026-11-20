"""Conservative source mapping for direct scanf destinations, never their values.

Only a real successful libc read confirms an input value. Other C initialization
states remain unknown; this mapping hides pending scalar input observations.
"""
import re

def input_targets(source):
    masked = re.sub(r'/\*[\s\S]*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'',
                    lambda m: re.sub(r'[^\n]', ' ', m[0]), source)
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
