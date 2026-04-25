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

        # 1. Remove ```json and ``` blocks
        text = re.sub(r'```json\s*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'```\s*', '', text, flags=re.IGNORECASE)

        # 2. Remove any leading/trailing non-JSON text
        json_match = re.search(r'(\[\s*\{.*?\}\s*\])', text, re.DOTALL)
        if json_match:
            text = json_match.group(1)

        text = text.strip()
        criteria = json.loads(text)

        if not isinstance(criteria, list):
            raise ValueError("AI did not return a JSON array")

        for item in criteria:
            if not isinstance(item, dict) or "name" not in item or "weight" not in item:
                raise ValueError(f"Invalid criterion format: {item}")
            item["name"] = str(item["name"]).strip()
            item["weight"] = int(item["weight"])

        return criteria

    except json.JSONDecodeError:
        raise ValueError(f"AI returned invalid JSON.\nRaw output:\n{text[:600]}...")
    except Exception as e:
        raise ValueError(f"Failed to extract criteria: {str(e)}")


# ═════════════════════════════════════════════════════════════════════════════
#  Name matching helper
# ═════════════════════════════════════════════════════════════════════════════

def _normalize(s: str) -> str:
    """Lowercase, strip punctuation and extra spaces for fuzzy matching."""
    return re.sub(r'[^a-z0-9 ]', '', s.lower()).strip()


def _find_db_weight(ai_name: str, criteria_map: dict) -> float | None:
    """
    Look up the DB weight for an AI-returned criterion name.

    Strategy (in order):
    1. Exact match (lowercased)
    2. Normalized match (strip punctuation/spaces)
    3. Substring match — AI name contains DB key, or DB key contains AI name
    4. Word-overlap match — majority of words overlap

    Returns None if no match found (caller falls back to ai_max).
    """
    ai_lower = ai_name.lower().strip()
    ai_norm  = _normalize(ai_name)

    # 1. Exact lowercase match
    if ai_lower in criteria_map:
        return criteria_map[ai_lower]

    # 2. Normalized match
    norm_map = {_normalize(k): v for k, v in criteria_map.items()}
    if ai_norm in norm_map:
        return norm_map[ai_norm]

    # 3. Substring match
    for db_key, db_weight in criteria_map.items():
        db_norm = _normalize(db_key)
        if ai_norm in db_norm or db_norm in ai_norm:
            return db_weight

    # 4. Word-overlap match (≥ 50% of words must overlap)
    ai_words = set(ai_norm.split())
    best_overlap = 0.0
    best_weight  = None
    for db_key, db_weight in criteria_map.items():
        db_words = set(_normalize(db_key).split())
        if not db_words:
            continue
        overlap = len(ai_words & db_words) / max(len(ai_words), len(db_words))
        if overlap > best_overlap:
            best_overlap = overlap
            best_weight  = db_weight
    if best_overlap >= 0.5:
        return best_weight

    return None  # no match found


# ═════════════════════════════════════════════════════════════════════════════
#  Response parser
#
#  FIX: db_weight is now always the authoritative maximum for each criterion.
#       ai_max from Gemini's output is only used as a last-resort fallback
#       when fuzzy matching completely fails — it is never used to normalise
#       the score when db_weight is known.
# ═════════════════════════════════════════════════════════════════════════════

def _parse_response(text: str, criteria: list[dict] | None = None) -> dict:
    score_match        = re.search(r"Score:\s*(\d+\.?\d*)", text)
    raw_score          = float(score_match.group(1)) if score_match else 0.0

    strengths_match    = re.search(r"Strengths:\s*(.*?)(?=Areas for Improvement:|$)", text, re.DOTALL)
    improvements_match = re.search(r"Areas for Improvement:\s*(.*?)(?=Comments:|$)", text, re.DOTALL)
    comments_match     = re.search(r"Comments:\s*(.*?)$", text, re.DOTALL)

    rubric_scores   = []
    criterion_block = re.search(r"Criterion Scores:\s*(.*?)(?=Score:|$)", text, re.DOTALL)

    # total_weight = sum of DB weights (always 100 when rubric is set up correctly)
    total_weight = sum(c.get("weight", 0) for c in (criteria or []))
    criteria_map = {c["name"].lower(): float(c["weight"]) for c in (criteria or [])}

    obtained = 0.0  # accumulated normalized score on the DB-weight scale

    if criterion_block and criteria:
        for line in criterion_block.group(1).strip().splitlines():
            match = re.match(r"-?\s*(.+?):\s*(\d+\.?\d*)\s*/\s*(\d+\.?\d*)", line)
            if match:
                name     = match.group(1).strip()
                ai_score = float(match.group(2))  # student score Gemini assigned
                ai_max   = float(match.group(3))  # max Gemini wrote — MAY be wrong

                # ── Authoritative max lookup ───────────────────────────────
                # Always prefer the DB weight; only fall back to ai_max when
                # fuzzy matching returns nothing (should be extremely rare).
                db_weight = _find_db_weight(name, criteria_map)

                if db_weight is None:
                    # Genuine no-match: warn and fall back to whatever Gemini wrote.
                    print(
                        f"[WARN] Criterion '{name}' not matched in DB. "
                        f"Falling back to ai_max={ai_max}. "
                        f"DB keys: {list(criteria_map.keys())}"
                    )
                    db_weight = ai_max

                # ── Score normalisation ────────────────────────────────────
                # Gemini was instructed to score on the DB scale, so ai_score
                # should already be out of db_weight.  We cap it for safety.
                # We do NOT use ai_max here — it may have been rescaled by Gemini
                # (e.g. Gemini writes "8 / 10" when the real max is 1 or 40).
                ai_score_capped = min(ai_score, db_weight)

                # If Gemini clearly used a different scale (ai_max ≠ db_weight
                # and ai_max > 0), re-proportion the score onto the DB scale.
                if ai_max > 0 and abs(ai_max - db_weight) > 0.01:
                    print(
                        f"[INFO] Criterion '{name}': Gemini used scale 0-{ai_max} "
                        f"but DB weight is {db_weight}. Re-proportioning score."
                    )
                    ai_score_capped = min((ai_score / ai_max) * db_weight, db_weight)

                contribution = round(ai_score_capped, 2)
                obtained += contribution

                rubric_scores.append({
                    "name":   name,
                    "score":  contribution,   # pts earned on DB scale
                    "weight": db_weight,      # authoritative max from DB
                })

    # Fallback: criterion block failed to parse — use raw AI score
    if obtained == 0 and raw_score > 0 and total_weight > 0:
        obtained = raw_score

    # percentage = obtained / total_weight * 100
    # Both values are on the same DB-weight scale (total_weight = 100)
    percentage = round((obtained / total_weight) * 100, 2) if total_weight > 0 else round(raw_score, 2)

    return {
        "raw_score":     raw_score,
        "obtained":      round(obtained, 2),        # pts earned out of total_weight
        "total_weight":  round(total_weight, 2),    # sum of DB weights (= 100)
        "percentage":    percentage,                # final grade %
        "strengths":     strengths_match.group(1).strip()    if strengths_match    else None,
        "improvements":  improvements_match.group(1).strip() if improvements_match else None,
        "comments":      comments_match.group(1).strip()     if comments_match     else text,
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
#
#  FIX: The output template and REMINDERS now explicitly tell Gemini to score
#       on the exact DB scale (e.g. 0-1, 0-40) and never re-scale to 10/100.
# ═════════════════════════════════════════════════════════════════════════════

def check_submission_with_files(
    criteria: list[dict],
    submission_file_path: str,
    submission_mime_type: str,
    question_file_path: str | None = None,
    question_mime_type: str | None = None,
    rubric_file_path: str | None = None,
    rubric_mime_type: str | None = None,
) -> dict:
    """
    Grade a student submission using:
      - The assignment question document uploaded by the lecturer (PDF/DOCX)
      - The rubric document with tables uploaded by the lecturer (PDF/DOCX)
      - The rubric JSON criteria stored in the database
      - The student submission file (PDF / DOCX / .py / .txt / etc.)
    """
    total = sum(c["weight"] for c in criteria)

    # Numbered list of official criteria — feeds both the authority block and
    # the pre-filled output template so Gemini has no ambiguity.
    numbered_criteria = "\n".join(
        f"  {i+1}. \"{c['name']}\" — max {c['weight']} pts"
        for i, c in enumerate(criteria)
    )

    # Pre-filled output template with exact names & maxes already inserted.
    # Gemini only needs to fill in the student's score number.
    # FIX: Added explicit range hint "(a number from 0 to <weight>)" so Gemini
    #      cannot justify rescaling to a "nicer" range like 0-10 or 0-100.
    example_lines = "\n".join(
        f'- "{c["name"]}": <a number from 0 to {c["weight"]}> / {c["weight"]}'
        for c in criteria
    )

    # ── Build Gemini content parts list ───────────────────────────────────────
    parts = []

    # 1. Grading authority — comes FIRST to frame everything that follows
    parts.append(f"""\
=== GRADING AUTHORITY ===
You are grading a student assignment.
The ONLY criteria you may use are the {len(criteria)} criteria in the \
OFFICIAL CRITERIA section below.
Do NOT invent, add, merge, split, or rename any criterion.
The rubric document below is provided for descriptive context only — \
it does NOT override the official criteria names or weights.\
""")

    # 2. Official criteria — single source of truth for names and weights
    parts.append(
        f"=== OFFICIAL CRITERIA (use EXACTLY these {len(criteria)} criteria) ===\n"
        f"Total marks: {total}\n"
        f"{numbered_criteria}\n\n"
        f"You MUST produce exactly {len(criteria)} lines in Criterion Scores, "
        f"one per criterion above, in the same order, "
        f"using the exact name and exact max shown."
    )

    # 3. Assignment question document (context only)
    question_part = _load_file_for_gemini(question_file_path, question_mime_type or "")
    if question_part:
        parts.append("=== ASSIGNMENT QUESTION (context only) ===")
        parts.append(question_part)
    else:
        parts.append("=== ASSIGNMENT QUESTION ===\n(Not provided by lecturer)")

    # 4. Rubric document (context only — names/weights already fixed above)
    rubric_doc_part = _load_file_for_gemini(rubric_file_path, rubric_mime_type or "")
    if rubric_doc_part:
        parts.append(
            "=== RUBRIC DOCUMENT (context only — use for descriptors, "
            "NOT to change criteria names or weights) ==="
        )
        parts.append(rubric_doc_part)

    # 5. Student submission
    submission_part = _load_file_for_gemini(submission_file_path, submission_mime_type)
    if not submission_part:
        raise ValueError(f"Student submission file not found: {submission_file_path}")

    parts.append("=== STUDENT SUBMISSION ===")
    parts.append(submission_part)

    # 6. Output instructions — pre-filled template leaves no room for deviation
    # FIX: REMINDERS now explicitly forbid re-scaling and give a concrete
    #      example that matches small weights (e.g. max = 1 → write 0.8 / 1).
    parts.append(f"""\
=== OUTPUT INSTRUCTIONS ===
Return your response in EXACTLY this format — no deviations:

Criterion Scores:
{example_lines}

Score: <total number out of {total}>

Strengths:
<what the student did well, referencing specific parts of the submission>

Areas for Improvement:
<specific, actionable suggestions tied to the rubric criteria>

Comments:
<overall explanation referencing the assignment objectives and rubric>

REMINDERS:
- Criterion Scores must have EXACTLY {len(criteria)} lines.
- Use the EXACT criterion name and EXACT max from the Official Criteria list.
- Score each criterion on the SAME scale as its stated max.
  • If max is 40  → write a number between 0 and 40   (e.g. 32 / 40)
  • If max is 1   → write a decimal between 0 and 1   (e.g. 0.8 / 1)
  • If max is 10  → write a number between 0 and 10   (e.g. 7 / 10)
- Do NOT rescale scores to a different range (e.g. do NOT convert a max-1
  criterion to 7 / 10 or 70 / 100 — that is a critical error).
- Do NOT add extra criteria lines beyond the {len(criteria)} listed.\
""")

    response = model.generate_content(parts)
    return _parse_response(response.text, criteria)