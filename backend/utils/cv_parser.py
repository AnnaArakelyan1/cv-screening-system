import fitz  # PyMuPDF
import docx
import re
import spacy

nlp = spacy.load("en_core_web_sm")

SKILLS_KEYWORDS = [
    "python", "java", "javascript", "react", "fastapi", "django", "sql",
    "postgresql", "docker", "machine learning", "deep learning", "nlp",
    "data analysis", "tensorflow", "pytorch", "aws", "git", "html", "css",
    "node.js", "typescript", "mongodb", "redis", "kubernetes", "c++", "c#",
    "scikit-learn", "pandas", "numpy", "matplotlib", "rest api", "fastapi"
]

EDUCATION_KEYWORDS = ["education", "academic", "qualification", "degree", "university", "college", "bachelor", "master", "phd"]
EXPERIENCE_KEYWORDS = ["experience", "employment", "work history", "career", "professional background", "positions held"]

def extract_text_from_pdf(file_bytes: bytes) -> str:
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    return "\n".join(page.get_text() for page in doc)

def extract_text_from_docx(file_bytes: bytes) -> str:
    import io
    doc = docx.Document(io.BytesIO(file_bytes))
    return "\n".join(para.text for para in doc.paragraphs)

def extract_email(text: str):
    match = re.findall(r"[\w\.-]+@[\w\.-]+\.\w+", text)
    return match[0] if match else None

def extract_phone(text: str):
    match = re.findall(r"[\+\(]?[0-9][0-9\s\-\(\)]{7,}[0-9]", text)
    return match[0] if match else None

def extract_skills(text: str):
    text_lower = text.lower()
    return [skill for skill in SKILLS_KEYWORDS if skill in text_lower]

def extract_name(text: str):
    doc = nlp(text[:500])
    for ent in doc.ents:
        if ent.label_ == "PERSON":
            return ent.text
    return None

def extract_section(text: str, section_keywords: list, next_section_keywords: list) -> str:
    """Extract a section from CV text based on section headers."""
    lines = text.split("\n")
    section_lines = []
    in_section = False

    all_section_headers = EDUCATION_KEYWORDS + EXPERIENCE_KEYWORDS + ["skills", "summary", "objective", "references", "certifications", "projects"]

    for line in lines:
        line_lower = line.strip().lower()

        # Check if this line is the start of our target section
        if any(kw in line_lower for kw in section_keywords) and len(line.strip()) < 50:
            in_section = True
            continue

        # Check if this line is the start of another section (stop collecting)
        if in_section and line.strip() and len(line.strip()) < 50:
            if any(kw in line_lower for kw in all_section_headers) and not any(kw in line_lower for kw in section_keywords):
                break

        if in_section and line.strip():
            section_lines.append(line.strip())

    return " | ".join(section_lines[:10]) if section_lines else None  # limit to 10 lines

def parse_cv(file_bytes: bytes, filename: str) -> dict:
    if filename.endswith(".pdf"):
        text = extract_text_from_pdf(file_bytes)
    elif filename.endswith(".docx"):
        text = extract_text_from_docx(file_bytes)
    else:
        text = file_bytes.decode("utf-8", errors="ignore")

    education = extract_section(text, EDUCATION_KEYWORDS, EXPERIENCE_KEYWORDS)
    experience = extract_section(text, EXPERIENCE_KEYWORDS, EDUCATION_KEYWORDS)

    return {
        "full_name": extract_name(text),
        "email": extract_email(text),
        "phone": extract_phone(text),
        "skills": extract_skills(text),
        "education": education,
        "experience": experience,
        "raw_text": text,
    }