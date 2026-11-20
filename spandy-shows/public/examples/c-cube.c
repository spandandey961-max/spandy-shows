#include <stdio.h>

int main(void) {
    int cube[2][2][3] = {
        {{1, 2, 3}, {4, 5, 6}},
        {{7, 8, 9}, {10, 11, 12}}
    };
    int *p = &cube[1][0][2];
    *p = 99;
    printf("cube[1][0][2] = %d\n", cube[1][0][2]);
    return 0;
}
