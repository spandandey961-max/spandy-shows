#include <stdio.h>

int main(void) {
    int A[] = {10, 20, 30, 40};
    int *p = &A[1];

    int value = *(p + 1);
    printf("p points to A[1] = %d\n", *p);
    printf("*(p + 1) reads A[2] = %d\n", value);

    A[2] = 99;
    printf("After the change, A[2] = %d\n", *(p + 1));
    return 0;
}
