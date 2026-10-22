
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import uuid

from core.evaluation.baseline_evaluator import BaselineCandidateEvaluator
from core.evaluation.criteria_validator import ResponsibleAICriteriaValidator
from core.evaluation.education_cert_evaluator import EducationCertEvaluator
from core.evaluation.evidence_synthesizer import MultiLayerEvidenceSynthesizer
from core.evaluation.experience_evaluator import ConservativeExperienceEvaluator
from core.evaluation.interfaces import ICandidateEvaluator
from core.evaluation.semantic_evaluator import SemanticCandidateEvaluator
from core.evaluation.semantic_matcher import SemanticMatcher
from core.models.candidate import Candidate
from core.models.enums import (
    CriterionCategory,
    CriterionType,
    EvidenceDisagreementType,
    MatchStatus,
    MatchType,
    ScoreStatus,
    SemanticSimilarityTier,
)
from core.models.eval_config import EvaluationConfiguration
from core.models.evaluation import (
    CandidateEvaluationRecord,
    CandidateScore,
    CriterionEvaluationResult,
    EvaluationCriterion,
    EvaluationEvidence,
)
from core.models.job import Job
from core.processing.resume_parser import StructuredResume, StructuredResumeParser
from core.utils.logger import logger


class MultiLayerCandidateEvaluator(ICandidateEvaluator):

    def __init__(
        self,
        baseline_evaluator: Optional[BaselineCandidateEvaluator] = None,
        semantic_evaluator: Optional[SemanticCandidateEvaluator] = None,
        experience_evaluator: Optional[ConservativeExperienceEvaluator] = None,
        education_cert_evaluator: Optional[EducationCertEvaluator] = None,
        synthesizer: Optional[MultiLayerEvidenceSynthesizer] = None,
        parser: Optional[StructuredResumeParser] = None,
        validator: Optional[ResponsibleAICriteriaValidator] = None,
    ):
        self.baseline_evaluator = baseline_evaluator or BaselineCandidateEvaluator()
        self.semantic_evaluator = semantic_evaluator
        self.experience_evaluator = experience_evaluator or ConservativeExperienceEvaluator()
        self.education_cert_evaluator = education_cert_evaluator or EducationCertEvaluator()
        self.synthesizer = synthesizer or MultiLayerEvidenceSynthesizer()
        self.parser = parser or StructuredResumeParser()
        self.validator = validator or ResponsibleAICriteriaValidator()

    def evaluate(
        self,
        candidate: Candidate,
        job: Job,
        criteria: List[EvaluationCriterion],
        structured_data: Optional[Dict[str, Any]] = None,
    ) -> List[EvaluationEvidence]:
        record = self.evaluate_candidate_record(
            candidate=candidate,
            job=job,
            criteria=criteria,
            structured_data=structured_data,
        )
        return self._record_to_evidence_list(record, candidate.id)

    def evaluate_candidate_record(
        self,
        candidate: Candidate,
        job: Job,
        criteria: Optional[List[EvaluationCriterion]] = None,
        config: Optional[EvaluationConfiguration] = None,
        structured_data: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
    ) -> CandidateEvaluationRecord:
        eval_config = config or EvaluationConfiguration.create_default(job_id=job.id)
        active_criteria = criteria if criteria is not None else eval_config.criteria

        compliant_criteria: List[EvaluationCriterion] = []
        for crit in active_criteria:
            val_res = self.validator.validate_criterion(crit)
            if val_res.is_valid:
                compliant_criteria.append(crit)
            else:
                logger.warning(
                    f"Criterion '{crit.criterion_name}' excluded by Responsible AI Validator: "
                    f"{'; '.join(val_res.violations)}"
                )

        resume_struct = self._load_structured_resume(candidate, structured_data)
        section_map = {s.canonical_name: s.content for s in resume_struct.sections}
        raw_text = candidate.extracted_text or resume_struct.raw_text

        baseline_results_map: Dict[str, CriterionEvaluationResult] = {}
        try:
            b_results, _ = self.baseline_evaluator.evaluate_candidate_detailed(
                candidate=candidate,
                job=job,
                criteria=compliant_criteria,
                structured_data=structured_data,
            )
            for res in b_results:
                baseline_results_map[res.criterion_id] = res
        except Exception as e:
            logger.error(f"Error during Layer 2 baseline evaluation for candidate {candidate.id}: {e}")

        semantic_results_map: Dict[str, CriterionEvaluationResult] = {}
        if self.semantic_evaluator:
            try:
                s_results, _ = self.semantic_evaluator.evaluate_candidate_detailed(
                    candidate=candidate,
                    job=job,
                    criteria=compliant_criteria,
                    structured_data=structured_data,
                )
                for res in s_results:
                    semantic_results_map[res.criterion_id] = res
            except Exception as e:
                logger.warning(f"Semantic evaluation skipped or failed for candidate {candidate.id}: {e}")

        criterion_results: List[CriterionEvaluationResult] = []
        unmet_mandatory: List[str] = []
        conflicting_criteria: List[str] = []
        warnings: List[str] = []

        for crit in compliant_criteria:
            cat = crit.category or self._infer_category(crit)
            crit.category = cat

            b_res = baseline_results_map.get(crit.id)
            s_res = semantic_results_map.get(crit.id)

            if not crit.is_enabled:
                c_res = CriterionEvaluationResult(
                    criterion_id=crit.id,
                    criterion_name=crit.criterion_name,
                    criterion_type=crit.criterion_type,
                    weight=crit.weight,
                    match_status=MatchStatus.NOT_EVALUATED,
                    score=0.0,
                    category=cat,
                    explanation="Criterion disabled in configuration.",
                )
            elif cat == CriterionCategory.EXPERIENCE_DURATION:
                c_res = self.experience_evaluator.evaluate(
                    criterion=crit,
                    work_experience=resume_struct.experience,
                    projects=getattr(resume_struct, "projects", []),
                    job_category=job.job_category,
                    relevant_keywords=getattr(crit, "keywords", None) or crit.matching_config.get("keywords"),
                )
            elif cat in (CriterionCategory.EDUCATION_REQUIREMENT, CriterionCategory.CERTIFICATION):
                cert_names = [c.name for c in resume_struct.certifications]
                c_res = self.education_cert_evaluator.evaluate(
                    criterion=crit,
                    education_records=resume_struct.education,
                    certifications=cert_names,
                    raw_text=raw_text,
                )
            else:
                structured_skills = [
                    {"evidence_text": s.evidence_text or s.skill_name, "source_location": s.source_location}
                    for s in resume_struct.skills
                    if s.skill_name.lower() in crit.criterion_name.lower() or crit.criterion_name.lower() in s.skill_name.lower()
                ]

                synth = self.synthesizer.synthesize_criterion(
                    criterion=crit,
                    baseline_result=b_res,
                    semantic_result=s_res,
                    structured_entities=structured_skills,
                    baseline_weight=eval_config.baseline_weight,
                    semantic_weight=eval_config.semantic_weight,
                )

                top_passages_dicts = [c.to_dict() for c in synth.citations]
                evidence_strings = [c.passage_text for c in synth.citations[:3]]
                evidence_sources = [c.source_section for c in synth.citations[:3]]

                c_res = CriterionEvaluationResult(
                    criterion_id=crit.id,
                    criterion_name=crit.criterion_name,
                    criterion_type=crit.criterion_type,
                    weight=crit.weight,
                    match_status=synth.match_status,
                    score=synth.synthesized_score,
                    matched_terms=b_res.matched_terms if b_res else [],
                    supporting_evidence=evidence_strings,
                    evidence_sources=evidence_sources,
                    matching_method="multi_layer_synthesized",
                    explanation=synth.explanation,
                    confidence=0.90 if synth.match_status == MatchStatus.SUPPORTED else 0.70,
                    is_negative_context=synth.is_negative_context,
                    semantic_score=synth.semantic_score,
                    similarity_tier=s_res.similarity_tier if s_res else None,
                    top_passages=top_passages_dicts,
                    category=cat,
                    disagreement_type=synth.disagreement_type,
                    conflict_explanation=synth.conflict_explanation,
                    synthesis_items=[c.to_dict() for c in synth.citations],
                )

            criterion_results.append(c_res)

            if c_res.match_status == MatchStatus.CONFLICTING_EVIDENCE or c_res.disagreement_type == EvidenceDisagreementType.KEYWORD_NEGATED_IN_CONTEXT:
                conflicting_criteria.append(crit.criterion_name)
                warnings.append(
                    f"Conflicting evidence flagged for '{crit.criterion_name}': {c_res.conflict_explanation or c_res.explanation}"
                )

            if crit.criterion_type == CriterionType.REQUIRED and c_res.match_status in (
                MatchStatus.NOT_FOUND,
                MatchStatus.INSUFFICIENT_EVIDENCE,
                MatchStatus.CONFLICTING_EVIDENCE,
            ):
                unmet_mandatory.append(crit.criterion_name)

        active_results = [r for r in criterion_results if r.match_status != MatchStatus.NOT_EVALUATED]
        total_active_weight = sum(r.weight for r in active_results) or 1.0

        weighted_sum = sum(r.score * r.weight for r in active_results)
        overall_score = round(weighted_sum / total_active_weight, 1)

        supported_count = sum(
            1 for r in active_results
            if r.match_status in (MatchStatus.SUPPORTED, MatchStatus.PARTIALLY_SUPPORTED)
        )
        total_active_criteria = len(active_results) or 1
        evidence_coverage = round((supported_count / total_active_criteria) * 100.0, 1)

        b_scores = [r.score for r in baseline_results_map.values() if r.match_status != MatchStatus.NOT_EVALUATED]
        s_scores = [r.score for r in semantic_results_map.values() if r.match_status != MatchStatus.NOT_EVALUATED]
        baseline_avg = round(sum(b_scores) / len(b_scores), 1) if b_scores else 0.0
        semantic_avg = round(sum(s_scores) / len(s_scores), 1) if s_scores else 0.0

        baseline_summary = {
            "evaluated_criteria_count": len(baseline_results_map),
            "average_baseline_score": baseline_avg,
            "weight": eval_config.baseline_weight,
        }
        semantic_summary = {
            "evaluated_criteria_count": len(semantic_results_map),
            "average_semantic_score": semantic_avg,
            "weight": eval_config.semantic_weight,
            "model_name": self.semantic_evaluator.matcher.model_name if self.semantic_evaluator else "None",
        }
        structured_summary = {
            "skills_extracted_count": len(resume_struct.skills),
            "experience_roles_count": len(resume_struct.experience),
            "education_records_count": len(resume_struct.education),
            "certifications_count": len(resume_struct.certifications),
            "sections_identified_count": len(resume_struct.sections),
        }

        eval_status = "CALCULATED"
        if conflicting_criteria:
            eval_status = "CONFLICT_REVIEW_REQUIRED"
        elif unmet_mandatory:
            eval_status = "MANDATORY_UNMET"

        record = CandidateEvaluationRecord(
            candidate_id=candidate.id,
            session_id=session_id or getattr(candidate, "session_id", "default_session"),
            config_id=eval_config.id,
            config_version=eval_config.version,
            overall_score=overall_score,
            evidence_coverage=evidence_coverage,
            evaluation_status=eval_status,
            criterion_results=criterion_results,
            baseline_summary=baseline_summary,
            semantic_summary=semantic_summary,
            structured_summary=structured_summary,
            unmet_mandatory_criteria=unmet_mandatory,
            conflicting_criteria=conflicting_criteria,
            warnings=warnings,
            evaluated_at=datetime.now(timezone.utc).isoformat(),
        )

        return record

    def evaluate_to_candidate_score(
        self,
        candidate: Candidate,
        job: Job,
        criteria: Optional[List[EvaluationCriterion]] = None,
        config: Optional[EvaluationConfiguration] = None,
        structured_data: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
    ) -> CandidateScore:
        record = self.evaluate_candidate_record(
            candidate=candidate,
            job=job,
            criteria=criteria,
            config=config,
            structured_data=structured_data,
            session_id=session_id,
        )
        return self.record_to_candidate_score(record, candidate.id)

    def record_to_candidate_score(
        self, record: CandidateEvaluationRecord, candidate_id: str
    ) -> CandidateScore:
        criterion_scores = {
            "evidence_coverage": record.evidence_coverage,
            "evaluation_mode": "MULTI_LAYER",
            "required_supported": len(record.unmet_mandatory_criteria) == 0,
            "required_unmet_count": len(record.unmet_mandatory_criteria),
            "baseline_score": record.baseline_summary.get("average_baseline_score", 0.0),
            "semantic_score": record.semantic_summary.get("average_semantic_score", 0.0),
            "combined_score": record.overall_score,
            "semantic_model": record.semantic_summary.get("model_name"),
            "config_id": record.config_id,
            "config_version": record.config_version,
            "criteria": [r.to_dict() for r in record.criterion_results],
            "conflicting_criteria": record.conflicting_criteria,
            "warnings": record.warnings,
        }

        explanation_lines = [
            f"Multi-Layer Evaluation (Score: {record.overall_score:.1f}, Coverage: {record.evidence_coverage:.1f}%)."
        ]
        if record.conflicting_criteria:
            explanation_lines.append(f"⚠️ Conflicting evidence detected in: {', '.join(record.conflicting_criteria)}.")
        if record.unmet_mandatory_criteria:
            explanation_lines.append(f"Mandatory requirements unmet: {', '.join(record.unmet_mandatory_criteria)}.")

        return CandidateScore(
            candidate_id=candidate_id,
            overall_score=record.overall_score,
            criterion_scores=criterion_scores,
            score_status=ScoreStatus.FLAGGED if record.conflicting_criteria else ScoreStatus.CALCULATED,
            explanation=" ".join(explanation_lines),
            scoring_config_version=record.config_version,
            evaluated_at=record.evaluated_at,
        )

    def _infer_category(self, criterion: EvaluationCriterion) -> CriterionCategory:
        name = criterion.criterion_name.lower()
        if "year" in name or "experience" in name or "tenure" in name:
            return CriterionCategory.EXPERIENCE_DURATION
        if "degree" in name or "bachelor" in name or "master" in name or "education" in name or "phd" in name:
            return CriterionCategory.EDUCATION_REQUIREMENT
        if "cert" in name or "aws" in name or "pmp" in name:
            return CriterionCategory.CERTIFICATION
        if "project" in name or "portfolio" in name:
            return CriterionCategory.PROJECT_EVIDENCE
        if "domain" in name or "industry" in name:
            return CriterionCategory.DOMAIN_EXPERIENCE
        return CriterionCategory.TECHNICAL_SKILL

    def _load_structured_resume(
        self, candidate: Candidate, structured_data: Optional[Dict[str, Any]] = None
    ) -> StructuredResume:
        return self.baseline_evaluator._load_structured_resume(candidate, structured_data)

    def _record_to_evidence_list(
        self, record: CandidateEvaluationRecord, candidate_id: str
    ) -> List[EvaluationEvidence]:
        evidence_list = []
        for c in record.criterion_results:
            match_type_map = {
                MatchStatus.SUPPORTED: MatchType.EXACT,
                MatchStatus.PARTIALLY_SUPPORTED: MatchType.PARTIAL,
                MatchStatus.NOT_FOUND: MatchType.MISSING,
                MatchStatus.INSUFFICIENT_EVIDENCE: MatchType.PARTIAL,
                MatchStatus.CONFLICTING_EVIDENCE: MatchType.NOT_EVALUATED,
                MatchStatus.NOT_EVALUATED: MatchType.NOT_EVALUATED,
            }
            primary_evidence = (
                c.supporting_evidence[0] if c.supporting_evidence else "No positive excerpt found."
            )
            evidence_source = c.evidence_sources[0] if c.evidence_sources else "general"

            evidence_list.append(
                EvaluationEvidence(
                    candidate_id=candidate_id,
                    criterion_id=c.criterion_id,
                    supporting_text=primary_evidence,
                    match_type=match_type_map.get(c.match_status, MatchType.NOT_EVALUATED),
                    evidence_source=evidence_source,
                    evaluation_status="EVALUATED" if c.match_status != MatchStatus.NOT_EVALUATED else "SKIPPED",
                    explanation=c.explanation,
                )
            )
        return evidence_list
