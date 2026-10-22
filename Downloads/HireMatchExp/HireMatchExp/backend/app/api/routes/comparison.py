
from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.api.deps import get_orchestrator
from backend.app.api.schemas.comparison_schemas import (
    CandidateCompareRequest,
    CandidateCompareResponse,
    CandidateHeader,
    AlignedCriterionRow,
    ComparisonCompatibility,
)
from core.services.session_orchestrator import ScreeningOrchestrator
from core.utils.logger import logger

router = APIRouter(prefix="/candidates", tags=["Candidate Comparison"])


@router.post("/compare", response_model=CandidateCompareResponse)
def compare_candidates(
    payload: CandidateCompareRequest,
    orchestrator: ScreeningOrchestrator = Depends(get_orchestrator),
):
    try:
        sess_id = payload.session_id
        if not sess_id and payload.candidate_ids:
            try:
                row = orchestrator.db.execute_query(
                    "SELECT session_id FROM session_candidates WHERE candidate_id = ? LIMIT 1;",
                    (payload.candidate_ids[0],)
                )
                if row:
                    sess_id = row[0]["session_id"]
            except Exception:
                pass

        if not sess_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A valid session_id is required for candidate comparison."
            )

        comp_data = orchestrator.generate_candidate_comparison(
            candidate_ids=payload.candidate_ids,
            session_id=sess_id,
        )

        headers = [
            CandidateHeader(
                candidate_id=h["candidate_id"],
                id=h.get("id") or h["candidate_id"],
                candidate_reference=h.get("candidate_reference", f"Candidate {h['candidate_id'][:6]}"),
                candidate_name=h.get("candidate_name") or h.get("name"),
                name=h.get("name") or h.get("candidate_name") or h.get("candidate_reference"),
                email=h.get("email"),
                original_filename=h.get("original_filename", "Resume.pdf"),
                overall_score=h.get("overall_score"),
                evidence_coverage=h.get("evidence_coverage", 0.0),
                review_status=h.get("review_status", "PENDING_REVIEW"),
                reviewer_notes=h.get("reviewer_notes"),
                resume_quality_score=h.get("resume_quality_score"),
                resume_quality_label=h.get("resume_quality_label"),
                fit_tier=h.get("fit_tier") or (
                    "Strong Match" if h.get("overall_score") and h["overall_score"] >= 80
                    else ("Potential Match" if h.get("overall_score") and h["overall_score"] >= 60 else "Under Review")
                ),
            )
            for h in comp_data.candidate_headers
        ]

        rows = [
            AlignedCriterionRow(
                criterion_id=r.criterion_id,
                criterion_name=r.criterion_name,
                criterion_type=r.criterion_type.value if hasattr(r.criterion_type, "value") else str(r.criterion_type),
                configured_weight=r.configured_weight,
                candidate_evaluations=r.candidate_evaluations,
                has_meaningful_difference=r.has_meaningful_difference,
                variance_note=r.variance_note or None,
            )
            for r in comp_data.aligned_criteria_rows
        ]

        compatibility = ComparisonCompatibility(
            is_compatible=comp_data.compatibility.is_compatible,
            shared_config_version=comp_data.compatibility.shared_config_version,
            compatibility_warnings=comp_data.compatibility.compatibility_warnings,
        )

        return CandidateCompareResponse(
            job_id=comp_data.job_id,
            job_title=comp_data.job_title,
            compared_at=comp_data.generated_at,
            compatibility=compatibility,
            candidate_headers=headers,
            candidates=headers,
            aligned_criteria_rows=rows,
            criteria_comparison=rows,
            key_differentiators=comp_data.key_differentiators,
            differentiators=comp_data.key_differentiators,
            education_comparison=comp_data.education_comparison,
            experience_comparison=comp_data.experience_comparison,
        )

    except ValueError as e:
        logger.warning(f"Validation failure comparing candidates: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in candidate comparison: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate candidate comparison: {str(e)}",
        )
