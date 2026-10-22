
from datetime import datetime, timezone
import hashlib
from typing import Dict, List, Optional, Tuple
import numpy as np

from core.storage.database import Database
from core.utils.logger import logger


class SQLiteEmbeddingCache:

    def __init__(self, db: Database):
        self.db = db

    @staticmethod
    def compute_cache_key(model_name: str, text: str) -> str:
        normalized = text.strip()
        payload = f"{model_name}:{normalized}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def get(self, model_name: str, text: str) -> Optional[np.ndarray]:
        key = self.compute_cache_key(model_name, text)
        sql = "SELECT embedding_blob, dimension FROM embedding_cache WHERE cache_key = ?;"
        rows = self.db.execute_query(sql, (key,))
        if not rows:
            return None
        blob = rows[0]["embedding_blob"]
        dim = rows[0]["dimension"]
        arr = np.frombuffer(blob, dtype=np.float32)
        if len(arr) != dim:
            logger.warning(f"Cache key {key} dimension mismatch: expected {dim}, got {len(arr)}")
            return None
        return arr

    def set(self, model_name: str, text: str, embedding: np.ndarray) -> None:
        key = self.compute_cache_key(model_name, text)
        arr = np.asarray(embedding, dtype=np.float32)
        blob = arr.tobytes()
        dim = len(arr)
        now = datetime.now(timezone.utc).isoformat()
        sql = """
        INSERT OR REPLACE INTO embedding_cache (cache_key, model_name, text_content, embedding_blob, dimension, created_at)
        VALUES (?, ?, ?, ?, ?, ?);
        """
        self.db.execute_non_query(sql, (key, model_name, text[:500], blob, dim, now))

    def get_batch(
        self, model_name: str, texts: List[str]
    ) -> Tuple[Dict[int, np.ndarray], List[Tuple[int, str]]]:
        if not texts:
            return {}, []

        key_to_indices: Dict[str, List[int]] = {}
        for idx, t in enumerate(texts):
            k = self.compute_cache_key(model_name, t)
            key_to_indices.setdefault(k, []).append(idx)

        cached: Dict[int, np.ndarray] = {}
        all_keys = list(key_to_indices.keys())

        chunk_size = 500
        for i in range(0, len(all_keys), chunk_size):
            chunk = all_keys[i : i + chunk_size]
            placeholders = ",".join("?" for _ in chunk)
            sql = f"SELECT cache_key, embedding_blob, dimension FROM embedding_cache WHERE cache_key IN ({placeholders});"
            rows = self.db.execute_query(sql, tuple(chunk))
            for r in rows:
                k = r["cache_key"]
                dim = r["dimension"]
                arr = np.frombuffer(r["embedding_blob"], dtype=np.float32)
                if len(arr) == dim:
                    for orig_idx in key_to_indices.get(k, []):
                        cached[orig_idx] = arr

        missing: List[Tuple[int, str]] = []
        for idx, t in enumerate(texts):
            if idx not in cached:
                missing.append((idx, t))

        return cached, missing

    def set_batch(self, model_name: str, items: List[Tuple[str, np.ndarray]]) -> None:
        if not items:
            return
        now = datetime.now(timezone.utc).isoformat()
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            sql = """
            INSERT OR REPLACE INTO embedding_cache (cache_key, model_name, text_content, embedding_blob, dimension, created_at)
            VALUES (?, ?, ?, ?, ?, ?);
            """
            for text, emb in items:
                k = self.compute_cache_key(model_name, text)
                arr = np.asarray(emb, dtype=np.float32)
                cursor.execute(sql, (k, model_name, text[:500], arr.tobytes(), len(arr), now))

    def count(self, model_name: Optional[str] = None) -> int:
        if model_name:
            sql = "SELECT COUNT(*) as cnt FROM embedding_cache WHERE model_name = ?;"
            rows = self.db.execute_query(sql, (model_name,))
        else:
            sql = "SELECT COUNT(*) as cnt FROM embedding_cache;"
            rows = self.db.execute_query(sql)
        return rows[0]["cnt"] if rows else 0

    def clear(self, model_name: Optional[str] = None) -> int:
        if model_name:
            sql = "DELETE FROM embedding_cache WHERE model_name = ?;"
            return self.db.execute_non_query(sql, (model_name,))
        else:
            sql = "DELETE FROM embedding_cache;"
            return self.db.execute_non_query(sql)
