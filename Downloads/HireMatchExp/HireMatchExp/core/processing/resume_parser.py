
from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional

from core.models.education import EducationRecord
from core.models.experience import WorkExperience
from core.models.skills import ExtractedSkill
from core.processing.cleaner import TextCleaner
from core.processing.section_detector import ResumeSectionDetector, SectionInfo
from core.processing.skill_normalizer import SkillTaxonomyNormalizer


@dataclass
class ContactInfo:
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None


@dataclass
class ProjectRecord:
    title: str
    description: str
    evidence_text: str


@dataclass
class CertificationRecord:
    name: str
    issuer: Optional[str] = None
    date: Optional[str] = None
    evidence_text: str = ""


@dataclass
class StructuredResume:
    contact: ContactInfo
    skills: List[ExtractedSkill] = field(default_factory=list)
    experience: List[WorkExperience] = field(default_factory=list)
    education: List[EducationRecord] = field(default_factory=list)
    projects: List[ProjectRecord] = field(default_factory=list)
    certifications: List[CertificationRecord] = field(default_factory=list)
    sections: List[SectionInfo] = field(default_factory=list)
    raw_text: str = ""
    cleaned_text: str = ""

    @property
    def work_experience(self) -> List[WorkExperience]:
        return self.experience


class StructuredResumeParser:

    def __init__(self, normalizer: Optional[SkillTaxonomyNormalizer] = None):
        self.normalizer = normalizer or SkillTaxonomyNormalizer()

    def parse_resume(self, text: str) -> StructuredResume:
        return self.parse(text)

    def parse(self, text: str) -> StructuredResume:
        cleaned = TextCleaner.clean(text)
        sections = ResumeSectionDetector.detect_sections(cleaned)
        section_map = {s.canonical_name: s.content for s in sections}

        header_text = section_map.get("HEADER", "")
        search_contact_text = header_text if header_text else cleaned[:1000]
        contact = self._extract_contact_info(search_contact_text)

        skills = []
        if "SKILLS" in section_map:
            skills.extend(self.normalizer.extract_and_normalize_skills(section_map["SKILLS"], source_section="SKILLS"))
        if "EXPERIENCE" in section_map:
            exp_skills = self.normalizer.extract_and_normalize_skills(section_map["EXPERIENCE"], source_section="EXPERIENCE")
            existing_names = {s.normalized_skill_name for s in skills}
            for es in exp_skills:
                if es.normalized_skill_name not in existing_names:
                    skills.append(es)
                    existing_names.add(es.normalized_skill_name)
        if "PROJECTS" in section_map:
            proj_skills = self.normalizer.extract_and_normalize_skills(section_map["PROJECTS"], source_section="PROJECTS")
            existing_names = {s.normalized_skill_name for s in skills}
            for ps in proj_skills:
                if ps.normalized_skill_name not in existing_names:
                    skills.append(ps)
                    existing_names.add(ps.normalized_skill_name)

        experience = []
        if "EXPERIENCE" in section_map:
            experience = self._extract_experience(section_map["EXPERIENCE"])

        education = []
        if "EDUCATION" in section_map:
            education = self._extract_education(section_map["EDUCATION"])

        projects = []
        if "PROJECTS" in section_map:
            projects = self._extract_projects(section_map["PROJECTS"])

        certifications = []
        if "CERTIFICATIONS" in section_map:
            certifications = self._extract_certifications(section_map["CERTIFICATIONS"])

        return StructuredResume(
            contact=contact,
            skills=skills,
            experience=experience,
            education=education,
            projects=projects,
            certifications=certifications,
            sections=sections,
            raw_text=text,
            cleaned_text=cleaned,
        )

    def _extract_contact_info(self, text: str) -> ContactInfo:
        email_match = re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b", text)
        email = email_match.group(0) if email_match else None

        phone_match = re.search(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", text)
        phone = phone_match.group(0) if phone_match else None

        name = None
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        for line in lines[:3]:
            if "@" in line or "http" in line.lower() or "resume" in line.lower() or "curriculum" in line.lower():
                continue
            if re.search(r"\d", line):
                continue
            words = line.split()
            if 2 <= len(words) <= 4 and len(line) <= 35:
                name = line
                break

        location = None
        loc_match = re.search(r"\b([A-Z][a-zA-Z\s]{2,18}),\s*([A-Z]{2}|[A-Z][a-zA-Z]{2,15})\b", text)
        if loc_match:
            location = loc_match.group(0).strip()
        elif re.search(r"\b(remote|hybrid|relocate)\b", text, re.IGNORECASE):
            r_match = re.search(r"\b(remote|hybrid)\b", text, re.IGNORECASE)
            if r_match:
                location = r_match.group(0).title()

        return ContactInfo(name=name, email=email, phone=phone, location=location)

    def _extract_experience(self, exp_text: str) -> List[WorkExperience]:
        records: List[WorkExperience] = []
        date_pattern = r"((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?|\d{1,2}/\d{2,4}|\d{4})\s*(?:-|–|to)\s*(?:Present|Current|\d{1,2}/\d{2,4}|\d{4}))"

        blocks = re.split(r"\n\s*\n", exp_text)
        for block in blocks:
            lines = [l.strip() for l in block.split("\n") if l.strip()]
            if not lines:
                continue

            date_str = None
            date_match = re.search(date_pattern, block, re.IGNORECASE)
            if date_match:
                date_str = date_match.group(0)

            first_line = lines[0]
            title = re.sub(date_pattern, "", first_line, flags=re.IGNORECASE).strip(" |,-")
            if not title:
                title = "Software Engineer" if "engineer" in block.lower() else "Professional Role"

            employer = None
            if len(lines) > 1 and not re.search(date_pattern, lines[1]):
                employer = lines[1]

            desc = "\n".join(lines[1:])

            records.append(
                WorkExperience(
                    job_title=title,
                    employer=employer,
                    dates=date_str,
                    extracted_description=desc,
                    evidence_text=block.strip(),
                )
            )

        return records

    def _extract_education(self, edu_text: str) -> List[EducationRecord]:
        records: List[EducationRecord] = []
        degree_patterns = [
            r"\b(Ph\.?D\.?|Doctorate|Doctor of Philosophy)\b",
            r"\b(Master'?s|M\.S\.|M\.Tech|M\.A\.|MBA)\b",
            r"\b(Bachelor'?s|B\.S\.|B\.Tech|B\.E\.|B\.A\.|Degree)\b",
            r"\b(Diploma|Associate'?s)\b",
        ]

        blocks = re.split(r"\n\s*\n", edu_text)
        for block in blocks:
            lines = [l.strip() for l in block.split("\n") if l.strip()]
            if not lines:
                continue

            detected_deg = "Degree"
            for pat in degree_patterns:
                match = re.search(pat, block, re.IGNORECASE)
                if match:
                    detected_deg = match.group(0)
                    break

            institution = None
            for line in lines:
                if any(k in line.lower() for k in ["university", "college", "institute", "school", "academy"]):
                    institution = line
                    break

            date_match = re.search(r"\b(19\d{2}|20\d{2})\b(?:\s*-\s*\b(19\d{2}|20\d{2}|Present)\b)?", block)
            date_str = date_match.group(0) if date_match else None

            records.append(
                EducationRecord(
                    qualification=lines[0] if lines else detected_deg,
                    institution=institution,
                    dates=date_str,
                    evidence_text=block.strip(),
                )
            )

        return records

    def _extract_projects(self, proj_text: str) -> List[ProjectRecord]:
        records: List[ProjectRecord] = []
        blocks = re.split(r"\n\s*\n", proj_text)
        for block in blocks:
            lines = [l.strip() for l in block.split("\n") if l.strip()]
            if lines:
                records.append(
                    ProjectRecord(
                        title=lines[0],
                        description="\n".join(lines[1:]),
                        evidence_text=block.strip(),
                    )
                )
        return records

    def _extract_certifications(self, cert_text: str) -> List[CertificationRecord]:
        records: List[CertificationRecord] = []
        for line in cert_text.split("\n"):
            clean = line.strip(" •-*")
            if clean and len(clean) > 4:
                records.append(
                    CertificationRecord(
                        name=clean,
                        evidence_text=clean,
                    )
                )
        return records
