import math

def check_palindrome():
    try:
        num = int(input("Enter an integer to check for Palindrome: "))
        original_str = str(abs(num))
        if original_str == original_str[::-1]:
            print(f"{num} is a Palindrome number.")
        else:
            print(f"{num} is not a Palindrome number.")
    except ValueError:
        print("Invalid input.")

def check_armstrong():
    try:
        num = int(input("Enter an integer to check for Armstrong: "))
        if num < 0:
            print(f"{num} is not an Armstrong number.")
            return
            
        num_str = str(num)
        power = len(num_str)
        total = sum(int(digit) ** power for digit in num_str)
        
        if total == num:
            print(f"{num} is an Armstrong number.")
        else:
            print(f"{num} is not an Armstrong number.")
    except ValueError:
        print("Invalid input.")

def check_prime():
    try:
        num = int(input("Enter a positive integer: "))
        if num <= 1:
            print(f"{num} is not a Prime number.")
            return
            
        is_prime = True
        for i in range(2, int(math.sqrt(num)) + 1):
            if num % i == 0:
                is_prime = False
                break
                
        if is_prime:
            print(f"{num} is a Prime number.")
        else:
            print(f"{num} is not a Prime number.")
    except ValueError:
        print("Invalid input.")

def print_fibonacci():
    try:
        n = int(input("Enter the number of terms for Fibonacci series: "))
        if n <= 0:
            print("Please enter a positive integer.")
            return
            
        t1, t2 = 0, 1
        print("Fibonacci Series:", end=" ")
        
        if n == 1:
            print(t1)
            return
            
        print(f"{t1}, {t2}", end="")
        for _ in range(3, n + 1):
            next_term = t1 + t2
            print(f", {next_term}", end="")
            t1, t2 = t2, next_term
        print()
    except ValueError:
        print("Invalid input.")

def find_factorial():
    try:
        n = int(input("Enter an integer to find its factorial: "))
        if n < 0:
            print("Error! Factorial of a negative number doesn't exist.")
        else:
            fact = 1
            for i in range(1, n + 1):
                fact *= i
            print(f"Factorial of {n} = {fact}")
    except ValueError:
        print("Invalid input.")

def reverse_string():
    string = input("Enter a string: ")
    print(f"Reversed string: {string[::-1]}")

def sum_of_digits():
    try:
        num = int(input("Enter an integer: "))
        total = sum(int(digit) for digit in str(abs(num)))
        print(f"Sum of digits of {num} is {total}")
    except ValueError:
        print("Invalid input.")

def check_leap_year():
    try:
        year = int(input("Enter a year: "))
        if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0):
            print(f"{year} is a Leap Year.")
        else:
            print(f"{year} is not a Leap Year.")
    except ValueError:
        print("Invalid input.")

def decimal_to_binary():
    try:
        n = int(input("Enter a decimal number: "))
        if n < 0:
            print(f"Binary equivalent of {n} is: -{bin(abs(n))[2:]}")
        else:
            print(f"Binary equivalent of {n} is: {bin(n)[2:]}")
    except ValueError:
        print("Invalid input.")

def main():
    while True:
        print("\n=========================================")
        print("      SIMPLE PYTHON UTILITY PROGRAM      ")
        print("=========================================")
        print("1. Check Palindrome Number")
        print("2. Check Armstrong Number")
        print("3. Check Prime Number")
        print("4. Print Fibonacci Series")
        print("5. Find Factorial")
        print("6. Reverse a String")
        print("7. Find Sum of Digits")
        print("8. Check Leap Year")
        print("9. Convert Decimal to Binary")
        print("0. Exit")
        print("=========================================")
        
        choice = input("Enter your choice (0-9): ")
        print()

        match choice:
            case '1':
                check_palindrome()
            case '2':
                check_armstrong()
            case '3':
                check_prime()
            case '4':
                print_fibonacci()
            case '5':
                find_factorial()
            case '6':
                reverse_string()
            case '7':
                sum_of_digits()
            case '8':
                check_leap_year()
            case '9':
                decimal_to_binary()
            case '0':
                print("Exiting program. Goodbye!")
                break
            case _:
                print("Invalid choice! Please select a valid option from 0 to 9.")

if __name__ == "__main__":
    main()