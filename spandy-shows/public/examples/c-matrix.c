#include <stdio.h>

int main(void) {
    int matrix[2][3] = {{1, 2, 3}, {4, 5, 6}};
    int *p = &matrix[1][2];
    *p = 9;
    for (int row = 0; row < 2; row++) {
        for (int col = 0; col < 3; col++)
            printf("%d ", matrix[row][col]);
        printf("\n");
    }
    return 0;
}
