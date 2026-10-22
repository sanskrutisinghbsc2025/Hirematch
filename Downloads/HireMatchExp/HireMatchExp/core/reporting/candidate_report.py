
from typing import Any, Dict, List, Optional
import uuid

from core.models.enums import CriterionCategory, CriterionType, MatchStatus
from core.models.report_models import CandidateReportData, CriterionReportItem
from core.storage.database import Database
from core.storage.eval_repository import EvaluationRecordRepository
from core.storage.quality_repository import ResumeQualityRepository
from core.storage.repositories import (
    CandidateRepository,
    JobRepository,
    ScoreRepository,
    SessionRepository,
)
from core.storage.scoring_repository import ScoringRecordRepository
from core.storage.shortlist_repository import ShortlistRepository
from core.utils.logger import logger


class CandidateReportGenerator:

    def __init__(self, db: Database):
        self.db = db
        self.candidate_repo = CandidateRepository(db)
        self.session_repo = SessionRepository(db)
        self.job_repo = JobRepository(db)
        self.eval_repo = EvaluationRecordRepository(db)
        self.scoring_repo = ScoringRecordRepository(db)
        self.shortlist_repo = ShortlistRepository(db)
        self.score_repo = ScoreRepository(db)
        self.quality_repo = ResumeQualityRepository(db)

    def generate(
        self,
        candidate_id: str,
        session_id: str,
        include_pii: bool = False,
    ) -> CandidateReportData:
        candidate = self.candidate_repo.get(candidate_id)
        if not candidate:
            raise ValueError(f"Candidate '{candidate_id}' not found.")

        session = self.session_repo.get(session_id)
        if not session:
            raise ValueError(f"Session '{session_id}' not found.")

        job = self.job_repo.get(session.job_id)
        job_title = job.title if job else "General Position"

        scoring_record = self.scoring_repo.get_by_candidate_and_session(candidate_id, session_id)
        eval_record = self.eval_repo.get_by_candidate_and_session(candidate_id, session_id)
        shortlist_record = self.shortlist_repo.get(session_id, candidate_id)
        quality_record = self.quality_repo.get_by_candidate(candidate_id)

        criterion_items: List[CriterionReportItem] = []
        eval_evidence_map: Dict[str, Any] = {}
        if eval_record:
            for cr in eval_record.criterion_results:
                eval_evidence_map[cr.criterion_id] = cr
                eval_evidence_map[cr.criterion_name.strip().lower()] = cr

        if scoring_record and scoring_record.criterion_contributions:
            for cc in scoring_record.criterion_contributions:
                ev_res = eval_evidence_map.get(cc.criterion_id) or eval_evidence_map.get(cc.criterion_name.strip().lower())
                ev_texts = []
                ev_sections = []
                if ev_res:
                    if hasattr(ev_res, "citations") and ev_res.citations:
                        ev_texts = [getattr(c, "evidence_text", str(c)) for c in ev_res.citations]
                        ev_sections = list({getattr(c, "section", "") for c in ev_res.citations if getattr(c, "section", "")})
                    elif hasattr(ev_res, "supporting_evidence") and ev_res.supporting_evidence:
                        ev_texts = list(ev_res.supporting_evidence)
                        ev_sections = list(getattr(ev_res, "evidence_sources", []))

                method_name = "MULTI_LAYER"
                if ev_res and hasattr(ev_res, "matched_by") and ev_res.matched_by:
                    method_name = "+".join(ev_res.matched_by)

                crit_item = CriterionReportItem(
                    criterion_id=cc.criterion_id,
                    criterion_name=cc.criterion_name,
                    category=cc.category,
                    criterion_type=cc.criterion_type,
                    configured_weight=cc.configured_weight,
                    support_value=cc.support_value,
                    normalized_points=cc.normalized_contribution,
                    match_status=cc.match_status,
                    matching_method=method_name,
                    supporting_evidence=ev_texts,
                    source_sections=ev_sections,
                    explanation=cc.notes or (ev_res.explanation if ev_res else ""),
                    warnings=getattr(ev_res, "uncertainty_reasons", []) if ev_res else [],
                    is_eligible=cc.is_eligible,
                    exclusion_reason=cc.exclusion_reason,
                )
                criterion_items.append(crit_item)
        elif eval_record and eval_record.criterion_results:
            for er in eval_record.criterion_results:
                ev_texts = []
                ev_sections = []
                if hasattr(er, "citations") and er.citations:
                    ev_texts = [getattr(c, "evidence_text", str(c)) for c in er.citations]
                    ev_sections = list({getattr(c, "section", "") for c in er.citations if getattr(c, "section", "")})
                elif hasattr(er, "supporting_evidence") and er.supporting_evidence:
                    ev_texts = list(er.supporting_evidence)
                    ev_sections = list(getattr(er, "evidence_sources", []))

                crit_item = CriterionReportItem(
                    criterion_id=er.criterion_id,
                    criterion_name=er.criterion_name,
                    category=getattr(er, "category", CriterionCategory.TECHNICAL_SKILL),
                    criterion_type=er.criterion_type,
                    configured_weight=er.weight,
                    support_value=er.score,
                    normalized_points=round(er.score * er.weight * 100.0, 2),
                    match_status=er.match_status,
                    matching_method="MULTI_LAYER",
                    supporting_evidence=ev_texts,
                    source_sections=ev_sections,
                    explanation=er.explanation,
                    warnings=getattr(er, "uncertainty_reasons", []),
                    is_eligible=True,
                    exclusion_reason=None,
                )
                criterion_items.append(crit_item)

        structured = self.candidate_repo.get_structured_data(candidate_id)
        raw_contact = structured.get("contact", {})

        skills_data = self.candidate_repo.get_extracted_skills(candidate_id) if hasattr(self.candidate_repo, "get_extracted_skills") else []
        extracted_skills = [s.get("normalized_skill_name") or s.get("skill_name") for s in skills_data if isinstance(s, dict)]
        if not extracted_skills and "skills" in structured:
            extracted_skills = [s.get("normalized_name") or s.get("name") for s in structured.get("skills", []) if isinstance(s, dict)]

        work_experience = self.candidate_repo.get_work_experience(candidate_id) if hasattr(self.candidate_repo, "get_work_experience") else []
        if not work_experience and "experience" in structured:
            work_experience = structured.get("experience", [])

        education = self.candidate_repo.get_education(candidate_id) if hasattr(self.candidate_repo, "get_education") else []
        if not education and "education" in structured:
            education = structured.get("education", [])

        certifications = [
            c.get("name") for c in structured.get("certifications", []) if isinstance(c, dict) and "name" in c
        ]

        review_status = shortlist_record.review_status.value if shortlist_record else "NEEDS_REVIEW"
        reviewer_notes = shortlist_record.reviewer_notes if shortlist_record else ""
        shortlist_updated_at = shortlist_record.updated_at if shortlist_record else None

        overall_score = scoring_record.overall_score if scoring_record else (eval_record.overall_score if eval_record else None)
        evidence_coverage = scoring_record.evidence_coverage if scoring_record else (eval_record.evidence_coverage if eval_record else 0.0)
        completeness_status = (
            scoring_record.completeness_status.value
            if scoring_record and hasattr(scoring_record.completeness_status, "value")
            else (eval_record.evaluation_status if eval_record else "NOT_EVALUATED")
        )
        scoring_config_version = scoring_record.scoring_config_version if scoring_record else (eval_record.config_version if eval_record else "v1.0")

        total_crit = len(criterion_items)
        supp_crit = sum(1 for c in criterion_items if c.match_status == MatchStatus.SUPPORTED)
        part_crit = sum(1 for c in criterion_items if c.match_status == MatchStatus.PARTIALLY_SUPPORTED)
        insuff_crit = sum(1 for c in criterion_items if c.match_status in (MatchStatus.NOT_FOUND, MatchStatus.INSUFFICIENT_EVIDENCE))
        conf_crit = sum(1 for c in criterion_items if c.match_status == MatchStatus.CONFLICTING_EVIDENCE)

        warnings: List[str] = []
        limitations: List[str] = []

        if scoring_record and scoring_record.warnings:
            warnings.extend(scoring_record.warnings)
        if eval_record and eval_record.warnings:
            warnings.extend(eval_record.warnings)

        if overall_score is None:
            limitations.append("Overall score is unavailable due to insufficient scorable evidence.")
        if structured.get("ocr_needed"):
            warnings.append("Document was identified as an image-only scan requiring OCR; text extraction may be incomplete.")
        if conf_crit > 0:
            warnings.append(f"{conf_crit} criterion(s) exhibited conflicting cross-layer evidence and received zero credit pending manual review.")

        contact_info = None
        if include_pii:
            contact_info = {
                "name": raw_contact.get("name") or candidate.original_filename,
                "email": raw_contact.get("email") or "Not Provided",
                "phone": raw_contact.get("phone") or "Not Provided",
                "location": raw_contact.get("location") or "Not Provided",
            }
        else:
            contact_info = {
                "name": f"Candidate Ref: {candidate.id[:8]}",
                "email": "[PROTECTED - PII QUARANTINE]",
                "phone": "[PROTECTED - PII QUARANTINE]",
                "location": "[PROTECTED - PII QUARANTINE]",
            }

        return CandidateReportData(
            report_id=str(uuid.uuid4()),
            candidate_id=candidate.id,
            candidate_reference=f"Cand-{candidate.id[:8].upper()}",
            original_filename=candidate.original_filename,
            session_id=session.id,
            session_name=session.session_name,
            job_id=session.job_id,
            job_title=job_title,
            processing_status=candidate.processing_status.value if hasattr(candidate.processing_status, "value") else str(candidate.processing_status),
            evaluation_status=eval_record.evaluation_status if eval_record else "NOT_EVALUATED",
            evaluated_at=eval_record.evaluated_at if eval_record else None,
            scoring_config_version=scoring_config_version,
            overall_score=overall_score,
            evidence_coverage=evidence_coverage,
            completeness_status=completeness_status,
            total_criteria_count=total_crit,
            supported_criteria_count=supp_crit,
            partial_criteria_count=part_crit,
            insufficient_criteria_count=insuff_crit,
            conflicting_criteria_count=conf_crit,
            criterion_items=criterion_items,
            extracted_skills=extracted_skills,
            work_experience=work_experience,
            education=education,
            certifications=certifications,
            review_status=review_status,
            reviewer_notes=reviewer_notes,
            shortlist_updated_at=shortlist_updated_at,
            evaluation_warnings=list(set(warnings)),
            evidence_limitations=limitations,
            contact_info=contact_info,
            resume_quality_score=quality_record.overall_score if quality_record else None,
            resume_quality_label=quality_record.quality_label.value if quality_record else None,
        )
