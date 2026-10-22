
import os
from pathlib import Path
import tempfile
import unittest

from config import AppConfig


class TestConfig(unittest.TestCase):

    def test_default_config_values(self):
        config = AppConfig()
        self.assertEqual(config.app_name, "HireMatch")
        self.assertEqual(config.max_resumes_per_session, 100)
        self.assertEqual(config.processing_batch_size, 10)
        self.assertIn(".pdf", config.supported_file_types)
        self.assertIn(".docx", config.supported_file_types)

    def test_invalid_max_resumes_raises_error(self):
        with self.assertRaises(ValueError):
            AppConfig(max_resumes_per_session=0)

        with self.assertRaises(ValueError):
            AppConfig(max_resumes_per_session=-10)

    def test_batch_size_exceeding_max_resumes_raises_error(self):
        with self.assertRaises(ValueError):
            AppConfig(max_resumes_per_session=50, processing_batch_size=100)

    def test_ensure_directories_creates_folders(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            config = AppConfig(
                base_dir=base,
                db_path=base / "data" / "test.db",
                storage_dir=base / "data" / "storage",
                cache_dir=base / "data" / "cache",
                temp_dir=base / "data" / "temp",
            )
            config.ensure_directories()
            self.assertTrue(config.storage_dir.exists())
            self.assertTrue(config.cache_dir.exists())
            self.assertTrue(config.temp_dir.exists())
            self.assertTrue(config.db_path.parent.exists())

    def test_env_override(self):
        os.environ["HIREMATCH_APP_NAME"] = "CustomHireMatch"
        os.environ["HIREMATCH_MAX_RESUMES_PER_SESSION"] = "75"
        try:
            cfg = AppConfig.from_env()
            self.assertEqual(cfg.app_name, "CustomHireMatch")
            self.assertEqual(cfg.max_resumes_per_session, 75)
        finally:
            os.environ.pop("HIREMATCH_APP_NAME", None)
            os.environ.pop("HIREMATCH_MAX_RESUMES_PER_SESSION", None)


if __name__ == "__main__":
    unittest.main()
