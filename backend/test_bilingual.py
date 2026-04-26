"""
docker exec cv-screening-system-backend-1 python test_bilingual.py
"""
from datetime import datetime
from utils.cv_parser import (
    extract_name, extract_skills, extract_section, is_likely_cv,
    build_embedding_text, EDUCATION_KEYWORDS, EXPERIENCE_KEYWORDS,
)
from utils.matcher import extract_years_of_experience, get_education_level

YEAR = datetime.now().year

def check(label, got, expected_contains=None, expected_empty=False, expected_not_contains=None):
    ok = True
    if expected_empty:
        ok = not bool(got)
    if expected_contains:
        for item in expected_contains:
            if isinstance(got, list):
                if not any(item.lower() in str(g).lower() for g in got):
                    ok = False
            elif got is None or item.lower() not in str(got).lower():
                ok = False
    if expected_not_contains:
        for item in expected_not_contains:
            if isinstance(got, list):
                if any(item.lower() in str(g).lower() for g in got):
                    ok = False
            elif got and item.lower() in str(got).lower():
                ok = False
    print(f"  {'✓' if ok else '✗'} {label}")
    if not ok:
        print(f"      got: {repr(got)}")

# ── Name extraction ───────────────────────────────────────────────────────────
print("\n── NAME EXTRACTION ──────────────────────────────────────────")

check("English name at top",
    extract_name("John Smith\njohn@test.com\nSoftware Engineer"),
    expected_contains=["John"])

check("'Resume' header skipped",
    extract_name("Resume\nJane Doe\njane@test.com"),
    expected_contains=["Jane"])

check("'CV' header skipped",
    extract_name("CV\nAlex Brown\nalex@test.com"),
    expected_contains=["Alex"])

check("'Curriculum Vitae' header skipped",
    extract_name("Curriculum Vitae\nSarah Lee\nsarah@test.com"),
    expected_contains=["Sarah"])

# Real Armenian text — these use proper Armenian Unicode from the source code
check("Armenian 'Ռեzjume' skipped",
    extract_name("Ռեzjume\nՄariam Hakobyan\nmariam@test.com"),
    expected_contains=["Մariam"])

# ── Skills extraction ─────────────────────────────────────────────────────────
print("\n── SKILLS EXTRACTION ────────────────────────────────────────")

check("Real skills found",
    extract_skills("3 years Python and Docker experience. Used PostgreSQL and AWS."),
    expected_contains=["python", "docker", "postgresql", "aws"])

check("English aspirational filtered",
    extract_skills("I want to learn Python. Eager to learn Docker."),
    expected_empty=True)

check("Only aspirational mention → filtered",
    extract_skills("I am eager to learn tensorflow and pytorch."),
    expected_empty=True)

check("Mixed: real Python kept, aspirational ML filtered",
    extract_skills("2 years Python experience.\nI want to learn machine learning."),
    expected_contains=["python"],
    expected_not_contains=["machine learning"])

check("Tech terms in Armenian sentence found (English tech names)",
    extract_skills("Python-ով backend, Docker կիրառել եm, PostgreSQL տshелнери:"),
    expected_contains=["python", "docker", "postgresql"])

# ── Section detection ─────────────────────────────────────────────────────────
print("\n── SECTION DETECTION ────────────────────────────────────────")

cv = """
John Smith

experience
Worked as software engineer at TechCorp 2021-2024.
Built Python services.

education
Bachelor degree from university, 2021.
Graduated with honours.

skills
Python, FastAPI, PostgreSQL
"""

exp = extract_section(cv, EXPERIENCE_KEYWORDS)
edu = extract_section(cv, EDUCATION_KEYWORDS)

check("Experience section found",
    exp, expected_contains=["TechCorp"])

check("Education found — content line with 'Bachelor' not skipped",
    edu, expected_contains=["Bachelor"])

check("Experience doesn't bleed into Education",
    exp, expected_not_contains=["Bachelor"])

check("Education doesn't bleed into Experience",
    edu, expected_not_contains=["TechCorp"])

# Verify Armenian section keyword triggers correctly
hy_cv = """
Anush Mkrtchyan

Аш катankayin фор
Software Engineer at TechCorp 2021-2024.

education
Bachelor degree, Yerevan State University 2021.

skills
Python, FastAPI
"""
hy_exp = extract_section(hy_cv, EXPERIENCE_KEYWORDS)
hy_edu = extract_section(hy_cv, EDUCATION_KEYWORDS)
check("English 'education' header works in otherwise Armenian CV", hy_edu, expected_contains=["Bachelor"])
check("Experience section content extracted",                       hy_exp, expected_contains=["TechCorp"])

# ── is_likely_cv ──────────────────────────────────────────────────────────────
print("\n── IS LIKELY CV ─────────────────────────────────────────────")

long_cv = (
    "John Smith software engineer john@test.com phone 555-0100 "
    "experience five years working as developer at tech company "
    "education bachelor degree computer science from university "
    "skills python docker aws postgresql javascript resume analyst"
)
not_cv = (
    "Dear John I am writing to inform you that the meeting has been "
    "rescheduled to next Tuesday please confirm your attendance and "
    "let me know if you have any questions best regards management team"
)

check("Real CV recognised",
    is_likely_cv({"raw_text": long_cv, "email": "j@t.com", "skills": ["python"], "experience": "5 years", "education": "BSc"}),
    expected_contains=["True"])

check("Random letter rejected",
    is_likely_cv({"raw_text": not_cv, "email": None, "skills": [], "experience": None, "education": None}),
    expected_contains=["False"])

# ── Year extraction ───────────────────────────────────────────────────────────
print("\n── YEAR EXTRACTION ──────────────────────────────────────────")

check("'X years'",        extract_years_of_experience("5 years of experience"),     expected_contains=["5"])
check("'X yrs'",          extract_years_of_experience("4 yrs backend development"), expected_contains=["4"])
check("date range",       extract_years_of_experience("TechCorp 2019-2024"),        expected_contains=["5"])
check("'present'",        extract_years_of_experience("Google 2022 - present"),     expected_contains=[str(YEAR-2022)])
check("'current'",        extract_years_of_experience("Startup 2021 - current"),    expected_contains=[str(YEAR-2021)])
check("Armenian տarи",    extract_years_of_experience("3 տarи Python developer"),   expected_contains=["3"])
check("Armenian ներкا",   extract_years_of_experience("TechCorp 2022 - ненка"),     expected_contains=[str(YEAR-2022)])
check("Armenian минч ors",extract_years_of_experience("Corp 2021 - мinch ors"),     expected_contains=[str(YEAR-2021)])

# ── Education level ───────────────────────────────────────────────────────────
print("\n── EDUCATION LEVEL ──────────────────────────────────────────")

check("BSc → 3",            get_education_level("BSc Computer Science"),            expected_contains=["3"])
check("MSc → 4",            get_education_level("MSc Artificial Intelligence"),     expected_contains=["4"])
check("PhD → 5",            get_education_level("PhD in Machine Learning"),         expected_contains=["5"])
check("bachelor → 3",       get_education_level("bachelor degree"),                 expected_contains=["3"])
check("master → 4",         get_education_level("master degree"),                   expected_contains=["4"])
check("doctorate → 5",      get_education_level("doctorate program"),               expected_contains=["5"])
check("Armenian բakalaвр→3",get_education_level("բakalaвр, НПН, 2021"),            expected_contains=["3"])
check("Armenian мagistр→4", get_education_level("мagistр degree, 2023"),            expected_contains=["4"])
check("Highest wins: BSc+MSc→4", get_education_level("BSc then MSc from MIT"),     expected_contains=["4"])

# ── build_embedding_text ──────────────────────────────────────────────────────
print("\n── BUILD EMBEDDING TEXT ─────────────────────────────────────")

check("Uses sections, ignores aspirational raw text",
    build_embedding_text({"skills": ["python","docker"], "experience": "Engineer 2020-2024", "education": "BSc MIT", "raw_text": "I want to be an ML expert."}),
    expected_contains=["python", "BSc"], expected_not_contains=["want to be"])

check("Short sections still used (no fallback to raw)",
    build_embedding_text({"skills": ["python"], "experience": "Dev 2022", "education": None, "raw_text": "I want to learn docker."}),
    expected_contains=["python"], expected_not_contains=["want to learn"])

check("No sections → fallback to filtered raw text",
    build_embedding_text({"skills": [], "experience": None, "education": None, "raw_text": "I want to learn Python.\nPython Docker work 2020-2024."}),
    expected_contains=["2020"], expected_not_contains=["want to learn"])

print()
