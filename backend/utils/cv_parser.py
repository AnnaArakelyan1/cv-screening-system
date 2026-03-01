import fitz  # PyMuPDF
import docx
import re
import spacy

nlp = spacy.load("en_core_web_sm")

SKILLS_KEYWORDS = [
    "python", "java", "javascript", "react", "fastapi", "django", "sql",
    "postgresql", "docker", "machine learning", "deep learning", "nlp",
    "data analysis", "tensorflow", "pytorch", "aws", "git", "html", "css",
    "node.js", "typescript", "mongodb", "redis", "kubernetes", "c++", "c#"
]

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

def parse_cv(file_bytes: bytes, filename: str) -> dict:
    if filename.endswith(".pdf"):
        text = extract_text_from_pdf(file_bytes)
    elif filename.endswith(".docx"):
        text = extract_text_from_docx(file_bytes)
    else:
        text = file_bytes.decode("utf-8", errors="ignore")

    return {
        "full_name": extract_name(text),
        "email": extract_email(text),
        "phone": extract_phone(text),
        "skills": extract_skills(text),
        "raw_text": text,
    }