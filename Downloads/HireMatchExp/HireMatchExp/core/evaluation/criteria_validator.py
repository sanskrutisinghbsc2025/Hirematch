
from enum import Enum
import re
from typing import Any, List, NamedTuple, Tuple, Union

from core.models.evaluation import EvaluationCriterion


class ValidationResult(NamedTuple):
    is_valid: bool
    violations: List[str]


class CriterionValidationError(ValueError):

    def __init__(self, message: str, violations: List[str]):
        super().__init__(message)
        self.violations = violations


class ProhibitedAttributeCategory(str, Enum):
    DEMOGRAPHICS = "DEMOGRAPHICS"
    GENDER_AND_SEX = "GENDER_AND_SEX"
    AGE_AND_BIRTH = "AGE_AND_BIRTH"
    RELIGION_AND_BELIEF = "RELIGION_AND_BELIEF"
    DISABILITY_AND_HEALTH = "DISABILITY_AND_HEALTH"
    MARITAL_AND_FAMILY = "MARITAL_AND_FAMILY"
    PERSONALITY_AND_SUBJECTIVE = "PERSONALITY_AND_SUBJECTIVE"
    PROTECTED_BIOGRAPHICAL = "PROTECTED_BIOGRAPHICAL"


PROHIBITED_PATTERNS = {
    ProhibitedAttributeCategory.DEMOGRAPHICS: [
        r"\brace\b",
        r"\bracial\b",
        r"\bethnicity\b",
        r"\bethnic\b",
        r"\bnationality\b",
        r"\bcitizen(ship)?\b",
        r"\baccent\b",
        r"\bcountry of origin\b",
        r"\bnative language\b",
        r"\bmother tongue\b",
    ],
    ProhibitedAttributeCategory.GENDER_AND_SEX: [
        r"\bgender\b",
        r"\bsex\b",
        r"\bsexual orientation\b",
        r"\bmale\b",
        r"\bfemale\b",
        r"\bwoman\b",
        r"\bman\b",
        r"\bpregnancy\b",
        r"\bmaternity\b",
    ],
    ProhibitedAttributeCategory.AGE_AND_BIRTH: [
        r"\bage\b",
        r"\byears?\s+old\b",
        r"\bbirthday\b",
        r"\bbirth year\b",
        r"\bdate of birth\b",
        r"\byoung\b",
        r"\byouth\b",
        r"\belderly\b",
        r"\bolder worker\b",
        r"\bretirement\b",
    ],
    ProhibitedAttributeCategory.RELIGION_AND_BELIEF: [
        r"\breligion\b",
        r"\breligious\b",
        r"\bcreed\b",
        r"\bfaith\b",
        r"\bchurch\b",
        r"\bmosque\b",
        r"\bsynagogue\b",
        r"\bspiritual\b",
        r"\bchristian\b",
        r"\bmuslim\b",
        r"\bjewish\b",
        r"\bhindu\b",
        r"\bbuddhist\b",
    ],
    ProhibitedAttributeCategory.DISABILITY_AND_HEALTH: [
        r"\bdisabilit(y|ies)\b",
        r"\bhandicap\b",
        r"\bable-bodied\b",
        r"\bmedical history\b",
        r"\billness\b",
        r"\bchronic condition\b",
        r"\bhealth status\b",
    ],
    ProhibitedAttributeCategory.MARITAL_AND_FAMILY: [
        r"\bmarital status\b",
        r"\bmarried\b",
        r"\bsingle\b",
        r"\bdivorced\b",
        r"\bchildren\b",
        r"\bkids\b",
        r"\bfamily status\b",
        r"\bparental status\b",
    ],
    ProhibitedAttributeCategory.PERSONALITY_AND_SUBJECTIVE: [
        r"\bpersonality\b",
        r"\bcultural fit\b",
        r"\bvibes?\b",
        r"\benergetic\b",
        r"\benthusiastic\b",
        r"\baggressive\b",
        r"\bpleasant\b",
        r"\blikable\b",
        r"\bextrovert\b",
        r"\bintrovert\b",
        r"\bcharismatic\b",
        r"\brockstar\b",
        r"\bninja\b",
        r"\bguru\b",
        r"\b10x\b",
    ],
    ProhibitedAttributeCategory.PROTECTED_BIOGRAPHICAL: [
        r"\bphoto(graph)?\b",
        r"\bheadshot\b",
        r"\bpicture\b",
        r"\bsalary history\b",
        r"\bcurrent salary\b",
        r"\bzip code\b",
        r"\bhome address\b",
    ],
}


class ResponsibleAICriteriaValidator:

    @classmethod
    def validate_criterion(cls, criterion: Union[EvaluationCriterion, str]) -> ValidationResult:
        violations: List[str] = []

        if isinstance(criterion, str):
            c_name = criterion.strip()
            c_desc = ""
            c_weight = 0.5
        else:
            c_name = criterion.criterion_name.strip() if criterion.criterion_name else ""
            c_desc = criterion.description or ""
            c_weight = criterion.weight

        if not c_name:
            violations.append("Criterion name cannot be empty.")

        if not (0.0 <= c_weight <= 1.0):
            violations.append(f"Criterion weight must be between 0.0 and 1.0, got {c_weight}.")

        search_text = f"{c_name} {c_desc}".lower()

        for category, patterns in PROHIBITED_PATTERNS.items():
            for pat in patterns:
                match = re.search(pat, search_text, re.IGNORECASE)
                if match:
                    term = match.group(0)
                    violations.append(
                        f"Prohibited {category.value.replace('_', ' ').title()} attribute detected: '{term}'. "
                        "HireMatch strictly forbids demographic, personal, or subjective personality criteria."
                    )

        return ValidationResult(len(violations) == 0, violations)

    @classmethod
    def assert_valid_criterion(cls, criterion: Union[EvaluationCriterion, str]) -> None:
        is_valid, violations = cls.validate_criterion(criterion)
        if not is_valid:
            name = criterion if isinstance(criterion, str) else criterion.criterion_name
            msg = f"Criterion '{name}' failed responsible AI validation:\n- " + "\n- ".join(violations)
            raise CriterionValidationError(msg, violations)


CriteriaValidator = ResponsibleAICriteriaValidator
