"""Run every bundled example against the connected real engines."""
import asyncio,json,os
from pathlib import Path
from backend.runner import execute_job,availability
from backend.schema import Program

async def main():
    os.environ['SPANDY_EXECUTION_MODE']='trusted-local'
    os.environ['SPANDY_TRUST_LOCAL_CODE']='1'
    examples=json.loads((Path(__file__).parent/'examples.json').read_text(encoding='utf-8'))
    results=[]
    for language,items in examples.items():
        for ex in items:
            if not availability()[language]:
                results.append({'language':language,'id':ex['id'],'status':'unverified'});continue
            trace=await execute_job({'id':'example-check','program':Program(language=language,source=ex['source'],stdin=ex.get('stdin','')),'cancel':asyncio.Event()})
            expected='failed' if ex['id']=='error' else 'completed'
            passed=trace['status']==expected
            print(language,ex['id'],trace['status'],trace['terminationReason'],'PASS' if passed else trace['diagnostics'],flush=True)
            results.append({'language':language,'id':ex['id'],'passed':passed,'status':trace['status'],'steps':len(trace['steps']),
                'output':trace['steps'][-1]['stdout'] if trace['steps'] else '', 'diagnostics':trace['diagnostics'] if not passed else []})
    (Path(__file__).parent/'example-results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    assert all(r.get('passed') for r in results),results

if __name__=='__main__':asyncio.run(main())
