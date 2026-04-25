#include <stdio.h>
#include <string.h>

// Structure to hold customer data 
typedef struct {
    char name[50];
    char ic[20];
    char address[100];
    char phoneNo[15];
    float rental;
    float smsSame;
    float smsDiff;
    float callSame;
    float callDiff;
    float internet;
} Customer;

// Function Prototypes 
float calculateCallCharge(int durationSec, int isSameOperator, int isDaytime);
float calculateSMSCharge(int isSameOperator);
void generateBill(Customer c);

int main() {
    Customer user;
    user.rental = 20.00; // Fixed monthly rental 

    printf("--- Telephone Billing System ---\n");
    printf("Enter Customer Name: ");
    fgets(user.name, 50, stdin);
    user.name[strcspn(user.name, "\n")] = 0;

    printf("Enter IC: ");
    scanf("%s", user.ic);
    
    // Example logic for a single session
    // In a full system, you would loop through call/SMS logs from a file 
    
    // Hardcoded example data based on project sample [cite: 38-56]
    user.smsSame = 5.00;
    user.smsDiff = 12.20;
    user.callSame = 24.60;
    user.callDiff = 19.70;
    user.internet = 50.00; // 1G Package 

    generateBill(user);

    return 0;
}

// Function to calculate call charges based on timing and duration [cite: 21, 28-32]
float calculateCallCharge(int durationSec, int isSameOperator, int isDaytime) {
    float rate;
    if (isDaytime) {
        rate = isSameOperator ? 0.15 : 0.30;
    } else {
        rate = isSameOperator ? 0.08 : 0.20;
    }

    if (durationSec < 30) {
        return rate * 0.30; // 30% of minute rate [cite: 28]
    } else {
        return rate; // Full minute rate [cite: 30]
    }
}

// Function to generate and display the monthly bill [cite: 19, 33]
void generateBill(Customer c) {
    float totalCharges = c.rental + c.smsSame + c.smsDiff + c.callSame + c.callDiff + c.internet;
    float serviceTax = totalCharges * 0.10; // 10% Service Tax [cite: 22]
    float totalDue = totalCharges + serviceTax;

    printf("\n--------------------------------------------\n");
    printf("Customer Name    : %s\n", c.name);
    printf("IC               : %s\n", c.ic);
    printf("Monthly Rental   : RM %.2f\n", c.rental);
    printf("Internet Package : RM %.2f\n", c.internet);
    printf("TOTAL CHARGES    : RM %.2f\n", totalCharges);
    printf("SERVICE TAX (10%%): RM %.2f\n", serviceTax);
    printf("TOTAL AMOUNT DUE : RM %.2f\n", totalDue);
    printf("--------------------------------------------\n");
}