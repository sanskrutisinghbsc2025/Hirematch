
from typing import List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from backend.app.api.deps import get_orchestrator
from core.models.report_models import ExportFormat, ReportType
from core.services.session_orchestrator import ScreeningOrchestrator
from core.utils.logger import logger

router = APIRouter(tags=["Reports & Exports"])


class ExportComparisonPayload(BaseModel):
    session_id: str
    candidate_ids: List[str] = Field(..., min_length=2, max_length=5)
    export_format: str = Field(default="pdf", pattern="^(pdf|csv|json)$")


@router.get("/candidates/{candidate_id}/report")
def export_candidate_report(
    candidate_id: str,
    session_id: Optional[str] = Query(None),
    format: str = Query("pdf", pattern="^(pdf|csv|json)$"),
    include_pii: bool = Query(False),
    orchestrator: ScreeningOrchestrator = Depends(get_orchestrator),
):
    try:
        if not session_id:
            cand = orchestrator.candidate_repo.get(candidate_id)
            if not cand:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
            session_id = cand.session_id

        fmt_map = {
            "pdf": ExportFormat.PDF,
            "csv": ExportFormat.CSV,
            "json": ExportFormat.JSON,
        }
        export_fmt = fmt_map.get(format.lower(), ExportFormat.PDF)

        content, filename, _record = orchestrator.export_candidate_report(
            candidate_id=candidate_id,
            session_id=session_id,
            export_format=export_fmt,
            include_pii=include_pii,
        )

        media_type = "application/pdf" if export_fmt == ExportFormat.PDF else "text/csv" if export_fmt == ExportFormat.CSV else "application/json"

        return Response(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating candidate report: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate candidate report: {str(e)}",
        )


@router.get("/sessions/{session_id}/report")
def export_session_report(
    session_id: str,
    format: str = Query("pdf", pattern="^(pdf|csv|json)$"),
    orchestrator: ScreeningOrchestrator = Depends(get_orchestrator),
):
    try:
        fmt_map = {
            "pdf": ExportFormat.PDF,
            "csv": ExportFormat.CSV,
            "json": ExportFormat.JSON,
        }
        export_fmt = fmt_map.get(format.lower(), ExportFormat.PDF)

        content, filename, _record = orchestrator.export_session_report(
            session_id=session_id,
            export_format=export_fmt,
        )

        media_type = "application/pdf" if export_fmt == ExportFormat.PDF else "text/csv" if export_fmt == ExportFormat.CSV else "application/json"

        return Response(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating session report: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate session report: {str(e)}",
        )


@router.get("/sessions/{session_id}/shortlist/report")
def export_shortlist_report(
    session_id: str,
    format: str = Query("pdf", pattern="^(pdf|csv|json)$"),
    orchestrator: ScreeningOrchestrator = Depends(get_orchestrator),
):
    try:
        fmt_map = {
            "pdf": ExportFormat.PDF,
            "csv": ExportFormat.CSV,
            "json": ExportFormat.JSON,
        }
        export_fmt = fmt_map.get(format.lower(), ExportFormat.PDF)

        content, filename, _record = orchestrator.export_shortlist_report(
            session_id=session_id,
            export_format=export_fmt,
        )

        media_type = "application/pdf" if export_fmt == ExportFormat.PDF else "text/csv" if export_fmt == ExportFormat.CSV else "application/json"

        return Response(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error exporting shortlist report: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export shortlist report: {str(e)}",
        )


@router.post("/reports/compare")
def export_candidate_comparison(
    payload: ExportComparisonPayload,
    orchestrator: ScreeningOrchestrator = Depends(get_orchestrator),
):
    try:
        fmt_map = {
            "pdf": ExportFormat.PDF,
            "csv": ExportFormat.CSV,
            "json": ExportFormat.JSON,
        }
        export_fmt = fmt_map.get(payload.export_format.lower(), ExportFormat.PDF)

        content, filename, _record = orchestrator.export_candidate_comparison(
            candidate_ids=payload.candidate_ids,
            session_id=payload.session_id,
            export_format=export_fmt,
        )

        media_type = "application/pdf" if export_fmt == ExportFormat.PDF else "text/csv" if export_fmt == ExportFormat.CSV else "application/json"

        return Response(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error exporting comparison report: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export comparison report: {str(e)}",
        )


@router.get("/sessions/{session_id}/reports")
def list_session_reports(
    session_id: str,
    orchestrator: ScreeningOrchestrator = Depends(get_orchestrator),
):
    try:
        records = orchestrator.list_generated_reports(session_id=session_id)
        return [r.to_dict() if hasattr(r, "to_dict") else r for r in records]
    except Exception as e:
        logger.error(f"Error listing session reports: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list session reports: {str(e)}",
        )
