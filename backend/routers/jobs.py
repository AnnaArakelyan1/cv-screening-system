from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import StreamingResponse
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

def _register_fonts():
    try:
        pdfmetrics.registerFont(TTFont('DejaVu', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'))
        pdfmetrics.registerFont(TTFont('DejaVu-Bold', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'))
        return 'DejaVu', 'DejaVu-Bold', 'DejaVu'
    except Exception:
        return 'Helvetica', 'Helvetica-Bold', 'Helvetica-Oblique'
from sqlalchemy.orm import Session
from database import get_db
from models.job import Job
from models.candidate import Candidate
from models.user import User
from models.match_result import MatchResult
from models.application import Application
from models.job_report import JobReport
from schemas.job import JobCreate, JobUpdate, JobOut
from datetime import datetime, timezone
from utils.auth import get_current_user
from utils.audit import log_action
from utils.matcher import get_embedding
from utils.tasks import enrich_and_match, is_in_progress
from utils.cv_parser import parse_cv_fast, is_likely_cv
from utils.email_sender import send_email
from typing import List
from pathlib import Path
import logging
import uuid

UPLOAD_DIR = Path("/app/uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

router = APIRouter()


@router.post("/", response_model=JobOut)
def create_job(
    job_data: JobCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    embedding = get_embedding(job_data.description + " " + " ".join(job_data.required_skills))
    job = Job(**job_data.model_dump(), embedding=embedding, created_by=current_user.id)
    db.add(job)
    db.commit()
    db.refresh(job)
    log_action(db, current_user, "job_created", {"job_id": job.id, "title": job.title})
    return job

@router.get("/", response_model=List[JobOut])
def get_jobs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    jobs = db.query(Job).all()
    now = datetime.now(timezone.utc)
    changed = False
    for job in jobs:
        if job.is_open and job.deadline and now > job.deadline:
            job.is_open = False
            changed = True
    if changed:
        db.commit()
    return jobs


@router.get("/{job_id}/match")
def match_candidates(
    job_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    applications = db.query(Application).filter(Application.job_id == job_id).all()
    applied_candidate_ids = {app.candidate_id: app.status for app in applications}

    existing_matches = db.query(MatchResult).filter(
        MatchResult.job_id == job_id,
        MatchResult.candidate_id.in_(list(applied_candidate_ids.keys()))
    ).all()

    FAILED = {"Analysis unavailable", "Analysis unavailable."}

    # ready: has a valid analysis result
    cached_map = {mr.candidate_id: mr for mr in existing_matches
                  if mr.analysis and mr.analysis not in FAILED}
    # has any MR at all
    has_mr = {mr.candidate_id for mr in existing_matches}

    # reset permanently-failed analyses so they can be retried
    needs_commit = False
    for mr in existing_matches:
        if mr.analysis in FAILED:
            mr.analysis = None
            needs_commit = True
    if needs_commit:
        db.commit()

    candidates = db.query(Candidate).filter(
        Candidate.id.in_(list(applied_candidate_ids.keys()))
    ).all()
    candidate_map = {c.id: c for c in candidates}

    results = []
    for cid, status in applied_candidate_ids.items():
        c = candidate_map.get(cid)
        if not c:
            continue

        if cid in cached_map:
            mr = cached_map[cid]
            results.append({
                "candidate": {
                    "id": cid, "full_name": c.full_name, "email": c.email,
                    "phone": c.phone, "skills": c.skills, "cluster_id": c.cluster_id,
                    "uploaded_at": c.uploaded_at.isoformat(), "cv_filename": c.cv_filename,
                },
                "match_score": mr.match_score,
                "matched_skills": mr.matched_skills or [],
                "missing_skills": mr.missing_skills or [],
                "experience_match": mr.experience_match or "unknown",
                "education_match": mr.education_match or "unknown",
                "analysis": mr.analysis,
                "applied": True,
                "application_status": status,
                "processing": False,
            })
        else:
            # Use in-memory set to know if a task is truly running right now.
            # After a server restart the set is empty, so any analysis=None in DB
            # (orphaned from killed tasks) will be re-triggered correctly.
            if not is_in_progress(cid, job_id):
                if cid not in has_mr:
                    db.add(MatchResult(candidate_id=cid, job_id=job_id, match_score=None,
                                       matched_skills=[], missing_skills=[]))
                    db.commit()
                background_tasks.add_task(enrich_and_match, cid, c.raw_text or "", job_id)

            results.append({
                "candidate": {
                    "id": cid, "full_name": c.full_name, "email": c.email,
                    "phone": c.phone, "skills": c.skills, "cluster_id": c.cluster_id,
                    "uploaded_at": c.uploaded_at.isoformat(), "cv_filename": c.cv_filename,
                },
                "match_score": None,
                "matched_skills": [],
                "missing_skills": [],
                "experience_match": "unknown",
                "education_match": "unknown",
                "analysis": None,
                "applied": True,
                "application_status": status,
                "processing": True,
            })

    results.sort(key=lambda x: -(x["match_score"] or -1))
    return {"results": results, "emails_sent": 0}

@router.get("/{job_id}/public")
def get_job_public(job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    deadline_passed = job.deadline and datetime.now(timezone.utc) > job.deadline
    return {
        "id": job.id,
        "title": job.title,
        "description": job.description,
        "required_skills": job.required_skills,
        "required_experience_years": job.required_experience_years,
        "required_education": job.required_education,
        "is_open": job.is_open and not deadline_passed,
        "deadline": job.deadline.isoformat() if job.deadline else None,
        "deadline_passed": bool(deadline_passed),
    }

@router.post("/{job_id}/apply")
async def public_apply(
    job_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    full_name: str = Form(None),
    email: str = Form(None),
    db: Session = Depends(get_db)
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.is_open:
        raise HTTPException(status_code=400, detail="This position is no longer accepting applications")
    if job.deadline and datetime.now(timezone.utc) > job.deadline:
        raise HTTPException(status_code=400, detail="The application deadline for this position has passed")

    if not file.filename.endswith((".pdf", ".docx")):
        raise HTTPException(status_code=400, detail="Only PDF and DOCX files are supported")

    file_bytes = await file.read()

    if len(file_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 10MB")

    is_pdf  = file_bytes[:4] == b'%PDF'
    is_docx = file_bytes[:4] == b'PK\x03\x04'
    if file.filename.endswith(".pdf") and not is_pdf:
        raise HTTPException(status_code=400, detail="File is not a valid PDF")
    if file.filename.endswith(".docx") and not is_docx:
        raise HTTPException(status_code=400, detail="File is not a valid DOCX")

    parsed = parse_cv_fast(file_bytes, file.filename)

    cv_valid, gemini_name = is_likely_cv(parsed)
    if not cv_valid:
        raise HTTPException(status_code=400, detail="The uploaded file does not appear to be a CV")

    resolved_email = email or parsed.get("email")
    resolved_name = full_name or gemini_name or parsed.get("full_name")

    candidate = None
    if resolved_email:
        candidate = db.query(Candidate).filter(Candidate.email == resolved_email).first()

    if candidate:
        existing_app = db.query(Application).filter(
            Application.candidate_id == candidate.id,
            Application.job_id == job_id
        ).first()
        if existing_app:
            raise HTTPException(status_code=400, detail="You have already applied to this position")
        if full_name:
            candidate.full_name = full_name
        db.commit()
    else:
        ext = Path(file.filename).suffix
        stored_filename = f"{uuid.uuid4().hex}{ext}"
        (UPLOAD_DIR / stored_filename).write_bytes(file_bytes)
        candidate = Candidate(
            full_name=resolved_name,
            email=resolved_email,
            phone=parsed["phone"],
            skills=parsed["skills"],
            education=parsed.get("education"),
            experience=parsed.get("experience"),
            raw_text=parsed["raw_text"],
            cv_filename=stored_filename,
            embedding=None,
            uploaded_by=None
        )
        db.add(candidate)
        db.commit()
        db.refresh(candidate)
        background_tasks.add_task(enrich_and_match, candidate.id, parsed["raw_text"], job_id)

    application = Application(candidate_id=candidate.id, job_id=job_id)
    db.add(application)
    db.commit()

    if candidate.email:
        background_tasks.add_task(
            send_email,
            candidate.email,
            f"Application Received – {job.title}",
            f"""Dear {candidate.full_name or 'Candidate'},

Thank you for applying for the position of {job.title}.

We have successfully received your CV and our HR team will review your profile shortly.

Best regards,
HR Team"""
        )

    return {"message": "Your CV has been received. We will be in touch soon!"}

def _generate_report(job, db):
    applications = db.query(Application).filter(Application.job_id == job.id).all()
    total = len(applications)
    by_status = {"pending": 0, "shortlisted": 0, "accepted": 0, "rejected": 0}
    hired, shortlisted_list, all_candidates = [], [], []
    scores = []
    missing_tally = {}
    score_dist = {"strong": 0, "good": 0, "moderate": 0, "weak": 0}

    for app in applications:
        s = app.status
        if s in ("applied", "reviewed"):
            by_status["pending"] += 1
        elif s == "shortlisted":
            by_status["shortlisted"] += 1
        elif s == "accepted":
            by_status["accepted"] += 1
        elif s == "rejected":
            by_status["rejected"] += 1

        candidate = db.query(Candidate).filter(Candidate.id == app.candidate_id).first()
        mr = db.query(MatchResult).filter(
            MatchResult.candidate_id == app.candidate_id,
            MatchResult.job_id == job.id
        ).first()

        score = mr.match_score if mr else None
        matched = mr.matched_skills or [] if mr else []
        missing = mr.missing_skills or [] if mr else []
        exp_match = mr.experience_match or "unknown" if mr else "unknown"
        edu_match = mr.education_match or "unknown" if mr else "unknown"
        analysis = mr.analysis or "" if mr else ""

        if score is not None:
            scores.append(score)
            if score >= 80:   score_dist["strong"] += 1
            elif score >= 60: score_dist["good"] += 1
            elif score >= 40: score_dist["moderate"] += 1
            else:             score_dist["weak"] += 1

        for skill in missing:
            missing_tally[skill] = missing_tally.get(skill, 0) + 1

        entry = {
            "name": candidate.full_name if candidate else "Unknown",
            "email": candidate.email if candidate else None,
            "phone": candidate.phone if candidate else None,
            "score": score,
            "status": s,
            "matched_skills": matched,
            "missing_skills": missing,
            "experience_match": exp_match,
            "education_match": edu_match,
            "analysis": analysis,
        }
        all_candidates.append(entry)
        if s == "accepted":
            hired.append(entry)
        elif s == "shortlisted":
            shortlisted_list.append(entry)

    all_candidates.sort(key=lambda x: -(x["score"] or 0))
    hired.sort(key=lambda x: -(x["score"] or 0))
    shortlisted_list.sort(key=lambda x: -(x["score"] or 0))
    top_missing = [s for s, _ in sorted(missing_tally.items(), key=lambda x: -x[1])[:6]]

    return {
        "job_title": job.title,
        "job_description": job.description or "",
        "required_skills": job.required_skills or [],
        "required_experience_years": job.required_experience_years,
        "required_education": job.required_education,
        "deadline": job.deadline.isoformat() if job.deadline else None,
        "closed_at": datetime.now(timezone.utc).isoformat(),
        "total_applicants": total,
        "by_status": by_status,
        "avg_score": round(sum(scores) / len(scores), 1) if scores else None,
        "score_distribution": score_dist,
        "top_missing_skills": top_missing,
        "hired": hired,
        "shortlisted": shortlisted_list,
        "all_candidates": all_candidates,
    }


@router.patch("/{job_id}/toggle")
def toggle_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not current_user.is_admin and job.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorised")
    job.is_open = not job.is_open
    db.commit()
    log_action(db, current_user, "job_toggled", {
        "job_id": job_id,
        "title": job.title,
        "is_open": job.is_open,
    })

    if not job.is_open:
        report_data = _generate_report(job, db)
        existing = db.query(JobReport).filter(JobReport.job_id == job.id).first()
        if existing:
            existing.data = report_data
            existing.generated_at = datetime.now(timezone.utc)
        else:
            db.add(JobReport(job_id=job.id, data=report_data))
        db.commit()

    return {"is_open": job.is_open}


@router.get("/{job_id}/report")
def get_job_report(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    report = db.query(JobReport).filter(JobReport.job_id == job_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="No report available for this job")
    return {"generated_at": report.generated_at.isoformat(), "data": report.data}

@router.get("/{job_id}/report/pdf")
def download_job_report_pdf(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    report = db.query(JobReport).filter(JobReport.job_id == job_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="No report available for this job")

    d = report.data
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=20*mm, rightMargin=20*mm,
                            topMargin=20*mm, bottomMargin=20*mm)

    from datetime import datetime as dt

    font_normal, font_bold, font_italic = _register_fonts()

    title_style   = ParagraphStyle('t',  fontSize=18, fontName=font_bold,   textColor=colors.HexColor('#1e1b4b'), spaceAfter=4)
    sub_style     = ParagraphStyle('s',  fontSize=9,  fontName=font_normal, textColor=colors.HexColor('#6b7280'), spaceAfter=12)
    heading_style = ParagraphStyle('h',  fontSize=10, fontName=font_bold,   textColor=colors.HexColor('#374151'), spaceBefore=14, spaceAfter=6)
    body_style    = ParagraphStyle('b',  fontSize=9,  fontName=font_normal, textColor=colors.HexColor('#374151'), spaceAfter=3)
    muted_style   = ParagraphStyle('m',  fontSize=8,  fontName=font_normal, textColor=colors.HexColor('#9ca3af'), spaceAfter=2)
    italic_style  = ParagraphStyle('i',  fontSize=8,  fontName=font_italic, textColor=colors.HexColor('#6b7280'), spaceAfter=6)

    def section_header(text):
        story.append(Spacer(1, 4))
        story.append(Paragraph(text, heading_style))
        story.append(HRFlowable(width='100%', thickness=0.5, color=colors.HexColor('#e5e7eb'), spaceAfter=6))

    def match_badge(val):
        icons = {'exceeds': '✓✓', 'meets': '✓', 'below': '✗', 'unknown': '—'}
        return icons.get(val, '—')

    story = []

    # ── Header ──
    story.append(Paragraph(d.get('job_title', 'Job Report'), title_style))
    closed_raw = d.get('closed_at', '')
    try:
        closed_fmt = dt.fromisoformat(closed_raw).strftime('%B %d, %Y')
    except Exception:
        closed_fmt = closed_raw
    generated = report.generated_at.strftime('%B %d, %Y') if report.generated_at else ''
    story.append(Paragraph(f"Report generated {generated}  ·  Closed {closed_fmt}", sub_style))
    story.append(HRFlowable(width='100%', thickness=1, color=colors.HexColor('#e5e7eb'), spaceAfter=14))

    # ── Summary stats ──
    bs  = d.get('by_status', {})
    avg = d.get('avg_score')
    sd  = d.get('score_distribution', {})
    stat_data = [
        ['Total', 'Hired', 'Shortlisted', 'Rejected', 'Pending', 'Avg Score'],
        [str(d.get('total_applicants', 0)), str(bs.get('accepted', 0)),
         str(bs.get('shortlisted', 0)), str(bs.get('rejected', 0)),
         str(bs.get('pending', 0)), f"{avg}%" if avg is not None else '—'],
    ]
    st = Table(stat_data, colWidths=[170/6*mm]*6)
    st.setStyle(TableStyle([
        ('BACKGROUND',   (0,0),(-1,0), colors.HexColor('#f3f4f6')),
        ('TEXTCOLOR',    (0,0),(-1,0), colors.HexColor('#6b7280')),
        ('FONTNAME',     (0,0),(-1,0), font_normal), ('FONTSIZE',(0,0),(-1,0), 7.5),
        ('FONTNAME',     (0,1),(-1,1), font_bold), ('FONTSIZE',(0,1),(-1,1), 15),
        ('TEXTCOLOR',    (0,1),(-1,1), colors.HexColor('#1e1b4b')),
        ('ALIGN',        (0,0),(-1,-1), 'CENTER'), ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('BOX',          (0,0),(-1,-1), 0.5, colors.HexColor('#e5e7eb')),
        ('INNERGRID',    (0,0),(-1,-1), 0.5, colors.HexColor('#e5e7eb')),
        ('TOPPADDING',   (0,0),(-1,-1), 7), ('BOTTOMPADDING',(0,0),(-1,-1), 7),
    ]))
    story.append(st)

    # ── Score distribution ──
    if any(sd.get(k, 0) for k in ('strong','good','moderate','weak')):
        section_header('Score Distribution')
        dist_data = [
            ['Strong (80–100)', 'Good (60–79)', 'Moderate (40–59)', 'Weak (0–39)'],
            [str(sd.get('strong',0)), str(sd.get('good',0)), str(sd.get('moderate',0)), str(sd.get('weak',0))],
        ]
        dt2 = Table(dist_data, colWidths=[42.5*mm]*4)
        dt2.setStyle(TableStyle([
            ('BACKGROUND',  (0,0),(-1,0), colors.HexColor('#f9fafb')),
            ('TEXTCOLOR',   (0,0),(-1,0), colors.HexColor('#6b7280')),
            ('FONTNAME',    (0,0),(-1,0), font_normal), ('FONTSIZE',(0,0),(-1,0), 8),
            ('FONTNAME',    (0,1),(-1,1), font_bold), ('FONTSIZE',(0,1),(-1,1), 13),
            ('TEXTCOLOR',   (0,1),(0,1),  colors.HexColor('#16a34a')),
            ('TEXTCOLOR',   (1,1),(1,1),  colors.HexColor('#2563eb')),
            ('TEXTCOLOR',   (2,1),(2,1),  colors.HexColor('#d97706')),
            ('TEXTCOLOR',   (3,1),(3,1),  colors.HexColor('#dc2626')),
            ('ALIGN',       (0,0),(-1,-1),'CENTER'), ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
            ('BOX',         (0,0),(-1,-1), 0.5, colors.HexColor('#e5e7eb')),
            ('INNERGRID',   (0,0),(-1,-1), 0.5, colors.HexColor('#e5e7eb')),
            ('TOPPADDING',  (0,0),(-1,-1), 6), ('BOTTOMPADDING',(0,0),(-1,-1), 6),
        ]))
        story.append(dt2)

    # ── Top missing skills ──
    top_missing = d.get('top_missing_skills', [])
    if top_missing:
        section_header('Most Commonly Missing Skills')
        story.append(Paragraph(', '.join(top_missing), body_style))

    # ── Requirements ──
    req_skills = d.get('required_skills', [])
    req_exp    = d.get('required_experience_years')
    req_edu    = d.get('required_education')
    if req_skills or req_exp or req_edu:
        section_header('Job Requirements')
        if req_skills: story.append(Paragraph(f"Skills: {', '.join(req_skills)}", body_style))
        if req_exp:    story.append(Paragraph(f"Experience: {req_exp} year(s)", body_style))
        if req_edu:    story.append(Paragraph(f"Education: {req_edu}", body_style))

    # ── Helper to render a candidate block ──
    def render_candidate(c):
        score_str = f"{c['score']}%" if c.get('score') is not None else '—'
        name_row = Table(
            [[Paragraph(f"<b>{c.get('name','Unknown')}</b>", body_style),
              Paragraph(score_str, ParagraphStyle('sc', fontSize=13, fontName=font_bold,
                        textColor=colors.HexColor('#7c3aed'), alignment=TA_CENTER))]],
            colWidths=[148*mm, 22*mm]
        )
        name_row.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE')]))
        story.append(name_row)
        contact = '  ·  '.join(filter(None, [c.get('email'), c.get('phone')]))
        if contact: story.append(Paragraph(contact, muted_style))
        exp_b = match_badge(c.get('experience_match','unknown'))
        edu_b = match_badge(c.get('education_match','unknown'))
        story.append(Paragraph(f"Experience: {exp_b}  ·  Education: {edu_b}", muted_style))
        if c.get('matched_skills'):
            story.append(Paragraph(f"Matched: {', '.join(c['matched_skills'])}", muted_style))
        if c.get('missing_skills'):
            story.append(Paragraph(f"Missing: {', '.join(c['missing_skills'])}", muted_style))
        if c.get('analysis'):
            story.append(Paragraph(c['analysis'], italic_style))
        story.append(Spacer(1, 6))

    # ── Hired ──
    hired = d.get('hired', [])
    if hired:
        section_header(f"Hired Candidates ({len(hired)})")
        for c in hired: render_candidate(c)

    # ── Shortlisted ──
    shortlisted = d.get('shortlisted', [])
    if shortlisted:
        section_header(f"Shortlisted — Not Hired ({len(shortlisted)})")
        for c in shortlisted: render_candidate(c)

    # ── All candidates table ──
    all_cands = d.get('all_candidates', [])
    if all_cands:
        section_header(f"All Candidates ({len(all_cands)})")
        STATUS_LABELS = {'applied':'Pending','reviewed':'Pending','shortlisted':'Interview',
                         'accepted':'Hired','rejected':'Rejected'}
        rows = [['#', 'Name', 'Email', 'Score', 'Status', 'Exp', 'Edu']]
        for i, c in enumerate(all_cands, 1):
            rows.append([
                str(i),
                c.get('name','—')[:28],
                (c.get('email') or '—')[:30],
                f"{c['score']}%" if c.get('score') is not None else '—',
                STATUS_LABELS.get(c.get('status',''), c.get('status','')),
                match_badge(c.get('experience_match','unknown')),
                match_badge(c.get('education_match','unknown')),
            ])
        tbl = Table(rows, colWidths=[8*mm, 42*mm, 52*mm, 14*mm, 20*mm, 10*mm, 10*mm])
        tbl_style = [
            ('BACKGROUND',   (0,0),(-1,0), colors.HexColor('#f3f4f6')),
            ('FONTNAME',     (0,0),(-1,0), font_bold),
            ('FONTSIZE',     (0,0),(-1,-1), 7.5),
            ('FONTNAME',     (0,1),(-1,-1), font_normal),
            ('TEXTCOLOR',    (0,0),(-1,0), colors.HexColor('#374151')),
            ('TEXTCOLOR',    (0,1),(-1,-1), colors.HexColor('#374151')),
            ('ALIGN',        (0,0),(-1,-1), 'LEFT'),
            ('ALIGN',        (3,0),(6,-1), 'CENTER'),
            ('VALIGN',       (0,0),(-1,-1), 'MIDDLE'),
            ('BOX',          (0,0),(-1,-1), 0.5, colors.HexColor('#e5e7eb')),
            ('INNERGRID',    (0,0),(-1,-1), 0.3, colors.HexColor('#e5e7eb')),
            ('TOPPADDING',   (0,0),(-1,-1), 4), ('BOTTOMPADDING',(0,0),(-1,-1), 4),
            ('ROWBACKGROUNDS',(0,1),(-1,-1), [colors.white, colors.HexColor('#f9fafb')]),
        ]
        tbl.setStyle(TableStyle(tbl_style))
        story.append(tbl)

    doc.build(story)
    buf.seek(0)
    filename = f"report_{d.get('job_title','job').replace(' ','_')}.pdf"
    return StreamingResponse(buf, media_type='application/pdf',
                             headers={'Content-Disposition': f'attachment; filename="{filename}"'})


@router.patch("/{job_id}")
def update_job(
    job_id: int,
    data: JobUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not current_user.is_admin and job.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorised")
    if data.title is not None:
        job.title = data.title
    if data.description is not None:
        job.description = data.description
    if data.required_skills is not None:
        job.required_skills = data.required_skills
    if data.required_experience_years is not None:
        job.required_experience_years = data.required_experience_years
    if data.required_education is not None:
        job.required_education = data.required_education
    job.deadline = data.deadline
    db.commit()
    db.refresh(job)
    return job

@router.delete("/{job_id}")
def delete_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Only admins can delete job postings")
    log_action(db, current_user, "job_deleted", {"job_id": job_id, "title": job.title})
    db.delete(job)
    db.commit()
    return {"message": "Job deleted successfully"}