
from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from config import AppConfig, settings
from core.evaluation.interfaces import IQualityEvaluator
from core.models.quality_models import (
    ExtractionDiagnostics,
    IssueSeverity,
    QualityCriterionKey,
    QualityCriterionResult,
    QualityImprovement,
    QualityIssue,
    QualityLabel,
    QualityStrength,
    ReadabilityMetrics,
    ResumeQualityAssessment,
    SectionPresence,
)
from core.processing.cleaner import TextCleaner
from core.processing.section_detector import ResumeSectionDetector, SectionInfo
from core.utils.logger import logger


ACTION_VERBS = {
    "accelerated", "accomplished", "achieved", "acquired", "adapted", "administered",
    "advanced", "advised", "analyzed", "architected", "arranged", "assembled",
    "assessed", "audited", "automated", "boosted", "built", "centralized",
    "championed", "clarified", "coached", "collaborated", "compiled", "composed",
    "conceptualized", "conducted", "consolidated", "constructed", "consulted",
    "coordinated", "crafted", "created", "customized", "debugged", "decreased",
    "defined", "delivered", "deployed", "designed", "developed", "devised",
    "diagnosed", "directed", "discovered", "dispatched", "documented", "doubled",
    "drafted", "drove", "eliminated", "enabled", "enacted", "engineered",
    "enhanced", "established", "estimated", "evaluated", "examined", "executed",
    "expanded", "expedited", "fabricated", "facilitated", "finalized", "focused",
    "forecasted", "formulated", "founded", "generated", "guided", "halted",
    "headed", "identified", "implemented", "improved", "increased", "influenced",
    "initiated", "innovated", "inspected", "installed", "instituted", "instructed",
    "integrated", "introduced", "invented", "investigated", "launched", "led",
    "leveraged", "managed", "maximized", "measured", "mentored", "migrated",
    "minimized", "modernized", "monitored", "motivated", "negotiated", "obtained",
    "operated", "optimized", "orchestrated", "organized", "originated", "overhauled",
    "oversaw", "partnered", "performed", "pioneered", "planned", "prepared",
    "presented", "produced", "programmed", "promoted", "proposed", "published",
    "rebuilt", "redesigned", "reduced", "refined", "refactored", "remodeled",
    "reorganized", "replaced", "researched", "resolved", "restructured", "revamped",
    "reviewed", "revitalized", "saved", "scaled", "scheduled", "screened",
    "secured", "selected", "separated", "simplified", "slashed", "solved",
    "spearheaded", "standardized", "streamlined", "strengthened", "structured",
    "supervised", "surpassed", "synthesized", "systematized", "targeted", "tested",
    "trained", "transformed", "transitioned", "translated", "troubleshot", "unified",
    "upgraded", "utilized", "validated", "verified",
}

DEFAULT_RUBRIC_WEIGHTS: Dict[str, float] = {
    QualityCriterionKey.COMPLETENESS.value: 0.15,
    QualityCriterionKey.STRUCTURE_ORGANIZATION.value: 0.12,
    QualityCriterionKey.READABILITY.value: 0.10,
    QualityCriterionKey.FORMATTING_CONSISTENCY.value: 0.10,
    QualityCriterionKey.EXPERIENCE_CLARITY.value: 0.12,
    QualityCriterionKey.SKILLS_CLARITY.value: 0.10,
    QualityCriterionKey.ACHIEVEMENT_SPECIFICITY.value: 0.10,
    QualityCriterionKey.DATE_CONSISTENCY.value: 0.08,
    QualityCriterionKey.CONTACT_COMPLETENESS.value: 0.05,
    QualityCriterionKey.EXTRACTION_QUALITY.value: 0.08,
}


class ResumeQualityEvaluator(IQualityEvaluator):

    def __init__(
        self,
        config: Optional[AppConfig] = None,
        rubric_weights: Optional[Dict[str, float]] = None,
        good_threshold: Optional[float] = None,
        moderate_threshold: Optional[float] = None,
    ):
        self.config = config or settings
        self.weights = rubric_weights or dict(DEFAULT_RUBRIC_WEIGHTS)
        self.good_threshold = (
            good_threshold
            if good_threshold is not None
            else getattr(self.config, "quality_good_threshold", 75.0)
        )
        self.moderate_threshold = (
            moderate_threshold
            if moderate_threshold is not None
            else getattr(self.config, "quality_moderate_threshold", 50.0)
        )

    def evaluate_quality(
        self, text: str, metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[float, List[str]]:
        assessment = self.evaluate(
            candidate_id=metadata.get("candidate_id", "adhoc") if metadata else "adhoc",
            text=text,
            structured_data=metadata.get("structured_data") if metadata else None,
            extraction_meta=metadata,
        )
        issues = [f"[{issue.severity.value}] {issue.description}" for issue in assessment.detected_issues]
        return assessment.overall_score, issues

    def evaluate(
        self,
        candidate_id: str,
        text: str,
        structured_data: Optional[Dict[str, Any]] = None,
        extraction_meta: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
    ) -> ResumeQualityAssessment:
        cleaned_text = TextCleaner.clean(text or "")
        structured = structured_data or {}
        ext_meta = extraction_meta or {}

        sections = ResumeSectionDetector.detect_sections(cleaned_text)
        section_map = {s.canonical_name: s for s in sections}
        lines = [line.strip() for line in cleaned_text.split("\n") if line.strip()]

        readability = self._compute_readability_metrics(lines, cleaned_text)

        extraction = self._compute_extraction_diagnostics(cleaned_text, lines, ext_meta)

        c_results: List[QualityCriterionResult] = []
        strengths: List[QualityStrength] = []
        improvements: List[QualityImprovement] = []
        issues: List[QualityIssue] = []

        res_comp, s_comp, i_comp, iss_comp, sec_audit = self._eval_completeness(section_map, structured, cleaned_text)
        c_results.append(res_comp)
        strengths.extend(s_comp)
        improvements.extend(i_comp)
        issues.extend(iss_comp)

        res_struct, s_struct, i_struct, iss_struct = self._eval_structure(sections, lines, cleaned_text)
        c_results.append(res_struct)
        strengths.extend(s_struct)
        improvements.extend(i_struct)
        issues.extend(iss_struct)

        res_read, s_read, i_read, iss_read = self._eval_readability(readability, lines)
        c_results.append(res_read)
        strengths.extend(s_read)
        improvements.extend(i_read)
        issues.extend(iss_read)

        res_fmt, s_fmt, i_fmt, iss_fmt = self._eval_formatting_consistency(lines, sections)
        c_results.append(res_fmt)
        strengths.extend(s_fmt)
        improvements.extend(i_fmt)
        issues.extend(iss_fmt)

        res_exp, s_exp, i_exp, iss_exp = self._eval_experience_clarity(structured, section_map)
        c_results.append(res_exp)
        strengths.extend(s_exp)
        improvements.extend(i_exp)
        issues.extend(iss_exp)

        res_skl, s_skl, i_skl, iss_skl = self._eval_skills_clarity(structured, section_map)
        c_results.append(res_skl)
        strengths.extend(s_skl)
        improvements.extend(i_skl)
        issues.extend(iss_skl)

        res_ach, s_ach, i_ach, iss_ach = self._eval_achievement_specificity(readability, lines)
        c_results.append(res_ach)
        strengths.extend(s_ach)
        improvements.extend(i_ach)
        issues.extend(iss_ach)

        res_dt, s_dt, i_dt, iss_dt = self._eval_date_consistency(structured, cleaned_text)
        c_results.append(res_dt)
        strengths.extend(s_dt)
        improvements.extend(i_dt)
        issues.extend(iss_dt)

        res_cnt, s_cnt, i_cnt, iss_cnt = self._eval_contact_completeness(structured, cleaned_text)
        c_results.append(res_cnt)
        strengths.extend(s_cnt)
        improvements.extend(i_cnt)
        issues.extend(iss_cnt)

        res_ext, s_ext, i_ext, iss_ext = self._eval_extraction_quality(extraction, cleaned_text)
        c_results.append(res_ext)
        strengths.extend(s_ext)
        improvements.extend(i_ext)
        issues.extend(iss_ext)

        total_weight = sum(r.weight for r in c_results)
        if total_weight > 0:
            overall_score = sum(r.score * r.weight for r in c_results) / total_weight
        else:
            overall_score = 0.0

        overall_score = max(0.0, min(100.0, overall_score))
        quality_label = QualityLabel.from_score(
            overall_score,
            good_threshold=self.good_threshold,
            moderate_threshold=self.moderate_threshold,
        )

        executive_summary = self._build_executive_summary(
            overall_score=overall_score,
            quality_label=quality_label,
            strengths=strengths,
            improvements=improvements,
            issues=issues,
            extraction=extraction,
        )

        return ResumeQualityAssessment(
            candidate_id=candidate_id,
            session_id=session_id,
            overall_score=round(overall_score, 1),
            quality_label=quality_label,
            criterion_results=c_results,
            strong_areas=strengths,
            areas_for_improvement=improvements,
            detected_issues=issues,
            section_completeness=sec_audit,
            readability_metrics=readability,
            extraction_diagnostics=extraction,
            executive_summary=executive_summary,
        )


    def _compute_readability_metrics(self, lines: List[str], text: str) -> ReadabilityMetrics:
        words = re.findall(r"\b[A-Za-z0-9+#.-]+\b", text)
        word_count = len(words)
        
        sentences = [s.strip() for s in re.split(r"[.!?]+|\n", text) if len(s.strip()) > 3]
        sentence_count = max(1, len(sentences))
        avg_wps = word_count / sentence_count if sentence_count > 0 else 0.0

        bullet_lines = [
            line for line in lines
            if re.match(r"^([•\-\*\u2022\u2023\u25E6\u2043\u2219]|(?:\d+[\.\)]))\s+", line)
        ]
        bullet_count = len(bullet_lines)
        bullet_ratio = bullet_count / len(lines) if lines else 0.0

        action_verb_count = 0
        for line in lines:
            clean = re.sub(r"^([•\-\*\u2022\u2023\u25E6\u2043\u2219]|(?:\d+[\.\)]))\s+", "", line).strip()
            first_word = clean.split()[0].lower() if clean else ""
            first_word = re.sub(r"[^a-z]", "", first_word)
            if first_word in ACTION_VERBS:
                action_verb_count += 1

        action_verb_ratio = action_verb_count / max(1, len(lines))

        quant_matches = re.findall(
            r"(?:\$\s*\d+(?:[\.,]\d+)?(?:\s*(?:k|m|b|million|billion))?|\b\d+(?:[\.,]\d+)?\s*%|\b\d+\s*x\b|\b(?:\d+[\.,])?\d+\s*(?:users|clients|engineers|people|team\s+members|projects|requests|queries|tps|ms|seconds|hours)\b)",
            text,
            flags=re.IGNORECASE,
        )
        quant_metric_count = len(quant_matches)

        if avg_wps <= 22 and bullet_ratio >= 0.25:
            readability_level = "High — Concise and Scannable"
        elif avg_wps <= 32:
            readability_level = "Moderate — Readable Paragraphs"
        else:
            readability_level = "Low — Dense Wall of Text"

        return ReadabilityMetrics(
            word_count=word_count,
            sentence_count=sentence_count,
            avg_words_per_sentence=avg_wps,
            bullet_count=bullet_count,
            bullet_ratio=bullet_ratio,
            action_verb_count=action_verb_count,
            action_verb_ratio=action_verb_ratio,
            quantified_metric_count=quant_metric_count,
            readability_level=readability_level,
        )

    def _compute_extraction_diagnostics(
        self, text: str, lines: List[str], ext_meta: Dict[str, Any]
    ) -> ExtractionDiagnostics:
        char_count = len(text)
        line_count = len(lines)
        page_count = ext_meta.get("page_count", max(1, int(line_count / 50)))
        ocr_needed = bool(ext_meta.get("ocr_needed", False))
        is_empty = char_count == 0 or ext_meta.get("is_empty", False)

        warnings: List[str] = []
        parse_confidence = 1.0

        if is_empty:
            warnings.append("Document extracted with zero textual content.")
            parse_confidence = 0.0
        elif ocr_needed:
            warnings.append("Document appears to be an image-only scan requiring OCR.")
            parse_confidence = 0.3
        elif char_count < 150:
            warnings.append("Extracted text is unusually sparse (< 150 characters).")
            parse_confidence = 0.5
        elif char_count > 25000:
            warnings.append("Extracted text is exceptionally large (> 25,000 characters).")
            parse_confidence = 0.85

        corrupt_chars = len(re.findall(r"[\ufffd\x00-\x08\x0b\x0c\x0e-\x1f]", text))
        if corrupt_chars > 5:
            warnings.append(f"Detected {corrupt_chars} unprintable or encoding artifacts.")
            parse_confidence = max(0.4, parse_confidence - 0.2)

        return ExtractionDiagnostics(
            char_count=char_count,
            line_count=line_count,
            page_count=page_count,
            ocr_needed=ocr_needed,
            is_empty=is_empty,
            parse_confidence=parse_confidence,
            warnings=warnings,
        )


    def _eval_completeness(
        self,
        section_map: Dict[str, SectionInfo],
        structured: Dict[str, Any],
        text: str,
    ) -> Tuple[QualityCriterionResult, List[QualityStrength], List[QualityImprovement], List[QualityIssue], Dict[str, Any]]:
        sec_audit: Dict[str, Any] = {}
        core_sections = {
            "EXPERIENCE": "Work Experience",
            "EDUCATION": "Education",
            "SKILLS": "Skills",
        }
        optional_sections = {
            "SUMMARY": "Professional Summary",
            "PROJECTS": "Projects",
            "CERTIFICATIONS": "Certifications",
            "PUBLICATIONS": "Publications",
        }

        contact = structured.get("contact", {})
        has_contact = bool(contact.get("email") or contact.get("phone") or "HEADER" in section_map)

        sec_audit["CONTACT"] = {
            "display_name": "Contact Information",
            "status": SectionPresence.PRESENT.value if has_contact else SectionPresence.MISSING_CORE.value,
            "is_core": True,
            "present": has_contact,
        }
        sec_audit["contact"] = sec_audit["CONTACT"]

        present_core_count = 1 if has_contact else 0
        missing_core_names: List[str] = []
        if not has_contact:
            missing_core_names.append("Contact Information")

        for code, label in core_sections.items():
            is_present = code in section_map
            if not is_present:
                if code == "EXPERIENCE" and structured.get("experience"):
                    is_present = True
                elif code == "EDUCATION" and structured.get("education"):
                    is_present = True
                elif code == "SKILLS" and structured.get("skills"):
                    is_present = True

            sec_audit[code] = {
                "display_name": label,
                "status": SectionPresence.PRESENT.value if is_present else SectionPresence.MISSING_CORE.value,
                "is_core": True,
                "present": is_present,
            }
            sec_audit[code.lower()] = sec_audit[code]
            if is_present:
                present_core_count += 1
            else:
                missing_core_names.append(label)

        present_optional_count = 0
        present_optional_names: List[str] = []
        for code, label in optional_sections.items():
            is_present = code in section_map
            sec_audit[code] = {
                "display_name": label,
                "status": SectionPresence.PRESENT.value if is_present else SectionPresence.OPTIONAL_MISSING.value,
                "is_core": False,
                "present": is_present,
            }
            sec_audit[code.lower()] = sec_audit[code]
            if is_present:
                present_optional_count += 1
                present_optional_names.append(label)

        score = present_core_count * 20.0
        score += min(20.0, present_optional_count * 5.0)
        score = max(10.0, min(100.0, score))

        strengths: List[QualityStrength] = []
        improvements: List[QualityImprovement] = []
        issues: List[QualityIssue] = []

        if present_core_count == 4:
            strengths.append(
                QualityStrength(
                    title="Comprehensive Core Structure",
                    description="All foundational resume sections (Contact, Experience, Education, and Skills) are clearly present.",
                    criterion_key=QualityCriterionKey.COMPLETENESS.value,
                    evidence_quote="Identified sections: Experience, Education, Skills, and Contact details.",
                )
            )
            if present_optional_names:
                strengths.append(
                    QualityStrength(
                        title="Enriched Profile Sections",
                        description=f"Includes complementary sections ({', '.join(present_optional_names)}) that provide helpful professional context.",
                        criterion_key=QualityCriterionKey.COMPLETENESS.value,
                    )
                )
        else:
            issues.append(
                QualityIssue(
                    issue_type="MISSING_CORE_SECTION",
                    severity=IssueSeverity.HIGH,
                    description=f"Missing standard core section(s): {', '.join(missing_core_names)}.",
                )
            )
            improvements.append(
                QualityImprovement(
                    title=f"Add {missing_core_names[0]} Section",
                    recommendation=f"Incorporate an explicit '{missing_core_names[0]}' section to ensure standard screening parsers identify your background.",
                    criterion_key=QualityCriterionKey.COMPLETENESS.value,
                    rationale="Complete resumes allow reviewers to verify baseline credentials without ambiguity.",
                )
            )

        status_str = "STRONG" if score >= 80 else ("ACCEPTABLE" if score >= 60 else "NEEDS_IMPROVEMENT")
        obs = (
            f"Found {present_core_count} of 4 core sections and {present_optional_count} optional sections."
        )

        result = QualityCriterionResult(
            criterion_key=QualityCriterionKey.COMPLETENESS.value,
            criterion_name="Completeness",
            score=score,
            weight=self.weights[QualityCriterionKey.COMPLETENESS.value],
            weighted_score=score * self.weights[QualityCriterionKey.COMPLETENESS.value],
            status=status_str,
            observations=obs,
            evidence_snippets=[f"{k}: {v['status']}" for k, v in sec_audit.items() if k.isupper()],
        )
        return result, strengths, improvements, issues, sec_audit

    def _eval_structure(
        self,
        sections: List[SectionInfo],
        lines: List[str],
        text: str,
    ) -> Tuple[QualityCriterionResult, List[QualityStrength], List[QualityImprovement], List[QualityIssue]]:
        strengths: List[QualityStrength] = []
        improvements: List[QualityImprovement] = []
        issues: List[QualityIssue] = []

        real_sections = [s for s in sections if s.canonical_name != "UNCLASSIFIED" and s.raw_heading]

        if not real_sections:
            result = QualityCriterionResult(
                criterion_key=QualityCriterionKey.STRUCTURE_ORGANIZATION.value,
                criterion_name="Structure and Organization",
                score=20.0,
                weight=self.weights[QualityCriterionKey.STRUCTURE_ORGANIZATION.value],
                weighted_score=20.0 * self.weights[QualityCriterionKey.STRUCTURE_ORGANIZATION.value],
                status="NEEDS_IMPROVEMENT",
                observations="No distinct section headings were identified. Document appears monolithic.",
                evidence_snippets=["Monolithic document layout without recognizable section headers."],
            )
            issues.append(
                QualityIssue(
                    issue_type="LACK_OF_SECTION_HEADINGS",
                    severity=IssueSeverity.HIGH,
                    description="The document lacks standardized section headers, making navigation difficult for human readers and parsers.",
                )
            )
            improvements.append(
                QualityImprovement(
                    title="Introduce Clear Section Headings",
                    recommendation="Add bold, standardized headings (e.g., 'Work Experience', 'Education', 'Skills') to separate thematic sections.",
                    criterion_key=QualityCriterionKey.STRUCTURE_ORGANIZATION.value,
                    rationale="Clear section headings enable recruiters to quickly locate relevant qualifications.",
                )
            )
            return result, strengths, improvements, issues

        score = 75.0
        sec_names = [s.canonical_name for s in real_sections]

        if "HEADER" in sec_names and sec_names.index("HEADER") > 1:
            score -= 15.0
            issues.append(
                QualityIssue(
                    issue_type="UNORTHODOX_HEADER_PLACEMENT",
                    severity=IssueSeverity.LOW,
                    description="Contact or header information appears deep in the resume rather than at the top.",
                )
            )

        candidate_sections = [s for s in real_sections if s.canonical_name != "HEADER"]
        if len(candidate_sections) >= 4:
            strengths.append(
                QualityStrength(
                    title="Logical Section Hierarchy",
                    description=f"Organized into {len(candidate_sections)} distinct, recognized sections with clear thematic boundaries.",
                    criterion_key=QualityCriterionKey.STRUCTURE_ORGANIZATION.value,
                    evidence_quote=f"Identified headings: {', '.join([s.display_title for s in candidate_sections[:4]])}",
                )
            )
            score += 20.0
        elif len(candidate_sections) == 3:
            score += 0.0
        else:
            score -= 15.0

        score = max(10.0, min(100.0, score))
        status_str = "STRONG" if score >= 80 else ("ACCEPTABLE" if score >= 60 else "NEEDS_IMPROVEMENT")

        result = QualityCriterionResult(
            criterion_key=QualityCriterionKey.STRUCTURE_ORGANIZATION.value,
            criterion_name="Structure and Organization",
            score=score,
            weight=self.weights[QualityCriterionKey.STRUCTURE_ORGANIZATION.value],
            weighted_score=score * self.weights[QualityCriterionKey.STRUCTURE_ORGANIZATION.value],
            status=status_str,
            observations=f"Document contains {len(real_sections)} cleanly partitioned sections with clear hierarchy.",
            evidence_snippets=[s.display_title for s in real_sections],
        )
        return result, strengths, improvements, issues

    def _eval_readability(
        self,
        readability: ReadabilityMetrics,
        lines: List[str],
    ) -> Tuple[QualityCriterionResult, List[QualityStrength], List[QualityImprovement], List[QualityIssue]]:
        strengths: List[QualityStrength] = []
        improvements: List[QualityImprovement] = []
        issues: List[QualityIssue] = []

        score = 75.0

        if readability.word_count < 60:
            score -= 30.0
            issues.append(
                QualityIssue(
                    issue_type="VERY_SHORT_CONTENT",
                    severity=IssueSeverity.HIGH,
                    description=f"Resume is very short ({readability.word_count} words) and lacks descriptive communicative depth.",
                )
            )
            improvements.append(
                QualityImprovement(
                    title="Expand Professional Background",
                    recommendation="Provide detailed bullet points outlining responsibilities, technical environments, and outcomes.",
                    criterion_key=QualityCriterionKey.READABILITY.value,
                    rationale="Very short resumes fail to convey necessary depth to recruiters.",
                )
            )

        if readability.bullet_ratio >= 0.30:
            score += 15.0
            strengths.append(
                QualityStrength(
                    title="Effective Bulleted Formatting",
                    description=f"{int(readability.bullet_ratio * 100)}% of content is formatted into concise bullet points rather than dense paragraphs.",
                    criterion_key=QualityCriterionKey.READABILITY.value,
                )
            )
        elif readability.bullet_ratio < 0.10:
            score -= 20.0
            issues.append(
                QualityIssue(
                    issue_type="DENSE_PARAGRAPH_STRUCTURE",
                    severity=IssueSeverity.MEDIUM,
                    description="Very few bullet points detected (< 10%). Information is formatted in dense paragraph blocks.",
                )
            )
            improvements.append(
                QualityImprovement(
                    title="Convert Paragraphs to Action Bullets",
                    recommendation="Break multi-sentence role descriptions into 3–5 bullet points starting with strong action verbs.",
                    criterion_key=QualityCriterionKey.READABILITY.value,
                    rationale="Recruiters scan resumes in 6–10 seconds; bullet points drastically increase scannability.",
                )
            )

        if 10.0 <= readability.avg_words_per_sentence <= 24.0:
            score += 10.0
        elif readability.avg_words_per_sentence > 35.0:
            score -= 15.0
            issues.append(
                QualityIssue(
                    issue_type="LONG_RUN_ON_SENTENCES",
                    severity=IssueSeverity.LOW,
                    description=f"Average sentence length ({readability.avg_words_per_sentence:.1f} words) is high, indicating potential run-on sentences.",
                )
            )

        if readability.action_verb_count >= 5:
            strengths.append(
                QualityStrength(
                    title="Active Voice & Action Verbs",
                    description=f"Identified {readability.action_verb_count} bullet points starting with strong action verbs.",
                    criterion_key=QualityCriterionKey.READABILITY.value,
                )
            )
            score += 5.0

        score = max(10.0, min(100.0, score))
        status_str = "STRONG" if score >= 80 else ("ACCEPTABLE" if score >= 60 else "NEEDS_IMPROVEMENT")

        result = QualityCriterionResult(
            criterion_key=QualityCriterionKey.READABILITY.value,
            criterion_name="Readability",
            score=score,
            weight=self.weights[QualityCriterionKey.READABILITY.value],
            weighted_score=score * self.weights[QualityCriterionKey.READABILITY.value],
            status=status_str,
            observations=(
                f"{readability.readability_level}. Avg sentence length: {readability.avg_words_per_sentence:.1f} words, "
                f"bullet ratio: {int(readability.bullet_ratio * 100)}%, action verbs: {readability.action_verb_count}."
            ),
            evidence_snippets=[
                f"Words: {readability.word_count}",
                f"Bullets: {readability.bullet_count} ({int(readability.bullet_ratio * 100)}%)",
                f"Action verbs: {readability.action_verb_count}",
            ],
        )
        return result, strengths, improvements, issues

    def _eval_formatting_consistency(
        self,
        lines: List[str],
        sections: List[SectionInfo],
    ) -> Tuple[QualityCriterionResult, List[QualityStrength], List[QualityImprovement], List[QualityIssue]]:
        strengths: List[QualityStrength] = []
        improvements: List[QualityImprovement] = []
        issues: List[QualityIssue] = []

        real_sections = [s for s in sections if s.canonical_name != "UNCLASSIFIED" and s.raw_heading]

        if not real_sections and len(lines) <= 10:
            score = 25.0
            issues.append(
                QualityIssue(
                    issue_type="LACK_OF_FORMATTING",
                    severity=IssueSeverity.HIGH,
                    description="Document lacks standard resume formatting, headings, or structural delimiters.",
                )
            )
            result = QualityCriterionResult(
                criterion_key=QualityCriterionKey.FORMATTING_CONSISTENCY.value,
                criterion_name="Formatting Consistency",
                score=score,
                weight=self.weights[QualityCriterionKey.FORMATTING_CONSISTENCY.value],
                weighted_score=score * self.weights[QualityCriterionKey.FORMATTING_CONSISTENCY.value],
                status="NEEDS_IMPROVEMENT",
                observations="Document appears as raw unformatted text without headings or bullets.",
                evidence_snippets=["Unformatted raw text block."],
            )
            return result, strengths, improvements, issues

        score = 80.0

        bullet_types: Set[str] = set()
        for line in lines:
            m = re.match(r"^([•\-\*\u2022\u2023\u25E6\u2043\u2219]|(?:\d+[\.\)]))\s+", line)
            if m:
                bullet_types.add(m.group(1))

        if len(bullet_types) == 1:
            score += 10.0
            strengths.append(
                QualityStrength(
                    title="Uniform Bullet Styling",
                    description=f"Consistently uses the same bullet marker ('{list(bullet_types)[0]}') throughout the document.",
                    criterion_key=QualityCriterionKey.FORMATTING_CONSISTENCY.value,
                )
            )
        elif len(bullet_types) > 1:
            score -= 20.0
            issues.append(
                QualityIssue(
                    issue_type="INCONSISTENT_BULLET_STYLES",
                    severity=IssueSeverity.LOW,
                    description=f"Document mixes {len(bullet_types)} different bullet point styles ({', '.join(bullet_types)}).",
                )
            )
            improvements.append(
                QualityImprovement(
                    title="Standardize Bullet Marker Style",
                    recommendation="Adopt a single bullet point style throughout the document rather than alternating symbols.",
                    criterion_key=QualityCriterionKey.FORMATTING_CONSISTENCY.value,
                    rationale="Visual consistency reduces distraction and presents information cleanly.",
                )
            )
        elif len(bullet_types) == 0 and len(lines) >= 8:
            score -= 10.0

        candidate_sections = [s for s in real_sections if s.canonical_name != "HEADER"]
        if len(candidate_sections) >= 2:
            clean_headings = [s.raw_heading.strip(": ") for s in candidate_sections if s.raw_heading]
            is_all_upper = all(h.isupper() for h in clean_headings)
            is_all_title = all(h.istitle() for h in clean_headings)
            if is_all_upper or is_all_title:
                score += 10.0
                strengths.append(
                    QualityStrength(
                        title="Consistent Heading Typography",
                        description=f"Headings follow a unified casing style ({'UPPERCASE' if is_all_upper else 'Title Case'}).",
                        criterion_key=QualityCriterionKey.FORMATTING_CONSISTENCY.value,
                    )
                )
            else:
                score -= 20.0
                issues.append(
                    QualityIssue(
                        issue_type="INCONSISTENT_HEADING_CASING",
                        severity=IssueSeverity.MEDIUM,
                        description="Inconsistent heading formatting and casing detected across sections (e.g., mixed uppercase, lowercase, or irregular capitalization).",
                    )
                )
                improvements.append(
                    QualityImprovement(
                        title="Standardize Heading Formatting",
                        recommendation="Adopt a consistent capitalization pattern for all section headers (e.g., all UPPERCASE or all Title Case).",
                        criterion_key=QualityCriterionKey.FORMATTING_CONSISTENCY.value,
                        rationale="Consistent heading typography creates a clean, predictable reading hierarchy.",
                    )
                )

        score = max(15.0, min(100.0, score))
        status_str = "STRONG" if score >= 80 else ("ACCEPTABLE" if score >= 60 else "NEEDS_IMPROVEMENT")

        result = QualityCriterionResult(
            criterion_key=QualityCriterionKey.FORMATTING_CONSISTENCY.value,
            criterion_name="Formatting Consistency",
            score=score,
            weight=self.weights[QualityCriterionKey.FORMATTING_CONSISTENCY.value],
            weighted_score=score * self.weights[QualityCriterionKey.FORMATTING_CONSISTENCY.value],
            status=status_str,
            observations=f"Evaluated typographical and bullet consistency across {len(lines)} lines.",
            evidence_snippets=[f"Bullet styles observed: {len(bullet_types)}"],
        )
        return result, strengths, improvements, issues

    def _eval_experience_clarity(
        self,
        structured: Dict[str, Any],
        section_map: Dict[str, SectionInfo],
    ) -> Tuple[QualityCriterionResult, List[QualityStrength], List[QualityImprovement], List[QualityIssue]]:
        strengths: List[QualityStrength] = []
        improvements: List[QualityImprovement] = []
        issues: List[QualityIssue] = []

        exp_list = structured.get("experience", [])
        has_exp_section = "EXPERIENCE" in section_map

        if not exp_list and not has_exp_section:
            result = QualityCriterionResult(
                criterion_key=QualityCriterionKey.EXPERIENCE_CLARITY.value,
                criterion_name="Experience Clarity",
                score=25.0,
                weight=self.weights[QualityCriterionKey.EXPERIENCE_CLARITY.value],
                weighted_score=25.0 * self.weights[QualityCriterionKey.EXPERIENCE_CLARITY.value],
                status="NEEDS_IMPROVEMENT",
                observations="No formal professional experience records were identified.",
                evidence_snippets=[],
            )
            return result, strengths, improvements, issues

        score = 65.0
        roles_with_titles = sum(1 for e in exp_list if isinstance(e, dict) and (e.get("title") or e.get("job_title")))
        roles_with_employers = sum(1 for e in exp_list if isinstance(e, dict) and e.get("employer"))
        roles_with_dates = sum(1 for e in exp_list if isinstance(e, dict) and e.get("dates"))

        total_roles = max(1, len(exp_list))
        if roles_with_titles == total_roles and roles_with_titles > 0:
            score += 10.0
        if roles_with_employers == total_roles and roles_with_employers > 0:
            score += 10.0
        if roles_with_dates == total_roles and roles_with_dates > 0:
            score += 5.0

        has_bulleted_desc = any(
            isinstance(e, dict) and ("•" in str(e.get("description", "")) or "-" in str(e.get("description", "")) or len(str(e.get("description", "")).splitlines()) > 1)
            for e in exp_list
        )
        if has_bulleted_desc:
            score += 10.0
        else:
            score -= 10.0

        if score >= 85 and exp_list:
            first_e = exp_list[0]
            if isinstance(first_e, dict):
                sample_role = first_e.get("title") or first_e.get("job_title") or "Role"
                sample_org = first_e.get("employer") or "Company"
            else:
                sample_role = str(first_e)
                sample_org = "Organization"
            strengths.append(
                QualityStrength(
                    title="Clearly Structured Roles",
                    description="Each employment entry clearly identifies job title, organization, dates, and responsibilities.",
                    criterion_key=QualityCriterionKey.EXPERIENCE_CLARITY.value,
                    evidence_quote=f"Example: {sample_role} at {sample_org}",
                )
            )
        elif roles_with_titles < total_roles:
            issues.append(
                QualityIssue(
                    issue_type="AMBIGUOUS_JOB_TITLES",
                    severity=IssueSeverity.MEDIUM,
                    description="Some work history entries lack explicit job titles.",
                )
            )
            improvements.append(
                QualityImprovement(
                    title="Explicitly State Job Titles for All Roles",
                    recommendation="Ensure every position clearly states your formal title alongside the organization name.",
                    criterion_key=QualityCriterionKey.EXPERIENCE_CLARITY.value,
                    rationale="Ambiguous role designations make career trajectory difficult to evaluate.",
                )
            )

        score = max(20.0, min(100.0, score))
        status_str = "STRONG" if score >= 80 else ("ACCEPTABLE" if score >= 60 else "NEEDS_IMPROVEMENT")

        snippets = []
        for e in exp_list[:3]:
            if isinstance(e, dict):
                snippets.append(f"{e.get('title') or e.get('job_title') or 'Role'} @ {e.get('employer') or 'N/A'}")
            else:
                snippets.append(str(e))

        result = QualityCriterionResult(
            criterion_key=QualityCriterionKey.EXPERIENCE_CLARITY.value,
            criterion_name="Experience Clarity",
            score=score,
            weight=self.weights[QualityCriterionKey.EXPERIENCE_CLARITY.value],
            weighted_score=score * self.weights[QualityCriterionKey.EXPERIENCE_CLARITY.value],
            status=status_str,
            observations=f"Extracted {len(exp_list)} role(s): {roles_with_titles} with titles, {roles_with_employers} with employers, {roles_with_dates} with dates.",
            evidence_snippets=snippets,
        )
        return result, strengths, improvements, issues

    def _eval_skills_clarity(
        self,
        structured: Dict[str, Any],
        section_map: Dict[str, SectionInfo],
    ) -> Tuple[QualityCriterionResult, List[QualityStrength], List[QualityImprovement], List[QualityIssue]]:
        strengths: List[QualityStrength] = []
        improvements: List[QualityImprovement] = []
        issues: List[QualityIssue] = []

        skills_list = structured.get("skills", [])
        has_skills_section = "SKILLS" in section_map

        score = 50.0
        if has_skills_section:
            score += 20.0
            sec_text = section_map["SKILLS"].content

            has_subcategories = bool(re.search(r"(?:languages|frameworks|tools|databases|cloud|libraries|technical|core)\s*:", sec_text, re.IGNORECASE))
            if has_subcategories:
                score += 25.0
                strengths.append(
                    QualityStrength(
                        title="Categorized Skills Inventory",
                        description="Skills are neatly categorized under thematic subheadings (e.g., Languages, Tools, Cloud), enhancing scannability.",
                        criterion_key=QualityCriterionKey.SKILLS_CLARITY.value,
                    )
                )
            elif len(skills_list) >= 5:
                score += 5.0
                strengths.append(
                    QualityStrength(
                        title="Dedicated Skills Section",
                        description=f"Distinct skills section containing {len(skills_list)} identifiable technical/domain skills.",
                        criterion_key=QualityCriterionKey.SKILLS_CLARITY.value,
                    )
                )
        else:
            score -= 15.0
            issues.append(
                QualityIssue(
                    issue_type="NO_DEDICATED_SKILLS_SECTION",
                    severity=IssueSeverity.LOW,
                    description="Skills are mentioned within narrative text rather than organized in a dedicated skills section.",
                )
            )
            improvements.append(
                QualityImprovement(
                    title="Add a Categorized Skills Section",
                    recommendation="Group your core skills under a dedicated 'Skills' heading, organized by domain (e.g., Languages, Cloud, Frameworks).",
                    criterion_key=QualityCriterionKey.SKILLS_CLARITY.value,
                    rationale="A dedicated skills section allows technical recruiters to verify stack compatibility instantly.",
                )
            )

        score = max(20.0, min(100.0, score))
        status_str = "STRONG" if score >= 80 else ("ACCEPTABLE" if score >= 60 else "NEEDS_IMPROVEMENT")

        skill_names = [s.get("skill_name") or str(s) if isinstance(s, dict) else str(s) for s in skills_list[:5]]

        result = QualityCriterionResult(
            criterion_key=QualityCriterionKey.SKILLS_CLARITY.value,
            criterion_name="Skills Clarity",
            score=score,
            weight=self.weights[QualityCriterionKey.SKILLS_CLARITY.value],
            weighted_score=score * self.weights[QualityCriterionKey.SKILLS_CLARITY.value],
            status=status_str,
            observations=f"Extracted {len(skills_list)} verified skills. Dedicated section: {'Yes' if has_skills_section else 'No'}.",
            evidence_snippets=skill_names,
        )
        return result, strengths, improvements, issues

    def _eval_achievement_specificity(
        self,
        readability: ReadabilityMetrics,
        lines: List[str],
    ) -> Tuple[QualityCriterionResult, List[QualityStrength], List[QualityImprovement], List[QualityIssue]]:
        strengths: List[QualityStrength] = []
        improvements: List[QualityImprovement] = []
        issues: List[QualityIssue] = []

        metric_count = readability.quantified_metric_count
        score = 50.0

        if metric_count >= 5:
            score = 95.0
            strengths.append(
                QualityStrength(
                    title="High Quantifiable Impact",
                    description=f"Contains {metric_count} concrete, metric-driven achievements (percentages, revenue, scale, latency).",
                    criterion_key=QualityCriterionKey.ACHIEVEMENT_SPECIFICITY.value,
                )
            )
        elif metric_count >= 2:
            score = 75.0
            strengths.append(
                QualityStrength(
                    title="Quantifiable Results Included",
                    description=f"Includes {metric_count} quantifiable results supporting responsibility descriptions.",
                    criterion_key=QualityCriterionKey.ACHIEVEMENT_SPECIFICITY.value,
                )
            )
        else:
            score = 45.0
            issues.append(
                QualityIssue(
                    issue_type="LOW_QUANTIFIABLE_METRICS",
                    severity=IssueSeverity.MEDIUM,
                    description="Few quantifiable metrics or concrete outcome figures were found in role descriptions.",
                )
            )
            improvements.append(
                QualityImprovement(
                    title="Quantify Achievements with Concrete Metrics",
                    recommendation="Incorporate measurable results into bullet points (e.g., 'reduced turnaround time by 30%', 'managed team of 5', 'scaled system to 10k users').",
                    criterion_key=QualityCriterionKey.ACHIEVEMENT_SPECIFICITY.value,
                    rationale="Quantified contributions demonstrate tangible business value rather than just job attendance.",
                )
            )

        status_str = "STRONG" if score >= 80 else ("ACCEPTABLE" if score >= 60 else "NEEDS_IMPROVEMENT")

        result = QualityCriterionResult(
            criterion_key=QualityCriterionKey.ACHIEVEMENT_SPECIFICITY.value,
            criterion_name="Achievement Specificity",
            score=score,
            weight=self.weights[QualityCriterionKey.ACHIEVEMENT_SPECIFICITY.value],
            weighted_score=score * self.weights[QualityCriterionKey.ACHIEVEMENT_SPECIFICITY.value],
            status=status_str,
            observations=f"Detected {metric_count} quantifiable outcome metrics in document descriptions.",
            evidence_snippets=[f"Metric count: {metric_count}"],
        )
        return result, strengths, improvements, issues

    def _eval_date_consistency(
        self,
        structured: Dict[str, Any],
        text: str,
    ) -> Tuple[QualityCriterionResult, List[QualityStrength], List[QualityImprovement], List[QualityIssue]]:
        strengths: List[QualityStrength] = []
        improvements: List[QualityImprovement] = []
        issues: List[QualityIssue] = []

        exp_list = structured.get("experience", [])
        edu_list = structured.get("education", [])

        if not exp_list:
            score = 30.0
            issues.append(
                QualityIssue(
                    issue_type="NO_CHRONOLOGICAL_EXPERIENCE",
                    severity=IssueSeverity.MEDIUM,
                    description="No structured employment timeline or chronological role tenures detected.",
                )
            )
            result = QualityCriterionResult(
                criterion_key=QualityCriterionKey.DATE_CONSISTENCY.value,
                criterion_name="Date Consistency",
                score=score,
                weight=self.weights[QualityCriterionKey.DATE_CONSISTENCY.value],
                weighted_score=score * self.weights[QualityCriterionKey.DATE_CONSISTENCY.value],
                status="NEEDS_IMPROVEMENT",
                observations="No structured experience dates detected in document.",
                evidence_snippets=[],
            )
            return result, strengths, improvements, issues

        year_matches = re.findall(r"\b(19\d\d|20\d\d)\b", text)
        years = [int(y) for y in year_matches]

        score = 80.0
        current_year = datetime.now(timezone.utc).year

        future_years = [y for y in years if y > current_year + 1]
        if future_years:
            score -= 20.0
            issues.append(
                QualityIssue(
                    issue_type="FUTURE_DATE_ANOMALY",
                    severity=IssueSeverity.MEDIUM,
                    description=f"Detected potentially anomalous future year: {future_years[0]}.",
                )
            )

        missing_dates_count = sum(1 for e in exp_list if not (isinstance(e, dict) and e.get("dates")))
        if missing_dates_count == 0 and len(exp_list) > 0:
            strengths.append(
                QualityStrength(
                    title="Complete Chronological Dates",
                    description="All employment positions have clearly designated dates or active tenures.",
                    criterion_key=QualityCriterionKey.DATE_CONSISTENCY.value,
                )
            )
            score += 10.0

        date_strings = [str(e.get("dates", "")) for e in exp_list if isinstance(e, dict) and e.get("dates")]
        has_numeric_slash = any("/" in d for d in date_strings)
        has_month_word = any(re.search(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b", d, re.IGNORECASE) for d in date_strings)
        has_year_only = any(re.match(r"^\s*\d{4}\s*$", d) for d in date_strings)

        if (has_numeric_slash and has_month_word) or (has_numeric_slash and has_year_only):
            score -= 20.0
            issues.append(
                QualityIssue(
                    issue_type="INCONSISTENT_DATE_FORMATTING",
                    severity=IssueSeverity.LOW,
                    description="Inconsistent date formatting across experience entries (mixing numeric MM/YYYY and textual month styles).",
                )
            )
            improvements.append(
                QualityImprovement(
                    title="Standardize Date Formats",
                    recommendation="Use a consistent date style across all positions (e.g., 'MM/YYYY – MM/YYYY' or 'Month YYYY – Month YYYY').",
                    criterion_key=QualityCriterionKey.DATE_CONSISTENCY.value,
                    rationale="Uniform dates prevent recruiter confusion and ensure accurate tenure calculation.",
                )
            )

        score = max(20.0, min(100.0, score))
        status_str = "STRONG" if score >= 80 else ("ACCEPTABLE" if score >= 60 else "NEEDS_IMPROVEMENT")

        result = QualityCriterionResult(
            criterion_key=QualityCriterionKey.DATE_CONSISTENCY.value,
            criterion_name="Date Consistency",
            score=score,
            weight=self.weights[QualityCriterionKey.DATE_CONSISTENCY.value],
            weighted_score=score * self.weights[QualityCriterionKey.DATE_CONSISTENCY.value],
            status=status_str,
            observations=f"Audited {len(years)} date reference(s). Missing tenure dates: {missing_dates_count}.",
            evidence_snippets=[str(y) for y in years[:5]],
        )
        return result, strengths, improvements, issues

    def _eval_contact_completeness(
        self,
        structured: Dict[str, Any],
        text: str,
    ) -> Tuple[QualityCriterionResult, List[QualityStrength], List[QualityImprovement], List[QualityIssue]]:
        strengths: List[QualityStrength] = []
        improvements: List[QualityImprovement] = []
        issues: List[QualityIssue] = []

        contact = structured.get("contact", {})
        has_email = bool(contact.get("email")) or bool(re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text))
        has_phone = bool(contact.get("phone")) or bool(re.search(r"(?:\+?\d{1,3}[\s-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}", text))
        has_linkedin = bool(re.search(r"linkedin\.com/in/[\w-]+", text, re.IGNORECASE))
        has_github = bool(re.search(r"github\.com/[\w-]+", text, re.IGNORECASE))
        has_portfolio = bool(re.search(r"https?://[\w.-]+", text, re.IGNORECASE))

        score = 0.0
        if has_email:
            score += 60.0
        if has_phone:
            score += 25.0
        if has_linkedin or has_github or has_portfolio:
            score += 15.0

        if has_email:
            score = max(80.0, score)
            strengths.append(
                QualityStrength(
                    title="Direct Contact Information",
                    description="Contains verifiable professional email communication channel.",
                    criterion_key=QualityCriterionKey.CONTACT_COMPLETENESS.value,
                )
            )
            if has_linkedin or has_github:
                strengths.append(
                    QualityStrength(
                        title="Professional Online Presence",
                        description="Includes links to verified technical/professional profiles (LinkedIn or GitHub).",
                        criterion_key=QualityCriterionKey.CONTACT_COMPLETENESS.value,
                    )
                )
        else:
            score = 25.0
            issues.append(
                QualityIssue(
                    issue_type="NO_EMAIL_DETECTED",
                    severity=IssueSeverity.HIGH,
                    description="No professional email address could be extracted from the resume.",
                )
            )
            improvements.append(
                QualityImprovement(
                    title="Add Direct Contact Information",
                    recommendation="Ensure a clean, professional email address is prominently visible in the header.",
                    criterion_key=QualityCriterionKey.CONTACT_COMPLETENESS.value,
                    rationale="Recruiters require direct contact details to schedule preliminary conversations.",
                )
            )

        score = max(10.0, min(100.0, score))
        status_str = "STRONG" if score >= 80 else ("ACCEPTABLE" if score >= 60 else "NEEDS_IMPROVEMENT")

        result = QualityCriterionResult(
            criterion_key=QualityCriterionKey.CONTACT_COMPLETENESS.value,
            criterion_name="Contact Completeness",
            score=score,
            weight=self.weights[QualityCriterionKey.CONTACT_COMPLETENESS.value],
            weighted_score=score * self.weights[QualityCriterionKey.CONTACT_COMPLETENESS.value],
            status=status_str,
            observations=(
                f"Contact audit: Email ({'Found' if has_email else 'Missing'}), "
                f"Phone ({'Found' if has_phone else 'Not detected'}), "
                f"Web/Profile ({'Found' if (has_linkedin or has_github or has_portfolio) else 'None'})."
            ),
            evidence_snippets=[
                f"Email: {'Yes' if has_email else 'No'}",
                f"Phone: {'Yes' if has_phone else 'No'}",
                f"Profile link: {'Yes' if (has_linkedin or has_github) else 'No'}",
            ],
        )
        return result, strengths, improvements, issues

    def _eval_extraction_quality(
        self,
        extraction: ExtractionDiagnostics,
        text: str,
    ) -> Tuple[QualityCriterionResult, List[QualityStrength], List[QualityImprovement], List[QualityIssue]]:
        strengths: List[QualityStrength] = []
        improvements: List[QualityImprovement] = []
        issues: List[QualityIssue] = []

        score = 95.0

        if extraction.is_empty:
            score = 0.0
            issues.append(
                QualityIssue(
                    issue_type="EMPTY_DOCUMENT",
                    severity=IssueSeverity.HIGH,
                    description="The uploaded file contained no extractable textual content.",
                )
            )
        elif extraction.ocr_needed:
            score = 30.0
            issues.append(
                QualityIssue(
                    issue_type="SCANNED_IMAGE_DOCUMENT",
                    severity=IssueSeverity.HIGH,
                    description="Document appears to be a flattened scanned image rather than a selectable text PDF/DOCX.",
                )
            )
            improvements.append(
                QualityImprovement(
                    title="Export Resume as Text-Selectable PDF",
                    recommendation="Export directly from Microsoft Word, Google Docs, or LaTeX rather than scanning a printed document.",
                    criterion_key=QualityCriterionKey.EXTRACTION_QUALITY.value,
                    rationale="Applicant Tracking Systems cannot reliably index non-selectable flattened scans.",
                )
            )
        elif extraction.char_count < 300:
            score = 35.0
            issues.append(
                QualityIssue(
                    issue_type="VERY_SHORT_DOCUMENT",
                    severity=IssueSeverity.MEDIUM,
                    description="Document character count is very short (< 300 characters).",
                )
            )
        else:
            strengths.append(
                QualityStrength(
                    title="Clean Digital Extraction",
                    description=f"Successfully extracted {extraction.char_count} characters across {extraction.line_count} structured lines without OCR artifacts.",
                    criterion_key=QualityCriterionKey.EXTRACTION_QUALITY.value,
                )
            )

        if extraction.warnings:
            for w in extraction.warnings:
                issues.append(
                    QualityIssue(
                        issue_type="EXTRACTION_WARNING",
                        severity=IssueSeverity.LOW,
                        description=w,
                    )
                )

        score = max(0.0, min(100.0, score))
        status_str = "STRONG" if score >= 80 else ("ACCEPTABLE" if score >= 60 else "NEEDS_IMPROVEMENT")

        result = QualityCriterionResult(
            criterion_key=QualityCriterionKey.EXTRACTION_QUALITY.value,
            criterion_name="Extraction Quality",
            score=score,
            weight=self.weights[QualityCriterionKey.EXTRACTION_QUALITY.value],
            weighted_score=score * self.weights[QualityCriterionKey.EXTRACTION_QUALITY.value],
            status=status_str,
            observations=f"Extracted {extraction.char_count} chars ({extraction.line_count} lines). Confidence: {int(extraction.parse_confidence * 100)}%.",
            evidence_snippets=[f"Chars: {extraction.char_count}", f"Lines: {extraction.line_count}"],
        )
        return result, strengths, improvements, issues


    def _build_executive_summary(
        self,
        overall_score: float,
        quality_label: QualityLabel,
        strengths: List[QualityStrength],
        improvements: List[QualityImprovement],
        issues: List[QualityIssue],
        extraction: ExtractionDiagnostics,
    ) -> str:
        lines: List[str] = []
        lines.append(
            f"Resume Quality Score: {overall_score:.1f}/100 ({quality_label.value})."
        )
        lines.append(
            "This assessment evaluates document structure, readability, and communicative clarity. "
            "It is completely independent of candidate qualifications and job fit."
        )

        if strengths:
            lines.append(
                f"Key document strengths include: {'; '.join([s.title for s in strengths[:3]])}."
            )

        if improvements:
            lines.append(
                f"Recommended improvements: {'; '.join([i.title for i in improvements[:2]])}."
            )

        if issues:
            high_issues = [iss for iss in issues if iss.severity == IssueSeverity.HIGH]
            if high_issues:
                lines.append(
                    f"Noted document alerts: {high_issues[0].description}"
                )

        return " ".join(lines)
