
from dataclasses import dataclass
import re
from typing import Any, Dict, List, Optional


@dataclass
class DocumentChunk:

    text: str
    source_section: str
    chunk_index: int
    char_start: int
    char_end: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "source_section": self.source_section,
            "chunk_index": self.chunk_index,
            "char_start": self.char_start,
            "char_end": self.char_end,
        }


class SectionAwareTextChunker:

    KNOWN_SECTIONS = [
        "experience",
        "work experience",
        "employment history",
        "professional experience",
        "education",
        "skills",
        "technical skills",
        "competencies",
        "summary",
        "professional summary",
        "profile",
        "projects",
        "certifications",
        "awards",
        "publications",
    ]

    SECTION_HEADER_REGEX = re.compile(
        r"^(?:\s*[\#\*\-]*\s*)([A-Z][A-Za-z\s]{2,30})(?:\s*[\:\-\*]*\s*)$",
        re.MULTILINE,
    )

    def __init__(
        self,
        min_chunk_chars: int = 60,
        target_chunk_chars: int = 250,
        max_chunk_chars: int = 500,
        overlap_sentences: int = 1,
    ):
        self.min_chunk_chars = min_chunk_chars
        self.target_chunk_chars = target_chunk_chars
        self.max_chunk_chars = max_chunk_chars
        self.overlap_sentences = overlap_sentences

    def chunk_candidate(
        self,
        text: str,
        structured_data: Optional[Dict[str, Any]] = None,
    ) -> List[DocumentChunk]:
        has_text = bool(text and text.strip())
        has_struct = bool(structured_data and structured_data.get("sections"))
        if not has_text and not has_struct:
            return []

        chunks: List[DocumentChunk] = []

        if structured_data and "sections" in structured_data:
            sections = structured_data["sections"]
            chunk_idx = 0
            if isinstance(sections, dict):
                for sec_name, sec_content in sections.items():
                    if isinstance(sec_content, str) and sec_content.strip():
                        sec_chunks = self._chunk_section_text(sec_content.strip(), sec_name, chunk_idx)
                        chunks.extend(sec_chunks)
                        chunk_idx += len(sec_chunks)
            elif isinstance(sections, list):
                for sec_item in sections:
                    if isinstance(sec_item, dict):
                        sec_name = sec_item.get("canonical_name") or sec_item.get("display_title") or "general"
                        sec_content = sec_item.get("content", "")
                        if isinstance(sec_content, str) and sec_content.strip():
                            sec_chunks = self._chunk_section_text(sec_content.strip(), str(sec_name), chunk_idx)
                            chunks.extend(sec_chunks)
                            chunk_idx += len(sec_chunks)
            if chunks:
                return chunks

        if not has_text:
            return []

        if text.startswith("%PDF-") or "/Filter /DCTDecode" in text or "/Type /Catalog" in text:
            return []

        sections = self._split_by_sections(text)
        chunk_idx = 0
        for sec_name, sec_text, start_offset in sections:
            sec_chunks = self._chunk_section_text(
                sec_text, sec_name, chunk_idx, base_offset=start_offset
            )
            chunks.extend(sec_chunks)
            chunk_idx += len(sec_chunks)
            if chunk_idx >= 50:
                break

        if not chunks and text.strip():
            chunks.append(
                DocumentChunk(
                    text=text.strip()[: self.max_chunk_chars],
                    source_section="general",
                    chunk_index=0,
                    char_start=0,
                    char_end=min(len(text), self.max_chunk_chars),
                )
            )

        return chunks[:50]

    def _split_by_sections(self, text: str) -> List[tuple[str, str, int]]:
        lines = text.splitlines(keepends=True)
        sections = []
        current_section = "general"
        current_lines: List[str] = []
        current_start = 0
        running_offset = 0

        for line in lines:
            line_len = len(line)
            stripped = line.strip().lower()
            clean_hdr = re.sub(r"^[\#\*\-\s]+|[\:\*\-\s]+$", "", stripped)

            is_header = False
            for known in self.KNOWN_SECTIONS:
                if clean_hdr == known or clean_hdr.startswith(known + ":"):
                    is_header = True
                    break

            if is_header:
                if current_lines:
                    sec_text = "".join(current_lines).strip()
                    if sec_text:
                        sections.append((current_section, sec_text, current_start))
                current_section = clean_hdr.split(":")[0].strip()
                current_lines = []
                current_start = running_offset
            else:
                current_lines.append(line)

            running_offset += line_len

        if current_lines:
            sec_text = "".join(current_lines).strip()
            if sec_text:
                sections.append((current_section, sec_text, current_start))

        if not sections and text.strip():
            sections.append(("general", text.strip(), 0))

        return sections

    def _split_sentences(self, text: str) -> List[str]:
        raw_items = re.split(r"(?<=[.!?])\s+|\n{2,}|\n(?=[\-\*•\d+\.]\s+)", text)
        sentences = [item.strip() for item in raw_items if item and item.strip()]
        return sentences

    def _chunk_section_text(
        self,
        text: str,
        section_name: str,
        start_chunk_idx: int,
        base_offset: int = 0,
    ) -> List[DocumentChunk]:
        sentences = self._split_sentences(text)
        if not sentences:
            return []

        chunks: List[DocumentChunk] = []
        current_sentences: List[str] = []
        current_len = 0
        chunk_idx = start_chunk_idx

        for sent in sentences:
            sent_len = len(sent)
            if current_len + sent_len > self.target_chunk_chars and current_sentences:
                passage = " ".join(current_sentences)
                pos = text.find(current_sentences[0])
                char_start = base_offset + (pos if pos != -1 else 0)
                char_end = char_start + len(passage)

                chunks.append(
                    DocumentChunk(
                        text=passage,
                        source_section=section_name,
                        chunk_index=chunk_idx,
                        char_start=char_start,
                        char_end=char_end,
                    )
                )
                chunk_idx += 1

                if self.overlap_sentences > 0:
                    current_sentences = current_sentences[-self.overlap_sentences :]
                    current_len = sum(len(s) for s in current_sentences) + len(current_sentences)
                else:
                    current_sentences = []
                    current_len = 0

            current_sentences.append(sent)
            current_len += sent_len

        if current_sentences:
            passage = " ".join(current_sentences)
            pos = text.find(current_sentences[0])
            char_start = base_offset + (pos if pos != -1 else 0)
            char_end = char_start + len(passage)
            chunks.append(
                DocumentChunk(
                    text=passage,
                    source_section=section_name,
                    chunk_index=chunk_idx,
                    char_start=char_start,
                    char_end=char_end,
                )
            )

        return chunks
