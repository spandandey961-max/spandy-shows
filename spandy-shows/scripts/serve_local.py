"""Logged, standalone entry point for the private Windows background server."""
import argparse
import os
from pathlib import Path
import sys

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--trusted-local',action='store_true')
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    os.chdir(root)
    sys.path.insert(0,str(root))
    (root/'.runtime').mkdir(exist_ok=True)
    log=(root/'.runtime'/'server.log').open('a',encoding='utf-8',buffering=1)
    sys.stdout=sys.stderr=log
    os.environ['SPANDY_EXECUTION_MODE']='trusted-local' if args.trusted_local else 'docker'
    if args.trusted_local:os.environ['SPANDY_TRUST_LOCAL_CODE']='1'
    else:os.environ.pop('SPANDY_TRUST_LOCAL_CODE',None)
    os.environ['SPANDY_ORIGINS']='http://127.0.0.1:8000,http://localhost:8000'
    import uvicorn
    uvicorn.run('backend.app:app',host='127.0.0.1',port=8000,access_log=False)

if __name__=='__main__':
    main()
