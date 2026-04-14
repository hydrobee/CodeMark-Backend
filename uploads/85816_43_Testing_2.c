#include <stdio.h>

int main() {
    printf("Welcome to PawPal Service!\n");
    
    double total_grooming = 0.0;
    double total_boarding = 0.0;
    int total_pets = 0;
    char next;
    
    do {
        char pet_name[50];
        int service;
        int days;
        
        // Input pet name
        printf("Pet name: ");
        scanf("%s", pet_name);
        
        // Input and validate service type (1-3)
        do {
            printf("Service (1=Basic, 2=Full, 3=Spa): ");
            scanf("%d", &service);
            if (service < 1 || service > 3) {
                printf("Invalid service type! Please enter 1, 2 or 3.\n");
            }
        } while (service < 1 || service > 3);
        
        // Input and validate boarding days (>= 0)
        do {
            printf("Boarding days: ");
            scanf("%d", &days);
            if (days < 0) {
                printf("Invalid! Number of days cannot be negative.\n");
            }
        } while (days < 0);
        
        // Calculate grooming fee
        double grooming_fee;
        if (service == 1) {
            grooming_fee = 35.00;
        } else if (service == 2) {
            grooming_fee = 60.00;
        } else {
            grooming_fee = 90.00;
        }
        
        // Calculate boarding fee with discount
        double boarding_base = days * 20.0;
        double discount_rate = 0.0;
        if (days >= 10) {
            discount_rate = 0.10;
        } else if (days >= 5) {
            discount_rate = 0.05;
        }
        double boarding_fee = boarding_base * (1.0 - discount_rate);
        
        // Calculate total for this pet
        double pet_total = grooming_fee + boarding_fee;
        
        // Display results for this pet
        printf("\nGrooming Fee: RM%.2f\n", grooming_fee);
        printf("Boarding Fee (after discount): RM%.2f\n", boarding_fee);
        printf("Total: RM%.2f\n\n", pet_total);
        
        // Accumulate totals
        total_grooming += grooming_fee;
        total_boarding += boarding_fee;
        total_pets++;
        
        // Ask if next pet (case insensitive)
        printf("Next pet? (Y/N): ");
        scanf(" %c", &next);
        
    } while (next == 'Y' || next == 'y');
    
    // Daily summary
    printf("\n**Daily summary**\n");
    printf("Total Pets: %d\n", total_pets);
    printf("Total Grooming Fees: RM%.2f\n", total_grooming);
    printf("Total Boarding Fees: RM%.2f\n", total_boarding);
    printf("Grand Total: RM%.2f\n", total_grooming + total_boarding);
    
    return 0;
}