
from typing import Any, Dict, List, Optional, Set
import uuid

from core.models.enums import CriterionCategory, CriterionType, MatchStatus
from core.models.report_models import (
    AlignedCriterionComparisonRow,
    CandidateComparisonData,
    ComparisonCompatibilityResult,
)
from core.storage.database import Database
from core.storage.eval_repository import EvaluationRecordRepository
from core.storage.repositories import (
    CandidateRepository,
    JobRepository,
    SessionRepository,
)
from core.storage.scoring_repository import ScoringRecordRepository
from core.storage.shortlist_repository import ShortlistRepository
from core.utils.logger import logger


class CandidateComparisonService:

    def __init__(self, db: Database):
        self.db = db
        self.candidate_repo = CandidateRepository(db)
        self.session_repo = SessionRepository(db)
        self.job_repo = JobRepository(db)
        self.eval_repo = EvaluationRecordRepository(db)
        self.scoring_repo = ScoringRecordRepository(db)
        self.shortlist_repo = ShortlistRepository(db)

    def compare_candidates(
        self,
        candidate_ids: List[str],
        session_id: str,
        selected_criterion_ids: Optional[List[str]] = None,
    ) -> CandidateComparisonData:
        if len(candidate_ids) < 2:
            raise ValueError("Candidate comparison requires at least 2 candidates.")

        session = self.session_repo.get(session_id)
        if not session:
            raise ValueError(f"Screening Session '{session_id}' not found.")

        job = self.job_repo.get(session.job_id)
        job_title = job.title if job else "General Role"

        candidates = [self.candidate_repo.get(cid) for cid in candidate_ids]
        candidates = [c for c in candidates if c is not None]
        if len(candidates) < 2:
            raise ValueError("Fewer than 2 valid candidates were resolved for comparison.")

        scoring_map = {}
        eval_map = {}
        shortlist_map = {}

        for cand in candidates:
            s_rec = self.scoring_repo.get_by_candidate_and_session(cand.id, session_id)
            if s_rec:
                scoring_map[cand.id] = s_rec
            e_rec = self.eval_repo.get_by_candidate_and_session(cand.id, session_id)
            if e_rec:
                eval_map[cand.id] = e_rec
            sl_rec = self.shortlist_repo.get(session_id, cand.id)
            if sl_rec:
                shortlist_map[cand.id] = sl_rec

        compatibility = self._check_compatibility(session.job_id, candidates, scoring_map, eval_map)

        from core.storage.quality_repository import ResumeQualityRepository
        quality_repo = ResumeQualityRepository(self.db)
        candidate_headers: List[Dict[str, Any]] = []

        for cand in candidates:
            s_rec = scoring_map.get(cand.id)
            e_rec = eval_map.get(cand.id)
            sl_rec = shortlist_map.get(cand.id)
            q_rec = quality_repo.get_by_candidate(cand.id)

            cand_score = s_rec.overall_score if s_rec else (e_rec.overall_score if e_rec else None)
            cand_cov = s_rec.evidence_coverage if s_rec else (e_rec.evidence_coverage if e_rec else 0.0)
            cand_status = sl_rec.review_status.value if sl_rec else "NEEDS_REVIEW"
            cand_notes = sl_rec.reviewer_notes if sl_rec else ""
            q_score = q_rec.overall_score if q_rec else None
            q_label = q_rec.quality_label.value if q_rec else None

            structured = self.candidate_repo.get_structured_data(cand.id) or {}
            contact = structured.get("contact", {}) if isinstance(structured, dict) else {}
            c_name = None
            if contact and isinstance(contact, dict):
                c_name = contact.get("name") or contact.get("full_name")
            if not c_name or not str(c_name).strip():
                import re, os
                stem = os.path.splitext(cand.original_filename)[0]
                cleaned = re.sub(r"^(resume|cv|candidate)[_\-\s]+", "", stem, flags=re.IGNORECASE)
                cleaned = re.sub(r"[_\-\s]+(resume|cv)$", "", cleaned, flags=re.IGNORECASE)
                cleaned = cleaned.replace("_", " ").replace("-", " ").strip()
                c_name = cleaned.title() if cleaned else stem.title()

            c_email = contact.get("email") if isinstance(contact, dict) else None

            candidate_headers.append({
                "candidate_id": cand.id,
                "id": cand.id,
                "candidate_reference": f"Cand-{cand.id[:8].upper()}",
                "candidate_name": c_name,
                "name": c_name,
                "email": c_email,
                "original_filename": cand.original_filename,
                "overall_score": cand_score,
                "fit_tier": "Strong Match" if cand_score and cand_score >= 80 else ("Potential Match" if cand_score and cand_score >= 60 else "Under Review"),
                "evidence_coverage": cand_cov,
                "review_status": cand_status,
                "reviewer_notes": cand_notes,
                "resume_quality_score": q_score,
                "resume_quality_label": q_label,
                "config_version": s_rec.scoring_config_version if s_rec else (e_rec.config_version if e_rec else "N/A"),
            })

        aligned_rows = self._build_aligned_criteria(
            candidates=candidates,
            scoring_map=scoring_map,
            eval_map=eval_map,
            selected_criterion_ids=selected_criterion_ids,
        )

        edu_comp = {}
        exp_comp = {}
        for cand in candidates:
            structured = self.candidate_repo.get_structured_data(cand.id)
            ed_list = structured.get("education", [])
            deg_names = [e.get("qualification") or e.get("degree") for e in ed_list if isinstance(e, dict)]
            edu_comp[cand.id] = ", ".join(deg_names) if deg_names else "Not Specified"

            exp_list = structured.get("experience", [])
            job_titles = [x.get("job_title") or x.get("title") for x in exp_list if isinstance(x, dict)]
            exp_comp[cand.id] = f"{len(exp_list)} roles ({', '.join(job_titles[:2])}...)" if job_titles else "Tenure details unmentioned"

        differentiators = []
        for row in aligned_rows:
            if row.has_meaningful_difference:
                differentiators.append(f"Criterion '{row.criterion_name}': {row.variance_note}")

        return CandidateComparisonData(
            report_id=str(uuid.uuid4()),
            session_id=session.id,
            session_name=session.session_name,
            job_id=session.job_id,
            job_title=job_title,
            compared_candidate_ids=[c.id for c in candidates],
            candidate_headers=candidate_headers,
            compatibility=compatibility,
            aligned_criteria_rows=aligned_rows,
            education_comparison=edu_comp,
            experience_comparison=exp_comp,
            key_differentiators=differentiators[:5],
        )

    def _check_compatibility(
        self,
        job_id: str,
        candidates: List[Any],
        scoring_map: Dict[str, Any],
        eval_map: Dict[str, Any],
    ) -> ComparisonCompatibilityResult:
        warnings: List[str] = []
        is_compatible = True

        versions: Set[str] = set()
        for cand in candidates:
            s_rec = scoring_map.get(cand.id)
            if s_rec:
                versions.add(s_rec.scoring_config_version)
            elif cand.id in eval_map:
                versions.add(eval_map[cand.id].config_version)

        shared_version = versions.pop() if len(versions) == 1 else None

        if len(versions) > 0:
            is_compatible = False
            all_vers = list(versions) + ([shared_version] if shared_version else [])
            warnings.append(
                f"Configuration Version Discrepancy: Compared candidates were evaluated under "
                f"different scoring configuration versions ({', '.join(all_vers)}). "
                f"Relative scores may reflect distinct criterion weightings."
            )

        cand_criteria_sets: List[Set[str]] = []
        for cand in candidates:
            c_set: Set[str] = set()
            s_rec = scoring_map.get(cand.id)
            if s_rec:
                c_set = {cc.criterion_name.strip().lower() for cc in s_rec.criterion_contributions}
            elif cand.id in eval_map:
                c_set = {cr.criterion_name.strip().lower() for cr in eval_map[cand.id].criterion_results}
            if c_set:
                cand_criteria_sets.append(c_set)

        common_count = 0
        discrepant: List[str] = []
        if cand_criteria_sets:
            common = set.intersection(*cand_criteria_sets)
            common_count = len(common)
            union = set.union(*cand_criteria_sets)
            diff = union - common
            if diff:
                is_compatible = False
                discrepant = sorted(list(diff))
                warnings.append(
                    f"Inconsistent Criteria: {len(discrepant)} criteria are evaluated for some candidates "
                    f"but absent in others ({', '.join(discrepant[:3])}{'...' if len(discrepant) > 3 else ''})."
                )

        return ComparisonCompatibilityResult(
            is_compatible=is_compatible,
            shared_job_id=job_id,
            shared_config_version=shared_version,
            compatibility_warnings=warnings,
            common_criteria_count=common_count,
            discrepant_criteria=discrepant,
        )

    def _build_aligned_criteria(
        self,
        candidates: List[Any],
        scoring_map: Dict[str, Any],
        eval_map: Dict[str, Any],
        selected_criterion_ids: Optional[List[str]] = None,
    ) -> List[AlignedCriterionComparisonRow]:
        criteria_catalog: Dict[str, Dict[str, Any]] = {}

        for cand in candidates:
            s_rec = scoring_map.get(cand.id)
            if s_rec:
                for cc in s_rec.criterion_contributions:
                    c_id = cc.criterion_id
                    if c_id not in criteria_catalog:
                        criteria_catalog[c_id] = {
                            "id": c_id,
                            "name": cc.criterion_name,
                            "category": cc.category,
                            "type": cc.criterion_type,
                            "weight": cc.configured_weight,
                        }
            elif cand.id in eval_map:
                for cr in eval_map[cand.id].criterion_results:
                    c_id = cr.criterion_id
                    if c_id not in criteria_catalog:
                        criteria_catalog[c_id] = {
                            "id": c_id,
                            "name": cr.criterion_name,
                            "category": getattr(cr, "category", CriterionCategory.TECHNICAL_SKILL),
                            "type": cr.criterion_type,
                            "weight": cr.weight,
                        }

        if selected_criterion_ids:
            criteria_catalog = {
                k: v for k, v in criteria_catalog.items() if k in selected_criterion_ids or v["name"] in selected_criterion_ids
            }

        aligned_rows: List[AlignedCriterionComparisonRow] = []

        for c_id, c_meta in criteria_catalog.items():
            cand_evals: Dict[str, Dict[str, Any]] = {}
            support_vals: List[float] = []

            for cand in candidates:
                s_rec = scoring_map.get(cand.id)
                e_rec = eval_map.get(cand.id)

                matched_item = None
                if s_rec:
                    for cc in s_rec.criterion_contributions:
                        if cc.criterion_id == c_id or cc.criterion_name.strip().lower() == c_meta["name"].strip().lower():
                            matched_item = cc
                            break

                ev_snippet = ""
                if e_rec:
                    for cr in e_rec.criterion_results:
                        if cr.criterion_id == c_id or cr.criterion_name.strip().lower() == c_meta["name"].strip().lower():
                            if hasattr(cr, "citations") and cr.citations:
                                ev_snippet = getattr(cr.citations[0], "evidence_text", str(cr.citations[0]))
                            elif hasattr(cr, "supporting_evidence") and cr.supporting_evidence:
                                ev_snippet = cr.supporting_evidence[0]
                            elif hasattr(cr, "top_passages") and cr.top_passages:
                                ev_snippet = str(cr.top_passages[0].get("text", "") or cr.top_passages[0].get("passage_text", ""))
                            break

                if matched_item:
                    s_val = matched_item.support_value
                    support_vals.append(s_val)
                    cand_evals[cand.id] = {
                        "support_value": s_val,
                        "normalized_points": matched_item.normalized_contribution,
                        "match_status": matched_item.match_status.value if hasattr(matched_item.match_status, "value") else str(matched_item.match_status),
                        "evidence_snippet": ev_snippet[:140] + ("..." if len(ev_snippet) > 140 else ""),
                        "is_missing": not matched_item.is_eligible,
                    }
                else:
                    cand_evals[cand.id] = {
                        "support_value": 0.0,
                        "normalized_points": 0.0,
                        "match_status": MatchStatus.NOT_EVALUATED.value,
                        "evidence_snippet": "Criterion not evaluated",
                        "is_missing": True,
                    }

            has_diff = False
            var_note = ""
            if support_vals:
                min_s = min(support_vals)
                max_s = max(support_vals)
                delta = max_s - min_s
                if delta >= 0.25:
                    has_diff = True
                    var_note = f"Score delta of {int(delta * 100)}% across candidates"
                elif any(cand_evals[c.id]["match_status"] == "SUPPORTED" for c in candidates) and any(
                    cand_evals[c.id]["match_status"] in ("NOT_FOUND", "INSUFFICIENT_EVIDENCE") for c in candidates
                ):
                    has_diff = True
                    var_note = "Supported in some candidates, unmentioned or insufficient in others"

            aligned_rows.append(
                AlignedCriterionComparisonRow(
                    criterion_id=c_id,
                    criterion_name=c_meta["name"],
                    category=c_meta["category"],
                    criterion_type=c_meta["type"],
                    configured_weight=c_meta["weight"],
                    candidate_evaluations=cand_evals,
                    has_meaningful_difference=has_diff,
                    variance_note=var_note,
                )
            )

        aligned_rows.sort(key=lambda r: (r.criterion_type == CriterionType.REQUIRED, r.configured_weight), reverse=True)
        return aligned_rows
