
import math
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from core.models.enums import SessionStatus
from core.models.session import ScreeningSession
from core.services.session_orchestrator import ScreeningOrchestrator
from core.storage.database import Database
from core.storage.repositories import JobRepository, SessionRepository
from core.utils.errors import SessionLimitExceededError, SessionNotFoundError

from backend.app.api.deps import get_database, get_orchestrator
from backend.app.api.schemas.session_schemas import (
    SessionCreate,
    SessionListResponse,
    SessionResponse,
)

router = APIRouter(prefix="/sessions", tags=["Sessions"])


@router.get("", response_model=SessionListResponse)
def list_sessions(
    q: Optional[str] = Query(None, description="Search term for session name"),
    status: Optional[str] = Query(None, description="Filter by status (CREATED, PROCESSING, COMPLETED, FAILED)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Database = Depends(get_database),
):
    session_repo = SessionRepository(db)
    job_repo = JobRepository(db)
    all_sessions = session_repo.list_all()

    filtered = all_sessions
    if q and q.strip():
        search_term = q.strip().lower()
        filtered = [s for s in filtered if search_term in s.session_name.lower()]

    if status and status.upper() != "ALL":
        filtered = [s for s in filtered if s.status.value == status.upper()]

    total = len(filtered)
    total_pages = max(1, math.ceil(total / page_size))
    start_idx = (page - 1) * page_size
    paged = filtered[start_idx : start_idx + page_size]

    items = []
    for s in paged:
        job = job_repo.get(s.job_id)
        live_count = s.candidate_count
        try:
            with db.get_connection() as conn:
                row = conn.execute("SELECT COUNT(*) as cnt FROM session_candidates WHERE session_id = ?", (s.id,)).fetchone()
                if row and row["cnt"] is not None:
                    live_count = max(live_count, int(row["cnt"]))
        except Exception:
            pass

        disp_title = s.session_name or (job.title if job else "Screening Requisition")
        items.append(
            SessionResponse(
                id=s.id,
                job_id=s.job_id,
                session_name=s.session_name,
                status=s.status.value,
                candidate_count=live_count,
                max_resume_count=s.max_resume_count,
                created_at=s.created_at,
                completed_at=s.completed_at,
                job_title=job.title if job else disp_title,
                job_department=job.department if job else None,
                title=disp_title,
                name=disp_title,
                resume_count=live_count,
                description=job.original_description if job else None,
                department=job.department if job else None,
            )
        )

    return SessionListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(
    payload: SessionCreate,
    orchestrator: ScreeningOrchestrator = Depends(get_orchestrator),
    db: Database = Depends(get_database),
):
    try:
        job_repo = JobRepository(db)
        session_name = payload.session_name or payload.title or payload.name or "Screening Session"
        job_id = payload.job_id
        if not job_id:
            job = Job(
                title=payload.title or session_name,
                department=payload.department,
                original_description=payload.description or f"Requisition for {session_name}",
            )
            created_job = job_repo.create(job)
            job_id = created_job.id

        session = orchestrator.create_session(
            job_id=job_id,
            session_name=session_name,
            max_resume_count=payload.max_resume_count,
        )
        job = job_repo.get(session.job_id)
        disp_title = session.session_name or (job.title if job else "Screening Requisition")

        return SessionResponse(
            id=session.id,
            job_id=session.job_id,
            session_name=session.session_name,
            status=session.status.value,
            candidate_count=session.candidate_count,
            max_resume_count=session.max_resume_count,
            created_at=session.created_at,
            completed_at=session.completed_at,
            job_title=job.title if job else disp_title,
            job_department=job.department if job else None,
            title=disp_title,
            name=disp_title,
            resume_count=session.candidate_count,
            description=job.original_description if job else None,
            department=job.department if job else None,
        )
    except SessionLimitExceededError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.user_message)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create session: {e}")


@router.delete("/cleanup-drafts", status_code=status.HTTP_200_OK)
def cleanup_empty_draft_sessions(db: Database = Depends(get_database)):
    with db.get_connection() as conn:
        cursor = conn.execute("""
            SELECT s.id FROM screening_sessions s
            LEFT JOIN session_candidates sc ON s.id = sc.session_id
            WHERE s.status = 'CREATED'
            GROUP BY s.id
            HAVING COUNT(sc.candidate_id) = 0;
        """)
        draft_ids = [row["id"] for row in cursor.fetchall()]
        for d_id in draft_ids:
            conn.execute("DELETE FROM session_candidates WHERE session_id = ?", (d_id,))
            conn.execute("DELETE FROM screening_sessions WHERE id = ?", (d_id,))
        conn.commit()
    return {"deleted_count": len(draft_ids), "deleted_session_ids": draft_ids}


@router.get("/{session_id}", response_model=SessionResponse)
def get_session(
    session_id: str,
    db: Database = Depends(get_database),
):
    session_repo = SessionRepository(db)
    session = session_repo.get(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Session '{session_id}' not found.")

    job_repo = JobRepository(db)
    job = job_repo.get(session.job_id)
    disp_title = session.session_name or (job.title if job else "Screening Requisition")

    live_count = session.candidate_count
    try:
        with db.get_connection() as conn:
            row = conn.execute("SELECT COUNT(*) as cnt FROM session_candidates WHERE session_id = ?", (session.id,)).fetchone()
            if row and row["cnt"] is not None:
                live_count = max(live_count, int(row["cnt"]))
    except Exception:
        pass

    return SessionResponse(
        id=session.id,
        job_id=session.job_id,
        session_name=session.session_name,
        status=session.status.value,
        candidate_count=live_count,
        max_resume_count=session.max_resume_count,
        created_at=session.created_at,
        completed_at=session.completed_at,
        job_title=job.title if job else disp_title,
        job_department=job.department if job else None,
        title=disp_title,
        name=disp_title,
        resume_count=live_count,
        description=job.original_description if job else None,
        department=job.department if job else None,
    )


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    session_id: str,
    db: Database = Depends(get_database),
):
    session_repo = SessionRepository(db)
    session = session_repo.get(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Session '{session_id}' not found.")

    session_repo.delete(session_id)
    return None

