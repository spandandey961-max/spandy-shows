"""Real input reads with standard EOF and partial-conversion results."""
import pytest
from backend.runner import availability
from backend.c_input import input_targets
from tests.test_native import run

PALINDROME = '''#include <stdio.h>

int main() {
    int n , original, reversed = 0, remainder;
    printf("Enter an integer: ");
    scanf("%d", &n);
    original = n;
    while (n != 0) {
        remainder = n % 10;
        reversed = reversed * 10 + remainder;
        n /= 10;
    }
    if (original == reversed)
        printf("Palindrome");
    else
        printf("Not a palindrome");
    return 0;
}'''

@pytest.mark.parametrize('response,expected',[('121','Palindrome'),('123','Not a palindrome'),('0','Palindrome'),('-121','Palindrome')])
def test_user_palindrome(response,expected):
    if not availability()['c']:pytest.skip('C engine missing.')
    trace=run('c',PALINDROME,response)
    assert trace['status']=='completed',trace['diagnostics']
    assert trace['steps'][-1]['stdout']=='Enter an integer: '+expected
    states=[s for s in trace['steps'] if s['frames']]
    # No arbitrary stack bytes are presented as n before the real scanf read.
    pending=[s for s in states if s['location']['line']<=6]
    assert pending and all(s['frames'][-1]['locals']['n']['kind']=='unavailable' for s in pending)
    received=next(s for s in states if s['location']['line']==7)
    assert received['frames'][-1]['locals']['n']['value']==int(response)
    assert any(s['frames'][-1]['locals'].get('original',{}).get('value')==int(response) for s in states)

@pytest.mark.parametrize('response,expected',[('','EOF'),('abc','Invalid'),('   ','EOF')])
def test_palindrome_can_handle_failed_reads(response,expected):
    if not availability()['c']:pytest.skip('C engine missing.')
    source=PALINDROME.replace('scanf("%d", &n);','int read = scanf("%d", &n);\n    if (read != 1) { puts(read == EOF ? "EOF" : "Invalid"); return 0; }')
    trace=run('c',source,response)
    assert trace['status']=='completed',trace['diagnostics']
    assert trace['steps'][-1]['stdout']=='Enter an integer: '+expected+'\n'
    assert all(f['locals'].get('n',{}).get('kind')!='primitive' for s in trace['steps'] for f in s['frames'])

def test_multiple_input_reads_and_partial_scanf():
    if not availability()['c']:pytest.skip('C engine missing.')
    source='''#include <stdio.h>
int main(void) {
 int first, second;
 int read = scanf("%d %d", &first, &second);
 if (read == 1) { printf("%d", first); return 0; }
 if (read != 2) return 1;
 printf("%d", first + second);
 return 0;
}'''
    good=run('c',source,'4\n8\n')
    assert good['status']=='completed' and good['steps'][-1]['stdout']=='12',good['diagnostics']
    for response in ['4','4 nope']:
        partial=run('c',source,response)
        assert partial['status']=='completed',partial['diagnostics']
        assert partial['steps'][-1]['stdout']=='4'

@pytest.mark.parametrize('reader,declaration,response,expected',[
 ('scanf("%d", &number)','int number','42','42'),
 ('fscanf(stdin, "%d", &number)','int number','42','42'),
 ('number = getchar()','int number','A','65'),
 ('number = fgetc(stdin)','int number','A','65'),
 ('fgets(text, sizeof text, stdin)','char text[20]','hello','hello'),
])
def test_other_c_stdin_readers(reader,declaration,response,expected):
    if not availability()['c']:pytest.skip('C engine missing.')
    output='printf("%s", text)' if 'text' in declaration else 'printf("%d", number)'
    source=f'#include <stdio.h>\nint main(void) {{\n {declaration};\n {reader};\n {output};\n return 0;\n}}'
    good=run('c',source,response)
    assert good['status']=='completed' and good['steps'][-1]['stdout']==expected,good['diagnostics']
    target='text' if 'text' in declaration else 'number'
    pending=[s for s in good['steps'] if s['location'] and s['location']['line']<=4]
    assert pending and all(s['frames'][-1]['locals'][target]['kind']=='unavailable' for s in pending)

def test_input_mapping_ignores_comments_strings_and_other_functions():
    source='''// scanf("%d", &fake);
void other(void) { int n; }
int main(void) {
 printf("scanf(hello)");
 int n;
 scanf("%d", &n);
}'''
    assert input_targets(source)=={6:{'function':'main','names':['n']}}
