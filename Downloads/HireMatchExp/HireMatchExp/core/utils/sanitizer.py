
from pathlib import Path
import re
import unicodedata
from typing import List, Optional


_UNSAFE_FILENAME_CHARS = re.compile(r'[\x00-\x1f\x7f/\\:\*\?"<>\|\r\n\t]')
_ANSI_ESCAPE_PATTERN = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

_ADVERSARIAL_INJECTION_PATTERNS = [
    (r"\bignore\s+(all\s+)?(previous|prior|above)\s+(instructions|requirements|rules|criteria)\b", "INSTRUCTION_OVERRIDE"),
    (r"\bsystem\s+(prompt|instruction|message)s?\s*:", "SYSTEM_PROMPT_EMULATION"),
    (r"\bdisregard\s+(the\s+)?(requirements|criteria|job\s+description)\b", "CRITERIA_DISREGARD"),
    (r"\b(give|award)\s+(this\s+)?(candidate|resume)\s+(a\s+)?(score\s+of\s+)?(100|full|perfect|maximum|\d+)", "SCORE_INJECTION"),
    (r"\byou\s+are\s+now\s+(in\s+)?(developer|admin|evaluator)\s+mode\b", "MODE_SWITCH"),
    (r"\bdo\s+not\s+evaluate\s+this\s+candidate\b", "EVALUATION_BYPASS"),
]


def sanitize_filename(filename: str, fallback_ext: str = ".pdf") -> str:
    if not filename or not isinstance(filename, str):
        return f"unnamed_document{fallback_ext}"

    norm_name = unicodedata.normalize("NFKC", filename.strip())
    base_name = norm_name.replace("\\", "/").split("/")[-1]

    p = Path(base_name)
    suffix = p.suffix.lower()
    stem = p.stem

    allowed_exts = {".pdf", ".docx"}
    final_ext = suffix if suffix in allowed_exts else fallback_ext

    clean_stem = _UNSAFE_FILENAME_CHARS.sub("_", stem)
    clean_stem = clean_stem.lstrip(".-").strip()

    clean_stem = re.sub(r"_+", "_", clean_stem)

    if not clean_stem:
        clean_stem = "resume_document"

    clean_stem = clean_stem[:80]

    return f"{clean_stem}{final_ext}"


def sanitize_text_for_display(text: str, max_chars: Optional[int] = None) -> str:
    if not text:
        return ""

    clean = _ANSI_ESCAPE_PATTERN.sub("", text)

    clean = "".join(ch for ch in clean if ch in ("\n", "\t") or (ord(ch) >= 32 and ord(ch) != 127))

    if max_chars is not None and len(clean) > max_chars:
        clean = clean[:max_chars] + "..."

    return clean


def detect_adversarial_patterns(text: str) -> List[str]:
    if not text:
        return []

    detected = []
    text_lower = text.lower()
    for pattern, code in _ADVERSARIAL_INJECTION_PATTERNS:
        if re.search(pattern, text_lower):
            detected.append(code)

    return list(dict.fromkeys(detected))


def mask_pii(text: str) -> str:
    if not text:
        return ""

    email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
    masked = re.sub(email_pattern, "[PROTECTED EMAIL]", text)

    phone_pattern = r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
    masked = re.sub(phone_pattern, "[PROTECTED PHONE]", masked)

    return masked
