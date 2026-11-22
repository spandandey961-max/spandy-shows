"""Discover the source filename and entry class without changing Java code."""
import re

def java_source_info(source):
    # Mask literals/comments so quoted examples do not become declarations.
    code=re.sub(r'""".*?"""|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|//[^\n]*|/\*.*?\*/',
                lambda m:re.sub(r'[^\n]',' ',m[0]),source,flags=re.S)
    tokens=list(re.finditer(r'(?:[^\W\d]|\$)[\w$]*|[{};]',code))
    depth=0;modifiers=[];classes=[];owner=None;member_start=0
    main_signature=re.compile(r'\s*\(\s*(?:(?:final\s+)?(?:java\s*\.\s*lang\s*\.\s*)?String\s*(?:(?:\[\s*\]|\.\.\.)\s*[\w$]+|[\w$]+\s*\[\s*\]))?\s*\)\s*(?:throws\b[^{};]+)?\s*\{')
    for i,token in enumerate(tokens):
        word=token[0]
        if word=='{':
            depth+=1;modifiers=[]
            if depth==1:member_start=i+1
        elif word=='}':
            depth-=1;modifiers=[]
            if depth==0:owner=None
            elif depth==1:member_start=i+1
        elif word==';':
            modifiers=[]
            if depth==1:member_start=i+1
        elif depth==0:
            if word in ('class','record','enum','interface') and i+1<len(tokens) and not code[:token.start()].rstrip().endswith('.'):
                owner={'name':tokens[i+1][0],'public':'public' in modifiers}
                classes.append(owner)
            modifiers.append(word)
        elif depth==1 and owner is not None and word=='main' and tokens[i-1][0]=='void':
            if main_signature.match(code,token.end()) and all(t[0]!='private' for t in tokens[member_start:i]):
                owner['main']=True
    public=next((c for c in classes if c['public']),None)
    main=next((c for c in classes if c.get('main')),None)
    chosen=public or main or (classes[0] if classes else {'name':'Main'})
    entry=main or chosen
    package=re.search(r'\bpackage\s+([\w$]+(?:\s*\.\s*[\w$]+)*)\s*;',code)
    prefix=re.sub(r'\s+','',package[1])+'.' if package else ''
    return {'sourceFile':chosen['name']+'.java','entryClass':prefix+entry['name']}
