import os
import shutil
import hashlib
import unittest
from pathlib import Path
import tempfile
import stat

from system.quarantines.repair import (
    repair_from_trusted_source,
    backup_file,
    get_repair_eligibility,
    _sha256
)

class TestFileRepair(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)
        
        # Create a "malicious" file
        self.malicious_file = self.base_path / "malicious.exe"
        self.malicious_file.write_bytes(b"malicious content")
        
        # Create a "clean" replacement
        self.clean_file = self.base_path / "clean.exe"
        self.clean_content = b"clean content"
        self.clean_file.write_bytes(self.clean_content)
        self.clean_hash = hashlib.sha256(self.clean_content).hexdigest()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_valid_trusted_replacement(self):
        """Test repair with a valid replacement and matching hash."""
        result = repair_from_trusted_source(
            str(self.malicious_file),
            str(self.clean_file),
            self.clean_hash
        )
        self.assertEqual(result["status"], "REPAIRED")
        self.assertTrue(os.path.exists(result["original_path"]))
        self.assertEqual(_sha256(result["original_path"]), self.clean_hash)
        self.assertTrue(os.path.exists(result["backup_path"]))

    def test_incorrect_replacement_hash(self):
        """Test repair with a mismatching hash."""
        wrong_hash = "a" * 64
        result = repair_from_trusted_source(
            str(self.malicious_file),
            str(self.clean_file),
            wrong_hash
        )
        self.assertEqual(result["status"], "FAILED")
        self.assertIn("hash mismatch", result["detail"])
        # Original file should still be malicious
        self.assertEqual(self.malicious_file.read_bytes(), b"malicious content")

    def test_missing_replacement(self):
        """Test repair when the replacement file is missing."""
        result = repair_from_trusted_source(
            str(self.malicious_file),
            "non_existent_file.exe",
            self.clean_hash
        )
        self.assertEqual(result["status"], "FAILED")
        self.assertIn("not found", result["detail"])

    def test_file_permission_error(self):
        """Test handling of permission errors on the original file."""
        # Make the file read-only and try to replace it (repair_from_trusted_source handles this by trying chmod)
        # To actually simulate a failure, we'd need a way to block chmod, but we can test if it succeeds even if read-only.
        os.chmod(self.malicious_file, stat.S_IREAD)
        result = repair_from_trusted_source(
            str(self.malicious_file),
            str(self.clean_file),
            self.clean_hash
        )
        self.assertEqual(result["status"], "REPAIRED")
        self.assertEqual(_sha256(str(self.malicious_file)), self.clean_hash)

    def test_eligibility(self):
        """Test repair eligibility logic."""
        threat = {
            "file_path": str(self.malicious_file),
            "behavior_types": ["Ransomware"]
        }
        eligibility = get_repair_eligibility(threat)
        self.assertTrue(eligibility["eligible_source"])
        # Currently no rules are implemented, so eligible_rule should be False
        self.assertFalse(eligibility["eligible_rule"])

    def test_backup_creation(self):
        """Test that a backup is correctly created."""
        backup_path = backup_file(str(self.malicious_file))
        self.assertTrue(os.path.exists(backup_path))
        self.assertEqual(_sha256(backup_path), _sha256(str(self.malicious_file)))
        # Backup should be read-only
        self.assertFalse(os.access(backup_path, os.W_OK))

if __name__ == "__main__":
    unittest.main()
