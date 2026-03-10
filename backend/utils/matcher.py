import numpy as np
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("all-MiniLM-L6-v2")

EDUCATION_LEVELS = {
    "high school": 1,
    "associate": 2,
    "bachelor": 3,
    "undergraduate": 3,
    "master": 4,
    "msc": 4,
    "mba": 4,
    "phd": 5,
    "doctorate": 5,
}

def get_embedding(text: str) -> list:
    return model.encode(text).tolist()

def cosine_similarity(vec1, vec2) -> float:
    v1 = np.array(vec1)
    v2 = np.array(vec2)
    return float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))

def get_education_level(text: str) -> int:
    """Return numeric education level from text."""
    if not text:
        return 0
    text_lower = text.lower()
    for keyword, level in EDUCATION_LEVELS.items():
        if keyword in text_lower:
            return level
    return 0

def extract_years_of_experience(text: str) -> int:
    """Extract total years of experience from text."""
    if not text:
        return 0

    import re
    from datetime import datetime
    current_year = datetime.now().year

    # Pattern 1: explicit "X years" mention
    explicit = re.findall(r"(\d+)\+?\s*years?", text.lower())
    if explicit:
        return max(int(m) for m in explicit)

    # Pattern 2: date ranges like (2021-2024) or 2020-2021
    ranges = re.findall(r"\b(20\d{2})\s*[-–]\s*(20\d{2}|present|current)\b", text.lower())
    total = 0
    for start, end in ranges:
        start_year = int(start)
        end_year = current_year if end in ("present", "current") else int(end)
        total += max(0, end_year - start_year)

    if total > 0:
        return total

    # Pattern 3: single year mentions - estimate from earliest year to now
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

def cluster_candidates(candidates, n_clusters=3):
    from sklearn.cluster import KMeans
    import numpy as np

    if len(candidates) < n_clusters:
        n_clusters = len(candidates)

    embeddings = np.array([c.embedding for c in candidates])
    kmeans = KMeans(n_clusters=n_clusters, random_state=42)
    labels = kmeans.fit_predict(embeddings)

    for i, candidate in enumerate(candidates):
        candidate.cluster_id = int(labels[i])

    return candidates