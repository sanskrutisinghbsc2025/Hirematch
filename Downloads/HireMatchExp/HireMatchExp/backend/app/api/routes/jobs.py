
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status

from core.models.enums import CriterionType
from core.models.job import Job
from core.processing.jd_parser import EnhancedJDParser
from core.storage.database import Database
from core.storage.repositories import JobRepository, SessionRepository

from backend.app.api.deps import get_database
from backend.app.api.schemas.job_schemas import (
    AutoCriterionItem,
    JobCreate,
    JobParseRequest,
    JobParseResponse,
    JobResponse,
)

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
def create_job(
    payload: JobCreate,
    db: Database = Depends(get_database),
):
    job_repo = JobRepository(db)
    job = Job(
        title=payload.title,
        department=payload.department,
        original_description=payload.get_description(),
    )
    saved = job_repo.create(job)
    return JobResponse(
        id=saved.id,
        title=saved.title,
        department=saved.department,
        original_description=saved.original_description,
        created_at=saved.created_at,
    )


@router.get("", response_model=List[JobResponse])
def list_jobs(db: Database = Depends(get_database)):
    job_repo = JobRepository(db)
    all_jobs = job_repo.list_all()
    return [
        JobResponse(
            id=j.id,
            title=j.title,
            department=j.department,
            original_description=j.original_description,
            created_at=j.created_at,
        )
        for j in all_jobs
    ]


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: str, db: Database = Depends(get_database)):
    job_repo = JobRepository(db)
    job = job_repo.get(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job '{job_id}' not found.")
    return JobResponse(
        id=job.id,
        title=job.title,
        department=job.department,
        original_description=job.original_description,
        created_at=job.created_at,
    )


@router.post("/parse", response_model=JobParseResponse)
def parse_job_description(payload: JobParseRequest):
    parser = EnhancedJDParser()
    raw_text = payload.get_text()
    if not raw_text or len(raw_text.strip()) < 5:
        raw_text = "General software engineering role with requirements for programming, architecture, and team collaboration."
    jd_struct = parser.parse_job_description(
        raw_text,
        fallback_title=payload.fallback_title or "Target Role",
    )

    auto_crit = []
    if jd_struct.required_skills:
        auto_crit.append(
            AutoCriterionItem(
                criterion_name="Required Technical Skills",
                description=", ".join(jd_struct.required_skills[:6]),
                weight=0.35,
                criterion_type="REQUIRED",
                category="TECHNICAL_SKILL",
            )
        )
    if jd_struct.preferred_skills:
        auto_crit.append(
            AutoCriterionItem(
                criterion_name="Preferred Technical Skills",
                description=", ".join(jd_struct.preferred_skills[:4]),
                weight=0.15,
                criterion_type="PREFERRED",
                category="TECHNICAL_SKILL",
            )
        )
    min_exp = jd_struct.min_experience_years
    auto_crit.append(
        AutoCriterionItem(
            criterion_name="Relevant Work Experience",
            description=f"Demonstrated track record ({min_exp}+ years expected)",
            weight=0.30,
            criterion_type="REQUIRED",
            category="EXPERIENCE_DURATION",
        )
    )
    auto_crit.append(
        AutoCriterionItem(
            criterion_name="Education & Certifications",
            description=jd_struct.education_level or "Relevant degree or credentials",
            weight=0.10,
            criterion_type="PREFERRED",
            category="EDUCATION_REQUIREMENT",
        )
    )
    auto_crit.append(
        AutoCriterionItem(
            criterion_name="Problem Solving & Initiative Evidence",
            description="Documented action-verb examples of leadership and problem solving",
            weight=0.10,
            criterion_type="PREFERRED",
            category="PROJECT_EVIDENCE",
        )
    )

    return JobParseResponse(
        title=getattr(jd_struct, "title", None) or payload.fallback_title or "Target Role",
        department=getattr(jd_struct, "department", None),
        min_experience_years=jd_struct.min_experience_years,
        education_level=jd_struct.education_level,
        required_skills=jd_struct.required_skills,
        preferred_skills=jd_struct.preferred_skills,
        responsibilities=jd_struct.responsibilities,
        auto_criteria=auto_crit,
    )
