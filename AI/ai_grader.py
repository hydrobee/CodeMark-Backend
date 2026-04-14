import re
import os
import base64
from docx import Document as DocxDocument
import json
from AI.gemini_config import model


# ═════════════════════════════════════════════════════════════════════════════
#  File helpers
# ═════════════════════════════════════════════════════════════════════════════

def _read_text_file(file_path: str) -> str:
    """Read a plain text / source code file."""
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def _read_pdf_as_blob(file_path: str) -> dict:
    """
    Read a PDF and return a Gemini-compatible inline_data blob.
    Gemini can natively understand PDFs sent this way.
    """
    with open(file_path, "rb") as f:
        data = base64.standard_b64encode(f.read()).decode("utf-8")
    return {
        "inline_data": {
            "mime_type": "application/pdf",
            "data": data
        }
    }


def _docx_to_text(file_path: str) -> str:
    """
    Extract plain text from a DOCX file including table cells.
    Gemini cannot read DOCX natively so we convert to text first.
    """
    doc = DocxDocument(file_path)
    parts = []

    for block in doc.element.body:
        tag = block.tag.split("}")[-1]

        if tag == "p":
            text = "".join(
                node.text or "" for node in block.iter()
                if node.tag.endswith("}t")
            )
            if text.strip():
                parts.append(text)

        elif tag == "tbl":
            for row in block.iter(
                "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tr"
            ):
                cells = []
                for cell in row.iter(
                    "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tc"
                ):
                    cell_text = "".join(
                        node.text or "" for node in cell.iter()
                        if node.tag.endswith("}t")
                    )
                    cells.append(cell_text.strip())
                parts.append(" | ".join(cells))

    return "\n".join(parts)


def _load_file_for_gemini(file_path: str, mime_type: str):
    """
    Return the appropriate Gemini content part for a file.

    PDF  → inline_data blob (Gemini reads natively)
    DOCX → extracted plain text string (tables included)
    Other (code, .txt, etc.) → plain text string
    Returns None if file_path is empty or file does not exist.
    """
    if not file_path or not os.path.exists(file_path):
        return None

    if mime_type == "application/pdf":
        return _read_pdf_as_blob(file_path)

    if mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        return _docx_to_text(file_path)

    # Plain text, source code files, etc.
    return _read_text_file(file_path)

def extract_criteria_from_rubric_file(file_path: str, mime_type: str) -> list[dict]:
    """
    Use Gemini to extract rubric criteria and weights.
    Improved cleaning to handle Gemini's markdown/code blocks reliably.
    """
    file_part = _load_file_for_gemini(file_path, mime_type)
    if not file_part:
        raise ValueError("Could not load rubric file")

    prompt = """
Extract all grading criteria from this rubric document.
Return **ONLY** a valid JSON array. No explanation, no markdown, no ``` fences, no extra text.

Each item must have exactly:
- "name": string (criterion name)
- "weight": integer (0-100)

The sum of all weights must be exactly 100.

Example:
[{"name": "Code Correctness", "weight": 40}, {"name": "Documentation", "weight": 30}, {"name": "Efficiency", "weight": 30}]
"""

    parts = [file_part, prompt]

    try:
        response = model.generate_content(parts)
        text = response.text.strip()

        # === Aggressive cleaning for Gemini's common habits ===
        # 1. Remove ```json and ``` blocks
        text = re.sub(r'```json\s*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'```\s*', '', text, flags=re.IGNORECASE)

        # 2. Remove any leading/trailing non-JSON text
        json_match = re.search(r'(\[\s*\{.*?\}\s*\])', text, re.DOTALL)
        if json_match:
            text = json_match.group(1)

        # 3. Final cleanup
        text = text.strip()

        # Parse JSON
        criteria = json.loads(text)

        if not isinstance(criteria, list):
            raise ValueError("AI did not return a JSON array")

        # Validate each item
        for item in criteria:
            if not isinstance(item, dict) or "name" not in item or "weight" not in item:
                raise ValueError(f"Invalid criterion format: {item}")
            item["name"] = str(item["name"]).strip()
            item["weight"] = int(item["weight"])

        return criteria

    except json.JSONDecodeError as e:
        raise ValueError(f"AI returned invalid JSON.\nRaw output:\n{text[:600]}...")
    except Exception as e:
        raise ValueError(f"Failed to extract criteria: {str(e)}")


# ═════════════════════════════════════════════════════════════════════════════
#  Response parser  (same logic as original)
# ═════════════════════════════════════════════════════════════════════════════

def _parse_response(text: str, criteria: list[dict] | None = None) -> dict:
    """Parse Gemini response + normalize score to percentage out of 100."""
    
    # Extract overall Score from AI response
    score_match = re.search(r"Score:\s*(\d+\.?\d*)", text)
    raw_score = float(score_match.group(1)) if score_match else 0.0

    strengths_match = re.search(r"Strengths:\s*(.*?)(?=Areas for Improvement:|$)", text, re.DOTALL)
    improvements_match = re.search(r"Areas for Improvement:\s*(.*?)(?=Comments:|$)", text, re.DOTALL)
    comments_match = re.search(r"Comments:\s*(.*?)$", text, re.DOTALL)

    # Parse per-criterion scores
    rubric_scores = []
    criterion_block = re.search(r"Criterion Scores:\s*(.*?)(?=Score:|$)", text, re.DOTALL)
    
    if criterion_block and criteria:
        for line in criterion_block.group(1).strip().splitlines():
            match = re.match(r"-?\s*(.+?):\s*(\d+\.?\d*)\s*/\s*(\d+\.?\d*)", line)
            if match:
                rubric_scores.append({
                    "name": match.group(1).strip(),
                    "score": float(match.group(2)),
                    "weight": float(match.group(3)),
                })

    # Calculate totals from rubric_scores (most accurate)
    obtained = sum(item.get("score", 0) for item in rubric_scores)
    total_weight = sum(c.get("weight", 0) for c in (criteria or []))

    # Fallback: if no rubric_scores parsed, use raw_score and total_weight
    if obtained == 0 and raw_score > 0:
        obtained = raw_score

    # === KEY NORMALIZATION ===
    if total_weight > 0:
        percentage = round((obtained / total_weight) * 100, 2)
    else:
        percentage = round(raw_score, 2)   # fallback if no weights

    return {
        "raw_score": raw_score,           # what AI originally said
        "obtained": obtained,             # total marks student got
        "total_weight": round(total_weight, 2),
        "percentage": percentage,         # ← This MUST be 100 when student got full marks
        "strengths": strengths_match.group(1).strip() if strengths_match else None,
        "improvements": improvements_match.group(1).strip() if improvements_match else None,
        "comments": comments_match.group(1).strip() if comments_match else text,
        "rubric_scores": rubric_scores,
    }

# ═════════════════════════════════════════════════════════════════════════════
#  Original function — kept exactly, used for simple code-text grading
# ═════════════════════════════════════════════════════════════════════════════

def check_code_with_ai(code_content: str, criteria: list[dict]) -> dict:
    """
    Original grading function — grades plain code text against rubric criteria.
    Kept unchanged so all existing call sites continue to work.
    """
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

Criterion Scores:
- <criterion name>: <score> / <max weight>
- <criterion name>: <score> / <max weight>

Score: <number>

Strengths:
<strengths here>

Areas for Improvement:
<areas here>

Comments:
<overall explanation here>
"""
    response = model.generate_content(prompt)
    return _parse_response(response.text, criteria)


# ═════════════════════════════════════════════════════════════════════════════
#  New function — grades using uploaded document files
# ═════════════════════════════════════════════════════════════════════════════

def check_submission_with_files(
    criteria: list[dict],
    # Student submission
    submission_file_path: str,
    submission_mime_type: str,
    # Assignment question document (optional but strongly recommended)
    question_file_path: str | None = None,
    question_mime_type: str | None = None,
    # Rubric document (optional but strongly recommended)
    rubric_file_path: str | None = None,
    rubric_mime_type: str | None = None,
) -> dict:
    """
    Grade a student submission using:
      - The assignment question document uploaded by the lecturer (PDF/DOCX)
      - The rubric document with tables uploaded by the lecturer (PDF/DOCX)
      - The rubric JSON criteria stored in the database
      - The student submission file (PDF / DOCX / .py / .txt / etc.)

    Return keys are identical to check_code_with_ai():
      score, strengths, improvements, comments
    """
    rubric_lines = "\n".join(
        f"- {c['name']}: {c['weight']} points" for c in criteria
    )
    total = sum(c["weight"] for c in criteria)

    # ── Build Gemini content parts list ───────────────────────────────────────
    # Gemini's generate_content() accepts a list mixing strings and inline blobs.
    parts = []

    # 1. Assignment question document
    question_part = _load_file_for_gemini(question_file_path, question_mime_type or "")
    if question_part:
        parts.append("=== ASSIGNMENT QUESTION / BRIEF ===")
        parts.append(question_part)
    else:
        parts.append("=== ASSIGNMENT QUESTION / BRIEF ===\n(Not provided by lecturer)")

    # 2. Rubric document (detailed marking scheme, may contain tables)
    rubric_doc_part = _load_file_for_gemini(rubric_file_path, rubric_mime_type or "")
    if rubric_doc_part:
        parts.append("=== RUBRIC DOCUMENT (detailed marking scheme) ===")
        parts.append(rubric_doc_part)

    # 3. Rubric JSON criteria (structured weights stored in DB)
    parts.append(
        f"=== RUBRIC CRITERIA (weights) ===\n"
        f"Total marks: {total}\n"
        f"{rubric_lines}"
    )

    # 4. Student submission
    submission_part = _load_file_for_gemini(submission_file_path, submission_mime_type)
    if not submission_part:
        raise ValueError(f"Student submission file not found: {submission_file_path}")

    parts.append("=== STUDENT SUBMISSION ===")
    parts.append(submission_part)

    # 5. Grading instruction — updated format includes per-criterion scores
    parts.append(f"""
=== GRADING INSTRUCTIONS ===
You are a university lecturer grading a student submission.

Use the assignment question/brief to understand what was expected.
Use the rubric document AND the rubric criteria weights to determine the score.
Evaluate the student submission thoroughly and objectively.

Return result STRICTLY in this format:

Criterion Scores:
- <criterion name>: <score> / <max weight>
- <criterion name>: <score> / <max weight>

Score: <total number out of {total}>

Strengths:
<what the student did well, referencing specific parts of the submission>

Areas for Improvement:
<specific, actionable suggestions tied to the rubric criteria>

Comments:
<overall explanation referencing the assignment objectives and rubric>
""")

    response = model.generate_content(parts)
    return _parse_response(response.text, criteria)  # ← pass criteria