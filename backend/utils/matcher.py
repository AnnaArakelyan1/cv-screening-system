import re
import json
import logging
import numpy as np
from google import genai
from sentence_transformers import SentenceTransformer
from config import settings

logger = logging.getLogger(__name__)

_gemini_client = genai.Client(api_key=settings.GOOGLE_API_KEY)

_model = None

def get_model():
    global _model
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

    # Words meaning "present" across languages/styles
    PRESENT_WORDS = {
        "present", "current", "now", "ongoing", "till date", "to date",
        "ներկա", "մինչ օրս", "առ այսօր",
    }
    present_pattern = "|".join(re.escape(w) for w in PRESENT_WORDS)

    # Pattern 1: date ranges  2021–2024 / 2021 - present / 2021–ներկա
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

    # Pattern 3: earliest year mentioned → rough estimate
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
  "matched_skills": ["skills the candidate has that match job requirements"],
  "missing_skills": ["important required skills the candidate lacks"],
  "experience_match": "exceeds" | "meets" | "below" | "unknown",
  "education_match": "exceeds" | "meets" | "below" | "unknown",
  "summary": "2-3 sentence honest assessment of this candidate for this role"
}}

Scoring guide: 70-100 = strong match, 40-69 = moderate, 0-39 = weak.

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
            response = _gemini_client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=prompt,
                config={"temperature": 0},
            )
            text = response.text.strip()
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