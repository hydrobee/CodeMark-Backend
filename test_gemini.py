from google import genai
import os
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

code = """
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
    char name[50];
    int score;
} Student;

void update_score(Student *s, int new_score) {
    if (new_score >= 0 && new_score <= 100) {
        s->score = new_score;
    }
}

int main() {
    int num_students = 3;
    Student *list = malloc(num_students * sizeof(Student));

    if (list == NULL) {
        return 1;
    }

    strcpy(list[0].name, "Alice");
    list[0].score = 85;

    strcpy(list[1].name, "Bob");
    list[1].score = 70;

    strcpy(list[2].name, "Charlie");
    list[2].score = 92;

    for (int i = 0; i < num_students; i++) {
        printf("Student: %s, Score: %d\n", list[i].name, list[i].score);
    }

    update_score(&list[1], 75);

    free(list);
    return 0;
}
"""

prompt = f"""
You are a university lecturer grading programming code. Please be strict in grading and giving feedback and humanely as possible.

Rubric:
Correctness: 40
Structure: 30
Readability: 30

Student Code:
{code}

Return result in format:

Score: <number>
Correctness: <number>
Structure: <number>
Readability: <number>

Feedback:
<explanation>

Strengths:
<explanation>

Areas for improvement:
<explanation>
"""

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=prompt
)

print(response.text)