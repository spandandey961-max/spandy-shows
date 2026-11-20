import java.util.Scanner;

public class Main {

    public static void main(String[] args) {
        Scanner scanner = new Scanner(System.in);
        int choice = -1;

        System.out.println("\n=========================================");
        System.out.println("       SIMPLE JAVA UTILITY PROGRAM       ");
        System.out.println("=========================================");
        System.out.println("1. Check Palindrome Number");
        System.out.println("2. Check Armstrong Number");
        System.out.println("3. Check Prime Number");
        System.out.println("4. Print Fibonacci Series");
        System.out.println("5. Find Factorial");
        System.out.println("6. Reverse a String");
        System.out.println("7. Find Sum of Digits");
        System.out.println("8. Check Leap Year");
        System.out.println("9. Convert Decimal to Binary");
        System.out.println("0. Exit");
        System.out.println("=========================================");
        System.out.print("Enter your choice (0-9): ");

        if (scanner.hasNextInt()) {
            choice = scanner.nextInt();
            System.out.println();
            
            switch (choice) {
                case 1:
                    checkPalindrome(scanner);
                    break;
                case 2:
                    checkArmstrong(scanner);
                    break;
                case 3:
                    checkPrime(scanner);
                    break;
                case 4:
                    printFibonacci(scanner);
                    break;
                case 5:
                    findFactorial(scanner);
                    break;
                case 6:
                    reverseString(scanner);
                    break;
                case 7:
                    sumOfDigits(scanner);
                    break;
                case 8:
                    checkLeapYear(scanner);
                    break;
                case 9:
                    decimalToBinary(scanner);
                    break;
                case 0:
                    System.out.println("Exiting program. Goodbye!");
                    break;
                default:
                    System.out.println("Invalid choice! Please select a valid option from 0 to 9.");
            }
        } else {
            System.out.println("Invalid input. Exiting...");
        }
        
        scanner.close();
    }

    // 1. Check Palindrome Number
    public static void checkPalindrome(Scanner scanner) {
        System.out.print("Enter an integer to check for Palindrome: ");
        int num = scanner.nextInt();
        int originalNum = num;
        int reversedNum = 0;

        while (num != 0) {
            int remainder = num % 10;
            reversedNum = reversedNum * 10 + remainder;
            num /= 10;
        }

        if (originalNum == reversedNum) {
            System.out.println(originalNum + " is a Palindrome number.");
        } else {
            System.out.println(originalNum + " is not a Palindrome number.");
        }
    }

    // 2. Check Armstrong Number
    public static void checkArmstrong(Scanner scanner) {
        System.out.print("Enter an integer to check for Armstrong: ");
        int num = scanner.nextInt();
        int originalNum = num;
        int result = 0;
        int n = String.valueOf(Math.abs(num)).length();

        originalNum = num;
        while (originalNum != 0) {
            int remainder = originalNum % 10;
            result += Math.pow(remainder, n);
            originalNum /= 10;
        }

        if (result == num) {
            System.out.println(num + " is an Armstrong number.");
        } else {
            System.out.println(num + " is not an Armstrong number.");
        }
    }

    // 3. Check Prime Number
    public static void checkPrime(Scanner scanner) {
        System.out.print("Enter a positive integer: ");
        int num = scanner.nextInt();
        boolean isPrime = true;

        if (num <= 1) {
            isPrime = false;
        } else {
            for (int i = 2; i <= Math.sqrt(num); i++) {
                if (num % i == 0) {
                    isPrime = false;
                    break;
                }
            }
        }

        if (isPrime) {
            System.out.println(num + " is a Prime number.");
        } else {
            System.out.println(num + " is not a Prime number.");
        }
    }

    // 4. Print Fibonacci Series
    public static void printFibonacci(Scanner scanner) {
        System.out.print("Enter the number of terms for Fibonacci series: ");
        int n = scanner.nextInt();

        if (n <= 0) {
            System.out.println("Please enter a positive integer.");
            return;
        }

        int t1 = 0, t2 = 1;
        System.out.print("Fibonacci Series: " + t1);

        if (n > 1) {
            System.out.print(", " + t2);
            for (int i = 3; i <= n; i++) {
                int nextTerm = t1 + t2;
                System.out.print(", " + nextTerm);
                t1 = t2;
                t2 = nextTerm;
            }
        }
        System.out.println();
    }

    // 5. Find Factorial
    public static void findFactorial(Scanner scanner) {
        System.out.print("Enter an integer to find its factorial: ");
        int n = scanner.nextInt();

        if (n < 0) {
            System.out.println("Error! Factorial of a negative number doesn't exist.");
        } else {
            long fact = 1;
            for (int i = 1; i <= n; i++) {
                fact *= i;
            }
            System.out.println("Factorial of " + n + " = " + fact);
        }
    }

    // 6. Reverse a String
    public static void reverseString(Scanner scanner) {
        System.out.print("Enter a string: ");
        scanner.nextLine(); // consume leftover newline
        String str = scanner.nextLine();
        
        StringBuilder reversed = new StringBuilder(str);
        System.out.println("Reversed string: " + reversed.reverse().toString());
    }

    // 7. Find Sum of Digits
    public static void sumOfDigits(Scanner scanner) {
        System.out.print("Enter an integer: ");
        int num = scanner.nextInt();
        int sum = 0;
        int temp = Math.abs(num);

        while (temp != 0) {
            sum += temp % 10;
            temp /= 10;
        }

        System.out.println("Sum of digits of " + num + " is " + sum);
    }

    // 8. Check Leap Year
    public static void checkLeapYear(Scanner scanner) {
        System.out.print("Enter a year: ");
        int year = scanner.nextInt();

        if ((year % 4 == 0 && year % 100 != 0) || (year % 400 == 0)) {
            System.out.println(year + " is a Leap Year.");
        } else {
            System.out.println(year + " is not a Leap Year.");
        }
    }

    // 9. Convert Decimal to Binary
    public static void decimalToBinary(Scanner scanner) {
        System.out.print("Enter a decimal number: ");
        int n = scanner.nextInt();
        
        if (n < 0) {
            System.out.println("Binary equivalent of " + n + " is: -" + Integer.toBinaryString(Math.abs(n)));
        } else {
            System.out.println("Binary equivalent of " + n + " is: " + Integer.toBinaryString(n));
        }
    }
}