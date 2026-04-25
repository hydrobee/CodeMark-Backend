#include <stdio.h>

int main() {
    int n;
    printf("Enter number of students: ");
    scanf("%d", &n);

    char names[50][50];
    int scores[50];

    int sum = 0;

    for (int i = 0; i < n; i++) {
        printf("Name: ");
        scanf("%s", names[i]);

        printf("Score: ");
        scanf("%d", &scores[i]);

        sum += scores[i];
    }

    float avg = (float)sum / n;

    int max = scores[0], min = scores[0];
    int maxIndex = 0, minIndex = 0;

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

    printf("Average: %.2f\n", avg);
    printf("Highest: %s (%d)\n", names[maxIndex], max);
    printf("Lowest: %s (%d)\n", names[minIndex], min);

    printf("\nName\tScore\tGrade\n");

    for (int i = 0; i < n; i++) {
        char grade;

        if (scores[i] >= 80) grade = 'A';
        else if (scores[i] >= 70) grade = 'B';
        else if (scores[i] >= 60) grade = 'C';
        else if (scores[i] >= 50) grade = 'D';
        else grade = 'F';

        printf("%s\t%d\t%c\n", names[i], scores[i], grade);
    }

    return 0;
}