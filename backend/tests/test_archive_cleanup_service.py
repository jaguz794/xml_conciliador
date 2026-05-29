import os
import tempfile
import unittest
from pathlib import Path

from backend.app.core.config import settings
from backend.app.services.archive_cleanup_service import cleanup_expired_runtime_files


class ArchiveCleanupServiceTests(unittest.TestCase):
    def test_cleans_only_expired_zip_and_cache_files(self) -> None:
        previous_processed_dir = settings.processed_dir
        previous_cache_dir = settings.reconciliation_cache_dir
        previous_zip_retention = settings.processed_zip_retention_days
        previous_cache_retention = settings.reconciliation_cache_retention_days

        with tempfile.TemporaryDirectory() as processed_dir, tempfile.TemporaryDirectory() as cache_dir:
            try:
                settings.processed_dir = Path(processed_dir)
                settings.reconciliation_cache_dir = Path(cache_dir)
                settings.processed_zip_retention_days = 15
                settings.reconciliation_cache_retention_days = 15

                expired_zip = settings.processed_dir / "old_batch.zip"
                fresh_zip = settings.processed_dir / "new_batch.zip"
                xml_file = settings.processed_dir / "keep.xml"
                expired_cache = settings.reconciliation_cache_dir / "old_snapshot.json"
                fresh_cache = settings.reconciliation_cache_dir / "new_snapshot.json"

                for path in [expired_zip, fresh_zip, xml_file, expired_cache, fresh_cache]:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("test", encoding="utf-8")

                sixteen_days_ago = int((os.path.getmtime(expired_zip) - (16 * 24 * 60 * 60)))
                now_timestamp = int(os.path.getmtime(fresh_zip))

                os.utime(expired_zip, (sixteen_days_ago, sixteen_days_ago))
                os.utime(expired_cache, (sixteen_days_ago, sixteen_days_ago))
                os.utime(fresh_zip, (now_timestamp, now_timestamp))
                os.utime(fresh_cache, (now_timestamp, now_timestamp))
                os.utime(xml_file, (sixteen_days_ago, sixteen_days_ago))

                result = cleanup_expired_runtime_files()

                self.assertEqual(result.processed_zips.scanned, 2)
                self.assertEqual(result.processed_zips.deleted, 1)
                self.assertEqual(result.processed_zips.kept, 1)
                self.assertEqual(result.processed_zips.deleted_files, ["old_batch.zip"])

                self.assertEqual(result.reconciliation_cache.scanned, 2)
                self.assertEqual(result.reconciliation_cache.deleted, 1)
                self.assertEqual(result.reconciliation_cache.kept, 1)
                self.assertEqual(result.reconciliation_cache.deleted_files, ["old_snapshot.json"])

                self.assertFalse(expired_zip.exists())
                self.assertFalse(expired_cache.exists())
                self.assertTrue(fresh_zip.exists())
                self.assertTrue(fresh_cache.exists())
                self.assertTrue(xml_file.exists())
            finally:
                settings.processed_dir = previous_processed_dir
                settings.reconciliation_cache_dir = previous_cache_dir
                settings.processed_zip_retention_days = previous_zip_retention
                settings.reconciliation_cache_retention_days = previous_cache_retention


if __name__ == "__main__":
    unittest.main()
