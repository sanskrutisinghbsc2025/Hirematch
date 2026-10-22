
from typing import Any, Dict, List, Optional, Tuple

from core.evaluation.education_matcher import EducationMatcher
from core.evaluation.experience_matcher import ExperienceMatcher
from core.evaluation.interfaces import ICandidateEvaluator
from core.evaluation.keyword_matcher import SectionAwareKeywordMatcher
from core.models.candidate import Candidate
from core.models.enums import CriterionType, MatchStatus, MatchType
from core.models.evaluation import (
    CriterionEvaluationResult,
    EvaluationCriterion,
    EvaluationEvidence,
)
from core.models.job import Job
from core.processing.resume_parser import StructuredResume, StructuredResumeParser


class BaselineCandidateEvaluator(ICandidateEvaluator):

    def __init__(
        self,
        keyword_matcher: Optional[SectionAwareKeywordMatcher] = None,
        experience_matcher: Optional[ExperienceMatcher] = None,
        education_matcher: Optional[EducationMatcher] = None,
        parser: Optional[StructuredResumeParser] = None,
    ):
        self.keyword_matcher = keyword_matcher or SectionAwareKeywordMatcher()
        self.experience_matcher = experience_matcher or ExperienceMatcher()
        self.education_matcher = education_matcher or EducationMatcher()
        self.parser = parser or StructuredResumeParser()

    def evaluate(
        self,
        candidate: Candidate,
        job: Job,
        criteria: List[EvaluationCriterion],
        structured_data: Optional[Dict[str, Any]] = None,
    ) -> List[EvaluationEvidence]:
        results, evidence_list = self.evaluate_candidate_detailed(
            candidate=candidate,
            job=job,
            criteria=criteria,
            structured_data=structured_data,
        )
        return evidence_list

    def evaluate_candidate_detailed(
        self,
        candidate: Candidate,
        job: Job,
        criteria: List[EvaluationCriterion],
        structured_data: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[CriterionEvaluationResult], List[EvaluationEvidence]]:
        resume_struct = self._load_structured_resume(candidate, structured_data)

        section_map = {s.canonical_name: s.content for s in resume_struct.sections}

        criterion_results: List[CriterionEvaluationResult] = []
        evidence_records: List[EvaluationEvidence] = []

        for crit in criteria:
            crit_category = self._classify_criterion(crit)

            if crit_category == "EXPERIENCE":
                c_res = self.experience_matcher.evaluate_criterion(
                    criterion=crit,
                    work_experience=resume_struct.experience,
                    job_category=job.job_category,
                )
            elif crit_category == "EDUCATION":
                cert_names = [c.name for c in resume_struct.certifications]
                c_res = self.education_matcher.evaluate_criterion(
                    criterion=crit,
                    education_records=resume_struct.education,
                    candidate_certifications=cert_names,
                )
            else:
                c_res = self.keyword_matcher.evaluate_criterion(
                    criterion=crit,
                    candidate_skills=resume_struct.skills,
                    candidate_sections=section_map,
                    candidate_raw_text=candidate.extracted_text or resume_struct.raw_text,
                )

            criterion_results.append(c_res)

            match_type_map = {
                MatchStatus.SUPPORTED: MatchType.EXACT,
                MatchStatus.PARTIALLY_SUPPORTED: MatchType.PARTIAL,
                MatchStatus.NOT_FOUND: MatchType.MISSING,
                MatchStatus.INSUFFICIENT_EVIDENCE: MatchType.PARTIAL,
                MatchStatus.NOT_EVALUATED: MatchType.NOT_EVALUATED,
            }
            mapped_type = match_type_map.get(c_res.match_status, MatchType.NOT_EVALUATED)

            primary_evidence = c_res.supporting_evidence[0] if c_res.supporting_evidence else "No positive excerpt found."
            evidence_source = c_res.evidence_sources[0] if c_res.evidence_sources else "general"

            evidence_records.append(
                EvaluationEvidence(
                    candidate_id=candidate.id,
                    criterion_id=crit.id,
                    supporting_text=primary_evidence,
                    match_type=mapped_type,
                    evidence_source=evidence_source,
                    evaluation_status="EVALUATED" if crit.is_enabled else "SKIPPED",
                    explanation=c_res.explanation,
                )
            )

        return criterion_results, evidence_records

    def _classify_criterion(self, criterion: EvaluationCriterion) -> str:
        rule = criterion.matching_config.get("rule_type") or criterion.matching_config.get("type")
        if rule:
            rule_str = str(rule).upper()
            if "EXP" in rule_str or "YEAR" in rule_str:
                return "EXPERIENCE"
            if "EDU" in rule_str or "DEGREE" in rule_str:
                return "EDUCATION"
            if "SKILL" in rule_str:
                return "SKILLS"

        combined = f"{criterion.criterion_name} {criterion.description}".lower()
        if any(k in combined for k in ["experience", "work history", "tenure", "years of experience", "years"]):
            return "EXPERIENCE"
        if any(k in combined for k in ["degree", "bachelor", "master", "phd", "education", "academic", "diploma"]):
            return "EDUCATION"

        return "SKILLS"

    def _load_structured_resume(
        self, candidate: Candidate, structured_data: Optional[Dict[str, Any]]
    ) -> StructuredResume:
        if structured_data and "skills" in structured_data:
            from core.models.education import EducationRecord
            from core.models.experience import WorkExperience
            from core.models.skills import ExtractedSkill
            from core.processing.resume_parser import (
                CertificationRecord,
                ContactInfo,
                ProjectRecord,
            )
            from core.processing.section_detector import SectionInfo

            contact_d = structured_data.get("contact", {})
            contact = ContactInfo(
                name=contact_d.get("name"),
                email=contact_d.get("email"),
                phone=contact_d.get("phone"),
                location=contact_d.get("location"),
            )
            skills = [s if isinstance(s, ExtractedSkill) else ExtractedSkill.from_dict(s) for s in structured_data.get("skills", [])]
            experience = [e if isinstance(e, WorkExperience) else WorkExperience.from_dict(e) for e in structured_data.get("experience", [])]
            education = [ed if isinstance(ed, EducationRecord) else EducationRecord.from_dict(ed) for ed in structured_data.get("education", [])]

            projects = []
            for p in structured_data.get("projects", []):
                if isinstance(p, ProjectRecord):
                    projects.append(p)
                elif isinstance(p, dict):
                    projects.append(ProjectRecord(title=p.get("title", ""), description=p.get("description", ""), evidence_text=p.get("evidence_text", "")))
                else:
                    projects.append(ProjectRecord(title=getattr(p, "title", ""), description=getattr(p, "description", ""), evidence_text=getattr(p, "evidence_text", "")))

            certs = []
            for c in structured_data.get("certifications", []):
                if isinstance(c, CertificationRecord):
                    certs.append(c)
                elif isinstance(c, dict):
                    certs.append(CertificationRecord(name=c.get("name", ""), issuer=c.get("issuer"), date=c.get("date"), evidence_text=c.get("evidence_text", "")))
                else:
                    certs.append(CertificationRecord(name=getattr(c, "name", ""), issuer=getattr(c, "issuer", None), date=getattr(c, "date", None), evidence_text=getattr(c, "evidence_text", "")))

            sections = []
            for s in structured_data.get("sections", []):
                if isinstance(s, SectionInfo):
                    sections.append(s)
                elif isinstance(s, dict):
                    sections.append(SectionInfo(
                        canonical_name=s.get("canonical_name", "UNCLASSIFIED"),
                        display_title=s.get("display_title", "Section"),
                        content=s.get("content", ""),
                        raw_heading=s.get("raw_heading", ""),
                    ))
                else:
                    sections.append(SectionInfo(
                        canonical_name=getattr(s, "canonical_name", "UNCLASSIFIED"),
                        display_title=getattr(s, "display_title", "Section"),
                        content=getattr(s, "content", ""),
                        raw_heading=getattr(s, "raw_heading", ""),
                    ))

            return StructuredResume(
                contact=contact,
                skills=skills,
                experience=experience,
                education=education,
                projects=projects,
                certifications=certs,
                sections=sections,
                raw_text=candidate.extracted_text or "",
                cleaned_text=candidate.extracted_text or "",
            )

        text = candidate.extracted_text or ""
        return self.parser.parse(text)
