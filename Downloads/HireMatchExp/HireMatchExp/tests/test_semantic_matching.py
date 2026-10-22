
import shutil
import tempfile
import unittest
from pathlib import Path
import numpy as np

from config import AppConfig
from core.evaluation.benchmark_dataset import BENCHMARK_CASES
from core.evaluation.embedding_provider import (
    CachedEmbeddingProvider,
    MockEmbeddingProvider,
    SentenceTransformerProvider,
    get_embedding_provider,
)
from core.evaluation.hybrid_scoring_engine import HybridScoringEngine
from core.evaluation.reranker import CrossEncoderReranker
from core.evaluation.scoring_engine import TransparentScoringEngine
from core.evaluation.semantic_evaluator import SemanticCandidateEvaluator
from core.evaluation.semantic_matcher import SemanticMatcher
from core.evaluation.text_chunker import DocumentChunk, SectionAwareTextChunker
from core.models.candidate import Candidate
from core.models.enums import (
    CriterionType,
    EvaluationMode,
    FileType,
    MatchStatus,
    ModelStatus,
    ProcessingStatus,
    SemanticSimilarityTier,
)
from core.models.evaluation import EvaluationCriterion
from core.models.job import Job
from core.services.model_manager import ModelManager
from core.services.session_orchestrator import ScreeningOrchestrator
from core.storage.database import Database
from core.storage.embedding_cache import SQLiteEmbeddingCache
from core.storage.repositories import (
    CandidateRepository,
    CriterionRepository,
    EvidenceRepository,
    JobRepository,
    ScoreRepository,
    SessionRepository,
)


class TestEmbeddingCache(unittest.TestCase):

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.db = Database(self.temp_dir / "cache_test.db")
        self.db.initialize_schema()
        self.cache = SQLiteEmbeddingCache(self.db)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_single_vector_set_and_get(self):
        vec = np.random.randn(384).astype(np.float32)
        norm_vec = vec / np.linalg.norm(vec)

        self.assertIsNone(self.cache.get("test-model", "Python Developer"))
        self.cache.set("test-model", "Python Developer", norm_vec)

        retrieved = self.cache.get("test-model", "Python Developer")
        self.assertIsNotNone(retrieved)
        self.assertEqual(len(retrieved), 384)
        np.testing.assert_allclose(norm_vec, retrieved, atol=1e-5)

    def test_batch_cache_operations(self):
        model_name = "test-model"
        texts = ["Text A", "Text B", "Text C", "Text D"]
        dim = 128

        vec_a = np.random.randn(dim).astype(np.float32)
        vec_c = np.random.randn(dim).astype(np.float32)
        self.cache.set(model_name, "Text A", vec_a)
        self.cache.set(model_name, "Text C", vec_c)

        cached, missing = self.cache.get_batch(model_name, texts)
        self.assertEqual(len(cached), 2)
        self.assertIn(0, cached)
        self.assertIn(2, cached)

        self.assertEqual(len(missing), 2)
        missing_indices = [idx for idx, _ in missing]
        self.assertEqual(missing_indices, [1, 3])

        vec_b = np.random.randn(dim).astype(np.float32)
        vec_d = np.random.randn(dim).astype(np.float32)
        self.cache.set_batch(model_name, [("Text B", vec_b), ("Text D", vec_d)])

        self.assertEqual(self.cache.count(model_name), 4)

    def test_cache_count_and_clear(self):
        self.cache.set("model-1", "Query 1", np.ones(64, dtype=np.float32))
        self.cache.set("model-1", "Query 2", np.ones(64, dtype=np.float32))
        self.cache.set("model-2", "Query 3", np.ones(64, dtype=np.float32))

        self.assertEqual(self.cache.count(), 3)
        self.assertEqual(self.cache.count("model-1"), 2)
        self.assertEqual(self.cache.count("model-2"), 1)

        deleted = self.cache.clear("model-1")
        self.assertEqual(deleted, 2)
        self.assertEqual(self.cache.count("model-1"), 0)
        self.assertEqual(self.cache.count("model-2"), 1)

        self.cache.clear()
        self.assertEqual(self.cache.count(), 0)


class TestSectionAwareTextChunker(unittest.TestCase):

    def setUp(self):
        self.chunker = SectionAwareTextChunker(
            min_chunk_chars=30,
            target_chunk_chars=150,
            max_chunk_chars=300,
            overlap_sentences=1,
        )

    def test_chunking_structured_sections(self):
        structured = {
            "sections": [
                {
                    "canonical_name": "EXPERIENCE",
                    "display_title": "Work Experience",
                    "content": "Senior Python Developer at Tech Corp from 2020 to 2024. Architected scalable REST microservices with FastAPI and Docker. Led team of 5 backend engineers.",
                },
                {
                    "canonical_name": "EDUCATION",
                    "display_title": "Education",
                    "content": "Master of Science in Computer Science from Stanford University.",
                },
            ]
        }
        chunks = self.chunker.chunk_candidate("", structured_data=structured)
        self.assertGreaterEqual(len(chunks), 2)
        self.assertTrue(any(c.source_section == "EXPERIENCE" for c in chunks))
        self.assertTrue(any(c.source_section == "EDUCATION" for c in chunks))
        self.assertTrue(all(isinstance(c.text, str) and len(c.text) > 0 for c in chunks))

    def test_chunking_raw_text_with_headers(self):
        raw_text = """
SUMMARY
Senior Cloud Engineer with 8 years of AWS and Kubernetes experience.

WORK EXPERIENCE
Lead Cloud Architect at MegaCorp 2021-Present.
Built multi-region EKS clusters. Managed Terraform infrastructure modules.

TECHNICAL SKILLS
Python, Go, Kubernetes, Terraform, Docker, AWS.
"""
        chunks = self.chunker.chunk_candidate(raw_text)
        self.assertGreaterEqual(len(chunks), 3)
        sections_found = {c.source_section.lower() for c in chunks}
        self.assertTrue("summary" in sections_found or "work experience" in sections_found)

    def test_chunking_empty_and_short_text(self):
        self.assertEqual(self.chunker.chunk_candidate(""), [])
        single = self.chunker.chunk_candidate("Short plain resume text.")
        self.assertEqual(len(single), 1)
        self.assertEqual(single[0].source_section, "general")


class TestEmbeddingProviders(unittest.TestCase):

    def test_mock_provider_properties_and_determinism(self):
        provider = MockEmbeddingProvider(dimension=384)
        self.assertEqual(provider.dimension, 384)
        self.assertEqual(provider.device, "cpu")
        self.assertEqual(provider.status, ModelStatus.READY)

        text = "Experienced Senior Python Backend Engineer"
        emb1 = provider.encode([text])[0]
        emb2 = provider.encode([text])[0]

        np.testing.assert_array_equal(emb1, emb2)

        norm = np.linalg.norm(emb1)
        self.assertAlmostEqual(norm, 1.0, places=5)

        cos_sim = float(np.dot(emb1, emb2))
        self.assertAlmostEqual(cos_sim, 1.0, places=5)

    def test_mock_provider_keyword_sharing(self):
        provider = MockEmbeddingProvider(dimension=384)
        v_py1 = provider.encode(["Python Developer"])[0]
        v_py2 = provider.encode(["Python Developer with FastAPI"])[0]
        v_unrelated = provider.encode(["Customer support and cashier duties"])[0]

        sim_related = float(np.dot(v_py1, v_py2))
        sim_unrelated = float(np.dot(v_py1, v_unrelated))

        self.assertGreater(sim_related, 0.40)
        self.assertLess(sim_unrelated, sim_related)

    def test_cached_provider_wrapper(self):
        temp_dir = Path(tempfile.mkdtemp())
        try:
            db = Database(temp_dir / "cache_test.db")
            db.initialize_schema()
            cache = SQLiteEmbeddingCache(db)

            base_provider = MockEmbeddingProvider(dimension=384)
            cached_provider = CachedEmbeddingProvider(base_provider, cache)

            texts = ["Query One", "Query Two"]
            embs1 = cached_provider.encode(texts)
            self.assertEqual(cache.count(base_provider.model_name), 2)

            embs2 = cached_provider.encode(texts)
            np.testing.assert_allclose(embs1, embs2, atol=1e-5)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_sentence_transformer_provider_graceful_missing(self):
        st_provider = SentenceTransformerProvider("non-existent-or-missing")
        self.assertIn(st_provider.status, (ModelStatus.REGISTERED, ModelStatus.UNAVAILABLE, ModelStatus.ERROR, ModelStatus.READY))


class TestSemanticMatcherAndReranker(unittest.TestCase):

    def setUp(self):
        self.provider = MockEmbeddingProvider(dimension=384)
        self.matcher = SemanticMatcher(self.provider)

    def test_tier_classification_thresholds(self):
        self.assertEqual(self.matcher.classify_tier(0.75), SemanticSimilarityTier.STRONG)
        self.assertEqual(self.matcher.classify_tier(0.70), SemanticSimilarityTier.STRONG)
        self.assertEqual(self.matcher.classify_tier(0.55), SemanticSimilarityTier.POSSIBLE)
        self.assertEqual(self.matcher.classify_tier(0.40), SemanticSimilarityTier.WEAK)
        self.assertEqual(self.matcher.classify_tier(0.20), SemanticSimilarityTier.INSUFFICIENT)

    def test_compute_similarity_ranking(self):
        query = "Python REST API microservices"
        passages = [
            "Built REST microservices using Python and Flask.",
            "Prepared financial balance sheets and accounting reports.",
            "Senior Backend Engineer with Python and REST API development.",
        ]
        sims = self.matcher.compute_similarity(query, passages)
        self.assertEqual(len(sims), 3)
        self.assertTrue(all(0.0 <= s <= 1.0 for s in sims))
        self.assertGreater(sims[0], sims[1])
        self.assertGreater(sims[2], sims[1])

    def test_match_criterion_top_k(self):
        query = "Kubernetes orchestration"
        chunks = [
            DocumentChunk(text="K8s cluster deployment", source_section="skills", chunk_index=0, char_start=0, char_end=22),
            DocumentChunk(text="Cooking Italian pasta", source_section="general", chunk_index=1, char_start=23, char_end=44),
            DocumentChunk(text="Kubernetes Helm charts and cloud infrastructure", source_section="experience", chunk_index=2, char_start=45, char_end=92),
        ]
        results = self.matcher.match_criterion(query, chunks, top_k=2)
        self.assertEqual(len(results), 2)
        self.assertGreaterEqual(results[0].similarity_score, results[1].similarity_score)

    def test_reranker_interface(self):
        reranker = CrossEncoderReranker()
        self.assertIn(reranker.status, (ModelStatus.READY, ModelStatus.UNAVAILABLE, ModelStatus.ERROR))
        ranked = reranker.rerank("Python developer", ["Passage A", "Passage B"])
        self.assertEqual(len(ranked), 2)


class TestSemanticAndHybridEvaluation(unittest.TestCase):

    def setUp(self):
        self.provider = MockEmbeddingProvider(dimension=384)
        self.matcher = SemanticMatcher(self.provider)
        self.chunker = SectionAwareTextChunker()
        self.semantic_evaluator = SemanticCandidateEvaluator(self.matcher, self.chunker)
        self.scoring_engine = TransparentScoringEngine()
        self.hybrid_engine = HybridScoringEngine(
            semantic_evaluator=self.semantic_evaluator,
            scoring_engine=self.scoring_engine,
        )

        self.job = Job(
            title="Senior Python Cloud Engineer",
            original_description="Looking for Senior Python Cloud Engineer with AWS experience and B.S. degree.",
            department="Engineering",
        )

        self.criteria = [
            EvaluationCriterion(
                criterion_name="Python Programming",
                description="Production Python development experience",
                weight=0.5,
                criterion_type=CriterionType.REQUIRED,
            ),
            EvaluationCriterion(
                criterion_name="AWS Cloud Services",
                description="Experience with AWS ECS, Lambda, S3",
                weight=0.3,
                criterion_type=CriterionType.REQUIRED,
            ),
            EvaluationCriterion(
                criterion_name="Computer Science Degree",
                description="B.S. or M.S. in Computer Science",
                weight=0.2,
                criterion_type=CriterionType.PREFERRED,
            ),
        ]

        self.qualified_candidate = Candidate(
            original_filename="alice_dev.pdf",
            file_hash="1" * 64,
            file_type=FileType.PDF,
            processing_status=ProcessingStatus.COMPLETED,
            extracted_text="Alice Smith Senior Python Developer with AWS cloud experience and B.S. in Computer Science.",
        )
        self.qualified_struct = {
            "skills": [
                {"skill_name": "Python", "normalized_skill_name": "Python", "evidence_text": "Python Developer", "source_location": "SKILLS"},
                {"skill_name": "AWS", "normalized_skill_name": "AWS", "evidence_text": "AWS cloud", "source_location": "SKILLS"},
            ],
            "experience": [
                {"job_title": "Python Developer", "employer": "CloudCorp", "dates": "2020 - 2024", "extracted_description": "Built AWS Python microservices"},
            ],
            "education": [
                {"qualification": "B.S. in Computer Science", "institution": "Tech Univ", "dates": "2016 - 2020"},
            ],
            "sections": [
                {"canonical_name": "SKILLS", "content": "Python, AWS, Docker, Git"},
                {"canonical_name": "EXPERIENCE", "content": "Python Developer at CloudCorp with AWS services"},
                {"canonical_name": "EDUCATION", "content": "B.S. in Computer Science from Tech Univ"},
            ],
        }

    def test_semantic_evaluator_traceability(self):
        crit_results, evidence = self.semantic_evaluator.evaluate_candidate_detailed(
            candidate=self.qualified_candidate,
            job=self.job,
            criteria=self.criteria,
            structured_data=self.qualified_struct,
        )
        self.assertEqual(len(crit_results), 3)
        self.assertTrue(all(r.matching_method == "semantic_similarity" for r in crit_results))
        self.assertTrue(all(r.semantic_score is not None for r in crit_results))
        self.assertTrue(all(r.similarity_tier is not None for r in crit_results))

        for r in crit_results:
            self.assertTrue(len(r.explanation) > 0)
            if r.top_passages:
                self.assertIn("passage_text", r.top_passages[0])
                self.assertIn("source_section", r.top_passages[0])

    def test_hybrid_engine_modes(self):
        score_base, ev_base = self.hybrid_engine.evaluate_candidate(
            candidate=self.qualified_candidate,
            job=self.job,
            criteria=self.criteria,
            mode=EvaluationMode.BASELINE,
            structured_data=self.qualified_struct,
        )
        self.assertEqual(score_base.evaluation_mode, "BASELINE")
        self.assertIsNotNone(score_base.baseline_score)

        score_sem, ev_sem = self.hybrid_engine.evaluate_candidate(
            candidate=self.qualified_candidate,
            job=self.job,
            criteria=self.criteria,
            mode=EvaluationMode.SEMANTIC,
            structured_data=self.qualified_struct,
        )
        self.assertEqual(score_sem.evaluation_mode, "SEMANTIC")
        self.assertIsNotNone(score_sem.semantic_score)

        score_comb, ev_comb = self.hybrid_engine.evaluate_candidate(
            candidate=self.qualified_candidate,
            job=self.job,
            criteria=self.criteria,
            mode=EvaluationMode.COMBINED,
            structured_data=self.qualified_struct,
        )
        self.assertEqual(score_comb.evaluation_mode, "COMBINED")
        self.assertIsNotNone(score_comb.baseline_score)
        self.assertIsNotNone(score_comb.semantic_score)
        self.assertIsNotNone(score_comb.combined_score)
        self.assertGreater(score_comb.overall_score, 0.0)


class TestOrchestratorSemanticBatch(unittest.TestCase):

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.db = Database(self.temp_dir / "orch_sem_test.db")
        self.db.initialize_schema()
        self.config = AppConfig(storage_dir=self.temp_dir / "storage")
        self.orchestrator = ScreeningOrchestrator(self.db, self.config)

        self.job_repo = JobRepository(self.db)
        self.session_repo = SessionRepository(self.db)
        self.candidate_repo = CandidateRepository(self.db)
        self.crit_repo = CriterionRepository(self.db)
        self.score_repo = ScoreRepository(self.db)

        self.job = self.job_repo.create(
            Job(
                title="Full Stack Software Engineer",
                original_description="Full stack engineer with Python and React experience.",
                department="Engineering",
            )
        )
        self.criteria = [
            EvaluationCriterion(
                criterion_name="Python Skills",
                description="Python backend development",
                weight=0.6,
                criterion_type=CriterionType.REQUIRED,
            ),
            EvaluationCriterion(
                criterion_name="React Skills",
                description="React frontend development",
                weight=0.4,
                criterion_type=CriterionType.REQUIRED,
            ),
        ]
        self.crit_repo.save_batch(self.criteria, self.job.id)

        self.session = self.orchestrator.create_session(self.job.id, "Batch Semantic Test")

        cand = Candidate(
            original_filename="candidate_one.pdf",
            file_hash="c1" * 32,
            file_type=FileType.PDF,
            processing_status=ProcessingStatus.COMPLETED,
            extracted_text="Full stack engineer with extensive Python and React production experience.",
        )
        self.candidate_repo.create(cand)
        self.candidate_repo.link_to_session(
            session_id=self.session.id,
            candidate_id=cand.id,
            processing_status=ProcessingStatus.COMPLETED,
            manifest_meta={"filename": "candidate_one.pdf"},
        )
        struct_data = {
            "skills": [
                {"skill_name": "Python", "normalized_skill_name": "Python", "evidence_text": "Python", "source_location": "SKILLS"},
                {"skill_name": "React", "normalized_skill_name": "React", "evidence_text": "React", "source_location": "SKILLS"},
            ],
            "sections": [
                {"canonical_name": "SKILLS", "content": "Python, React, TypeScript"},
            ],
        }
        self.candidate_repo.update_structured_data(cand.id, struct_data)
        self.cand_id = cand.id

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_orchestrator_evaluate_batch_combined(self):
        res = self.orchestrator.evaluate_session_batch(
            self.session.id,
            evaluation_mode=EvaluationMode.COMBINED,
        )
        self.assertEqual(res["evaluated_in_chunk"], 1)
        self.assertEqual(res["failed_in_chunk"], 0)

        score = self.score_repo.get_score(self.cand_id)
        self.assertIsNotNone(score)
        self.assertEqual(score.evaluation_mode, "COMBINED")
        self.assertIsNotNone(score.baseline_score)
        self.assertIsNotNone(score.semantic_score)
        self.assertGreater(score.overall_score, 0.0)

    def test_orchestrator_evaluate_batch_semantic_only(self):
        res = self.orchestrator.evaluate_session_batch(
            self.session.id,
            evaluation_mode=EvaluationMode.SEMANTIC,
        )
        self.assertEqual(res["evaluated_in_chunk"], 1)
        score = self.score_repo.get_score(self.cand_id)
        self.assertIsNotNone(score)
        self.assertEqual(score.evaluation_mode, "SEMANTIC")
        self.assertIsNotNone(score.semantic_score)


class TestBenchmarkDatasetIntegrity(unittest.TestCase):

    def test_benchmark_cases_count_and_types(self):
        self.assertGreaterEqual(len(BENCHMARK_CASES), 5)
        categories = {b.category for b in BENCHMARK_CASES}
        self.assertIn("SYNONYM", categories)
        self.assertIn("PARAPHRASE", categories)
        self.assertIn("DISTRACTOR", categories)
        self.assertIn("NEGATION", categories)


if __name__ == "__main__":
    unittest.main()
