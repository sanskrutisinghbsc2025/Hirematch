
import re
from typing import Optional, Tuple


class NegationDetector:

    PREFIX_NEGATION_PATTERNS = [
        r"\b(?:no|zero)\s+(?:hands-on\s+|prior\s+|practical\s+|direct\s+)?(?:experience|knowledge|exposure|background)\s+(?:with|in|using|of)\b",
        r"\b(?:have|has|had)\s+not\s+(?:yet\s+)?(?:worked|used|developed|built|managed|implemented|administered)\s+(?:with|in|on)?\b",
        r"\b(?:haven't|hasn't|hadn't)\s+(?:yet\s+)?(?:worked|used|developed|built|managed|implemented)\s+(?:with|in|on)?\b",
        r"\b(?:did|does|do)\s+not\s+(?:have|possess|use)\b",
        r"\b(?:didn't|doesn't|don't)\s+(?:have|possess|use)\b",
        r"\b(?:not|never)\s+(?:proficient|familiar|skilled|certified|experienced)\s+(?:in|with)\b",
        r"\b(?:never|rarely)\s+(?:used|worked\s+with|touched|encountered)\b",
        r"\b(?:lack|lacking)\s+(?:of\s+)?(?:experience|knowledge|depth)\s+(?:in|with)?\b",
        r"\b(?:minimal|little|limited)\s+(?:or\s+no\s+)?(?:exposure|experience)\s+(?:to|with|in)\b",
        r"\bwithout\s+(?:prior\s+|any\s+)?(?:knowledge|experience|use)\s+(?:of|in|with)\b",
        r"\bneither\b",
    ]

    POSTFIX_NEGATION_PATTERNS = [
        r"\b(?:is|was|are|were)\s+not\s+(?:used|required|supported|utilized|familiar)\b",
        r"\b(?:experience\s+)?(?:is\s+)?(?:lacking|minimal|none|absent)\b",
    ]

    def __init__(self):
        self.compiled_prefix = [re.compile(pat, re.IGNORECASE) for pat in self.PREFIX_NEGATION_PATTERNS]
        self.compiled_postfix = [re.compile(pat, re.IGNORECASE) for pat in self.POSTFIX_NEGATION_PATTERNS]

    def is_negated(self, sentence: str, target_term: str) -> Tuple[bool, Optional[str]]:
        if not sentence or not target_term:
            return False, None

        escaped_term = re.escape(target_term.strip().lower())
        norm_sentence = sentence.lower()

        term_match = re.search(r"(?<!\w)" + escaped_term + r"(?!\w)", norm_sentence)
        if not term_match:
            term_match = re.search(escaped_term, norm_sentence)
            if not term_match:
                return False, None

        start_idx = term_match.start()
        end_idx = term_match.end()

        prefix_window = norm_sentence[max(0, start_idx - 80) : start_idx]
        for pat in self.compiled_prefix:
            m = pat.search(prefix_window)
            if m:
                between = prefix_window[m.end() :]
                if not any(punct in between for punct in [".", ";", "but", "however"]):
                    return True, m.group(0)

        postfix_window = norm_sentence[end_idx : min(len(norm_sentence), end_idx + 60)]
        for pat in self.compiled_postfix:
            m = pat.search(postfix_window)
            if m:
                between = postfix_window[: m.start()]
                if not any(punct in between for punct in [".", ";", "but", "however"]):
                    return True, m.group(0)

        return False, None
