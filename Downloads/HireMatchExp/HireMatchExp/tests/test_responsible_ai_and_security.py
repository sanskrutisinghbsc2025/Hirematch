
import io
import logging
from pathlib import Path
import tempfile
import unittest

from core.evaluation.criteria_validator import ResponsibleAICriteriaValidator
from core.models.enums import CriterionType, ShortlistReviewStatus
from core.models.evaluation import EvaluationCriterion
from core.utils.errors import HireMatchError
from core.utils.logger import setup_logger
from core.utils.sanitizer import mask_pii, sanitize_filename, sanitize_text_for_display


class TestResponsibleAIAndSecuritySafeguards(unittest.TestCase):

    def setUp(self):
        self.validator = ResponsibleAICriteriaValidator()

    def test_prohibited_protected_traits_rejected(self):
        prohibited_samples = [
            "Candidate must be under 35 years old",
            "Prefer female candidates for diversity quotas",
            "Christian or church-affiliated background preferred",
            "Must be able-bodied with no chronic disabilities",
            "Native US citizen with no foreign accent",
            "Married candidates with stable family life preferred",
        ]

        for phrase in prohibited_samples:
            crit = EvaluationCriterion(
                id="crit-bias",
                criterion_name=phrase,
                description=phrase,
                criterion_type=CriterionType.REQUIRED,
            )
            is_valid, violations = self.validator.validate_criterion(crit)
            self.assertFalse(is_valid, f"Validator failed to reject prohibited trait: '{phrase}'")
            reason_str = " ".join(violations).lower()
            self.assertTrue(
                any(keyword in reason_str for keyword in ["prohibited", "demographic", "protected", "non-job-related", "age and birth", "religion", "disability"]),
                f"Unexpected rejection reason for '{phrase}': {violations}",
            )

    def test_subjective_personality_and_vibe_traits_rejected(self):
        subjective_samples = [
            "True 10x rockstar ninja developer",
            "Good team vibes and cheerful attitude",
            "Strong cultural fit and fun personality",
            "High energy, naturally aggressive salesperson",
        ]

        for phrase in subjective_samples:
            crit = EvaluationCriterion(
                id="crit-subj",
                criterion_name=phrase,
                description=phrase,
                criterion_type=CriterionType.REQUIRED,
            )
            is_valid, violations = self.validator.validate_criterion(crit)
            self.assertFalse(is_valid, f"Validator failed to reject subjective trait: '{phrase}'")
            reason_str = " ".join(violations).lower()
            self.assertIn("subjective", reason_str)

    def test_valid_technical_and_job_related_criteria_accepted(self):
        valid_samples = [
            "Proficient in Python and FastAPI",
            "Bachelor's degree in Computer Science or equivalent",
            "At least 4 years experience in PostgreSQL database tuning",
            "AWS Certified Solutions Architect certification",
            "Experience with Docker containerization and Kubernetes orchestration",
        ]

        for phrase in valid_samples:
            crit = EvaluationCriterion(
                id="crit-ok",
                criterion_name=phrase,
                description=phrase,
                criterion_type=CriterionType.REQUIRED,
            )
            is_valid, reason = self.validator.validate_criterion(crit)
            self.assertTrue(is_valid, f"Validator incorrectly rejected valid criterion: '{phrase}' (Reason: {reason})")

    def test_no_automated_rejection_authority(self):
        from core.models.scoring_models import ShortlistRecord

        record = ShortlistRecord(
            candidate_id="cand-1",
            session_id="sess-1",
            review_status=ShortlistReviewStatus.NEEDS_REVIEW,
        )
        self.assertEqual(record.review_status, ShortlistReviewStatus.NEEDS_REVIEW)
        self.assertNotEqual(record.review_status, ShortlistReviewStatus.NOT_SHORTLISTED)

    def test_path_traversal_filename_sanitization(self):
        traversal_attempts = [
            ("../../etc/passwd.pdf", "passwd.pdf"),
            ("..\\..\\Windows\\System32\\cmd.exe.pdf", "cmd.exe.pdf"),
            ("/var/www/html/exploit.docx", "exploit.docx"),
            ("../../../../../../../boot.ini.pdf", "boot.ini.pdf"),
            ("normal_resume.pdf\x00.exe", "normal_resume.pdf_.pdf"),
            ("   leading_spaces.pdf   ", "leading_spaces.pdf"),
        ]

        for unsafe, expected in traversal_attempts:
            safe = sanitize_filename(unsafe)
            self.assertNotIn("/", safe)
            self.assertNotIn("\\", safe)
            self.assertNotIn("..", safe)
            self.assertNotIn("\x00", safe)
            self.assertTrue(safe.endswith(".pdf") or safe.endswith(".docx"))

    def test_safe_error_messages_contain_no_internal_paths(self):
        internal_msg = "Database connection failed at C:\\Users\\Administrator\\data\\production.db"
        safe_user_msg = "A storage operation could not be completed. Please try again or contact support."

        err = HireMatchError(message=internal_msg, user_message=safe_user_msg)
        self.assertEqual(err.user_message, safe_user_msg)
        self.assertNotIn("C:\\", err.user_message)
        self.assertNotIn("production.db", err.user_message)

    def test_log_hygiene_and_pii_masking(self):
        log_stream = io.StringIO()
        test_logger = logging.getLogger("test_security_logger")
        test_logger.setLevel(logging.INFO)
        handler = logging.StreamHandler(log_stream)
        handler.setFormatter(logging.Formatter("%(message)s"))
        test_logger.addHandler(handler)

        raw_snippet = "Contact candidate at john.doe@example.com or call (555) 123-4567 regarding the role."
        masked_snippet = mask_pii(raw_snippet)

        test_logger.info(f"Processed candidate evidence: {masked_snippet}")
        log_output = log_stream.getvalue()

        self.assertNotIn("john.doe@example.com", log_output)
        self.assertNotIn("(555) 123-4567", log_output)
        self.assertIn("[PROTECTED EMAIL]", log_output)
        self.assertIn("[PROTECTED PHONE]", log_output)


if __name__ == "__main__":
    unittest.main()
