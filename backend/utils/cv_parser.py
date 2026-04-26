import fitz  # PyMuPDF
import docx
import re
import json
import logging
import spacy
from utils.llm import generate as llm_generate

logger = logging.getLogger(__name__)
nlp = spacy.load("en_core_web_sm")

SKILLS_KEYWORDS = [
    # Languages
    "python", "java", "javascript", "typescript", "c++", "c#", "c", "go", "rust",
    "kotlin", "swift", "ruby", "php", "scala", "r", "matlab",
    # Web / Frameworks
    "react", "angular", "vue", "next.js", "node.js", "fastapi", "django", "flask",
    "spring", "express", "tailwind", "html", "css",
    # Data / ML
    "machine learning", "deep learning", "nlp", "data analysis", "tensorflow",
    "pytorch", "scikit-learn", "pandas", "numpy", "matplotlib", "seaborn",
    "huggingface", "transformers", "computer vision", "llm",
    # Databases
    "sql", "postgresql", "mysql", "mongodb", "redis", "sqlite", "elasticsearch",
    "cassandra", "dynamodb", "oracle",
    # Cloud / Infra
    "aws", "azure", "gcp", "docker", "kubernetes", "linux", "terraform",
    "ansible", "nginx", "apache",
    # Tools / Practices
    "git", "github", "gitlab", "ci/cd", "rest api", "graphql", "grpc",
    "microservices", "agile", "scrum", "jira", "figma",
]

EDUCATION_KEYWORDS = [
    "education", "academic", "qualification", "degree", "university", "college",
    "bachelor", "master", "phd", "diploma", "institute", "school", "graduated",
]
EXPERIENCE_KEYWORDS = [
    "experience", "employment", "work history", "career", "professional background",
    "positions held", "work experience", "professional experience",
]
SKILLS_SECTION_KEYWORDS = [
    "skills", "technical skills", "technologies", "tools", "competencies",
    "expertise", "stack", "core skills", "key skills",
]


def is_likely_cv_regex(parsed: dict) -> bool:
    signals = 0
    if parsed.get("email"):
        signals += 2
    if parsed.get("phone"):
        signals += 1
    if parsed.get("skills"):
        signals += 2
    if parsed.get("experience"):
        signals += 2
    if parsed.get("education"):
        signals += 2
    text = (parsed.get("raw_text") or "").lower()
    if len(text.split()) < 30:
        return False
    cv_hints = [
        "experience", "education", "skills", "work", "university", "degree",
        "developer", "engineer", "manager", "analyst", "resume", "cv",
    ]
    for hint in cv_hints:
        if re.search(r'\b' + hint + r'\b', text):
            signals += 1
    return signals >= 4


def _gemini_validate(raw_text: str) -> dict:
    """Returns {"is_cv": bool, "full_name": str|None} in one Gemini call."""
    prompt = (
        "Analyze the following document and return ONLY valid JSON, no markdown.\n\n"
        "Return exactly this structure:\n"
        '{"is_cv": true, "full_name": "John Smith"}\n'
        "or if name not found:\n"
        '{"is_cv": true, "full_name": null}\n\n'
        "Rules:\n"
        "- is_cv must be true if this is a CV/resume, false otherwise\n"
        "- full_name must be the person's real name, NOT section headings like "
        "'Personal Information', 'Biographical Data', 'Կենսագրական Տվյալներ', etc.\n"
        "- Names can be in ANY language (English, Armenian, Russian, etc.) — Armenian names are valid person names.\n"
        "- If the document starts with a section heading in any language, skip it and look for the actual name.\n"
        "- If you cannot find a real person name, set full_name to null\n\n"
        "Valid name examples: John Smith, Narek Petrosyan, Armen Hovhannisyan, Anna Grigoryan, Անի Առաքելյան\n"
        "DOCUMENT:\n"
        + raw_text[:4000]
    )
    try:
        text = llm_generate(prompt, fast=True)
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        data = json.loads(text)
        name = data.get("full_name")
        if isinstance(name, str) and name.strip().lower() in ("null", "none", "n/a", ""):
            name = None
        logger.info(f"_gemini_validate result: is_cv={data.get('is_cv')}, name={name!r}")
        return {"is_cv": bool(data.get("is_cv")), "full_name": name}
    except Exception as e:
        logger.warning(f"_gemini_validate failed: {e}")
        return {"is_cv": True, "full_name": None}  # fail open — background task will enrich later


def is_likely_cv(parsed: dict) -> tuple:
    """Returns (is_cv: bool, full_name: str|None)."""
    if not is_likely_cv_regex(parsed):
        return False, None
    result = _gemini_validate(parsed.get("raw_text", ""))
    name = result["full_name"]
    if not name:
        name = extract_name(parsed.get("raw_text", ""))
    return result["is_cv"], name


def detect_language(text: str) -> str:
    armenian_chars = set('abcdefghijklmnopqrstuvwxyz')
    # simple heuristic: if few latin chars relative to total, likely non-latin
    latin_count = sum(1 for c in text.lower() if c in armenian_chars)
    return 'en' if latin_count > len(text) * 0.3 else 'hy'


def extract_text_from_pdf(file_bytes: bytes) -> str:
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    pages_text = []

    for page in doc:
        blocks = page.get_text("blocks")
        # Keep only text blocks (type 0) with content
        text_blocks = [b for b in blocks if b[6] == 0 and b[4].strip()]
        if not text_blocks:
            continue

        page_width = page.rect.width
        # Detect columns: check if blocks cluster on both left and right halves
        left = [b for b in text_blocks if b[0] < page_width * 0.45]
        right = [b for b in text_blocks if b[0] >= page_width * 0.45]
        is_two_column = len(left) >= 2 and len(right) >= 2

        if is_two_column:
            left_sorted  = sorted(left,  key=lambda b: b[1])
            right_sorted = sorted(right, key=lambda b: b[1])
            ordered = left_sorted + right_sorted
        else:
            ordered = sorted(text_blocks, key=lambda b: (b[1], b[0]))

        pages_text.append("\n".join(b[4].strip() for b in ordered))

    return "\n\n".join(pages_text)


def extract_text_from_docx(file_bytes: bytes) -> str:
    import io
    from docx.oxml.ns import qn

    doc = docx.Document(io.BytesIO(file_bytes))
    parts = []

    for element in doc.element.body:
        tag = element.tag.split('}')[-1] if '}' in element.tag else element.tag

        if tag == 'p':
            text = ''.join(node.text or '' for node in element.iter() if node.tag.endswith('}t'))
            if text.strip():
                parts.append(text.strip())
        elif tag == 'tbl':
            for row in element.iter(qn('w:tr')):
                cells = []
                for cell in row.iter(qn('w:tc')):
                    cell_text = ''.join(
                        node.text or '' for node in cell.iter() if node.tag.endswith('}t')
                    )
                    if cell_text.strip():
                        cells.append(cell_text.strip())
                if cells:
                    parts.append(' | '.join(cells))

    return '\n'.join(parts)


def extract_email(text: str):
    match = re.findall(r"[\w\.-]+@[\w\.-]+\.\w+", text)
    return match[0] if match else None


def extract_phone(text: str):
    match = re.findall(r"[\+\(]?[0-9][0-9\s\-\(\)]{7,}[0-9]", text)
    return match[0] if match else None


def extract_skills(text: str):
    found = set()
    text_lower = text.lower()

    for skill in SKILLS_KEYWORDS:
        pattern = r'(?<!\w)' + re.escape(skill.lower()) + r'(?!\w)'
        if re.search(pattern, text_lower):
            found.add(skill)

    lines = text.split('\n')
    in_section = False
    all_other_headers = EDUCATION_KEYWORDS + EXPERIENCE_KEYWORDS + [
        "summary", "objective", "references", "certifications", "projects", "languages",
    ]

    for line in lines:
        stripped = line.strip()
        lower = stripped.lower()

        if any(kw in lower for kw in SKILLS_SECTION_KEYWORDS) and len(stripped) < 60:
            in_section = True
            continue

        if in_section:
            if not stripped:
                continue
            if any(kw in lower for kw in all_other_headers) and len(stripped) < 60:
                break
            for part in re.split(r'[,;|]+', stripped):
                part = part.strip().strip('-').strip()
                if part and 1 < len(part) < 50 and re.search(r'[a-zA-Z]', part):
                    found.add(part)

    # Deduplicate case-insensitively, preferring mixed-case over all-lowercase
    deduped = {}
    for skill in found:
        key = skill.lower()
        if key not in deduped or (skill != skill.lower() and deduped[key] == deduped[key].lower()):
            deduped[key] = skill
    return list(deduped.values())


_NAME_BLACKLIST = {
    # English section headers
    "resume", "curriculum vitae", "cv", "profile", "summary", "objective",
    "personal information", "personal details", "contact", "contact information",
    "skills", "experience", "education", "references", "certifications", "projects",
    # Armenian section headers
    "կենսագրական տվյալներ", "անձնական տվյալներ", "կրթություն", "փորձ",
    "հմտություններ", "կապ", "ծանոթություններ", "նախագծեր", "ամփոփում",
}

def extract_name(text: str, original_text: str = None):
    doc = nlp(text[:500])
    for ent in doc.ents:
        if ent.label_ == "PERSON":
            return ent.text

    source = original_text or text
    lines = [l.strip() for l in source.split("\n") if l.strip()]
    for i, line in enumerate(lines):
        if not (2 < len(line) < 60):
            continue
        if "@" in line or re.match(r'^[\d\s\+\-\(\)]+$', line):
            continue
        if line.lower() in _NAME_BLACKLIST:
            continue
        # Skip lines that look like "Label: value" (section field labels)
        if re.search(r':\s*\S', line):
            continue
        # Skip lines where any of the next 3 lines look like label:value pairs —
        # that pattern means this line is a section heading above a form, not a name
        next_lines = lines[i + 1: i + 4]
        if any(re.search(r':\s*\S', nl) for nl in next_lines):
            continue
        return line
    return None


def extract_section(text: str, section_keywords: list) -> str:
    lines = text.split("\n")
    section_lines = []
    in_section = False

    all_section_headers = (
        EDUCATION_KEYWORDS + EXPERIENCE_KEYWORDS +
        ["skills", "summary", "objective", "references", "certifications", "projects"]
    )

    for line in lines:
        line_lower = line.strip().lower()

        if any(kw in line_lower for kw in section_keywords) and len(line.strip()) < 50:
            in_section = True
            continue

        if in_section and line.strip() and len(line.strip()) < 50:
            if any(kw in line_lower for kw in all_section_headers) and not any(kw in line_lower for kw in section_keywords):
                break

        if in_section and line.strip():
            section_lines.append(line.strip())

    return " | ".join(section_lines[:10]) if section_lines else None


def build_embedding_text(parsed: dict) -> str:
    """Build focused text for embedding from structured CV fields."""
    parts = []
    if parsed.get("skills"):
        parts.append("Skills: " + ", ".join(parsed["skills"]))
    if parsed.get("experience"):
        parts.append("Experience: " + str(parsed["experience"]))
    if parsed.get("education"):
        parts.append("Education: " + str(parsed["education"]))
    if not parts:
        return parsed.get("raw_text", "")
    return " ".join(parts)


def _gemini_parse(raw_text: str) -> dict:
    """Step 1: Ask Gemini to extract structured CV fields from raw text."""
    prompt = (
        "You are a CV parser. Extract information from this CV and return ONLY valid JSON, "
        "no markdown, no explanation.\n\n"
        "Return this exact structure:\n"
        '{\n'
        '  "full_name": "candidate full name or null",\n'
        '  "email": "email address or null",\n'
        '  "phone": "phone number or null",\n'
        '  "skills": ["list of ALL technical skills, tools, frameworks, languages, '
        'databases, cloud platforms the candidate actually has"],\n'
        '  "education": "education background as a single descriptive string (degree, institution, year), or null",\n'
        '  "experience": "work experience as a single string (companies, roles, date ranges), or null"\n'
        '}\n\n'
        "Rules:\n"
        "- Only include skills the candidate demonstrably has, not things they want to learn\n"
        "- If a field is not found use null\n"
        "- The CV may be in English or Armenian - handle both\n"
        "- Preserve the original casing of skill names (e.g. 'Python' not 'python', 'REST API' not 'rest api', '.NET' not '.net')\n\n"
        "CV TEXT:\n"
        + raw_text[:8000]
    )

    import time
    last_err = None
    for attempt in range(5):
        try:
            text = llm_generate(prompt, fast=True)
            text = re.sub(r'^```(?:json)?\s*', '', text)
            text = re.sub(r'\s*```$', '', text)
            data = json.loads(text)
            return {
                "full_name": data.get("full_name"),
                "email": data.get("email"),
                "phone": data.get("phone"),
                "skills": data.get("skills") or [],
                "education": data.get("education"),
                "experience": data.get("experience"),
            }
        except Exception as e:
            last_err = e
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                wait = 5 * (attempt + 1)
                logger.warning(f"Gemini rate limited during CV parse, retrying in {wait}s (attempt {attempt+1}/5)")
                time.sleep(wait)
            else:
                break
    logger.warning(f"Gemini CV parse failed: {last_err}")
    return {"full_name": None, "email": None, "phone": None,
            "skills": [], "education": None, "experience": None}


def parse_cv_fast(file_bytes: bytes, filename: str) -> dict:
    """Fast regex-only parse — no Gemini call. Used on upload for instant response.
    Gemini enrichment happens lazily at match time."""
    if filename.endswith(".pdf"):
        raw_text = extract_text_from_pdf(file_bytes)
    elif filename.endswith(".docx"):
        raw_text = extract_text_from_docx(file_bytes)
    else:
        raw_text = file_bytes.decode("utf-8", errors="ignore")

    return {
        "full_name": None,
        "email": extract_email(raw_text),
        "phone": extract_phone(raw_text),
        "skills": extract_skills(raw_text),
        "education": extract_section(raw_text, EDUCATION_KEYWORDS),
        "experience": extract_section(raw_text, EXPERIENCE_KEYWORDS),
        "raw_text": raw_text,
    }


def parse_cv(file_bytes: bytes, filename: str) -> dict:
    if filename.endswith(".pdf"):
        raw_text = extract_text_from_pdf(file_bytes)
    elif filename.endswith(".docx"):
        raw_text = extract_text_from_docx(file_bytes)
    else:
        raw_text = file_bytes.decode("utf-8", errors="ignore")

    gemini = _gemini_parse(raw_text)

    # Regex fallback for email/phone in case Gemini missed them
    email = gemini["email"] or extract_email(raw_text)
    phone = gemini["phone"] or extract_phone(raw_text)

    return {
        "full_name": gemini["full_name"],
        "email": email,
        "phone": phone,
        "skills": gemini["skills"],
        "education": gemini["education"],
        "experience": gemini["experience"],
        "raw_text": raw_text,
    }
