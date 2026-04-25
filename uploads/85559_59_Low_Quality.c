#include <stdio.h>

int main() {
    int n, i;
    printf("Enter number: ");
    scanf("%d", &n);

    char name[50];
    int score;

    int total = 0;
    int max = 0;
    int min = 100;

    for (i = 0; i < n; i++) {
        printf("Enter name: ");
        scanf("%s", name);

        printf("Enter score: ");
        scanf("%d", &score);

        total += score;

        if (score > max) {
            max = score;
        }

        if (score < min) {
            min = score;
        }
    }

    printf("Average: %d\n", total / n);
    printf("Max: %d\n", max);
    printf("Min: %d\n", min);

    return 0;
}