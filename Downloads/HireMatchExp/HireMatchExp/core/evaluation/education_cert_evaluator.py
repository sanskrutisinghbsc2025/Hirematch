
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from core.evaluation.education_matcher import EducationMatcher
from core.models.education import EducationRecord
from core.models.enums import CriterionCategory, CriterionType, EvidenceDisagreementType, MatchStatus, MatchingRuleType
from core.models.evaluation import CriterionEvaluationResult, EvaluationCriterion


class EducationCertEvaluator:

    TIER_RANKINGS: Dict[str, int] = {
        "NONE": 0,
        "HIGH_SCHOOL": 1,
        "ASSOCIATE": 2,
        "BACHELOR": 3,
        "MASTER": 4,
        "DOCTORATE": 5,
    }

    KNOWN_ISSUERS: Dict[str, List[str]] = {
        "Amazon Web Services": ["aws", "amazon web services"],
        "Microsoft": ["microsoft", "azure"],
        "Google Cloud": ["gcp", "google cloud"],
        "Cisco": ["cisco", "ccna", "ccnp", "ccie"],
        "PMI": ["pmp", "project management professional", "capm", "pmi"],
        "CompTIA": ["comptia", "security+", "network+", "a+"],
        "CNCF / Linux Foundation": ["ckad", "cka", "cks", "kubernetes", "linux foundation"],
        "Scrum.org / Scrum Alliance": ["csm", "psm", "scrum master", "scrum product owner"],
        "HashiCorp": ["hashicorp", "terraform associate"],
        "Salesforce": ["salesforce", "salesforce administrator", "salesforce developer"],
    }

    STEM_FIELDS = {
        "computer science", "software engineering", "computer engineering", "information technology",
        "data science", "statistics", "mathematics", "electrical engineering", "cybersecurity",
        "artificial intelligence", "machine learning", "physics", "informatics"
    }

    def __init__(self, base_matcher: Optional[EducationMatcher] = None):
        self.base_matcher = base_matcher or EducationMatcher()

    def evaluate(
        self,
        criterion: EvaluationCriterion,
        education_records: List[EducationRecord],
        certifications: Optional[List[str]] = None,
        raw_text: Optional[str] = None,
    ) -> CriterionEvaluationResult:
        if not criterion.is_enabled:
            return CriterionEvaluationResult(
                criterion_id=criterion.id,
                criterion_name=criterion.criterion_name,
                criterion_type=criterion.criterion_type,
                weight=criterion.weight,
                match_status=MatchStatus.NOT_EVALUATED,
                score=0.0,
                category=criterion.category,
                explanation="Criterion disabled.",
            )

        if criterion.category == CriterionCategory.CERTIFICATION or "cert" in criterion.criterion_name.lower():
            return self.evaluate_certification(criterion, certifications or [], raw_text)
        else:
            return self.evaluate_education(criterion, education_records, certifications)

    def evaluate_education(
        self,
        criterion: EvaluationCriterion,
        education_records: List[EducationRecord],
        certifications: Optional[List[str]] = None,
    ) -> CriterionEvaluationResult:
        req_tier_key, req_tier_name = self.base_matcher._determine_target_tier(criterion)
        req_tier_val = self.TIER_RANKINGS.get(req_tier_key, 3)

        target_field = self._detect_required_field(criterion)

        if not education_records:
            certs = certifications or []
            if certs:
                return CriterionEvaluationResult(
                    criterion_id=criterion.id,
                    criterion_name=criterion.criterion_name,
                    criterion_type=criterion.criterion_type,
                    weight=criterion.weight,
                    match_status=MatchStatus.PARTIALLY_SUPPORTED,
                    score=45.0,
                    matched_terms=certs[:3],
                    supporting_evidence=[f"Alternative credentials found: {', '.join(certs[:3])}"],
                    evidence_sources=["CERTIFICATIONS"],
                    matching_method="credential_substitution",
                    category=CriterionCategory.EDUCATION_REQUIREMENT,
                    explanation=(
                        f"No formal academic degrees extracted from resume, but {len(certs)} professional credential(s) documented. "
                        f"(Target: {req_tier_name}). Note: Missing resume education does not prove lack of degree."
                    ),
                    confidence=0.75,
                )

            return CriterionEvaluationResult(
                criterion_id=criterion.id,
                criterion_name=criterion.criterion_name,
                criterion_type=criterion.criterion_type,
                weight=criterion.weight,
                match_status=MatchStatus.INSUFFICIENT_EVIDENCE if criterion.criterion_type == CriterionType.REQUIRED else MatchStatus.NOT_FOUND,
                score=0.0,
                evidence_sources=["EDUCATION"],
                matching_method="academic_tier_analysis",
                category=CriterionCategory.EDUCATION_REQUIREMENT,
                explanation=(
                    f"No degree or educational background documented in resume. "
                    f"Evaluated as unmentioned (Target: {req_tier_name}). This does not confirm absence of qualifications."
                ),
            )

        classified = []
        for edu in education_records:
            deg_title = getattr(edu, "degree", "") or edu.qualification or ""
            inst = getattr(edu, "institution", "") or "Unspecified Institution"
            dates = getattr(edu, "dates", "") or getattr(edu, "graduation_year", "") or ""
            field = getattr(edu, "field_of_study", "") or ""

            tier_k, tier_n = self.base_matcher._classify_text(deg_title)
            tier_v = self.TIER_RANKINGS.get(tier_k, 0)
            classified.append({
                "tier_key": tier_k,
                "tier_name": tier_n,
                "tier_val": tier_v,
                "degree_title": deg_title,
                "institution": inst,
                "dates": dates,
                "field": field,
                "record": edu,
            })

        best = max(classified, key=lambda x: x["tier_val"])
        best_tier_val = best["tier_val"]
        best_tier_name = best["tier_name"]

        evidence_quote = f"{best['degree_title'] or best['tier_name']}"
        if best['field']:
            evidence_quote += f" in {best['field']}"
        evidence_quote += f" from {best['institution']}"
        if best['dates']:
            evidence_quote += f" ({best['dates']})"

        field_matched = True
        field_note = ""
        if target_field:
            all_edu_text = " ".join([
                f"{c['degree_title']} {c['field']} {getattr(c['record'], 'evidence_text', '')}"
                for c in classified
            ]).lower()
            if target_field.lower() in all_edu_text:
                field_matched = True
                field_note = f" (in target field: {target_field})"
            elif any(stem in all_edu_text for stem in self.STEM_FIELDS) and target_field.lower() in ("stem", "computer science", "related technical field"):
                field_matched = True
                field_note = " (in related STEM field)"
            else:
                field_matched = False
                field_note = f" (target discipline '{target_field}' not explicitly confirmed)"

        if best_tier_val >= req_tier_val:
            if field_matched:
                score = 100.0
                status = MatchStatus.SUPPORTED
                disagreement = EvidenceDisagreementType.NONE
                if best_tier_val > req_tier_val:
                    explanation = (
                        f"Exceeds requirement: Candidate holds {best_tier_name}{field_note}, "
                        f"surpassing target {req_tier_name}."
                    )
                else:
                    explanation = (
                        f"Directly satisfies requirement: Candidate holds {best_tier_name}{field_note}, "
                        f"meeting target {req_tier_name}."
                    )
            else:
                score = 80.0
                status = MatchStatus.PARTIALLY_SUPPORTED
                disagreement = EvidenceDisagreementType.DEGREE_MISMATCH
                explanation = (
                    f"Degree level satisfies requirement ({best_tier_name} vs target {req_tier_name}), "
                    f"but target field of study '{target_field}' was not explicitly verified."
                )
        elif best_tier_val == req_tier_val - 1:
            score = 65.0 if field_matched else 50.0
            status = MatchStatus.PARTIALLY_SUPPORTED
            disagreement = EvidenceDisagreementType.DEGREE_MISMATCH
            explanation = (
                f"Partially satisfies: Candidate holds {best_tier_name} (target {req_tier_name}){field_note}."
            )
        else:
            score = 30.0
            status = MatchStatus.NOT_FOUND
            disagreement = EvidenceDisagreementType.DEGREE_MISMATCH
            explanation = (
                f"Candidate degree tier ({best_tier_name}) does not reach the specified {req_tier_name} level."
            )

        return CriterionEvaluationResult(
            criterion_id=criterion.id,
            criterion_name=criterion.criterion_name,
            criterion_type=criterion.criterion_type,
            weight=criterion.weight,
            match_status=status,
            score=score,
            matched_terms=[best_tier_name],
            supporting_evidence=[evidence_quote],
            evidence_sources=["EDUCATION"],
            matching_method="academic_tier_and_discipline_analysis",
            disagreement_type=disagreement,
            category=CriterionCategory.EDUCATION_REQUIREMENT,
            explanation=explanation,
            confidence=0.92,
        )

    def evaluate_certification(
        self,
        criterion: EvaluationCriterion,
        candidate_certifications: List[str],
        raw_text: Optional[str] = None,
    ) -> CriterionEvaluationResult:
        target_name = criterion.criterion_name
        req_terms = self._extract_cert_terms(criterion)

        all_certs_text = " ".join(candidate_certifications).lower()
        if raw_text:
            all_certs_text += " " + raw_text.lower()

        matched_certs: List[str] = []
        matched_issuers: List[str] = []

        for term in req_terms:
            t = term.lower().strip()
            for c in candidate_certifications:
                if t in c.lower():
                    matched_certs.append(c)

            for issuer, patterns in self.KNOWN_ISSUERS.items():
                if any(p in t for p in patterns):
                    if any(p in all_certs_text for p in patterns):
                        matched_issuers.append(issuer)

        matched_certs = list(dict.fromkeys(matched_certs))
        matched_issuers = list(dict.fromkeys(matched_issuers))

        if matched_certs:
            score = 100.0
            status = MatchStatus.SUPPORTED
            explanation = f"Verified certification credential: {', '.join(matched_certs)}."
            if matched_issuers:
                explanation += f" (Recognized issuer: {', '.join(matched_issuers)})"
            evidence = matched_certs
        elif matched_issuers:
            score = 75.0
            status = MatchStatus.PARTIALLY_SUPPORTED
            explanation = (
                f"Candidate documents relevant credentials from required ecosystem/issuer: {', '.join(matched_issuers)}, "
                f"though exact certificate title '{target_name}' was not uniquely verified."
            )
            evidence = [f"Issuer evidence: {', '.join(matched_issuers)}"]
        else:
            if not candidate_certifications:
                score = 0.0
                status = MatchStatus.INSUFFICIENT_EVIDENCE if criterion.criterion_type == CriterionType.REQUIRED else MatchStatus.NOT_FOUND
                explanation = (
                    f"No matching certification '{target_name}' extracted from candidate profile. "
                    "Note: Unmentioned certifications in a resume do not prove absence of accreditation."
                )
                evidence = []
            else:
                score = 0.0
                status = MatchStatus.NOT_FOUND
                explanation = (
                    f"Required certification '{target_name}' not listed among candidate's "
                    f"{len(candidate_certifications)} documented certification(s)."
                )
                evidence = []

        return CriterionEvaluationResult(
            criterion_id=criterion.id,
            criterion_name=criterion.criterion_name,
            criterion_type=criterion.criterion_type,
            weight=criterion.weight,
            match_status=status,
            score=score,
            matched_terms=matched_certs or matched_issuers,
            supporting_evidence=evidence,
            evidence_sources=["CERTIFICATIONS"],
            matching_method="certification_credential_verification",
            disagreement_type=EvidenceDisagreementType.NONE if status == MatchStatus.SUPPORTED else EvidenceDisagreementType.SEMANTIC_WITHOUT_KEYWORD,
            category=CriterionCategory.CERTIFICATION,
            explanation=explanation,
            confidence=0.90,
        )

    def _detect_required_field(self, criterion: EvaluationCriterion) -> Optional[str]:
        combined = f"{criterion.criterion_name} {criterion.description}".lower()
        m = re.search(r"in\s+([A-Za-z\s]+?)(?:\s+or\s+related|\s+degree|\.|\,|$)", combined)
        if m:
            candidate = m.group(1).strip()
            if len(candidate) > 2 and candidate not in ("a", "an", "the", "any"):
                return candidate
        return None

    def _extract_cert_terms(self, criterion: EvaluationCriterion) -> List[str]:
        terms = [criterion.criterion_name]
        if hasattr(criterion, "keywords") and criterion.keywords:
            terms.extend(criterion.keywords)
        if "keywords" in criterion.matching_config:
            terms.extend(criterion.matching_config["keywords"])
        if "cert_name" in criterion.evidence_requirements:
            terms.append(str(criterion.evidence_requirements["cert_name"]))
        return list(dict.fromkeys(terms))
