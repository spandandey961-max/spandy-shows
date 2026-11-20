#include <stdio.h>
int main() {
int c=1;
    for (int i = 1; i < 6; i++)
    {
        for (int j = 1; j <10; j++)
        {

            if (i+j<6)
                printf(" ");
            else if ((i+j)%2==0&& c<=i)
            {
                printf("*");
                c++;
            }
             else
            printf(" ");
           if (c>i)
            {
                c= 1;
                break;
            }

        }
        printf("\n");
    }
    return 0;
}
