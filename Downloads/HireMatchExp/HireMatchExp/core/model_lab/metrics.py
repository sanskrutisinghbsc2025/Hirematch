
import math
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import psutil

try:
    from scipy.stats import kendalltau, spearmanr
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False


class ProfileContext:

    def __init__(self, item_count: int = 1):
        self.item_count = max(1, item_count)
        self.process = psutil.Process(os.getpid())
        self.start_time: float = 0.0
        self.elapsed_seconds: float = 0.0
        self.mem_start_mb: float = 0.0
        self.mem_peak_mb: float = 0.0
        self.throughput: float = 0.0

    def __enter__(self) -> "ProfileContext":
        self.mem_start_mb = self.process.memory_info().rss / (1024 * 1024)
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.elapsed_seconds = max(1e-6, time.perf_counter() - self.start_time)
        mem_end_mb = self.process.memory_info().rss / (1024 * 1024)
        self.mem_peak_mb = max(0.0, round(mem_end_mb - self.mem_start_mb, 2))
        self.throughput = round(self.item_count / self.elapsed_seconds, 2)


class EvaluationMetricsCalculator:


    @staticmethod
    def compute_classification_metrics(
        y_true: List[bool],
        y_pred: List[bool],
    ) -> Dict[str, float]:
        if not y_true or len(y_true) != len(y_pred):
            return {"precision": 0.0, "recall": 0.0, "f1": 0.0, "accuracy": 0.0}

        tp = sum(1 for yt, yp in zip(y_true, y_pred) if yt and yp)
        fp = sum(1 for yt, yp in zip(y_true, y_pred) if not yt and yp)
        fn = sum(1 for yt, yp in zip(y_true, y_pred) if yt and not yp)
        tn = sum(1 for yt, yp in zip(y_true, y_pred) if not yt and not yp)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        accuracy = (tp + tn) / len(y_true) if len(y_true) > 0 else 0.0

        return {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "accuracy": round(accuracy, 4),
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
            "true_negatives": tn,
        }

    @staticmethod
    def precision_at_k(ranked_labels: List[bool], k: int) -> float:
        if not ranked_labels or k <= 0:
            return 0.0
        top_k = ranked_labels[:k]
        return round(sum(1 for rel in top_k if rel) / len(top_k), 4)

    @staticmethod
    def recall_at_k(ranked_labels: List[bool], total_relevant: int, k: int) -> float:
        if not ranked_labels or total_relevant <= 0 or k <= 0:
            return 0.0
        top_k = ranked_labels[:k]
        return round(sum(1 for rel in top_k if rel) / total_relevant, 4)

    @staticmethod
    def ndcg_at_k(ranked_relevance_grades: List[int], k: int) -> float:
        if not ranked_relevance_grades or k <= 0:
            return 0.0

        actual_k = ranked_relevance_grades[:k]

        dcg = 0.0
        for i, grade in enumerate(actual_k):
            if grade > 0:
                gain = (2**grade) - 1
                discount = math.log2(i + 2)
                dcg += gain / discount

        ideal_k = sorted(ranked_relevance_grades, reverse=True)[:k]
        idcg = 0.0
        for i, grade in enumerate(ideal_k):
            if grade > 0:
                gain = (2**grade) - 1
                discount = math.log2(i + 2)
                idcg += gain / discount

        if idcg <= 0.0:
            return 0.0
        return round(dcg / idcg, 4)

    @staticmethod
    def mean_reciprocal_rank(ranked_labels: List[bool]) -> float:
        for i, is_rel in enumerate(ranked_labels):
            if is_rel:
                return round(1.0 / (i + 1), 4)
        return 0.0

    @staticmethod
    def compute_pairwise_rank_correlation(
        scores_a: List[float],
        scores_b: List[float],
    ) -> Dict[str, Optional[float]]:
        if len(scores_a) != len(scores_b) or len(scores_a) < 2:
            return {"kendall_tau": None, "spearman_rho": None}

        if len(set(scores_a)) <= 1 or len(set(scores_b)) <= 1:
            return {"kendall_tau": 0.0, "spearman_rho": 0.0}

        if SCIPY_AVAILABLE:
            try:
                tau, _ = kendalltau(scores_a, scores_b)
                rho, _ = spearmanr(scores_a, scores_b)
                return {
                    "kendall_tau": round(float(tau), 4) if not math.isnan(tau) else 0.0,
                    "spearman_rho": round(float(rho), 4) if not math.isnan(rho) else 0.0,
                }
            except Exception:
                pass

        concordant = 0
        discordant = 0
        n = len(scores_a)
        for i in range(n):
            for j in range(i + 1, n):
                diff_a = scores_a[i] - scores_a[j]
                diff_b = scores_b[i] - scores_b[j]
                prod = diff_a * diff_b
                if prod > 0:
                    concordant += 1
                elif prod < 0:
                    discordant += 1

        total_pairs = concordant + discordant
        approx_tau = (concordant - discordant) / total_pairs if total_pairs > 0 else 0.0
        return {
            "kendall_tau": round(approx_tau, 4),
            "spearman_rho": round(approx_tau, 4),
        }


    @staticmethod
    def compute_distribution_statistics(
        scores: List[float],
        threshold: float = 0.50,
    ) -> Dict[str, float]:
        if not scores:
            return {
                "count": 0,
                "mean": 0.0,
                "median": 0.0,
                "std_dev": 0.0,
                "variance": 0.0,
                "min": 0.0,
                "max": 0.0,
                "q25": 0.0,
                "q75": 0.0,
                "iqr": 0.0,
                "coverage_pct": 0.0,
            }

        arr = np.array(scores, dtype=float)
        mean_val = float(np.mean(arr))
        median_val = float(np.median(arr))
        std_val = float(np.std(arr)) if len(arr) > 1 else 0.0
        var_val = float(np.var(arr)) if len(arr) > 1 else 0.0
        q25 = float(np.percentile(arr, 25))
        q75 = float(np.percentile(arr, 75))
        iqr = round(q75 - q25, 4)
        cov = float(np.sum(arr >= threshold) / len(arr)) * 100.0

        return {
            "count": len(scores),
            "mean": round(mean_val, 4),
            "median": round(median_val, 4),
            "std_dev": round(std_val, 4),
            "variance": round(var_val, 4),
            "min": round(float(np.min(arr)), 4),
            "max": round(float(np.max(arr)), 4),
            "q25": round(q25, 4),
            "q75": round(q75, 4),
            "iqr": iqr,
            "coverage_pct": round(cov, 2),
        }
