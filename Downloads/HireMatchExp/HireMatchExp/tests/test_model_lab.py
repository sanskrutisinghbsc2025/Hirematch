
from pathlib import Path
import tempfile
import unittest

from config import AppConfig
from core.model_lab.dataset_service import EvaluationDatasetService
from core.model_lab.metrics import EvaluationMetricsCalculator, ProfileContext
from core.model_lab.models import (
    BenchmarkConfiguration,
    BenchmarkStatus,
    EvaluationDataset,
    EvaluationDatasetItem,
    RelevanceGrade,
    TaskType,
)
from core.model_lab.registry import ModelRegistry
from core.model_lab.runner import BenchmarkRunner
from core.services.session_orchestrator import ScreeningOrchestrator
from core.storage.benchmark_repository import BenchmarkRunRepository, EvaluationDatasetRepository
from core.storage.database import Database


class TestModelComparisonLaboratory(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_model_lab.db"
        self.db = Database(str(self.db_path))
        self.db.initialize_schema()

        self.config = AppConfig()
        self.config.reports_dir = Path(self.temp_dir.name) / "reports"
        self.config.ensure_directories()

        self.orchestrator = ScreeningOrchestrator(self.db, self.config)
        self.registry = self.orchestrator.model_registry
        self.dataset_service = self.orchestrator.evaluation_dataset_service
        self.runner = self.orchestrator.benchmark_runner

    def tearDown(self):
        self.registry.clear_all()
        self.temp_dir.cleanup()

    def test_model_registry_metadata_and_catalog(self):
        models = self.registry.list_models()
        self.assertGreaterEqual(len(models), 6)

        minilm = self.registry.get("sentence-transformers/all-MiniLM-L6-v2")
        self.assertIsNotNone(minilm)
        self.assertEqual(minilm.embedding_dimension, 384)
        self.assertEqual(minilm.task_type, TaskType.SEMANTIC_RETRIEVAL)
        self.assertFalse(minilm.is_loaded)

        mpnet = self.registry.get("sentence-transformers/all-mpnet-base-v2")
        self.assertIsNotNone(mpnet)
        self.assertEqual(mpnet.embedding_dimension, 768)

        reranker = self.registry.get("cross-encoder/ms-marco-MiniLM-L-6-v2")
        self.assertIsNotNone(reranker)
        self.assertEqual(reranker.task_type, TaskType.PASSAGE_RERANKING)

        keyword = self.registry.get("rule-based-keyword")
        self.assertIsNotNone(keyword)
        self.assertEqual(keyword.task_type, TaskType.KEYWORD_MATCHING)

    def test_model_compatibility_validation(self):
        is_comp, warnings = self.registry.validate_compatibility([
            "sentence-transformers/all-MiniLM-L6-v2",
            "mock-deterministic-embedding",
        ])
        self.assertTrue(is_comp)
        self.assertEqual(len(warnings), 0)

        is_comp, warnings = self.registry.validate_compatibility([
            "sentence-transformers/all-MiniLM-L6-v2",
            "rule-based-keyword",
        ])
        self.assertTrue(is_comp)
        self.assertTrue(any("Cross-Paradigm" in w for w in warnings))

        is_comp, warnings = self.registry.validate_compatibility([
            "en_core_web_sm",
            "sentence-transformers/all-MiniLM-L6-v2",
        ])
        self.assertFalse(is_comp)
        self.assertTrue(any("Incompatible Task Types" in w for w in warnings))

        is_comp, warnings = self.registry.validate_compatibility([
            "sentence-transformers/all-MiniLM-L6-v2"
        ])
        self.assertFalse(is_comp)

    def test_on_demand_loading_and_memory_reclamation(self):
        model_id = "mock-deterministic-embedding"
        meta = self.registry.get(model_id)
        self.assertFalse(meta.is_loaded)

        loaded = self.registry.load_model(model_id)
        self.assertIsNotNone(loaded)
        meta_loaded = self.registry.get(model_id)
        self.assertTrue(meta_loaded.is_loaded)

        unloaded = self.registry.unload_model(model_id)
        self.assertTrue(unloaded)
        meta_unloaded = self.registry.get(model_id)
        self.assertFalse(meta_unloaded.is_loaded)

    def test_evaluation_dataset_versioning_and_immutability(self):
        ds = self.dataset_service.create_dataset(
            name="Custom Engineering Benchmark",
            version="v1.0",
            task=TaskType.SEMANTIC_RETRIEVAL,
            description="Testing engineering criteria",
        )
        self.assertFalse(ds.is_frozen)

        item = self.dataset_service.add_item_to_dataset(
            dataset_id=ds.id,
            query_text="Distributed database administration and sharding",
            passage_text="Managed multi-node CockroachDB clusters with distributed partition balancing.",
            relevance_grade=RelevanceGrade.HIGHLY_RELEVANT,
            category="SYNONYM",
            reviewer_notes="CockroachDB represents distributed relational database.",
        )
        self.assertIsNotNone(item.id)

        loaded = self.dataset_service.get_dataset(ds.id, load_items=True)
        self.assertEqual(len(loaded.items), 1)

        self.dataset_service.freeze_dataset(ds.id)
        self.assertTrue(self.dataset_service.is_frozen(ds.id))

        with self.assertRaises(ValueError):
            self.dataset_service.add_item_to_dataset(
                dataset_id=ds.id,
                query_text="Kubernetes networking",
                passage_text="Configured Calico CNI plugins.",
                relevance_grade=RelevanceGrade.HIGHLY_RELEVANT,
            )

    def test_responsible_ai_rubric_validation(self):
        ds = self.dataset_service.create_dataset(
            name="Compliance Test Dataset",
            version="v1.0",
        )

        with self.assertRaises(ValueError):
            self.dataset_service.add_item_to_dataset(
                dataset_id=ds.id,
                query_text="Candidate age under 35 with youthful energy",
                passage_text="Recent graduate born in 2001.",
                relevance_grade=RelevanceGrade.HIGHLY_RELEVANT,
            )

        with self.assertRaises(ValueError):
            self.dataset_service.add_item_to_dataset(
                dataset_id=ds.id,
                query_text="Culture fit rockstar with great vibe",
                passage_text="Passionate team player.",
                relevance_grade=RelevanceGrade.HIGHLY_RELEVANT,
            )

    def test_reference_ground_truth_metrics_calculation(self):
        y_true = [True, True, False, False, True]
        y_pred = [True, False, False, True, True]
        cls_metrics = EvaluationMetricsCalculator.compute_classification_metrics(y_true, y_pred)

        self.assertEqual(cls_metrics["precision"], 0.6667)
        self.assertEqual(cls_metrics["recall"], 0.6667)
        self.assertEqual(cls_metrics["f1"], 0.6667)

        ranked_labels = [True, False, True, False, False]
        self.assertEqual(EvaluationMetricsCalculator.precision_at_k(ranked_labels, k=2), 0.5)
        self.assertEqual(EvaluationMetricsCalculator.precision_at_k(ranked_labels, k=3), 0.6667)
        self.assertEqual(EvaluationMetricsCalculator.recall_at_k(ranked_labels, total_relevant=2, k=3), 1.0)

        perfect_grades = [2, 1, 0, 0]
        self.assertEqual(EvaluationMetricsCalculator.ndcg_at_k(perfect_grades, k=3), 1.0)

        imperfect_grades = [0, 2, 1, 0]
        ndcg_val = EvaluationMetricsCalculator.ndcg_at_k(imperfect_grades, k=3)
        self.assertLess(ndcg_val, 1.0)
        self.assertGreater(ndcg_val, 0.0)

        self.assertEqual(EvaluationMetricsCalculator.mean_reciprocal_rank([True, False, True]), 1.0)
        self.assertEqual(EvaluationMetricsCalculator.mean_reciprocal_rank([False, True, False]), 0.5)
        self.assertEqual(EvaluationMetricsCalculator.mean_reciprocal_rank([False, False, False]), 0.0)

    def test_unlabeled_descriptive_statistics(self):
        scores = [0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90]
        stats = EvaluationMetricsCalculator.compute_distribution_statistics(scores, threshold=0.50)

        self.assertEqual(stats["count"], 9)
        self.assertEqual(stats["median"], 0.50)
        self.assertEqual(stats["min"], 0.10)
        self.assertEqual(stats["max"], 0.90)
        self.assertGreater(stats["std_dev"], 0.0)
        self.assertGreater(stats["iqr"], 0.0)
        self.assertEqual(stats["coverage_pct"], 55.56)

    def test_pairwise_ranking_agreement_concordance(self):
        scores_a = [0.90, 0.80, 0.70, 0.60, 0.50]
        scores_b = [0.85, 0.75, 0.65, 0.55, 0.45]
        scores_c = [0.10, 0.20, 0.30, 0.40, 0.50]

        concordant = EvaluationMetricsCalculator.compute_pairwise_rank_correlation(scores_a, scores_b)
        self.assertEqual(concordant["kendall_tau"], 1.0)

        discordant = EvaluationMetricsCalculator.compute_pairwise_rank_correlation(scores_a, scores_c)
        self.assertEqual(discordant["kendall_tau"], -1.0)

    def test_benchmark_runner_execution_and_persistence(self):
        ds = self.dataset_service.ensure_synthetic_benchmark_dataset()

        cfg = BenchmarkConfiguration(
            models=["mock-deterministic-embedding", "rule-based-keyword"],
            dataset_id=ds.id,
            top_k=5,
            similarity_threshold=0.50,
            batch_size=16,
        )

        run_record = self.runner.run_benchmark(cfg, run_name="Unit Test Benchmark Run")

        self.assertEqual(run_record.status, BenchmarkStatus.COMPLETED)
        self.assertIsNotNone(run_record.completed_at)
        self.assertEqual(len(run_record.model_results), 2)

        mock_res = run_record.model_results["mock-deterministic-embedding"]
        self.assertGreater(mock_res.throughput_items_per_sec, 0.0)
        self.assertIsNotNone(mock_res.ground_truth_metrics)
        self.assertIn("ndcg_at_5", mock_res.ground_truth_metrics)

        self.assertIn("mock-deterministic-embedding vs rule-based-keyword", run_record.pairwise_agreement)

        persisted = self.orchestrator.get_benchmark_run(run_record.id)
        self.assertIsNotNone(persisted)
        self.assertEqual(persisted.run_name, "Unit Test Benchmark Run")
        self.assertEqual(len(persisted.model_results), 2)

    def test_reproducibility_and_rerun_capability(self):
        ds = self.dataset_service.ensure_synthetic_benchmark_dataset()

        cfg = BenchmarkConfiguration(
            models=["mock-deterministic-embedding"],
            dataset_id=ds.id,
            top_k=3,
            similarity_threshold=0.40,
        )

        run_1 = self.runner.run_benchmark(cfg, run_name="Run 1")
        run_2 = self.runner.run_benchmark(run_1.configuration, run_name="Run 2")

        scores_1 = [s["score"] for s in run_1.model_results["mock-deterministic-embedding"].detailed_scores]
        scores_2 = [s["score"] for s in run_2.model_results["mock-deterministic-embedding"].detailed_scores]

        self.assertEqual(scores_1, scores_2)

    def test_runtime_profiling_context(self):
        with ProfileContext(item_count=100) as profiler:
            _ = [i**2 for i in range(10000)]

        self.assertGreater(profiler.elapsed_seconds, 0.0)
        self.assertGreater(profiler.throughput, 0.0)


if __name__ == "__main__":
    unittest.main()
