"""Real compiler/debugger regressions for pointer aliases and nested C storage."""
import asyncio,os
from pathlib import Path
import pytest
from backend.runner import execute_job,availability
from backend.schema import JobRequest,Trace


def run(source,stdin='',execution='visualize'):
    os.environ['SPANDY_EXECUTION_MODE']='trusted-local'
    os.environ['SPANDY_TRUST_LOCAL_CODE']='1'
    trace=asyncio.run(execute_job({'id':'array-regression','program':JobRequest(language='c',source=source,stdin=stdin,execution=execution),'cancel':asyncio.Event()}))
    Trace.model_validate(trace)
    assert trace['status']=='completed',trace['diagnostics']
    return trace


def last_state(trace):
    return next(step for step in reversed(trace['steps']) if step['frames'])


def test_pointer_aliases_target_the_actual_array_element():
    source='''#include <stdio.h>
int main(void) {
 int a[] = {3, 7};
 int *p = a, *q = a + 1;
 p = q;
 *p += *q;
 printf("%d %d\\n", a[0], a[1]);
 return 0;
}'''
    trace=run(source)
    assert trace['steps'][-1]['stdout']=='3 14\n'
    state=last_state(trace);values=state['frames'][-1]['locals'];oid=values['a']['ref']
    assert values['p']['ref']==values['q']['ref']==oid
    assert values['p']['path']==values['q']['path']==[1]
    assert [value['value'] for value in state['objects'][oid]['items']]==[3,14]
    before=next(step for step in trace['steps'] if step['location'] and step['location']['line']==5)
    assert before['frames'][-1]['locals']['p']['path']==[0]
    assert before['objects'][oid]['items'][1]['value']==7


def test_three_dimensions_rows_and_pointer_to_row_preserve_storage():
    source='''#include <stdio.h>
int main(void) {
 int a[2][2][3]={{{1,2,3},{4,5,6}},{{7,8,9},{10,11,12}}};
 int *p=&a[1][0][2];
 int (*row)[3]=a[1];
 *p=99;
 row[1][1]=42;
 printf("%d %d\\n",a[1][0][2],a[1][1][1]);
 return 0;
}'''
    trace=run(source);assert trace['steps'][-1]['stdout']=='99 42\n'
    state=last_state(trace);values=state['frames'][-1]['locals'];objects=state['objects']
    cube=objects[values['a']['ref']];plane0=objects[cube['items'][0]['ref']]
    row0=objects[plane0['items'][0]['ref']]
    assert len({cube['id'],plane0['id'],row0['id']})==3
    assert cube['address']==plane0['address']==row0['address']
    plane1=objects[cube['items'][1]['ref']];target=objects[plane1['items'][0]['ref']]
    assert values['p']['ref']==values['row']['ref']==target['id']
    assert values['p']['path']==[2] and values['row']['path']==[]
    assert [item['value'] for item in target['items']]==[7,8,99]
    assert objects[plane1['items'][1]['ref']]['items'][1]['value']==42


@pytest.mark.parametrize('iteration',range(2))
def test_input_sized_2d_array_never_inspected_before_its_declaration(iteration):
    source='''#include <stdio.h>
int main(void) {
 int rows, cols, sum=0;
 scanf("%d %d",&rows,&cols);
 int a[rows][cols];
 for(int i=0;i<rows;i++)
  for(int j=0;j<cols;j++) scanf("%d",&a[i][j]);
 int *p=&a[1][2];
 for(int i=0;i<rows;i++)
  for(int j=0;j<cols;j++) sum+=a[i][j];
 printf("%d %d\\n",sum,*p);
 return 0;
}'''
    trace=run(source,'2 3\n1 2 3 4 5 6\n')
    assert trace['steps'][-1]['stdout']=='21 6\n'
    first=trace['steps'][0]['frames'][-1]['locals']['a']
    assert first['kind']=='uninitialized'
    state=last_state(trace);values=state['frames'][-1]['locals'];objects=state['objects']
    matrix=objects[values['a']['ref']]
    assert [[item['value'] for item in objects[row['ref']]['items']] for row in matrix['items']]==[[1,2,3],[4,5,6]]
    assert values['p']['ref']==matrix['items'][1]['ref'] and values['p']['path']==[2]


def test_bounded_inspection_does_not_limit_the_programs_actual_array():
    trace=run('''#include <stdio.h>
static int data[1000000];
int main(void) {
 data[999999]=17;
 printf("%d\\n",data[999999]);
 return 0;
}''')
    assert trace['steps'][-1]['stdout']=='17\n'
    state=last_state(trace);array=state['objects'][state['globals']['data']['ref']]
    assert array['length']==1000000 and len(array['items'])==40 and array['truncated']


def test_pointer_to_struct_field_and_pointer_to_pointer():
    trace=run('''#include <stdio.h>
struct Pair { int x,y; };
int main(void) {
 struct Pair pair={1,2};
 int *p=&pair.y;
 int **alias=&p;
 **alias=11;
 printf("%d\\n",pair.y);
 return 0;
}''')
    state=last_state(trace);values=state['frames'][-1]['locals'];objects=state['objects']
    assert values['p']['ref']==values['pair']['ref'] and values['p']['path']==['y']
    pointer=objects[values['alias']['ref']]['fields']['value']
    assert pointer['ref']==values['p']['ref'] and pointer['path']==['y']
    assert trace['steps'][-1]['stdout']=='11\n'


def test_large_source_keeps_real_line_locations_and_full_trace():
    source='#include <stdio.h>\nint main(void) {\n int n=0;\n'+'\n'.join(' n++;' for _ in range(2500))+'\n printf("%d",n);\n return 0;\n}'
    trace=run(source)
    assert trace['steps'][-1]['stdout']=='2500'
    assert len(trace['steps'])>2500
    assert max(step['location']['line'] for step in trace['steps'] if step['location'])>2500


def test_missing_main_reports_syntax_problem_without_rewriting_source():
    os.environ['SPANDY_EXECUTION_MODE']='trusted-local';os.environ['SPANDY_TRUST_LOCAL_CODE']='1'
    source='#include <stdio.h>\n\n{\n int a[]={3,7};\n printf("%d",a[0]);\n}'
    trace=asyncio.run(execute_job({'id':'missing-main','program':JobRequest(language='c',source=source),'cancel':asyncio.Event()}))
    assert trace['terminationReason']=='compilation_error'
    assert trace['diagnostics'][0]['line']==3 and 'int main(void)' in trace['diagnostics'][0]['message']
