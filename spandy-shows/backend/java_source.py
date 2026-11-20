"""Discover the source filename and entry class without changing Java code."""
import re

def java_source_info(source):
    # Mask literals/comments so quoted examples do not become declarations.
    code=re.sub(r'""".*?"""|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|//[^\n]*|/\*.*?\*/',
                lambda m:re.sub(r'[^\n]',' ',m[0]),source,flags=re.S)
    tokens=list(re.finditer(r'(?:[^\W\d]|\$)[\w$]*|[{};]',code))
    depth=0;modifiers=[];classes=[]
    for i,token in enumerate(tokens):
        word=token[0]
        if word=='{':depth+=1;modifiers=[]
        elif word=='}':depth-=1;modifiers=[]
        elif word==';':modifiers=[]
        elif depth==0:
            if word in ('class','record','enum','interface') and i+1<len(tokens) and not code[:token.start()].rstrip().endswith('.'):
                classes.append({'name':tokens[i+1][0],'public':'public' in modifiers,'start':token.start()})
            modifiers.append(word)
    public=next((c for c in classes if c['public']),None)
    main=next((c for i,c in enumerate(classes) if re.search(r'\bstatic\s+(?:(?:final|synchronized|strictfp)\s+)*void\s+main\s*\(',code[c['start']:classes[i+1]['start'] if i+1<len(classes) else len(code)])),None)
    chosen=public or main or (classes[0] if classes else {'name':'Main'})
    entry=main or chosen
    package=re.search(r'\bpackage\s+([\w$]+(?:\s*\.\s*[\w$]+)*)\s*;',code)
    prefix=re.sub(r'\s+','',package[1])+'.' if package else ''
    return {'sourceFile':chosen['name']+'.java','entryClass':prefix+entry['name']}
