#include <stdio.h>

int main(void) {
    int rows, cols;
    printf("Rows (1-10): ");
    scanf("%d", &rows);
    printf("Columns (1-10): ");
    scanf("%d", &cols);
    if (rows < 1 || rows > 10 || cols < 1 || cols > 10) {
        printf("Please use dimensions from 1 to 10.\n");
        return 0;
    }
    int matrix[rows][cols];
    for (int row = 0; row < rows; row++) {
        for (int col = 0; col < cols; col++) {
            printf("matrix[%d][%d]: ", row, col);
            scanf("%d", &matrix[row][col]);
        }
    }
    printf("Your matrix:\n");
    for (int row = 0; row < rows; row++) {
        for (int col = 0; col < cols; col++)
            printf("%d ", matrix[row][col]);
        printf("\n");
    }
    return 0;
}
