import java.util.Scanner;

public class Main {
    public static void main(String[] args) {
        Scanner in = new Scanner(System.in);
        System.out.println("Type a for Pattern a");
        System.out.println("Type b for Pattern b");
        System.out.println("Type c for Pattern c");
        System.out.println("Type d for Pattern d");
        System.out.print("Enter your choice: ");
        char ch = in.next().charAt(0);
        System.out.print("Enter the number of terms: ");
        int n = in.nextInt();
        switch (ch) {
            case 'a':
                for (int i = 1; i <= n; i++) {
                    for (int j = 1; j <= i; j++)
                        System.out.print('#');
                    System.out.println();
                }
                break;
            case 'b':
                for (int i = n; i >= 1; i--) {
                    for (int j = 1; j <= i; j++)
                        System.out.print('#');
                    System.out.println();
                }
                break;
            case 'c':
                for (int i = n; i >= 1; i--) {
                    for (int j = i; j < n; j++)
                        System.out.print(" ");
                    for (int k = 0; k < i; k++)
                        System.out.print('#');
                    System.out.println();
                }
                break;
            case 'd':
                for (int i = n; i >= 1; i--) {
                    for (int j = 1; j < i; j++)
                        System.out.print(" ");
                    for (int k = i; k <= n; k++)
                        System.out.print('#');
                    System.out.println();
                }
                break;
            default:
                System.out.println("Incorrect choice");
                break;
        }
        in.close();
    }
}
