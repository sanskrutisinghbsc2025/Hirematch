
import unittest
import uuid
from typing import Dict, Any

from config import AppConfig, settings
from core.evaluation.resume_quality_evaluator import ResumeQualityEvaluator
from core.models.quality_models import (
    QualityLabel,
    ResumeQualityAssessment,
    QualityCriterionKey,
)
from core.models.enums import ScoreCompleteness
from core.models.scoring_models import (
    CandidateScoringRecord,
    ScoringConfiguration,
    RankedCandidate,
)
from core.scoring.ranker import DeterministicCandidateRanker
from core.models.report_models import CandidateReportData, SessionSummaryReportData
from core.reporting.formatters.csv_formatter import CSVReportFormatter


class TestSyntheticResumeQuality(unittest.TestCase):

    def setUp(self):
        self.evaluator = ResumeQualityEvaluator()

    @staticmethod
    def get_well_structured_resume() -> Dict[str, Any]:
        text = (
            "ALEXANDER WONG\n"
            "alexander.wong@example.com | +1 (555) 234-5678 | San Francisco, CA | linkedin.com/in/alexwong\n\n"
            "PROFESSIONAL SUMMARY\n"
            "Results-driven Senior Software Engineer with over 8 years of experience designing scalable distributed systems "
            "and high-throughput data processing architectures. Proven track record of improving latency by 45% and leading "
            "cross-functional engineering teams.\n\n"
            "PROFESSIONAL EXPERIENCE\n"
            "TechNova Solutions — Staff Software Engineer\n"
            "January 2021 – Present | San Francisco, CA\n"
            "• Architected and deployed microservices architecture handling over 50,000 requests per second with 99.99% uptime.\n"
            "• Reduced query latency by 45% and cut cloud infrastructure costs by $120,000 annually through PostgreSQL query caching.\n"
            "• Spearheaded migration of legacy monolith to Kubernetes and Docker, accelerating deployment frequency by 3x.\n"
            "• Mentored 6 junior and mid-level software engineers in test-driven development and clean code principles.\n\n"
            "Apex Systems — Senior Software Developer\n"
            "June 2017 – December 2020 | Seattle, WA\n"
            "• Designed RESTful APIs and asynchronous message queues using Python, FastAPI, and Redis processing 2M events daily.\n"
            "• Implemented end-to-end CI/CD pipelines with GitHub Actions, reducing release build failures by 60%.\n"
            "• Collaborated with product management to define technical specifications for mission-critical customer analytics platform.\n\n"
            "EDUCATION\n"
            "University of California, Berkeley\n"
            "Bachelor of Science in Computer Science | September 2013 – May 2017\n"
            "Graduated Magna Cum Laude, GPA 3.85/4.0\n\n"
            "TECHNICAL SKILLS\n"
            "• Programming Languages: Python, Go, TypeScript, SQL\n"
            "• Frameworks & Libraries: FastAPI, Django, React, PyTorch\n"
            "• Infrastructure & Cloud: AWS, Docker, Kubernetes, Terraform, PostgreSQL, Redis\n"
            "• Methodologies: Agile/Scrum, CI/CD, Microservices, System Design\n\n"
            "CERTIFICATIONS\n"
            "• AWS Certified Solutions Architect – Professional (2022)\n"
        )
        return {
            "text": text,
            "structured": {
                "contact": {
                    "name": "Alexander Wong",
                    "email": "alexander.wong@example.com",
                    "phone": "+1 (555) 234-5678",
                    "location": "San Francisco, CA",
                    "linkedin": "linkedin.com/in/alexwong",
                },
                "summary": "Results-driven Senior Software Engineer with over 8 years of experience...",
                "experience": [
                    {
                        "title": "Staff Software Engineer",
                        "employer": "TechNova Solutions",
                        "dates": "January 2021 – Present",
                        "description": "Architected microservices handling 50k rps...",
                    },
                    {
                        "title": "Senior Software Developer",
                        "employer": "Apex Systems",
                        "dates": "June 2017 – December 2020",
                        "description": "Designed RESTful APIs using Python and FastAPI...",
                    },
                ],
                "education": [
                    {
                        "qualification": "Bachelor of Science in Computer Science",
                        "institution": "University of California, Berkeley",
                        "dates": "September 2013 – May 2017",
                    }
                ],
                "skills": ["Python", "Go", "TypeScript", "SQL", "FastAPI", "Docker", "Kubernetes", "AWS"],
                "certifications": ["AWS Certified Solutions Architect"],
            },
        }

    @staticmethod
    def get_average_resume() -> Dict[str, Any]:
        text = (
            "JORDAN MILLER\n"
            "jordan.m@email.com\n\n"
            "EXPERIENCE\n"
            "Acme Corp - Developer\n"
            "2021 - Present\n"
            "Worked on backend web development using Python and Flask. Fixed bugs and added features to the customer portal.\n"
            "Attended sprint planning and daily standups with the team.\n\n"
            "Beta Interactive - Junior Coder\n"
            "2019 - 2021\n"
            "Helped build internal dashboards using JavaScript and HTML. Assisted senior engineers with testing and QA.\n\n"
            "EDUCATION\n"
            "State College\n"
            "B.S. Information Technology, 2019\n\n"
            "SKILLS\n"
            "Python, JavaScript, HTML, CSS, Git, MySQL\n"
        )
        return {
            "text": text,
            "structured": {
                "contact": {
                    "name": "Jordan Miller",
                    "email": "jordan.m@email.com",
                },
                "experience": [
                    {
                        "title": "Developer",
                        "employer": "Acme Corp",
                        "dates": "2021 - Present",
                        "description": "Worked on backend web development using Python and Flask.",
                    },
                    {
                        "title": "Junior Coder",
                        "employer": "Beta Interactive",
                        "dates": "2019 - 2021",
                        "description": "Helped build internal dashboards.",
                    },
                ],
                "education": [
                    {
                        "qualification": "B.S. Information Technology",
                        "institution": "State College",
                        "dates": "2019",
                    }
                ],
                "skills": ["Python", "JavaScript", "HTML", "CSS", "Git", "MySQL"],
            },
        }

    @staticmethod
    def get_poorly_structured_resume() -> Dict[str, Any]:
        text = (
            "samuel coder stuff done in the past worked at some places doing python and sql.\n"
            "also know html css and javascript. I can do whatever you need me to do.\n"
            "worked from 2019 to now at various gigs fixing computers and making small websites.\n"
            "contact me if interested."
        )
        return {
            "text": text,
            "structured": {
                "skills": ["python", "sql", "html", "css", "javascript"],
            },
        }

    @staticmethod
    def get_missing_sections_resume() -> Dict[str, Any]:
        text = (
            "WORK EXPERIENCE\n"
            "Software Engineer at CloudTech (2020 - 2023)\n"
            "Built Python microservices and managed Docker containers.\n\n"
            "SKILLS\n"
            "Python, Docker, Linux, Bash\n"
        )
        return {
            "text": text,
            "structured": {
                "experience": [
                    {
                        "title": "Software Engineer",
                        "employer": "CloudTech",
                        "dates": "2020 - 2023",
                        "description": "Built Python microservices and managed Docker containers.",
                    }
                ],
                "skills": ["Python", "Docker", "Linux", "Bash"],
            },
        }

    @staticmethod
    def get_inconsistent_formatting_resume() -> Dict[str, Any]:
        text = (
            "EMILY CHEN\n"
            "emily@example.com\n\n"
            "EXPERIENCE:\n"
            "Role: Senior Dev | Company: Nova | Dates: 03/2022 - present\n"
            "Worked on lots of things. Did python coding.\n"
            "Job: Developer, Inc: Beta, Date: Jan 2019 to 2021\n"
            "worked on front-end.\n"
            "Role: intern, company: alpha, 2018\n\n"
            "Education:\n"
            "bs cs state univ 2018\n\n"
            "skills:\n"
            "python, java, react\n"
        )
        return {
            "text": text,
            "structured": {
                "contact": {"name": "Emily Chen", "email": "emily@example.com"},
                "experience": [
                    {"title": "Senior Dev", "employer": "Nova", "dates": "03/2022 - present"},
                    {"title": "Developer", "employer": "Beta", "dates": "Jan 2019 to 2021"},
                ],
                "education": [{"qualification": "bs cs", "institution": "state univ", "dates": "2018"}],
                "skills": ["python", "java", "react"],
            },
        }

    @staticmethod
    def get_very_short_resume() -> Dict[str, Any]:
        text = "John Doe. Contact: john@test.com. Skills: Python, SQL. 2 years experience building simple scripts."
        return {
            "text": text,
            "structured": {
                "contact": {"name": "John Doe", "email": "john@test.com"},
                "skills": ["Python", "SQL"],
            },
        }

    @staticmethod
    def get_long_resume() -> Dict[str, Any]:
        paragraphs = []
        paragraphs.append("DR. ROBERT MONTGOMERY, PH.D.")
        paragraphs.append("robert.montgomery@example.com | (555) 987-6543 | Boston, MA\n")
        paragraphs.append("EXECUTIVE SUMMARY\nDistinguished Principal Research Scientist with 20+ years of experience leading large-scale AI research teams.\n")

        for i in range(1, 10):
            paragraphs.append(
                f"POSITION {i}: Senior Research Lead — Global Lab {i}\n"
                f"Dates: 200{i} – 20{10+i}\n"
                f"• Spearheaded major high-performance computing initiatives across {i*10} research engineers.\n"
                f"• Published over {i*3} peer-reviewed research papers in top-tier ACM and IEEE conferences.\n"
                f"• Engineered scalable distributed pipeline processing {i*500} Terabytes of scientific telemetry with 99.9% accuracy.\n"
                f"• Managed annual research budget exceeding ${i*2}M dollars and secured government grants.\n"
                f"• Authored comprehensive technical documentation, patents, and conference proceedings.\n"
                f"• Deployed machine learning clusters across hybrid Kubernetes and on-premise supercomputing environments.\n"
            )

        paragraphs.append(
            "EDUCATION\n"
            "Ph.D. in Computer Science, Massachusetts Institute of Technology, 2002\n"
            "M.S. in Electrical Engineering, Stanford University, 1998\n"
            "B.S. in Mathematics, Harvard University, 1996\n"
        )
        paragraphs.append(
            "SKILLS\n"
            "Python, C++, CUDA, PyTorch, Distributed Systems, Cloud Architecture, Data Governance, Research Leadership\n"
        )
        text = "\n\n".join(paragraphs)
        return {
            "text": text,
            "structured": {
                "contact": {"name": "Robert Montgomery", "email": "robert.montgomery@example.com"},
                "summary": "Distinguished Principal Research Scientist...",
                "experience": [{"title": f"Lead {i}", "employer": f"Lab {i}", "dates": f"200{i}-201{i}"} for i in range(1, 10)],
                "education": [{"qualification": "Ph.D.", "institution": "MIT", "dates": "2002"}],
                "skills": ["Python", "C++", "CUDA", "PyTorch"],
            },
        }

    @staticmethod
    def get_functional_resume() -> Dict[str, Any]:
        text = (
            "MORGAN BLAKE\n"
            "morgan.blake@portfolio.dev | Seattle, WA\n\n"
            "PROFESSIONAL PROFILE\n"
            "Full-Stack Software Engineer with deep expertise in cloud architectures, microservices, and reactive user interfaces.\n\n"
            "AREAS OF EXPERTISE\n\n"
            "Cloud Architecture & DevOps\n"
            "• Designed and maintained AWS ECS and Kubernetes infrastructure supporting 100k daily active users.\n"
            "• Automated deployment workflows using Terraform, reducing environment provisioning time from 4 hours to 10 minutes.\n\n"
            "Backend & API Engineering\n"
            "• Implemented event-driven services with Python, Kafka, and PostgreSQL processing 10k messages per second.\n"
            "• Optimized database indexing and caching, improving 95th percentile response times by 35%.\n\n"
            "Frontend Development\n"
            "• Created responsive React/TypeScript interfaces with 98% Lighthouse accessibility scores.\n\n"
            "SELECTED PROJECTS & EMPLOYMENT HISTORY\n"
            "• Lead Engineer at DataCraft Studio (2021 – Present): Spearheaded SaaS analytics platform.\n"
            "• Software Engineer at CloudCraft (2018 – 2021): Core contributor to payment gateway integration.\n\n"
            "EDUCATION & CERTIFICATIONS\n"
            "B.S. in Software Engineering, Washington State University (2018)\n"
            "AWS Certified Developer Associate\n"
        )
        return {
            "text": text,
            "structured": {
                "contact": {"name": "Morgan Blake", "email": "morgan.blake@portfolio.dev", "location": "Seattle, WA"},
                "summary": "Full-Stack Software Engineer with deep expertise in cloud architectures...",
                "experience": [
                    {"title": "Lead Engineer", "employer": "DataCraft Studio", "dates": "2021 – Present"},
                    {"title": "Software Engineer", "employer": "CloudCraft", "dates": "2018 – 2021"},
                ],
                "education": [{"qualification": "B.S. in Software Engineering", "institution": "Washington State University", "dates": "2018"}],
                "skills": ["AWS", "Kubernetes", "Terraform", "Python", "Kafka", "PostgreSQL", "React", "TypeScript"],
            },
        }

    def test_well_structured_resume(self):
        data = self.get_well_structured_resume()
        assessment = self.evaluator.evaluate("cand-well-structured", data["text"], data["structured"])

        self.assertTrue(0.0 <= assessment.overall_score <= 100.0)
        self.assertGreaterEqual(assessment.overall_score, 75.0)
        self.assertEqual(assessment.quality_label, QualityLabel.GOOD)
        self.assertEqual(len(assessment.criterion_results), 10)
        self.assertGreaterEqual(len(assessment.strong_areas), 2)
        self.assertEqual(len(assessment.detected_issues), 0)

        comp = next(c for c in assessment.criterion_results if c.criterion_key == QualityCriterionKey.COMPLETENESS.value)
        self.assertGreaterEqual(comp.score, 85.0)

        read = next(c for c in assessment.criterion_results if c.criterion_key == QualityCriterionKey.READABILITY.value)
        self.assertGreaterEqual(read.score, 80.0)

    def test_average_resume_minor_issues(self):
        data = self.get_average_resume()
        assessment = self.evaluator.evaluate("cand-average", data["text"], data["structured"])

        self.assertTrue(0.0 <= assessment.overall_score <= 100.0)
        self.assertTrue(50.0 <= assessment.overall_score < 75.0)
        self.assertEqual(assessment.quality_label, QualityLabel.MODERATE)
        self.assertGreaterEqual(len(assessment.areas_for_improvement), 1)

    def test_poorly_structured_resume(self):
        data = self.get_poorly_structured_resume()
        assessment = self.evaluator.evaluate("cand-poor", data["text"], data["structured"])

        self.assertTrue(0.0 <= assessment.overall_score < 50.0)
        self.assertEqual(assessment.quality_label, QualityLabel.POOR)
        self.assertGreaterEqual(len(assessment.detected_issues), 1)
        self.assertGreaterEqual(len(assessment.areas_for_improvement), 2)

    def test_missing_sections_resume(self):
        data = self.get_missing_sections_resume()
        assessment = self.evaluator.evaluate("cand-missing-sections", data["text"], data["structured"])

        comp = next(c for c in assessment.criterion_results if c.criterion_key == QualityCriterionKey.COMPLETENESS.value)
        self.assertLess(comp.score, 60.0)
        self.assertFalse(assessment.section_completeness["education"]["present"])

    def test_inconsistent_formatting_resume(self):
        data = self.get_inconsistent_formatting_resume()
        assessment = self.evaluator.evaluate("cand-inconsistent", data["text"], data["structured"])

        date_crit = next(c for c in assessment.criterion_results if c.criterion_key == QualityCriterionKey.DATE_CONSISTENCY.value)
        fmt_crit = next(c for c in assessment.criterion_results if c.criterion_key == QualityCriterionKey.FORMATTING_CONSISTENCY.value)
        self.assertTrue(date_crit.score < 80.0 or fmt_crit.score < 80.0)
        self.assertTrue(any("inconsistent" in issue.description.lower() or "date" in issue.description.lower() for issue in assessment.detected_issues))

    def test_very_short_resume(self):
        data = self.get_very_short_resume()
        assessment = self.evaluator.evaluate("cand-very-short", data["text"], data["structured"])

        self.assertLess(assessment.readability_metrics.word_count, 50)
        read = next(c for c in assessment.criterion_results if c.criterion_key == QualityCriterionKey.READABILITY.value)
        self.assertLess(read.score, 60.0)
        self.assertTrue(any("short" in issue.description.lower() for issue in assessment.detected_issues))

    def test_long_resume(self):
        data = self.get_long_resume()
        assessment = self.evaluator.evaluate("cand-long", data["text"], data["structured"])

        self.assertGreater(assessment.readability_metrics.word_count, 400)
        self.assertTrue(0.0 <= assessment.overall_score <= 100.0)
        self.assertIn(assessment.quality_label, [QualityLabel.GOOD, QualityLabel.MODERATE])

    def test_functional_resume_style(self):
        data = self.get_functional_resume()
        assessment = self.evaluator.evaluate("cand-functional", data["text"], data["structured"])

        self.assertGreaterEqual(assessment.overall_score, 50.0)
        self.assertIn(assessment.quality_label, [QualityLabel.GOOD, QualityLabel.MODERATE])
        exp_crit = next(c for c in assessment.criterion_results if c.criterion_key == QualityCriterionKey.EXPERIENCE_CLARITY.value)
        self.assertGreaterEqual(exp_crit.score, 50.0)


class TestConfigurableThresholds(unittest.TestCase):

    def test_configurable_thresholds_override_labels(self):
        data = TestSyntheticResumeQuality.get_average_resume()

        evaluator_default = ResumeQualityEvaluator(good_threshold=75.0, moderate_threshold=50.0)
        res_default = evaluator_default.evaluate("cand-1", data["text"], data["structured"])

        evaluator_strict = ResumeQualityEvaluator(good_threshold=90.0, moderate_threshold=80.0)
        res_strict = evaluator_strict.evaluate("cand-1", data["text"], data["structured"])

        evaluator_lenient = ResumeQualityEvaluator(good_threshold=70.0, moderate_threshold=40.0)
        res_lenient = evaluator_lenient.evaluate("cand-1", data["text"], data["structured"])

        self.assertEqual(res_default.quality_label, QualityLabel.MODERATE)
        self.assertEqual(res_strict.quality_label, QualityLabel.POOR)
        self.assertEqual(res_lenient.quality_label, QualityLabel.GOOD)
        self.assertEqual(res_default.overall_score, res_strict.overall_score)
        self.assertEqual(res_default.overall_score, res_lenient.overall_score)


class TestDecoupledCompositeScore(unittest.TestCase):

    def test_composite_score_independence(self):
        records = [
            CandidateScoringRecord(
                candidate_id="cand-A",
                session_id="sess-test",
                evaluation_record_id="eval-A",
                scoring_config_id="cfg-1",
                scoring_config_version="v1.0",
                overall_score=87.4,
                evidence_coverage=92.0,
                completeness_status=ScoreCompleteness.COMPLETE,
            ),
            CandidateScoringRecord(
                candidate_id="cand-B",
                session_id="sess-test",
                evaluation_record_id="eval-B",
                scoring_config_id="cfg-1",
                scoring_config_version="v1.0",
                overall_score=84.1,
                evidence_coverage=88.0,
                completeness_status=ScoreCompleteness.COMPLETE,
            ),
        ]

        cfg = ScoringConfiguration(job_id="job-test", version="v1.0")
        ranker = DeterministicCandidateRanker()

        ranked_no_qual = ranker.rank_candidates(records, cfg)

        quality_map = {
            "cand-A": ResumeQualityAssessment(
                candidate_id="cand-A",
                overall_score=25.0,
                quality_label=QualityLabel.POOR,
                criterion_results=[],
            ),
            "cand-B": ResumeQualityAssessment(
                candidate_id="cand-B",
                overall_score=98.0,
                quality_label=QualityLabel.GOOD,
                criterion_results=[],
            ),
        }
        ranked_with_qual = ranker.rank_candidates(records, cfg, quality_map=quality_map)

        self.assertEqual(ranked_no_qual[0].candidate_id, "cand-A")
        self.assertEqual(ranked_no_qual[0].overall_score, 87.4)
        self.assertEqual(ranked_with_qual[0].candidate_id, "cand-A")
        self.assertEqual(ranked_with_qual[0].overall_score, 87.4)

        self.assertEqual(ranked_no_qual[1].candidate_id, "cand-B")
        self.assertEqual(ranked_no_qual[1].overall_score, 84.1)
        self.assertEqual(ranked_with_qual[1].candidate_id, "cand-B")
        self.assertEqual(ranked_with_qual[1].overall_score, 84.1)

        self.assertEqual(ranked_with_qual[0].resume_quality_score, 25.0)
        self.assertEqual(ranked_with_qual[0].resume_quality_label, "Poor Quality")
        self.assertEqual(ranked_with_qual[1].resume_quality_score, 98.0)
        self.assertEqual(ranked_with_qual[1].resume_quality_label, "Good Quality")


class TestReportingExports(unittest.TestCase):

    def test_csv_export_preserves_resume_quality(self):
        cand_summary = {
            "candidate_id": "cand-123",
            "candidate_reference": "Cand-001",
            "original_filename": "resume.pdf",
            "processing_status": "COMPLETED",
            "overall_score": 88.5,
            "evidence_coverage": 90.0,
            "review_status": "SHORTLISTED",
            "reviewer_notes": "Great candidate",
            "resume_quality_score": 92.0,
            "resume_quality_label": "Good Quality",
        }

        session_report_data = SessionSummaryReportData(
            report_id="rep-1",
            session_id="sess-1",
            session_name="Backend Screen",
            job_id="job-1",
            job_title="Backend Engineer",
            department="Engineering",
            session_created_at="2026-10-07T00:00:00",
            max_resume_count=100,
            total_resumes_enrolled=1,
            completed_processing_count=1,
            failed_processing_count=0,
            pending_processing_count=0,
            duplicate_count=0,
            completed_evaluation_count=1,
            scoring_config_id="cfg-1",
            scoring_config_version="v1.0",
            evaluation_methods_used=["MULTI_LAYER"],
            score_distribution={"mean": 88.5, "median": 88.5, "std_dev": 0.0, "p25": 88.5, "p75": 88.5, "iqr": 0.0, "min": 88.5, "max": 88.5},
            criterion_performance=[],
            shortlist_summary={"SHORTLISTED": 1},
            candidate_summaries=[cand_summary],
        )

        csv_output = CSVReportFormatter.format_session_report(session_report_data)
        csv_text = csv_output.decode("utf-8") if isinstance(csv_output, bytes) else str(csv_output)

        self.assertIn("resume_quality_score", csv_text)
        self.assertIn("resume_quality_label", csv_text)
        self.assertIn("92.0", csv_text)
        self.assertIn("Good Quality", csv_text)


if __name__ == "__main__":
    unittest.main()
