
import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status


from core.evaluation.discrepancy_detector import DiscrepancyDetector
from core.models.enums import ShortlistReviewStatus
from core.services.session_orchestrator import ScreeningOrchestrator
from core.storage.database import Database
from core.storage.eval_repository import EvaluationRecordRepository
from core.storage.repositories import CandidateRepository, ScoreRepository, SessionRepository
from core.storage.scoring_repository import ScoringRecordRepository
from core.storage.shortlist_repository import ShortlistRepository

from backend.app.api.deps import get_database, get_orchestrator
from backend.app.api.schemas.candidate_schemas import (
    CandidateDetailResponse,
    CandidateListResponse,
    CandidateSummary,
    ResumeQualityReportResponse,
    ShortlistUpdateRequest,
)
from backend.app.api.schemas.evaluation_schemas import (
    CandidateEvaluationResponse,
    CriterionResultItem,
    ScoringContributionItem,
)

router = APIRouter(tags=["Candidates"])


def _derive_name(original_filename: str, contact: Optional[dict] = None) -> str:
    if contact and isinstance(contact, dict):
        cand_name = contact.get("name") or contact.get("full_name")
        if cand_name and isinstance(cand_name, str) and cand_name.strip():
            clean = cand_name.strip()
            return clean.title() if clean.isupper() else clean
    stem = Path(original_filename).stem
    cleaned = re.sub(r"^(resume|cv|candidate)[_\-\s]+", "", stem, flags=re.IGNORECASE)
    cleaned = re.sub(r"[_\-\s]+(resume|cv)$", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace("_", " ").replace("-", " ").strip()
    return cleaned.title() if cleaned else stem.title()


def _compute_fit_tier(score: Optional[float]) -> str:
    if score is None:
        return "Under Review"
    if score >= 80:
        return "Strong Match"
    if score >= 60:
        return "Potential Match"
    return "Under Review"


@router.get("/sessions/{session_id}/candidates", response_model=CandidateListResponse)
def list_session_candidates(
    session_id: str,
    q: Optional[str] = Query(None, description="Filename or candidate reference search"),
    status: Optional[str] = Query(None, description="Shortlist/Review status or processing status"),
    min_score: Optional[float] = Query(None, ge=0.0, le=100.0, description="Minimum score threshold"),
    required_filter: Optional[str] = Query(None, description="ALL_REQUIRED_MET, HAS_CONFLICTS, HAS_UNMET_REQUIRED"),
    sort_by: str = Query("rank", description="rank, score_desc, score_asc, filename"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=1000),
    limit: Optional[int] = Query(None, ge=1, le=1000, description="Alias for page_size"),
    orchestrator: ScreeningOrchestrator = Depends(get_orchestrator),
    db: Database = Depends(get_database),
):
    search_query = q if isinstance(q, str) else None
    min_score_val = min_score if isinstance(min_score, (int, float)) else None
    status_val = status if isinstance(status, str) else None
    sort_by_val = sort_by if isinstance(sort_by, str) else "rank"
    page_val = page if isinstance(page, int) else 1
    page_size_val = page_size if isinstance(page_size, int) else 50
    limit_val = limit if isinstance(limit, int) else None
    effective_page_size = limit_val if limit_val is not None else page_size_val

    session_repo = SessionRepository(db)
    if not session_repo.get(session_id):
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail=f"Session '{session_id}' not found.")

    cand_repo = CandidateRepository(db)
    session_cands = cand_repo.list_by_session(session_id)
    cand_status_map = {item["candidate"].id: item["session_status"].value for item in session_cands}

    from core.storage.shortlist_repository import ShortlistRepository
    shortlist_repo = ShortlistRepository(db)
    shortlist_map = {sr.candidate_id: sr for sr in shortlist_repo.list_by_session(session_id)}

    ranked_candidates = orchestrator.get_ranked_candidates(
        session_id=session_id,
        filters={
            "search_query": search_query,
            "min_score": min_score_val,
            "required_filter": required_filter if (isinstance(required_filter, str) and required_filter != "ALL") else None,
        },
    )

    cand_obj_map = {item["candidate"].id: item["candidate"] for item in session_cands}
    import json
    contacts_map: Dict[str, Any] = {}
    contact_rows = db.execute_query(
        "SELECT id, structured_data FROM candidates WHERE id IN (SELECT candidate_id FROM session_candidates WHERE session_id = ?);",
        (session_id,)
    )
    for r in contact_rows:
        if r["structured_data"]:
            try:
                sd = json.loads(r["structured_data"])
                if isinstance(sd, dict) and "contact" in sd and isinstance(sd["contact"], dict):
                    contacts_map[r["id"]] = sd["contact"]
            except Exception:
                pass

    quality_map = orchestrator.quality_repo.get_session_map(session_id)
    ranked_ids = {c.candidate_id for c in ranked_candidates}

    combined_items: List[CandidateSummary] = []
    for c in ranked_candidates:
        cand_obj = cand_obj_map.get(c.candidate_id)
        c_contact = contacts_map.get(c.candidate_id, {})
        c_filename = getattr(c, "filename", None) or (cand_obj.original_filename if cand_obj else "Resume.pdf")
        cand_name_raw = getattr(c, "candidate_name", None)
        if cand_name_raw and not cand_name_raw.lower().endswith((".pdf", ".docx", ".txt")) and "_" not in cand_name_raw:
            c_name = cand_name_raw
        else:
            c_name = _derive_name(c_filename, c_contact)
        c_email = c_contact.get("email") if isinstance(c_contact, dict) else None
        c_tier = _compute_fit_tier(c.overall_score)
        
        req_summary = getattr(c, "required_summary", None)
        sat_count = (req_summary.supported_count + req_summary.partially_supported_count) if req_summary else getattr(c, "required_satisfied_count", 0)
        tot_count = req_summary.total_required if req_summary else getattr(c, "required_total_count", 0)
        c_missing = max(0, tot_count - sat_count)
        conflicts = req_summary.conflicting_count if req_summary else 0
        
        sl_entry = shortlist_map.get(c.candidate_id)
        if sl_entry:
            rev_status = sl_entry.review_status.value
        else:
            sl_status = getattr(c, "shortlist_status", None)
            rev_status = sl_status.value if (sl_status and hasattr(sl_status, "value")) else "IN_REVIEW"

        comp_status = c.completeness_status.value if hasattr(c.completeness_status, "value") else str(c.completeness_status)
        created_at_val = cand_obj.created_at if cand_obj else datetime.now(timezone.utc).isoformat()

        q_item = quality_map.get(c.candidate_id)
        if not q_item:
            try:
                q_item = orchestrator.get_candidate_quality_assessment(c.candidate_id, session_id=session_id)
                quality_map[c.candidate_id] = q_item
            except Exception:
                pass
        q_score = getattr(c, "resume_quality_score", None) or (q_item.overall_score if q_item else None)
        q_label = (
            getattr(c, "resume_quality_label", None)
            or (q_item.quality_label.value if q_item else None)
        )

        combined_items.append(
            CandidateSummary(
                id=c.candidate_id,
                candidate_id=c.candidate_id,
                name=c_name,
                original_filename=c_filename,
                email=c_email,
                fit_tier=c_tier,
                rank=c.rank,
                overall_score=c.overall_score,
                evidence_coverage=c.evidence_coverage,
                review_status=rev_status,
                is_tied=getattr(c, "is_tied", False),
                required_satisfied_count=sat_count,
                required_total_count=tot_count,
                missing_critical_count=c_missing,
                conflicts_count=conflicts,
                completeness_status=comp_status,
                session_status=cand_status_map.get(c.candidate_id, "PENDING"),
                created_at=created_at_val,
                resume_quality_score=q_score,
                resume_quality_label=q_label,
            )
        )

    if min_score is None and (not required_filter or required_filter == "ALL"):
        for sc in session_cands:
            cand_obj = sc["candidate"]
            if cand_obj.id not in ranked_ids:
                c_contact = contacts_map.get(cand_obj.id, {})
                c_name = _derive_name(cand_obj.original_filename, c_contact)
                if q and (q.lower() not in cand_obj.original_filename.lower() and q.lower() not in c_name.lower()):
                    continue
                st_val = sc["session_status"].value
                sl_entry = shortlist_map.get(cand_obj.id)
                cand_rev_status = sl_entry.review_status.value if sl_entry else "PENDING"
                q_item = quality_map.get(cand_obj.id)
                if not q_item:
                    try:
                        q_item = orchestrator.get_candidate_quality_assessment(cand_obj.id, session_id=session_id)
                        quality_map[cand_obj.id] = q_item
                    except Exception:
                        pass
                q_score = q_item.overall_score if q_item else None
                q_label = q_item.quality_label.value if q_item else None

                combined_items.append(
                    CandidateSummary(
                        id=cand_obj.id,
                        candidate_id=cand_obj.id,
                        name=c_name,
                        original_filename=cand_obj.original_filename,
                        email=c_contact.get("email") if isinstance(c_contact, dict) else None,
                        fit_tier="Under Review",
                        rank=0,
                        overall_score=None,
                        evidence_coverage=0.0,
                        review_status=cand_rev_status,
                        is_tied=False,
                        required_satisfied_count=0,
                        required_total_count=0,
                        missing_critical_count=0,
                        conflicts_count=0,
                        completeness_status="PENDING",
                        session_status=st_val,
                        created_at=cand_obj.created_at,
                        resume_quality_score=q_score,
                        resume_quality_label=q_label,
                    )
                )

    scored_items = [c for c in combined_items if c.overall_score is not None]
    unscored_items = [c for c in combined_items if c.overall_score is None]
    scored_items.sort(key=lambda c: c.overall_score or 0.0, reverse=True)
    for idx, c in enumerate(scored_items):
        c.rank = idx + 1

    if status_val and status_val.upper() != "ALL":
        target_st = status_val.upper().replace("-", "_").replace(" ", "_")
        if target_st in ("SHORTLISTED", "SHORTLIST"):
            combined_items = [c for c in combined_items if c.review_status == "SHORTLISTED"]
        elif target_st in ("IN_REVIEW", "UNDER_REVIEW"):
            combined_items = [c for c in combined_items if c.review_status in ("IN_REVIEW", "UNDER_REVIEW")]
        elif target_st in ("NOT_SHORTLISTED", "REJECTED"):
            combined_items = [c for c in combined_items if c.review_status in ("NOT_SHORTLISTED", "REJECTED")]
        else:
            combined_items = [
                c for c in combined_items
                if c.review_status == target_st or c.session_status == target_st
            ]
    else:
        combined_items = scored_items + unscored_items

    if sort_by_val == "score_desc":
        combined_items.sort(key=lambda c: (c.overall_score is not None, c.overall_score or 0.0), reverse=True)
    elif sort_by_val == "score_asc":
        combined_items.sort(key=lambda c: (c.overall_score is not None, c.overall_score or 0.0))
    elif sort_by_val == "quality_desc":
        combined_items.sort(key=lambda c: (c.resume_quality_score is not None, c.resume_quality_score or 0.0), reverse=True)
    elif sort_by_val == "quality_asc":
        combined_items.sort(key=lambda c: (c.resume_quality_score is not None, c.resume_quality_score or 0.0))
    elif sort_by_val == "filename":
        combined_items.sort(key=lambda c: c.original_filename.lower())
    else:
        combined_items.sort(key=lambda c: c.rank if c.rank > 0 else 999999)

    total = len(combined_items)
    total_pages = max(1, math.ceil(total / effective_page_size))
    start_idx = (page_val - 1) * effective_page_size
    paged = combined_items[start_idx : start_idx + effective_page_size]

    return CandidateListResponse(
        items=paged,
        total=total,
        page=page_val,
        page_size=effective_page_size,
        total_pages=total_pages,
    )


@router.get("/candidates/{candidate_id}", response_model=CandidateDetailResponse)
def get_candidate_details(
    candidate_id: str,
    session_id: Optional[str] = Query(None),
    orchestrator: ScreeningOrchestrator = Depends(get_orchestrator),
    db: Database = Depends(get_database),
):
    cand_repo = CandidateRepository(db)
    cand = cand_repo.get(candidate_id)
    if not cand:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail=f"Candidate '{candidate_id}' not found.")

    structured_data = cand_repo.get_structured_data(candidate_id) or {}

    skills_rows = db.execute_query("SELECT * FROM extracted_skills WHERE candidate_id = ?;", (candidate_id,))
    skills = [r["skill_name"] for r in skills_rows] if skills_rows else structured_data.get("skills", [])

    exp_rows = db.execute_query("SELECT * FROM work_experience WHERE candidate_id = ?;", (candidate_id,))
    experience = [dict(r) for r in exp_rows] if exp_rows else structured_data.get("experience", [])

    edu_rows = db.execute_query("SELECT * FROM education_records WHERE candidate_id = ?;", (candidate_id,))
    education = [dict(r) for r in edu_rows] if edu_rows else structured_data.get("education", [])

    shortlist_repo = ShortlistRepository(db)
    shortlist_record = None
    if session_id:
        shortlist_record = shortlist_repo.get(session_id, candidate_id)
    if not shortlist_record:
        all_sl = shortlist_repo.list_by_candidate(candidate_id)
        shortlist_record = all_sl[0] if all_sl else None

    score_repo = ScoreRepository(db)
    score_rec = score_repo.get_score(candidate_id)
    score_val = score_rec.overall_score if score_rec else None

    scoring_repo = ScoringRecordRepository(db)
    scoring_rec = scoring_repo.get_latest_by_candidate(candidate_id)
    explanation_val = scoring_rec.explanation if scoring_rec else (score_rec.explanation if score_rec else None)
    if not explanation_val:
        eval_repo = EvaluationRecordRepository(db)
        eval_rec = eval_repo.get_latest_record(candidate_id, session_id)
        if eval_rec:
            parts = [
                f"Candidate achieved an overall score of {eval_rec.overall_score:.1f}/100 "
                f"with {eval_rec.evidence_coverage:.1f}% verified criterion evidence coverage."
            ]
            if eval_rec.unmet_mandatory_criteria:
                parts.append(f"Unmet mandatory requirements: {', '.join(eval_rec.unmet_mandatory_criteria)}.")
            if eval_rec.conflicting_criteria:
                parts.append(f"Discrepancies flagged in: {', '.join(eval_rec.conflicting_criteria)}.")
            explanation_val = " ".join(parts)

    contact_dict = structured_data.get("contact", {})
    name_val = _derive_name(cand.original_filename, contact_dict)
    email_val = contact_dict.get("email") if isinstance(contact_dict, dict) else None
    phone_val = contact_dict.get("phone") if isinstance(contact_dict, dict) else None

    rank_val = None
    target_session_id = session_id
    if not target_session_id:
        try:
            with db.get_connection() as conn:
                s_row = conn.execute(
                    "SELECT session_id FROM session_candidates WHERE candidate_id = ? LIMIT 1;",
                    (cand.id,),
                ).fetchone()
                if s_row:
                    target_session_id = s_row["session_id"]
        except Exception:
            pass

    if target_session_id and score_val is not None:
        try:
            with db.get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT sc.candidate_id, COALESCE(cs.overall_score, 0) as score
                    FROM session_candidates sc
                    JOIN candidates c ON sc.candidate_id = c.id
                    LEFT JOIN candidate_scores cs ON c.id = cs.candidate_id
                    WHERE sc.session_id = ?
                    ORDER BY COALESCE(cs.overall_score, 0) DESC, c.created_at ASC;
                    """,
                    (target_session_id,),
                )
                for idx, row in enumerate(cursor.fetchall(), start=1):
                    if row["candidate_id"] == cand.id:
                        rank_val = idx
                        break
        except Exception:
            pass

    eval_repo = EvaluationRecordRepository(db)
    eval_rec = eval_repo.get_latest_record(candidate_id, session_id)
    cand_discrepancies: List[Dict[str, Any]] = []
    unmet_list = eval_rec.unmet_mandatory_criteria if eval_rec else []
    conflict_list = eval_rec.conflicting_criteria if eval_rec else []

    if eval_rec:
        crit_dicts = [r.to_dict() for r in eval_rec.criterion_results]
        cand_discrepancies = DiscrepancyDetector.detect_discrepancies(
            candidate_id=candidate_id,
            criterion_results=crit_dicts,
            overall_score=eval_rec.overall_score,
            evidence_coverage=eval_rec.evidence_coverage,
            experience=experience,
            skills=skills,
            extracted_text=cand.extracted_text,
            projects=structured_data.get("projects", []),
            conflicting_criteria=conflict_list,
            unmet_mandatory_criteria=unmet_list,
        )
    elif score_val is not None:
        cand_discrepancies = DiscrepancyDetector.detect_discrepancies(
            candidate_id=candidate_id,
            criterion_results=[],
            overall_score=score_val,
            experience=experience,
            skills=skills,
            extracted_text=cand.extracted_text,
            projects=structured_data.get("projects", []),
        )

    try:
        quality_assessment = orchestrator.get_candidate_quality_assessment(
            candidate_id, session_id=target_session_id
        )
        q_data = quality_assessment.to_dict() if quality_assessment else None
        q_score = quality_assessment.overall_score if quality_assessment else None
        q_label = quality_assessment.quality_label.value if quality_assessment else None
    except Exception as q_err:
        q_data = None
        q_score = None
        q_label = None

    return CandidateDetailResponse(
        id=cand.id,
        candidate_id=cand.id,
        name=name_val,
        email=email_val,
        phone=phone_val,
        fit_tier=_compute_fit_tier(score_val),
        rank=rank_val,
        overall_score=score_val,
        original_filename=cand.original_filename,
        file_type=cand.file_type.value,
        file_hash=cand.file_hash,
        processing_status=cand.processing_status.value,
        error_info=cand.error_info,
        created_at=cand.created_at,
        contact=contact_dict,
        ocr_needed=structured_data.get("ocr_needed", False),
        sections=structured_data.get("sections", []),
        skills=skills,
        experience=experience,
        education=education,
        projects=structured_data.get("projects", []),
        certifications=structured_data.get("certifications", []),
        extracted_text=cand.extracted_text,
        latest_score=score_val,
        review_status=shortlist_record.review_status.value if shortlist_record else "IN_REVIEW",
        reviewer_notes=shortlist_record.reviewer_notes if shortlist_record else None,
        notes=shortlist_record.reviewer_notes if shortlist_record else None,
        explanation=explanation_val,
        ai_review=explanation_val,
        unmet_mandatory_criteria=unmet_list,
        conflicting_criteria=conflict_list,
        discrepancies=cand_discrepancies,
        discrepancy_count=len(cand_discrepancies),
        resume_quality=q_data,
        resume_quality_score=q_score,
        resume_quality_label=q_label,
    )


@router.get("/candidates/{candidate_id}/quality", response_model=ResumeQualityReportResponse)
def get_candidate_quality_report(
    candidate_id: str,
    session_id: Optional[str] = Query(None),
    orchestrator: ScreeningOrchestrator = Depends(get_orchestrator),
):
    try:
        assessment = orchestrator.get_candidate_quality_assessment(candidate_id, session_id=session_id)
        return assessment.to_dict()
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Could not retrieve resume quality assessment for candidate '{candidate_id}': {e}",
        )


@router.get("/candidates/{candidate_id}/evaluation", response_model=CandidateEvaluationResponse)
def get_candidate_evaluation(
    candidate_id: str,
    session_id: Optional[str] = Query(None),
    db: Database = Depends(get_database),
):
    eval_repo = EvaluationRecordRepository(db)
    eval_record = eval_repo.get_latest_record(candidate_id, session_id if session_id else None)

    if not eval_record:
        score_repo = ScoreRepository(db)
        cand_score = score_repo.get_score(candidate_id)
        if not cand_score:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"No evaluation record found for candidate '{candidate_id}'.",
            )
        return CandidateEvaluationResponse(
            candidate_id=candidate_id,
            session_id=session_id,
            overall_score=cand_score.overall_score,
            evidence_coverage=0.0,
            config_version="v1.0",
            evaluated_at=cand_score.evaluated_at,
            fit_tier=_compute_fit_tier(cand_score.overall_score),
            unmet_mandatory_criteria=[],
            conflicting_criteria=[],
            criterion_results=[],
            criterion_contributions=[],
            criteria_scores=[],
            discrepancies=[],
            explanation=cand_score.explanation,
            ai_review=cand_score.explanation,
        )

    scoring_repo = ScoringRecordRepository(db)
    scoring_rec = scoring_repo.get_latest_by_candidate(candidate_id)

    crit_results = [
        CriterionResultItem(
            criterion_name=r.criterion_name,
            criterion_type=r.criterion_type.value if hasattr(r.criterion_type, "value") else str(r.criterion_type),
            category=r.category.value if r.category and hasattr(r.category, "value") else (str(r.category) if r.category else None),
            weight=r.weight,
            score=r.score,
            match_status=r.match_status.value if hasattr(r.match_status, "value") else str(r.match_status),
            explanation=r.explanation,
            supporting_evidence=r.supporting_evidence or [],
            evidence_sources=r.evidence_sources or [],
            matching_method=r.matching_method,
            similarity_tier=r.similarity_tier.value if r.similarity_tier and hasattr(r.similarity_tier, "value") else (str(r.similarity_tier) if r.similarity_tier else None),
            semantic_score=r.semantic_score if r.semantic_score is not None else 0.0,
            synthesis_items=r.synthesis_items or [],
        )
        for r in eval_record.criterion_results
    ]

    criteria_scores = [
        {
            "criterion_name": r.criterion_name,
            "score": round(r.score * 100, 1) if r.score <= 1.0 else round(r.score, 1),
            "weight": r.weight,
            "is_required": (r.criterion_type.value == "REQUIRED") if hasattr(r.criterion_type, "value") else (str(r.criterion_type) == "REQUIRED"),
            "explanation": r.explanation,
            "evidence": r.supporting_evidence or [],
            "match_status": r.match_status.value if hasattr(r.match_status, "value") else str(r.match_status),
        }
        for r in eval_record.criterion_results
    ]

    cand_repo = CandidateRepository(db)
    cand = cand_repo.get(candidate_id)
    structured_data = cand_repo.get_structured_data(candidate_id) or {} if cand else {}
    exp_rows = db.execute_query("SELECT * FROM work_experience WHERE candidate_id = ?;", (candidate_id,))
    experience = [dict(r) for r in exp_rows] if exp_rows else structured_data.get("experience", [])
    skills_rows = db.execute_query("SELECT skill_name FROM extracted_skills WHERE candidate_id = ?;", (candidate_id,))
    skills = [r["skill_name"] for r in skills_rows] if skills_rows else structured_data.get("skills", [])
    projects = structured_data.get("projects", [])
    extracted_text = cand.extracted_text if cand else ""

    crit_dicts = [r.to_dict() for r in eval_record.criterion_results]
    discrepancies = DiscrepancyDetector.detect_discrepancies(
        candidate_id=candidate_id,
        criterion_results=crit_dicts,
        overall_score=eval_record.overall_score,
        evidence_coverage=eval_record.evidence_coverage,
        experience=experience,
        skills=skills,
        extracted_text=extracted_text,
        projects=projects,
        conflicting_criteria=eval_record.conflicting_criteria,
        unmet_mandatory_criteria=eval_record.unmet_mandatory_criteria,
    )

    contrib_items = []
    if scoring_rec:
        for c in scoring_rec.criterion_contributions:
            contrib_items.append(
                ScoringContributionItem(
                    criterion_name=c.criterion_name,
                    category=c.category.value if hasattr(c.category, "value") else str(c.category),
                    criterion_type=c.criterion_type.value if hasattr(c.criterion_type, "value") else str(c.criterion_type),
                    configured_weight=c.configured_weight,
                    support_value=c.support_value,
                    normalized_contribution=c.normalized_contribution,
                    notes=c.notes,
                    match_status=c.match_status.value if hasattr(c.match_status, "value") else str(c.match_status),
                )
            )

    explanation_val = scoring_rec.explanation if scoring_rec else None
    if not explanation_val:
        score_repo = ScoreRepository(db)
        cand_score = score_repo.get_score(candidate_id)
        if cand_score and cand_score.explanation:
            explanation_val = cand_score.explanation

    if not explanation_val:
        parts = [
            f"Candidate achieved an overall score of {eval_record.overall_score:.1f}/100 "
            f"with {eval_record.evidence_coverage:.1f}% verified criterion evidence coverage."
        ]
        if eval_record.unmet_mandatory_criteria:
            parts.append(f"Unmet mandatory requirements: {', '.join(eval_record.unmet_mandatory_criteria)}.")
        if eval_record.conflicting_criteria:
            parts.append(f"Discrepancies flagged in: {', '.join(eval_record.conflicting_criteria)}.")
        if eval_record.semantic_summary and eval_record.semantic_summary.get("average_semantic_score"):
            parts.append(f"Semantic match strength: {eval_record.semantic_summary.get('average_semantic_score', 0):.1f}%.")
        explanation_val = " ".join(parts)

    return CandidateEvaluationResponse(
        candidate_id=eval_record.candidate_id,
        session_id=eval_record.session_id,
        overall_score=eval_record.overall_score,
        evidence_coverage=eval_record.evidence_coverage,
        config_version=eval_record.config_version,
        evaluated_at=eval_record.evaluated_at,
        fit_tier=_compute_fit_tier(eval_record.overall_score),
        unmet_mandatory_criteria=eval_record.unmet_mandatory_criteria,
        conflicting_criteria=eval_record.conflicting_criteria,
        baseline_summary=eval_record.baseline_summary,
        semantic_summary=eval_record.semantic_summary,
        structured_summary=eval_record.structured_summary,
        criterion_results=crit_results,
        criterion_contributions=contrib_items,
        criteria_scores=criteria_scores,
        discrepancies=discrepancies,
        explanation=explanation_val,
        ai_review=explanation_val,
    )


@router.put("/candidates/{candidate_id}/shortlist")
def update_shortlist_status(
    candidate_id: str,
    payload: ShortlistUpdateRequest,
    session_id: Optional[str] = Query(None, description="Target session context"),
    orchestrator: ScreeningOrchestrator = Depends(get_orchestrator),
):
    if not session_id:
        rows = orchestrator.db.execute_query(
            "SELECT session_id FROM session_candidates WHERE candidate_id = ? LIMIT 1",
            (candidate_id,),
        )
        if rows:
            session_id = rows[0]["session_id"]
        else:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Candidate '{candidate_id}' is not enrolled in any session.",
            )

    status_raw = (payload.review_status or "IN_REVIEW").strip().upper().replace("-", "_").replace(" ", "_")
    STATUS_MAP = {
        "SHORTLISTED": ShortlistReviewStatus.SHORTLISTED,
        "SHORTLIST": ShortlistReviewStatus.SHORTLISTED,
        "UNDER_REVIEW": ShortlistReviewStatus.IN_REVIEW,
        "IN_REVIEW": ShortlistReviewStatus.IN_REVIEW,
        "REVIEW": ShortlistReviewStatus.IN_REVIEW,
        "NEEDS_REVIEW": ShortlistReviewStatus.NEEDS_REVIEW,
        "PENDING": ShortlistReviewStatus.NEEDS_REVIEW,
        "NOT_SHORTLISTED": ShortlistReviewStatus.NOT_SHORTLISTED,
        "NOT_SHORTLIST": ShortlistReviewStatus.NOT_SHORTLISTED,
        "REJECTED": ShortlistReviewStatus.NOT_SHORTLISTED,
        "ARCHIVED": ShortlistReviewStatus.NOT_SHORTLISTED,
        "ON_HOLD": ShortlistReviewStatus.ON_HOLD,
        "HOLD": ShortlistReviewStatus.ON_HOLD,
    }
    review_enum = STATUS_MAP.get(status_raw, ShortlistReviewStatus.IN_REVIEW)

    updated_record = orchestrator.shortlist_service.set_review_status(
        session_id=session_id,
        candidate_id=candidate_id,
        status=review_enum,
        reviewer_notes=payload.reviewer_notes,
    )
    return {
        "candidate_id": candidate_id,
        "session_id": session_id,
        "review_status": updated_record.review_status.value,
        "reviewer_notes": updated_record.reviewer_notes,
        "updated_at": updated_record.updated_at,
    }
