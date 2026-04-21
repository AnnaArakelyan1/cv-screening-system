import fitz  # PyMuPDF
import docx
import re
import spacy

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
    "education", "academic", "qualification", "degree", "university", "college", "bachelor", "master", "phd",
    "կրթություն", "կրթ", "բակալավր", "մագիստր", "դիպլոմ", "համալսարան",
]
EXPERIENCE_KEYWORDS = [
    "experience", "employment", "work history", "career", "professional background", "positions held",
    "աշխատանքային փորձ", "աշխատանք", "փորձ",
]
SKILLS_SECTION_KEYWORDS = [
    "skills", "technical skills", "technologies", "tools", "competencies", "expertise", "stack",
    "հմտություններ", "հմտ",
]

def is_likely_cv(parsed: dict) -> bool:
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
        "աշխատանք", "կրթություն", "հմտություններ", "փորձ",
    ]
    for hint in cv_hints:
        if hint in text:
            signals += 1
    return signals >= 4

def detect_language(text: str) -> str:
    """Detect if text contains Armenian characters."""
    armenian_chars = set('աբգդեզէըթժիլխծկհձղճմյնշոչպջռսվտրցւփքօֆ')
    text_lower = text.lower()
    armenian_count = sum(1 for c in text_lower if c in armenian_chars)
    return 'hy' if armenian_count > 20 else 'en'



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
    found = set()
    text_lower = text.lower()

    # 1. Match known keywords
    for skill in SKILLS_KEYWORDS:
        if skill.lower() in text_lower:
            found.add(skill)

    # 2. Extract anything listed in a dedicated skills section
    lines = text.split('\n')
    in_section = False
    all_other_headers = EDUCATION_KEYWORDS + EXPERIENCE_KEYWORDS + [
        "summary", "objective", "references", "certifications", "projects",
        "languages", "ամփոփում", "նախագծեր",
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
            for part in re.split(r'[,;|•·]+', stripped):
                part = part.strip().strip('-').strip()
                if part and 1 < len(part) < 50 and re.search(r'[a-zA-Z]', part):
                    found.add(part)

    return list(found)

# def extract_name(text: str):
#     doc = nlp(text[:500])
#     for ent in doc.ents:
#         if ent.label_ == "PERSON":
#             return ent.text
#     return None

def extract_name(text: str, original_text: str = None):
    # Նախ փորձենք spaCy-ով (translated text-ի վրա)
    doc = nlp(text[:500])
    for ent in doc.ents:
        if ent.label_ == "PERSON":
            return ent.text
    
    # Եթե չգտավ, վերցնենք original text-ի առաջին non-empty տողը
    if original_text:
        for line in original_text.split("\n"):
            line = line.strip()
            # Բաց թողնենք email, phone, կարճ տողեր
            if line and len(line) > 2 and len(line) < 60:
                if "@" not in line and not re.match(r'^[\d\s\+\-\(\)]+$', line):
                    return line
    return None

# SKILL_EMBEDDINGS = {
#     "python": model.encode("python programming"),
#     "machine learning": model.encode("machine learning ML AI"),
#     "javascript": model.encode("javascript JS frontend")
    
# }

# def extract_skills_semantic(text: str):
#     text_embedding = model.encode(text)
#     found_skills = []
#     for skill, skill_emb in SKILL_EMBEDDINGS.items():
#         similarity = cosine_similarity(text_embedding, skill_emb)
#         if similarity > 0.6: 
#             found_skills.append(skill)
#     return found_skills




def extract_section(text: str, section_keywords: list, next_section_keywords: list) -> str:
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

# def parse_cv(file_bytes: bytes, filename: str) -> dict:
#     if filename.endswith(".pdf"):
#         raw_text = extract_text_from_pdf(file_bytes)
#     elif filename.endswith(".docx"):
#         raw_text = extract_text_from_docx(file_bytes)
#     else:
#         raw_text = file_bytes.decode("utf-8", errors="ignore")


#     lang = detect_language(raw_text)
#     if lang == 'hy':
#         parsed_text = translate_to_english(raw_text)
#     else:
#         parsed_text = raw_text


#     email = extract_email(raw_text)
#     phone = extract_phone(raw_text)

#     name = extract_name(parsed_text, original_text=raw_text)
#     skills = extract_skills(parsed_text)
#     education = extract_section(parsed_text, EDUCATION_KEYWORDS, EXPERIENCE_KEYWORDS)
#     experience = extract_section(parsed_text, EXPERIENCE_KEYWORDS, EDUCATION_KEYWORDS)

#     return {
#         "full_name": name,
#         "email": email,
#         "phone": phone,
#         "skills": skills,
#         "education": education,
#         "experience": experience,
#         "raw_text": parsed_text,  
#     }


def parse_cv(file_bytes: bytes, filename: str) -> dict:
    if filename.endswith(".pdf"):
        raw_text = extract_text_from_pdf(file_bytes)
    elif filename.endswith(".docx"):
        raw_text = extract_text_from_docx(file_bytes)
    else:
        raw_text = file_bytes.decode("utf-8", errors="ignore")

    # Translation հանել - multilingual model-ն ուղղակի հայերեն կհասկանա
    email = extract_email(raw_text)
    phone = extract_phone(raw_text)
    name = extract_name(raw_text, original_text=raw_text)  # raw_text-ով
    skills = extract_skills(raw_text)
    education = extract_section(raw_text, EDUCATION_KEYWORDS, EXPERIENCE_KEYWORDS)
    experience = extract_section(raw_text, EXPERIENCE_KEYWORDS, EDUCATION_KEYWORDS)

    return {
        "full_name": name,
        "email": email,
        "phone": phone,
        "skills": skills,
        "education": education,
        "experience": experience,
        "raw_text": raw_text,  # հայերեն տեքստը ուղղակի
    }