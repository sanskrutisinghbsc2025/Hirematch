
from typing import List

from core.models.enums import CriterionType, MatchStatus
from core.models.scoring_models import CandidateScoringRecord


class ScoreExplanationGenerator:

    RESPONSIBLE_AI_DISCLAIMER = (
        "Note: This score reflects documented evidence matching against specified job requirements, "
        "not an assessment of general candidate competence, character, or guaranteed job performance. "
        "Final recruitment and hiring decisions remain solely with human recruiters."
    )

    def generate_narrative_explanation(self, record: CandidateScoringRecord) -> str:
        if record.overall_score is None:
            return (
                f"Candidate evaluation is pending or incomplete (Status: {record.completeness_status.value}). "
                f"Insufficient verifiable evidence or criteria were available in the active configuration.\n\n"
                f"{self.RESPONSIBLE_AI_DISCLAIMER}"
            )

        score = record.overall_score
        coverage = record.evidence_coverage
        supported = [
            c for c in record.criterion_contributions
            if c.is_eligible and c.match_status in (MatchStatus.SUPPORTED, MatchStatus.PARTIALLY_SUPPORTED)
        ]
        supported.sort(key=lambda x: x.normalized_contribution, reverse=True)

        conflicts = [c for c in record.criterion_contributions if c.match_status == MatchStatus.CONFLICTING_EVIDENCE]
        missing = [
            c for c in record.criterion_contributions
            if c.is_eligible and c.match_status in (MatchStatus.NOT_FOUND, MatchStatus.INSUFFICIENT_EVIDENCE)
        ]
        missing.sort(key=lambda x: x.configured_weight, reverse=True)

        fit_tier = "Strong Match" if score >= 80 else ("Potential Match" if score >= 60 else "Under Review")
        if score >= 80:
            exec_summary = (
                f"Candidate demonstrates strong alignment with role requirements, achieving a composite score of "
                f"{score:.1f}/100 across {coverage:.1f}% verified evidence coverage. "
                f"Their background reflects well-documented core competencies and practical tool proficiency."
            )
        elif score >= 60:
            exec_summary = (
                f"Candidate represents a viable potential match with a composite score of {score:.1f}/100 "
                f"and {coverage:.1f}% evidence coverage. While essential baseline skills are evidenced, "
                f"there are partial matches or specific tooling/tenure gaps that warrant targeted recruiter probing."
            )
        else:
            exec_summary = (
                f"Candidate scored {score:.1f}/100 with {coverage:.1f}% evidence coverage, indicating notable gaps "
                f"against required job criteria. Documented resume evidence is currently insufficient for several core qualifications."
            )

        sections: List[str] = [
            f"**Executive Evaluation Summary ({fit_tier} • {score:.1f}/100)**\n{exec_summary}"
        ]

        if supported:
            strength_lines = []
            for c in supported:
                notes_text = f" — {c.notes}" if c.notes else ""
                strength_lines.append(
                    f"• **{c.criterion_name}** (+{c.normalized_contribution:.1f} pts | Weight {c.configured_weight:.2f}): "
                    f"Verified ({c.match_status.value.replace('_', ' ').title()}){notes_text}."
                )
            sections.append(
                "**Key Matched Strengths (Why Candidate Matched)**\n" + "\n".join(strength_lines)
            )

        if missing or conflicts:
            gap_lines = []
            for c in missing:
                gap_lines.append(
                    f"• **{c.criterion_name}** (0.0 pts awarded | Weight {c.configured_weight:.2f}): "
                    f"Resume does not contain verifiable documentation for this requirement. The candidate lacks demonstrated proficiency in this area."
                )
            for c in conflicts:
                gap_lines.append(
                    f"• **⚠️ {c.criterion_name}**: Conflicting evidence detected in documentation. Awarded 0.0 pts pending human verification."
                )
            sections.append(
                "**Identified Deficiencies & Gaps (What Candidate Lacks)**\n" + "\n".join(gap_lines)
            )
        else:
            sections.append(
                "**Identified Deficiencies & Gaps**\n• No critical omissions detected; candidate meets or exceeds all active criteria."
            )

        if record.required_summary.total_required > 0:
            req = record.required_summary
            sat = req.supported_count + req.partially_supported_count
            sections.append(
                f"**Mandatory Requirements Tracking**\n"
                f"Candidate satisfied {sat} of {req.total_required} mandatory requirements "
                f"({req.supported_count} fully supported, {req.partially_supported_count} partially supported, {len(missing)} unmet)."
            )

        probes = []
        if missing:
            top_missing = missing[0].criterion_name
            probes.append(
                f"1. **Gap Validation ({top_missing})**: \"Can you describe your direct experience or hands-on background working with {top_missing.lower()}?\""
            )
        if supported:
            top_supported = supported[0].criterion_name
            probes.append(
                f"2. **Technical Depth ({top_supported})**: \"Could you walk through the most complex project where you applied your expertise in {top_supported.lower()}? What was the outcome?\""
            )
        probes.append(
            "3. **Practical Problem-Solving**: \"Describe a situation where you had to adapt quickly to unfamiliar tools or vague business requirements. How did you deliver results?\""
        )
        sections.append(
            "**Recommended Recruiter Interview Probe Questions**\n" + "\n".join(probes)
        )

        sections.append(f"*{self.RESPONSIBLE_AI_DISCLAIMER}*")

        return "\n\n".join(sections)
