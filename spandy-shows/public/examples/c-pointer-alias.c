#include <stdio.h>

int main(void) {
    int a[] = {3, 7};
    int *p = a, *q = a + 1;
    p = q;
    *p += *q;
    printf("%d %d\n", a[0], a[1]);
    return 0;
}
