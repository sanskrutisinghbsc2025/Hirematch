
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from core.models.enums import EvaluationMode, ProcessingStatus, SessionStatus
from core.services.session_orchestrator import ScreeningOrchestrator
from core.storage.database import Database
from core.storage.repositories import CandidateRepository, SessionRepository
from core.utils.errors import (
    FileValidationError,
    SessionLimitExceededError,
    SessionNotFoundError,
)

from backend.app.api.deps import get_database, get_orchestrator
from backend.app.api.schemas.session_schemas import SessionProgressResponse

router = APIRouter(prefix="/sessions/{session_id}", tags=["Screening & Ingestion"])


@router.post("/resumes")
async def upload_resumes(
    session_id: str,
    files: List[UploadFile] = File(...),
    orchestrator: ScreeningOrchestrator = Depends(get_orchestrator),
):
    file_payloads = []
    for f in files:
        content_bytes = await f.read()
        file_payloads.append(
            {
                "filename": f.filename or "unknown_resume.pdf",
                "content": content_bytes,
                "size": len(content_bytes),
            }
        )

    try:
        report = orchestrator.add_resumes_to_session(session_id, file_payloads)
        return report
    except SessionLimitExceededError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.user_message or str(e),
        )
    except SessionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to ingest resumes: {e}")


@router.get("/resumes")
def list_session_resumes(
    session_id: str,
    db: Database = Depends(get_database),
):
    cand_repo = CandidateRepository(db)
    items = cand_repo.list_by_session(session_id)
    return [
        {
            "candidate_id": item["candidate"].id,
            "filename": item["candidate"].original_filename,
            "file_type": item["candidate"].file_type.value,
            "status": item["session_status"].value,
            "error_info": item["error_info"],
            "created_at": item["candidate"].created_at,
        }
        for item in items
    ]


@router.delete("/resumes/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_resume_from_session(
    session_id: str,
    candidate_id: str,
    db: Database = Depends(get_database),
):
    cand_repo = CandidateRepository(db)
    cand_repo.unlink_from_session(session_id, candidate_id)
    return None


@router.post("/process")
def process_resumes(
    session_id: str,
    batch_size: Optional[int] = Query(None, ge=1, le=100),
    process_all: bool = Query(True, description="If true, loops until all pending resumes are processed"),
    orchestrator: ScreeningOrchestrator = Depends(get_orchestrator),
):
    try:
        if process_all:
            total_processed = 0
            total_failed = 0
            while True:
                res = orchestrator.process_session_batch(session_id, batch_size=batch_size)
                total_processed += res["processed_in_chunk"]
                total_failed += res["failed_in_chunk"]
                if res["progress"]["pending"] == 0 or (res["processed_in_chunk"] == 0 and res["failed_in_chunk"] == 0):
                    break
            return {
                "session_id": session_id,
                "total_processed": total_processed,
                "total_failed": total_failed,
                "progress": res["progress"],
            }
        else:
            return orchestrator.process_session_batch(session_id, batch_size=batch_size)
    except SessionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Processing failed: {e}")


@router.get("/processing-status", response_model=SessionProgressResponse)
def get_processing_status(
    session_id: str,
    orchestrator: ScreeningOrchestrator = Depends(get_orchestrator),
    db: Database = Depends(get_database),
):
    session_repo = SessionRepository(db)
    session = session_repo.get(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Session '{session_id}' not found.")

    progress = orchestrator._refresh_progress_metadata(session_id)
    pending = progress.get("pending", 0)
    is_finished = pending == 0 and progress.get("total", 0) > 0

    return SessionProgressResponse(
        session_id=session_id,
        total=progress.get("total", 0),
        pending=pending,
        validating=progress.get("validating", 0),
        extracting=progress.get("extracting", 0),
        completed=progress.get("processed", progress.get("completed", 0)),
        failed=progress.get("failed", 0),
        duplicate=progress.get("duplicate", 0),
        flagged_quality=progress.get("flagged_quality", 0),
        evaluated=progress.get("evaluated", 0),
        status=session.status.value,
        is_finished=is_finished,
    )


@router.post("/evaluate")
def evaluate_resumes(
    session_id: str,
    batch_size: Optional[int] = Query(None, ge=1, le=100),
    mode: str = Query("COMBINED", description="BASELINE, SEMANTIC, or COMBINED"),
    evaluate_all: bool = Query(True, description="If true, evaluates all eligible resumes"),
    orchestrator: ScreeningOrchestrator = Depends(get_orchestrator),
):
    try:
        orchestrator.retry_failed_candidates(session_id)
        while True:
            extract_res = orchestrator.process_session_batch(session_id)
            if extract_res["progress"]["pending"] == 0 or (extract_res["processed_in_chunk"] == 0 and extract_res["failed_in_chunk"] == 0):
                break

        total_evaluated = 0
        total_failed = 0

        all_session_cands = orchestrator.candidate_repo.list_by_session(session_id)
        if evaluate_all:
            eligible_cands = [
                sc for sc in all_session_cands
                if sc["session_status"] in (ProcessingStatus.COMPLETED, ProcessingStatus.EVALUATED, ProcessingStatus.FLAGGED_QUALITY)
            ]
        else:
            existing_records = orchestrator.eval_record_repo.list_records_for_session(session_id)
            eligible_cands = [
                sc for sc in all_session_cands
                if sc["session_status"] in (ProcessingStatus.COMPLETED, ProcessingStatus.EVALUATED, ProcessingStatus.FLAGGED_QUALITY)
                and sc["candidate"].id not in existing_records
            ]

        chunk_sz = batch_size or 20
        for i in range(0, len(eligible_cands), chunk_sz):
            chunk = eligible_cands[i : i + chunk_sz]
            chunk_ids = [sc["candidate"].id for sc in chunk]
            res = orchestrator.evaluate_session_multi_layer(
                session_id=session_id,
                batch_size=len(chunk_ids),
                candidate_ids=chunk_ids,
            )
            total_evaluated += res.get("evaluated_in_chunk", 0)
            total_failed += res.get("failed_in_chunk", 0)

        scoring_res = orchestrator.score_session(session_id)
        orchestrator.session_repo.update_status(session_id, SessionStatus.COMPLETED)

        return {
            "session_id": session_id,
            "total_evaluated": total_evaluated,
            "total_failed": total_failed,
            "scored_count": scoring_res.get("scored_count", 0),
            "status": "COMPLETED",
        }
    except SessionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Evaluation failed: {e}")


@router.post("/retry")
def retry_failed(
    session_id: str,
    orchestrator: ScreeningOrchestrator = Depends(get_orchestrator),
):
    count = orchestrator.retry_failed_candidates(session_id)
    return {"session_id": session_id, "reset_count": count}
