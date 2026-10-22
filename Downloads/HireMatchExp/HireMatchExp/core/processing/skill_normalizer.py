
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from config import settings
from core.models.skills import ExtractedSkill
from core.utils.logger import logger


@dataclass
class NormalizedSkillResult:
    original_phrase: str
    canonical_name: str
    category: str
    evidence_text: str
    source_location: str = "general"
    confidence: float = 1.0


class SkillTaxonomyNormalizer:

    _TAXONOMY_CACHE: Dict[str, Tuple[Dict[str, str], Dict[str, str], List[Tuple[str, str, str, Any]]]] = {}

    def __init__(self, taxonomy_path: Optional[Path] = None):
        self.taxonomy_path = taxonomy_path or (settings.base_dir / "config" / "skills_db.json")
        self.alias_to_canonical: Dict[str, str] = {}
        self.canonical_to_category: Dict[str, str] = {}
        self.all_aliases_sorted: List[Tuple[str, str, str, Any]] = []
        self._load_taxonomy()

    def _load_taxonomy(self) -> None:
        key = str(self.taxonomy_path.resolve()) if self.taxonomy_path.exists() else str(self.taxonomy_path)
        if key in SkillTaxonomyNormalizer._TAXONOMY_CACHE:
            a2c, c2c, aliases = SkillTaxonomyNormalizer._TAXONOMY_CACHE[key]
            self.alias_to_canonical = a2c
            self.canonical_to_category = c2c
            self.all_aliases_sorted = aliases
            return

        if not self.taxonomy_path.exists():
            logger.warning(f"Taxonomy file not found at {self.taxonomy_path}. Using minimal fallback.")
            return

        try:
            with open(self.taxonomy_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            categories = data.get("categories", {})
            raw_aliases: List[Tuple[str, str, str]] = []
            for cat_name, skills_dict in categories.items():
                for canonical, aliases in skills_dict.items():
                    clean_canonical = canonical.strip()
                    cat_key = clean_canonical.lower()
                    self.canonical_to_category[cat_key] = cat_name
                    self.alias_to_canonical[cat_key] = clean_canonical

                    for alias in aliases:
                        norm_alias = alias.strip().lower()
                        self.alias_to_canonical[norm_alias] = clean_canonical
                        raw_aliases.append((norm_alias, clean_canonical, cat_name))

            raw_aliases.sort(key=lambda x: len(x[0]), reverse=True)

            for norm_alias, clean_canonical, cat_name in raw_aliases:
                escaped_alias = re.escape(norm_alias)
                if re.search(r"\w$", norm_alias):
                    pattern_str = r"(?<!\w)" + escaped_alias + r"(?!\w)"
                else:
                    pattern_str = r"(?<!\w)" + escaped_alias
                compiled = re.compile(pattern_str, re.IGNORECASE)
                self.all_aliases_sorted.append((norm_alias, clean_canonical, cat_name, compiled))

            SkillTaxonomyNormalizer._TAXONOMY_CACHE[key] = (
                self.alias_to_canonical,
                self.canonical_to_category,
                self.all_aliases_sorted,
            )
            logger.info(f"Loaded {len(self.all_aliases_sorted)} skill alias mappings from {self.taxonomy_path.name}")

        except Exception as e:
            logger.error(f"Failed to load skill taxonomy: {e}")

    def normalize(self, raw_skill: str) -> Tuple[str, str]:
        clean_key = raw_skill.strip().lower()
        canonical = self.alias_to_canonical.get(clean_key, raw_skill.strip())
        category = self.canonical_to_category.get(canonical.lower(), "General Technical")
        return canonical, category

    def normalize_skill(self, raw_skill: str) -> Tuple[str, str]:
        return self.normalize(raw_skill)

    def extract_and_normalize(self, text: str, source_section: str = "general") -> List[ExtractedSkill]:
        return self.extract_and_normalize_skills(text, source_section)

    def extract_and_normalize_skills(
        self,
        text: str,
        source_section: str = "general",
    ) -> List[ExtractedSkill]:
        if not text or not text.strip():
            return []

        extracted: List[ExtractedSkill] = []
        found_canonicals: Set[str] = set()

        sentences = re.split(r"(?<=[.!?\n])\s+", text)
        text_lower = text.lower()

        for alias, canonical, category, compiled_pattern in self.all_aliases_sorted:
            if canonical in found_canonicals:
                continue

            # Fast C-level substring check: avoid regex if alias is not even in text
            if alias not in text_lower:
                continue

            match = compiled_pattern.search(text)
            if match:
                found_canonicals.add(canonical)
                verbatim_match = match.group(0)

                evidence = verbatim_match
                for sent in sentences:
                    if verbatim_match in sent or alias in sent.lower():
                        evidence = sent.strip()
                        break

                extracted.append(
                    ExtractedSkill(
                        skill_name=verbatim_match,
                        normalized_skill_name=canonical,
                        evidence_text=evidence,
                        source_location=source_section,
                        extraction_method="taxonomy_regex",
                        confidence=1.0,
                    )
                )

        return extracted
