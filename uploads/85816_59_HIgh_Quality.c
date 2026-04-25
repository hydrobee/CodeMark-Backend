#include <stdio.h>
#include <string.h>

#define MAX 50

// Function to calculate average
float calculateAverage(int scores[], int n) {
    int sum = 0;
    for (int i = 0; i < n; i++) {
        sum += scores[i];
    }
    return (float)sum / n;
}

// Function to determine grade
char getGrade(int score) {
    if (score >= 80) return 'A';
    else if (score >= 70) return 'B';
    else if (score >= 60) return 'C';
    else if (score >= 50) return 'D';
    else return 'F';
}

int main() {
    int n;

    printf("Enter number of students: ");
    scanf("%d", &n);

    // Input validation
    if (n <= 0 || n > MAX) {
        printf("Invalid number of students.\n");
        return 1;
    }

    char names[MAX][50];
    int scores[MAX];

    // Input data
    for (int i = 0; i < n; i++) {
        printf("\nStudent %d name: ", i + 1);
        scanf("%s", names[i]);

        printf("Score: ");
        scanf("%d", &scores[i]);

        while (scores[i] < 0 || scores[i] > 100) {
            printf("Invalid score. Enter again: ");
            scanf("%d", &scores[i]);
        }
    }

    // Initialize
    int max = scores[0], min = scores[0];
    int maxIndex = 0, minIndex = 0;

    // Find max and min
    for (int i = 1; i < n; i++) {
        if (scores[i] > max) {
            max = scores[i];
            maxIndex = i;
        }
        if (scores[i] < min) {
            min = scores[i];
            minIndex = i;
        }
    }

    float avg = calculateAverage(scores, n);

    // Output
    printf("\nAverage Score: %.2f\n", avg);
    printf("Highest Score: %s (%d)\n", names[maxIndex], max);
    printf("Lowest Score: %s (%d)\n", names[minIndex], min);

    printf("\nStudent Summary:\n");
    printf("Name\tScore\tGrade\n");

    for (int i = 0; i < n; i++) {
        printf("%s\t%d\t%c\n", names[i], scores[i], getGrade(scores[i]));
    }

    return 0;
}