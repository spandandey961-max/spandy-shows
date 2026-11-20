import runpy,sys
from pathlib import Path
language=sys.argv.pop(1)
if language not in ('python','java','c'):raise SystemExit('Unsupported language')
runpy.run_path(str(Path(__file__).parent/f'{language}_worker.py'),run_name='__main__')
