
from dataclasses import dataclass, field
import re
from typing import Dict, List, Optional, Tuple


@dataclass
class SectionInfo:
    canonical_name: str
    display_title: str
    content: str
    raw_heading: str
    confidence: float = 1.0


class ResumeSectionDetector:

    SECTION_PATTERNS: Dict[str, List[str]] = {
        "SUMMARY": [
            r"^(?:professional\s+)?summary$",
            r"^(?:career\s+)?profile$",
            r"^executive\s+summary$",
            r"^(?:career\s+)?objective$",
            r"^about(?:\s+me)?$",
        ],
        "SKILLS": [
            r"^(?:technical\s+|core\s+|key\s+)?skills(?:\s+(&|and)\s+abilities)?$",
            r"^(?:technical\s+|core\s+)?competencies$",
            r"^technologies(?:\s+(&|and)\s+tools)?$",
            r"^(?:tools\s+(&|and)\s+technologies)$",
            r"^areas\s+of\s+expertise$",
            r"^tech\s+stack$",
        ],
        "EXPERIENCE": [
            r"^(?:work|professional|employment)\s+experience$",
            r"^(?:career|employment|work)\s+history$",
            r"^experience$",
            r"^work\s+background$",
            r"^relevant\s+experience$",
        ],
        "EDUCATION": [
            r"^(?:academic\s+|educational\s+)?background$",
            r"^education(?:\s+(&|and)\s+training)?$",
            r"^qualifications$",
            r"^academic\s+history$",
            r"^degrees(?:\s+(&|and)\s+diplomas)?$",
        ],
        "PROJECTS": [
            r"^(?:key\s+|recent\s+|technical\s+|academic\s+|personal\s+)?projects$",
            r"^project\s+experience$",
            r"^portfolio(?:\s+projects)?$",
        ],
        "CERTIFICATIONS": [
            r"^(?:professional\s+)?certifications?(?:\s+(&|and)\s+licenses?)?$",
            r"^(?:licenses?\s+(&|and)\s+)?certifications?$",
            r"^training(?:\s+(&|and)\s+certifications?)?$",
            r"^courses?(?:\s+(&|and)\s+certificates?)?$",
        ],
        "PUBLICATIONS": [
            r"^publications?(?:\s+(&|and)\s+research)?$",
            r"^research\s+papers?$",
            r"^patents?$",
        ],
        "LANGUAGES": [
            r"^languages?(?:\s+proficiency)?$",
            r"^language\s+skills?$",
        ],
    }

    @classmethod
    def detect_sections(cls, text: str) -> List[SectionInfo]:
        if not text or not text.strip():
            return []

        lines = text.split("\n")
        heading_matches: List[Tuple[int, str, str]] = []

        for line_idx, line in enumerate(lines):
            clean_line = line.strip()
            if not clean_line or len(clean_line) > 50:
                continue

            norm_heading = re.sub(r"^[\d\.\-\•\*\#\:\s]+", "", clean_line)
            norm_heading = re.sub(r"[\:\-\s]+$", "", norm_heading).strip().lower()

            if not norm_heading:
                continue

            matched_canonical = None
            for canonical, patterns in cls.SECTION_PATTERNS.items():
                for pat in patterns:
                    if re.match(pat, norm_heading, re.IGNORECASE):
                        matched_canonical = canonical
                        break
                if matched_canonical:
                    break

            if matched_canonical:
                heading_matches.append((line_idx, matched_canonical, clean_line))

        if not heading_matches:
            return [
                SectionInfo(
                    canonical_name="UNCLASSIFIED",
                    display_title="General Content",
                    content=text.strip(),
                    raw_heading="",
                    confidence=0.5,
                )
            ]

        sections: List[SectionInfo] = []

        first_h_idx = heading_matches[0][0]
        if first_h_idx > 0:
            header_text = "\n".join(lines[:first_h_idx]).strip()
            if header_text:
                sections.append(
                    SectionInfo(
                        canonical_name="HEADER",
                        display_title="Header & Contact",
                        content=header_text,
                        raw_heading="Header",
                        confidence=0.9,
                    )
                )

        for i in range(len(heading_matches)):
            start_line, canonical, raw_h = heading_matches[i]
            end_line = heading_matches[i + 1][0] if i + 1 < len(heading_matches) else len(lines)

            content_lines = lines[start_line + 1 : end_line]
            content_text = "\n".join(content_lines).strip()

            sections.append(
                SectionInfo(
                    canonical_name=canonical,
                    display_title=canonical.title().replace("_", " "),
                    content=content_text,
                    raw_heading=raw_h,
                    confidence=1.0,
                )
            )

        return sections

    @classmethod
    def get_section(cls, sections: List[SectionInfo], canonical_name: str) -> Optional[SectionInfo]:
        for s in sections:
            if s.canonical_name.upper() == canonical_name.upper():
                return s
        return None


SectionDetector = ResumeSectionDetector
