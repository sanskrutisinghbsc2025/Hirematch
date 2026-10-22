
from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("hirematch.discrepancy_detector")


class DiscrepancyDetector:

    @classmethod
    def detect_discrepancies(
        cls,
        candidate_id: str,
        criterion_results: List[Dict[str, Any]],
        overall_score: Optional[float] = None,
        evidence_coverage: Optional[float] = None,
        experience: Optional[List[Dict[str, Any]]] = None,
        skills: Optional[List[str]] = None,
        extracted_text: Optional[str] = None,
        projects: Optional[List[Dict[str, Any]]] = None,
        conflicting_criteria: Optional[List[str]] = None,
        unmet_mandatory_criteria: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        discrepancies: List[Dict[str, Any]] = []

        known_unmet = set(unmet_mandatory_criteria or [])
        for crit in criterion_results or []:
            c_name = crit.get("criterion_name") or "Unknown Requirement"
            c_type = str(crit.get("criterion_type", "")).upper()
            status = str(crit.get("match_status", "")).upper()
            score = float(crit.get("score", 0.0))
            is_req = "REQUIRED" in c_type or crit.get("is_required", False)

            is_unmet = (
                c_name in known_unmet
                or (
                    is_req
                    and (
                        score < 50.0
                        or status in ("NOT_FOUND", "INSUFFICIENT_EVIDENCE", "NOT_SUPPORTED", "CONTRADICTED")
                    )
                )
            )

            if is_unmet:
                explanation = crit.get("explanation") or "Resume lacks verifiable documentation for this requirement."
                score_str = f"{score:.1f}%" if score <= 100.0 else f"{score:.1f}"
                discrepancies.append({
                    "severity": "CRITICAL",
                    "type": "Mandatory Requirement Unmet",
                    "title": f"Mandatory Requirement Unmet: {c_name}",
                    "description": (
                        f"Candidate does not satisfy mandatory requirement '{c_name}'. "
                        f"Evaluation score: {score_str} ({status}). {explanation}"
                    ),
                    "criterion_name": c_name,
                    "evidence": crit.get("supporting_evidence") or [],
                })

        covered_crits = {d.get("criterion_name") for d in discrepancies if d.get("criterion_name")}
        for u in known_unmet:
            if u not in covered_crits:
                discrepancies.append({
                    "severity": "CRITICAL",
                    "type": "Mandatory Requirement Unmet",
                    "title": f"Mandatory Requirement Unmet: {u}",
                    "description": f"Mandatory requirement '{u}' was not verified in candidate documentation.",
                    "criterion_name": u,
                    "evidence": [],
                })

        known_conflicts = set(conflicting_criteria or [])
        for crit in criterion_results or []:
            c_name = crit.get("criterion_name") or "Requirement"
            status = str(crit.get("match_status", "")).upper()
            disagreement = str(crit.get("disagreement_type", "")).upper()
            has_conflict = (
                c_name in known_conflicts
                or status in ("CONFLICTING_EVIDENCE", "CONTRADICTED")
                or "NEGATED" in disagreement
            )
            if has_conflict:
                conflict_exp = crit.get("conflict_explanation") or crit.get("explanation") or (
                    "Contradictory evidence detected in resume context."
                )
                discrepancies.append({
                    "severity": "HIGH",
                    "type": "Conflicting Evidence",
                    "title": f"Conflicting Evidence: {c_name}",
                    "description": (
                        f"Conflicting or contradictory evidence flagged for '{c_name}'. "
                        f"{conflict_exp} Zero credit awarded pending recruiter audit."
                    ),
                    "criterion_name": c_name,
                    "evidence": crit.get("supporting_evidence") or [],
                })

        for c in known_conflicts:
            if c not in {d.get("criterion_name") for d in discrepancies if d.get("type") == "Conflicting Evidence"}:
                discrepancies.append({
                    "severity": "HIGH",
                    "type": "Conflicting Evidence",
                    "title": f"Conflicting Evidence: {c}",
                    "description": f"Conflicting evidence flagged for criterion '{c}' (recruiter review required).",
                    "criterion_name": c,
                    "evidence": [],
                })

        if overall_score is not None and overall_score < 50.0:
            discrepancies.append({
                "severity": "CRITICAL",
                "type": "Low Composite Fit Score",
                "title": f"Candidate Does Not Meet Baseline Qualification ({overall_score:.1f}/100)",
                "description": (
                    f"Overall composite score of {overall_score:.1f}/100 falls below the 50.0 threshold. "
                    "Candidate lacks verified qualifications across one or more critical job dimensions."
                ),
                "criterion_name": "Overall Fit",
                "evidence": [],
            })

        has_experience = bool(experience and len(experience) > 0)
        if not has_experience:
            discrepancies.append({
                "severity": "HIGH",
                "type": "Tenure Deficiency",
                "title": "Zero Documented Professional Experience",
                "description": (
                    "No verifiable employment records or professional work history could be parsed "
                    "from candidate documentation. Ensure candidate is not a blank or unparseable submission."
                ),
                "criterion_name": "Work Experience",
                "evidence": [],
            })

        if has_experience and experience:
            cls._check_timeline_anomalies(experience, discrepancies)

        if skills and (experience or extracted_text or projects):
            cls._check_uncorroborated_skills(skills, experience or [], projects or [], extracted_text or "", discrepancies)

        if evidence_coverage is not None and evidence_coverage < 40.0:
            discrepancies.append({
                "severity": "MEDIUM",
                "type": "Low Evidence Coverage",
                "title": f"Low Evidence Coverage ({evidence_coverage:.1f}%)",
                "description": (
                    f"Verified evidence was only found for {evidence_coverage:.1f}% of evaluated job requirements. "
                    "A substantial portion of required credentials could not be substantiated in the resume."
                ),
                "criterion_name": "Evidence Verification",
                "evidence": [],
            })

        priority_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "ADVISORY": 3}
        discrepancies.sort(key=lambda d: priority_order.get(d.get("severity", "MEDIUM"), 4))

        return discrepancies

    @classmethod
    def _check_timeline_anomalies(
        cls,
        experience: List[Dict[str, Any]],
        discrepancies: List[Dict[str, Any]],
    ) -> None:
        parsed_intervals: List[Tuple[Optional[datetime], Optional[datetime], str, str]] = []

        for exp in experience:
            role = exp.get("job_title") or exp.get("title") or "Unknown Role"
            company = exp.get("employer") or exp.get("company") or "Unknown Company"
            date_str = exp.get("dates") or exp.get("date_range") or exp.get("extracted_description", "")
            
            start_dt, end_dt, is_present = cls._parse_dates(date_str)
            if not start_dt:
                start_dt, end_dt, is_present = cls._parse_dates(str(exp.get("employer", "")))

            if not start_dt and not end_dt:
                # Overlook/skip undated roles - do not flag as discrepancies or anomalies
                continue

            resolved_end = datetime.now() if is_present or not end_dt else end_dt
            if start_dt:
                parsed_intervals.append((start_dt, resolved_end, role, company))

        parsed_intervals.sort(key=lambda x: x[0] or datetime.min)

        for i in range(len(parsed_intervals) - 1):
            curr_start, curr_end, curr_role, curr_comp = parsed_intervals[i]
            next_start, next_end, next_role, next_comp = parsed_intervals[i + 1]

            if curr_end and next_start:
                delta = (next_start - curr_end).days
                if delta > 270:
                    gap_months = round(delta / 30.4)
                    discrepancies.append({
                        "severity": "MEDIUM",
                        "type": "Employment Timeline Gap",
                        "title": f"Employment Gap ({gap_months} months)",
                        "description": (
                            f"Detected an unexplained employment gap of approximately {gap_months} months "
                            f"between '{curr_role}' at {curr_comp} (ended {curr_end.strftime('%b %Y')}) "
                            f"and '{next_role}' at {next_comp} (started {next_start.strftime('%b %Y')})."
                        ),
                        "criterion_name": "Career Continuity",
                        "evidence": [f"Gap from {curr_end.strftime('%m/%Y')} to {next_start.strftime('%m/%Y')}"],
                    })
                elif delta < -90:
                    if curr_comp.lower() != next_comp.lower() and "intern" not in curr_role.lower():
                        discrepancies.append({
                            "severity": "MEDIUM",
                            "type": "Overlapping Employment",
                            "title": f"Concurrent Employment Overlap: {curr_role} & {next_role}",
                            "description": (
                                f"Overlapping tenure detected between '{curr_role}' at {curr_comp} and "
                                f"'{next_role}' at {next_comp}. Verify if positions were concurrent or part-time."
                            ),
                            "criterion_name": "Career Continuity",
                            "evidence": [f"{curr_role} ({curr_comp}) overlaps with {next_role} ({next_comp})"],
                        })

    @classmethod
    def _parse_dates(cls, text: str) -> Tuple[Optional[datetime], Optional[datetime], bool]:
        if not text:
            return None, None, False

        text_lower = text.lower()
        is_present = any(kw in text_lower for kw in ("present", "current", "now", "ongoing"))

        year_matches = list(re.finditer(r"\b(19\d\d|20\d\d)\b", text))
        if not year_matches:
            return None, None, is_present

        years = [int(m.group(1)) for m in year_matches]

        month_map = {
            "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
            "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
        }

        start_year = years[0]
        start_month = 1
        m_match = re.search(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s*" + str(start_year), text_lower)
        if m_match:
            start_month = month_map.get(m_match.group(1)[:3], 1)

        start_dt = datetime(start_year, start_month, 1)

        end_dt = None
        if len(years) > 1:
            end_year = years[-1]
            end_month = 12
            m_end_match = re.search(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s*" + str(end_year), text_lower)
            if m_end_match:
                end_month = month_map.get(m_end_match.group(1)[:3], 12)
            end_dt = datetime(end_year, end_month, 1)
        elif is_present:
            end_dt = datetime.now()

        return start_dt, end_dt, is_present

    @classmethod
    def _check_uncorroborated_skills(
        cls,
        skills: List[str],
        experience: List[Dict[str, Any]],
        projects: List[Dict[str, Any]],
        extracted_text: str,
        discrepancies: List[Dict[str, Any]],
    ) -> None:
        if not skills or len(skills) < 3:
            return

        exp_text = " ".join([
            str(e.get("extracted_description", "")) + " " + str(e.get("job_title", "")) + " " + str(e.get("evidence_text", ""))
            for e in experience
        ]).lower()

        proj_text = " ".join([
            str(p.get("description", "")) + " " + str(p.get("title", "")) + " " + str(p.get("technologies", ""))
            for p in projects
        ]).lower()

        practical_corpus = exp_text + " " + proj_text

        uncorroborated: List[str] = []
        for s in skills[:20]:
            s_clean = s.strip()
            if len(s_clean) < 3:
                continue
            pattern = r"\b" + re.escape(s_clean.lower()) + r"\b"
            if not re.search(pattern, practical_corpus):
                uncorroborated.append(s_clean)

        if len(uncorroborated) >= 3:
            sample = ", ".join(uncorroborated[:4])
            discrepancies.append({
                "severity": "ADVISORY",
                "type": "Uncorroborated Skill Claim",
                "title": f"Uncorroborated Skill Claims ({len(uncorroborated)} skills)",
                "description": (
                    f"Found {len(uncorroborated)} skills listed in skills section without practical context or project "
                    f"demonstration in work experience: {sample}."
                ),
                "criterion_name": "Skill Corroboration",
                "evidence": uncorroborated[:6],
            })
