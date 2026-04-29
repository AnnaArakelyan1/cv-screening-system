import re
import json
import logging
import numpy as np
from sentence_transformers import SentenceTransformer
from utils.llm import generate as llm_generate

logger = logging.getLogger(__name__)

import threading
_model = None
_model_lock = threading.Lock()

def get_model():
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                _model = SentenceTransformer("paraphrase-multilingual-mpnet-base-v2")
    return _model



EDUCATION_LEVELS = {
    # ── English keywords ──────────────────────────────────────────
    "high school": 1, "secondary school": 1, "secondary education": 1,
    "associate": 2, "foundation degree": 2,
    "bachelor": 3, "undergraduate": 3, "higher education": 3,
    "master": 4, "msc": 4, "mba": 4, "graduate": 4,
    "phd": 5, "doctorate": 5, "doctoral": 5,
    # ── Degree abbreviations (appear in CVs of any language) ──────
    "b.sc": 3, "bsc": 3, "b.a": 3, "ba ": 3,
    "b.eng": 3, "beng": 3, "b.tech": 3, "btech": 3,
    "m.sc": 4, "msc": 4, "m.a": 4, "m.eng": 4, "m.tech": 4,
    "ph.d": 5, "d.phil": 5,
    # ── Armenian ──────────────────────────────────────────────────
    "բակալավր": 3, "դիպլոմ": 3,
    "մագիստր": 4, "մագիստրատուրա": 4,
    "դոկտոր": 5, "ասպիրանտուրա": 5, "դոկտորանտուրա": 5,
    "միջնակարգ": 1,
    "քոլեջ": 2,
}

def get_embedding(text: str) -> list:
    return get_model().encode(text).tolist()

def cosine_similarity(vec1, vec2) -> float:
    v1 = np.array(vec1)
    v2 = np.array(vec2)
    return float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))

def get_education_level(text: str) -> int:
    """Return the highest education level found in text."""
    if not text:
        return 0
    text_lower = text.lower()
    highest = 0
    for keyword, level in EDUCATION_LEVELS.items():
        if keyword in text_lower:
            highest = max(highest, level)
    return highest

def extract_years_of_experience(text: str) -> int:
    """Extract total years of experience from text.

    Strategy (in priority order):
    1. Sum up date ranges — works in any language since dates are numeric.
    2. Explicit 'X years / X տարի / X yr' mention — language-specific bonus.
    3. Earliest year mentioned to now — rough fallback.
    """
    if not text:
        return 0

    import re
    from datetime import datetime
    current_year = datetime.now().year
    text_lower = text.lower()

    PRESENT_WORDS = {
        "present", "current", "now", "ongoing", "till date", "to date",
        "ներկա", "մինչ օրս", "առ այսօր",
    }
    present_pattern = "|".join(re.escape(w) for w in PRESENT_WORDS)

    ranges = re.findall(
        rf"\b(20\d{{2}})\s*[-–/]\s*(20\d{{2}}|{present_pattern})\b",
        text_lower
    )
    total = 0
    for start, end in ranges:
        start_year = int(start)
        end_year = current_year if end in PRESENT_WORDS else int(end)
        total += max(0, end_year - start_year)

    if total > 0:
        return total

    # Pattern 2: explicit "X years / X yrs / X yr / X տարի / X год / X año"
    # Covers English abbreviations + Armenian + common romanised forms
    explicit = re.findall(
        r"(\d+)\+?\s*(?:years?|yrs?|տարի|год(?:а|ов)?|años?|anni?|jahre?)",
        text_lower
    )
    if explicit:
        return max(int(m) for m in explicit)

    years_found = re.findall(r"\b(20\d{2})\b", text)
    if years_found:
        earliest = min(int(y) for y in years_found)
        return max(0, current_year - earliest)

    return 0

def calculate_match_score(
    candidate_embedding: list,
    job_embedding: list,
    candidate_experience_text: str = None,
    candidate_education_text: str = None,
    required_experience_years: int = 0,
    required_education: str = None,
) -> dict:
    # 1. Semantic similarity (weight: 70%)
    semantic_score = cosine_similarity(candidate_embedding, job_embedding) * 100
    semantic_weighted = semantic_score * 0.70

    # 2. Experience score (weight: 20%)
    candidate_years = extract_years_of_experience(candidate_experience_text or "")
    if required_experience_years and required_experience_years > 0:
        if candidate_years >= required_experience_years:
            experience_score = 100
        elif candidate_years == 0:
            experience_score = 0
        else:
            experience_score = (candidate_years / required_experience_years) * 100
    else:
        experience_score = 100  # no requirement = full score
    experience_weighted = experience_score * 0.20

    # 3. Education score (weight: 10%)
    candidate_edu_level = get_education_level(candidate_education_text or "")
    required_edu_level = get_education_level(required_education or "")
    if required_edu_level == 0:
        education_score = 100  # no requirement = full score
    elif candidate_edu_level >= required_edu_level:
        education_score = 100
    elif candidate_edu_level == 0:
        education_score = 0
    else:
        education_score = (candidate_edu_level / required_edu_level) * 100
    education_weighted = education_score * 0.10

    # Final score
    final_score = semantic_weighted + experience_weighted + education_weighted

    return {
        "final_score": round(final_score, 2),
        "semantic_score": round(semantic_score, 2),
        "experience_score": round(experience_score, 2),
        "education_score": round(education_score, 2),
        "candidate_years": candidate_years,
    }

def cluster_candidates(embeddings, n_clusters=3):
    from sklearn.cluster import KMeans

    if len(embeddings) < n_clusters:
        n_clusters = len(embeddings)

    matrix = np.array(embeddings)
    kmeans = KMeans(n_clusters=n_clusters, random_state=42)
    return kmeans.fit_predict(matrix).tolist()


def match_cv_with_gemini(
    cv_data: dict,
    job_title: str,
    job_description: str,
    required_skills: list,
    required_experience_years: int = 0,
    required_education: str = None,
) -> dict:
    """Step 2: CV JSON + Job details → Gemini → match score and analysis."""
    candidate_skills = ", ".join(cv_data.get("skills") or []) or "not specified"
    candidate_experience = cv_data.get("experience") or "not specified"
    candidate_education = cv_data.get("education") or "not specified"
    raw_text = cv_data.get("raw_text") or ""

    has_structured_data = (
        candidate_skills != "not specified" or
        candidate_experience != "not specified" or
        candidate_education != "not specified"
    )
    required_skills_str = ", ".join(required_skills) if required_skills else "not specified"
    req_exp = f"{required_experience_years} years" if required_experience_years else "not specified"
    req_edu = required_education or "not specified"

    if has_structured_data:
        candidate_section = f"""Skills: {candidate_skills}
Experience: {candidate_experience}
Education: {candidate_education}"""
    else:
        candidate_section = f"""CV TEXT (extract skills, experience and education from this):
{raw_text[:6000]}"""

    prompt = f"""You are an expert HR recruiter. Analyze how well this candidate matches the job and return ONLY valid JSON, no markdown, no explanation.

Return this exact structure:
{{
  "score": <integer 0-100>,
  "matched_skills": ["only skills that appear in BOTH the candidate profile AND the required skills list"],
  "missing_skills": ["important required skills the candidate lacks"],
  "experience_match": "exceeds" | "meets" | "below" | "unknown",
  "education_match": "exceeds" | "meets" | "below" | "unknown",
  "summary": "2-3 sentence honest assessment of this candidate for this role, written in English, no repeated sentences"
}}

Scoring guide (be strict):
- 80-100: candidate has most or all required skills, sufficient experience, meets education
- 60-79: candidate has more than half the required skills with relevant experience
- 40-59: candidate has some relevant skills but is missing several key requirements
- 20-39: candidate has few required skills, significant gaps in experience or domain
- 0-19: candidate is clearly unqualified for this role
Missing core required skills must heavily penalize the score. Do not inflate scores based on general programming knowledge alone.

JOB POSTING:
Title: {job_title}
Description: {job_description}
Required Skills: {required_skills_str}
Required Experience: {req_exp}
Required Education: {req_edu}

CANDIDATE PROFILE:
{candidate_section}"""

    import time
    last_err = None
    for attempt in range(5):
        try:
            text = llm_generate(prompt)
            text = re.sub(r'^```(?:json)?\s*', '', text)
            text = re.sub(r'\s*```$', '', text)
            data = json.loads(text)
            return {
                "score": max(0, min(100, int(data.get("score", 0)))),
                "matched_skills": data.get("matched_skills") or [],
                "missing_skills": data.get("missing_skills") or [],
                "experience_match": data.get("experience_match", "unknown"),
                "education_match": data.get("education_match", "unknown"),
                "summary": data.get("summary", ""),
            }
        except Exception as e:
            last_err = e
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                wait = 15 * (attempt + 1)
                logger.warning(f"Gemini rate limited, retrying in {wait}s (attempt {attempt+1}/5)")
                time.sleep(wait)
            else:
                break
    logger.warning(f"Gemini match failed: {last_err}")
    return {
        "score": 0,
        "matched_skills": [],
        "missing_skills": [],
        "experience_match": "unknown",
        "education_match": "unknown",
        "summary": "Analysis unavailable.",
    }


def parse_and_match(
    raw_text: str,
    job_title: str,
    job_description: str,
    required_skills: list,
    required_experience_years: int = 0,
    required_education: str = None,
) -> dict:
    """Single Gemini call: parse CV + score match. Returns combined result."""
    req_skills_str = ", ".join(required_skills) if required_skills else "not specified"
    req_exp = f"{required_experience_years} years" if required_experience_years else "not specified"
    req_edu = required_education or "not specified"

    prompt = f"""You are a CV parser and HR recruiter. Given this CV and job posting, extract CV info AND score the match in a single response.

Return ONLY valid JSON, no markdown, no explanation:
{{
  "full_name": "candidate's personal given+family name (may be in Armenian, Russian, or any language) — NOT section headings like 'Biographical Data' or 'Personal Information' — or null if not found",
  "email": "email address or null",
  "phone": "phone number or null",
  "skills": ["list of technical skills the candidate has, preserve original casing"],
  "education": "education background as a single string or null",
  "experience": "work experience as a single string or null",
  "match_score": <integer 0-100>,
  "matched_skills": ["skills that appear in BOTH the required skills list AND are explicitly mentioned in the CV text — do NOT include a skill unless it is clearly written in the CV"],
  "missing_skills": ["required skills that are NOT found anywhere in the CV text"],
  "experience_match": "exceeds" | "meets" | "below" | "unknown",
  "education_match": "exceeds" | "meets" | "below" | "unknown",
  "summary": "2-3 sentence honest assessment of this candidate for this role, written in English, no repeated sentences"
}}

STRICT RULES for matched_skills and missing_skills:
- A skill is matched ONLY if the exact skill or a clear synonym appears in the CV text
- If a required skill is not written anywhere in the CV, it MUST go in missing_skills, not matched_skills
- Do not infer or assume skills that are not stated
- Python listed in CV + Python required = matched. Machine learning NOT in CV + machine learning required = missing.

Scoring guide (be strict):
- 80-100: candidate has most or all required skills, sufficient experience, meets education
- 60-79: candidate has more than half the required skills with relevant experience
- 40-59: candidate has some relevant skills but is missing several key requirements
- 20-39: candidate has few required skills, significant gaps in experience or domain
- 0-19: candidate is clearly unqualified for this role
IMPORTANT: Score is based primarily on required skills coverage.
- If the candidate is missing more than half the required skills, the score MUST be below 40.
- If the candidate is missing ALL of the domain-specific required skills (e.g. all ML skills for an ML role), the score MUST be below 30, regardless of experience or education.
- General programming knowledge (knowing Python alone) does NOT compensate for missing domain skills.
- Do not inflate scores. A backend developer applying for an ML role with no ML skills should score 15-25.

JOB POSTING:
Title: {job_title}
Description: {job_description}
Required Skills: {req_skills_str}
Required Experience: {req_exp}
Required Education: {req_edu}

CV TEXT:
{raw_text[:12000]}"""

    import time
    last_err = None
    for attempt in range(5):
        try:
            text = llm_generate(prompt)
            text = re.sub(r'^```(?:json)?\s*', '', text)
            text = re.sub(r'\s*```$', '', text)
            data = json.loads(text)
            req_lower = {s.lower() for s in required_skills}
            raw_matched = data.get("matched_skills") or []
            raw_text_lower = raw_text.lower()
            matched = [
                s for s in raw_matched
                if s.lower() in req_lower
                and s.lower() in raw_text_lower
            ]
            return {
                "full_name": data.get("full_name"),
                "email": data.get("email"),
                "phone": data.get("phone"),
                "skills": data.get("skills") or [],
                "education": data.get("education"),
                "experience": data.get("experience"),
                "match_score": max(0, min(100, int(data.get("match_score", 0)))),
                "matched_skills": matched,
                "missing_skills": data.get("missing_skills") or [],
                "experience_match": data.get("experience_match", "unknown"),
                "education_match": data.get("education_match", "unknown"),
                "summary": data.get("summary", ""),
            }
        except Exception as e:
            last_err = e
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                wait = 5 * (attempt + 1)
                logger.warning(f"Gemini rate limited during parse+match, retrying in {wait}s (attempt {attempt+1}/5)")
                time.sleep(wait)
            else:
                break
    logger.warning(f"Gemini parse+match failed: {last_err}")
    return {
        "full_name": None, "email": None, "phone": None,
        "skills": [], "education": None, "experience": None,
        "match_score": 0, "matched_skills": [], "missing_skills": [],
        "experience_match": "unknown", "education_match": "unknown",
        "summary": "Analysis unavailable.",
    }