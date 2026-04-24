from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from collections import Counter
from database import get_db
from models.candidate import Candidate
from models.job import Job
from models.application import Application
from models.match_result import MatchResult
from models.user import User
from utils.auth import get_current_user

router = APIRouter()

@router.get("/")
def get_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    total_candidates = db.query(Candidate).count()
    total_jobs = db.query(Job).count()
    open_jobs = db.query(Job).filter(Job.is_open == True).count()
    total_applications = db.query(Application).count()

    applications = db.query(Application).all()
    status_counts = {"accepted": 0, "rejected": 0, "pending": 0}
    for app in applications:
        s = app.status or "pending"
        status_counts[s] = status_counts.get(s, 0) + 1

    jobs = db.query(Job).all()
    match_results_all = db.query(MatchResult).all()
    match_map = {}
    for mr in match_results_all:
        match_map.setdefault(mr.job_id, []).append(mr.match_score)

    candidates_per_job = []
    for job in jobs:
        job_apps = [a for a in applications if a.job_id == job.id]
        accepted = sum(1 for a in job_apps if a.status == "accepted")
        rejected = sum(1 for a in job_apps if a.status == "rejected")
        pending = len(job_apps) - accepted - rejected
        scores = match_map.get(job.id, [])
        avg_score = round(sum(scores) / len(scores), 1) if scores else 0
        candidates_per_job.append({
            "title": job.title[:30] + ("…" if len(job.title) > 30 else ""),
            "full_title": job.title,
            "total_applicants": len(job_apps),
            "accepted": accepted,
            "rejected": rejected,
            "pending": pending,
            "avg_score": avg_score,
            "is_open": job.is_open,
        })

    buckets = [
        {"range": "0–20",  "count": 0},
        {"range": "21–40", "count": 0},
        {"range": "41–60", "count": 0},
        {"range": "61–80", "count": 0},
        {"range": "81–100","count": 0},
    ]
    for mr in match_results_all:
        s = mr.match_score
        if s <= 20:   buckets[0]["count"] += 1
        elif s <= 40: buckets[1]["count"] += 1
        elif s <= 60: buckets[2]["count"] += 1
        elif s <= 80: buckets[3]["count"] += 1
        else:         buckets[4]["count"] += 1

    candidates = db.query(Candidate).all()
    skill_counter = Counter()
    for c in candidates:
        for skill in (c.skills or []):
            skill_counter[skill.strip().lower()] += 1
    top_skills = [{"skill": s, "count": n} for s, n in skill_counter.most_common(12)]

    return {
        "total_candidates": total_candidates,
        "total_jobs": total_jobs,
        "open_jobs": open_jobs,
        "total_applications": total_applications,
        "candidates_per_job": candidates_per_job,
        "applications_by_status": [
            {"status": "Accepted", "count": status_counts.get("accepted", 0), "fill": "#27ae60"},
            {"status": "Pending",  "count": status_counts.get("pending", 0),  "fill": "#f39c12"},
            {"status": "Rejected", "count": status_counts.get("rejected", 0), "fill": "#e74c3c"},
        ],
        "score_distribution": buckets,
        "top_skills": top_skills,
    }
