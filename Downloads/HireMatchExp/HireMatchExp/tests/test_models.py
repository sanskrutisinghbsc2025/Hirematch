
import unittest

from core.models.candidate import Candidate
from core.models.education import EducationRecord
from core.models.enums import (
    CriterionType,
    FileType,
    MatchType,
    ModelType,
    ProcessingStatus,
    ScoreStatus,
    SessionStatus,
)
from core.models.evaluation import (
    CandidateScore,
    EvaluationCriterion,
    EvaluationEvidence,
)
from core.models.experience import WorkExperience
from core.models.job import Job
from core.models.model_config import ModelConfiguration
from core.models.session import ScreeningSession
from core.models.skills import ExtractedSkill


class TestModels(unittest.TestCase):

    def test_job_validation(self):
        job = Job(title="Senior Backend Engineer", original_description="Build distributed APIs in Python.")
        self.assertIsNotNone(job.id)
        self.assertEqual(job.title, "Senior Backend Engineer")

        with self.assertRaises(ValueError):
            Job(title="", original_description="Description")

        with self.assertRaises(ValueError):
            Job(title="Engineer", original_description="")

        data = job.to_dict()
        job_recon = Job.from_dict(data)
        self.assertEqual(job.id, job_recon.id)
        self.assertEqual(job.title, job_recon.title)

    def test_candidate_validation(self):
        valid_hash = "a" * 64
        cand = Candidate(
            original_filename="alice_resume.pdf",
            file_hash=valid_hash,
            file_type=FileType.PDF,
        )
        self.assertEqual(cand.processing_status, ProcessingStatus.PENDING)

        with self.assertRaises(ValueError):
            Candidate(original_filename="resume.pdf", file_hash="short", file_type=FileType.PDF)

        with self.assertRaises(ValueError):
            Candidate(original_filename="", file_hash=valid_hash, file_type=FileType.PDF)

        data = cand.to_dict()
        cand_recon = Candidate.from_dict(data)
        self.assertEqual(cand.id, cand_recon.id)
        self.assertEqual(cand.file_hash, cand_recon.file_hash)

    def test_extracted_skill_validation(self):
        skill = ExtractedSkill(
            skill_name="Python",
            normalized_skill_name="python",
            evidence_text="Developed Python microservices.",
            confidence=0.95,
        )
        self.assertEqual(skill.normalized_skill_name, "python")

        with self.assertRaises(ValueError):
            ExtractedSkill(skill_name="Go", normalized_skill_name="go", evidence_text="Go code", confidence=1.5)

    def test_work_experience_and_education(self):
        exp = WorkExperience(job_title="Software Architect", employer="Tech Corp", dates="2020 - Present")
        self.assertEqual(exp.job_title, "Software Architect")
        self.assertEqual(exp.employer, "Tech Corp")

        with self.assertRaises(ValueError):
            WorkExperience(job_title="")

        edu = EducationRecord(qualification="B.S. in Computer Science", institution="University of Technology")
        self.assertEqual(edu.qualification, "B.S. in Computer Science")

        with self.assertRaises(ValueError):
            EducationRecord(qualification="")

    def test_evaluation_criterion_weight_validation(self):
        crit = EvaluationCriterion(
            criterion_name="Python Proficiency",
            weight=0.35,
            criterion_type=CriterionType.REQUIRED,
        )
        self.assertEqual(crit.weight, 0.35)

        with self.assertRaises(ValueError):
            EvaluationCriterion(criterion_name="Invalid Weight", weight=1.2)

        with self.assertRaises(ValueError):
            EvaluationCriterion(criterion_name="Negative Weight", weight=-0.1)

    def test_candidate_score_validation(self):
        score = CandidateScore(
            candidate_id="cand-123",
            overall_score=87.5,
            criterion_scores={"tech_skills": 90.0, "experience": 85.0},
        )
        self.assertEqual(score.overall_score, 87.5)

        with self.assertRaises(ValueError):
            CandidateScore(candidate_id="cand-123", overall_score=105.0)

        with self.assertRaises(ValueError):
            CandidateScore(candidate_id="cand-123", overall_score=-5.0)

    def test_screening_session_validation(self):
        session = ScreeningSession(
            job_id="job-1",
            session_name="Batch 1",
            max_resume_count=100,
        )
        self.assertEqual(session.status, SessionStatus.CREATED)
        self.assertEqual(session.max_resume_count, 100)

        with self.assertRaises(ValueError):
            ScreeningSession(
                job_id="job-1",
                session_name="Batch 1",
                candidate_count=101,
                max_resume_count=100,
            )

        with self.assertRaises(ValueError):
            ScreeningSession(job_id="job-1", session_name="Batch 1", max_resume_count=0)


if __name__ == "__main__":
    unittest.main()
