import asyncio,os
from backend.runner import execute_job
from backend.schema import Program

async def check(source,expected):
    result=await execute_job({'id':'supervisor-test','program':Program(language='python',source=source),'cancel':asyncio.Event()})
    assert result['terminationReason']==expected,result
    print(expected,'PASS',flush=True)

async def main():
    os.environ['SPANDY_EXECUTION_MODE']='trusted-local';os.environ['SPANDY_TRUST_LOCAL_CODE']='1'
    await check('__import__("time").sleep(30)','timeout')
    await check('values = [0] * 200000000','memory_limit')

if __name__=='__main__':asyncio.run(main())
