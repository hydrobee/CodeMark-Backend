from AI.gemini_config import model
import re

def check_code_with_ai(code_content: str, criteria: list[dict]):
    rubric_lines = "\n".join(
        f"- {c['name']}: {c['weight']} points" for c in criteria
    )
    total = sum(c["weight"] for c in criteria)

    prompt = f"""
You are a university lecturer grading a programming assignment.

Rubric (total: {total} points):
{rubric_lines}

Student Code:
{code_content}

Return result STRICTLY in this format:

Score: <number>

Strengths:
<strengths here>

Areas for Improvement:
<areas here>

Comments:
<overall explanation here>
"""
    response = model.generate_content(prompt)
    text = response.text

    score_match = re.search(r"Score:\s*(\d+\.?\d*)", text)
    strengths_match = re.search(r"Strengths:\s*(.*?)(?=Areas for Improvement:|$)", text, re.DOTALL)
    improvements_match = re.search(r"Areas for Improvement:\s*(.*?)(?=Comments:|$)", text, re.DOTALL)
    comments_match = re.search(r"Comments:\s*(.*?)$", text, re.DOTALL)

    return {
        "score": float(score_match.group(1)) if score_match else None,
        "strengths": strengths_match.group(1).strip() if strengths_match else None,
        "improvements": improvements_match.group(1).strip() if improvements_match else None,
        "comments": comments_match.group(1).strip() if comments_match else text
    }