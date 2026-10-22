
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status

from core.models.enums import CriterionCategory, CriterionType
from core.models.evaluation import EvaluationCriterion
from core.storage.database import Database
from core.storage.repositories import CriterionRepository, JobRepository, SessionRepository

from backend.app.api.deps import get_database
from backend.app.api.schemas.criteria_schemas import (
    CriteriaBatchSaveRequest,
    CriterionItem,
)

router = APIRouter(tags=["Criteria"])


@router.get("/sessions/{session_id}/criteria", response_model=List[CriterionItem])
def get_session_criteria(
    session_id: str,
    db: Database = Depends(get_database),
):
    session_repo = SessionRepository(db)
    session = session_repo.get(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Session '{session_id}' not found.")

    crit_repo = CriterionRepository(db)
    criteria = crit_repo.list_by_job(session.job_id)
    return [
        CriterionItem(
            id=c.id,
            job_id=getattr(c, "job_id", session.job_id),
            criterion_name=c.criterion_name,
            name=c.criterion_name,
            description=c.description,
            weight=c.weight,
            criterion_type=c.criterion_type.value if hasattr(c.criterion_type, "value") else str(c.criterion_type),
            category=c.category.value if c.category and hasattr(c.category, "value") else (str(c.category) if c.category else "TECHNICAL_SKILL"),
            is_enabled=c.is_enabled,
        )
        for c in criteria
    ]


@router.put("/sessions/{session_id}/criteria", response_model=List[CriterionItem])
def update_session_criteria(
    session_id: str,
    payload: CriteriaBatchSaveRequest,
    db: Database = Depends(get_database),
):
    session_repo = SessionRepository(db)
    session = session_repo.get(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Session '{session_id}' not found.")

    crit_repo = CriterionRepository(db)
    crit_objs = [
        EvaluationCriterion(
            criterion_name=item.criterion_name,
            description=item.description or "",
            weight=item.weight,
            criterion_type=CriterionType(item.criterion_type.upper()),
            category=CriterionCategory(item.category.upper()) if item.category else CriterionCategory.TECHNICAL_SKILL,
            is_enabled=item.is_enabled,
        )
        for item in payload.criteria
    ]

    saved = crit_repo.save_batch(crit_objs, session.job_id)
    return [
        CriterionItem(
            id=c.id,
            job_id=getattr(c, "job_id", session.job_id),
            criterion_name=c.criterion_name,
            name=c.criterion_name,
            description=c.description,
            weight=c.weight,
            criterion_type=c.criterion_type.value if hasattr(c.criterion_type, "value") else str(c.criterion_type),
            category=c.category.value if c.category and hasattr(c.category, "value") else (str(c.category) if c.category else "TECHNICAL_SKILL"),
            is_enabled=c.is_enabled,
        )
        for c in saved
    ]


@router.get("/jobs/{job_id}/criteria", response_model=List[CriterionItem])
def get_job_criteria(
    job_id: str,
    db: Database = Depends(get_database),
):
    crit_repo = CriterionRepository(db)
    criteria = crit_repo.list_by_job(job_id)
    return [
        CriterionItem(
            id=c.id,
            job_id=getattr(c, "job_id", job_id),
            criterion_name=c.criterion_name,
            name=c.criterion_name,
            description=c.description,
            weight=c.weight,
            criterion_type=c.criterion_type.value if hasattr(c.criterion_type, "value") else str(c.criterion_type),
            category=c.category.value if c.category and hasattr(c.category, "value") else (str(c.category) if c.category else "TECHNICAL_SKILL"),
            is_enabled=c.is_enabled,
        )
        for c in criteria
    ]


@router.post("/jobs/{job_id}/criteria", response_model=List[CriterionItem])
def save_job_criteria(
    job_id: str,
    payload: CriteriaBatchSaveRequest,
    db: Database = Depends(get_database),
):
    job_repo = JobRepository(db)
    if not job_repo.get(job_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job '{job_id}' not found.")

    crit_repo = CriterionRepository(db)
    crit_objs = [
        EvaluationCriterion(
            criterion_name=item.criterion_name,
            description=item.description or "",
            weight=item.weight,
            criterion_type=CriterionType(item.criterion_type.upper()),
            category=CriterionCategory(item.category.upper()) if item.category else CriterionCategory.TECHNICAL_SKILL,
            is_enabled=item.is_enabled,
        )
        for item in payload.criteria
    ]

    saved = crit_repo.save_batch(crit_objs, job_id)
    return [
        CriterionItem(
            id=c.id,
            job_id=c.job_id,
            criterion_name=c.criterion_name,
            description=c.description,
            weight=c.weight,
            criterion_type=c.criterion_type.value,
            category=c.category.value if c.category else "TECHNICAL_SKILL",
            is_enabled=c.is_enabled,
        )
        for c in saved
    ]
