import os
import shutil
import hashlib
import stat
import json
from pathlib import Path
from datetime import datetime
from system.config import QUARANTINE_DIR, _normalize_path
from system.history.logs import add_log_entry

def _sha256(file_path):
    """Calculate SHA-256 hash of a file."""
    digest = hashlib.sha256()
    try:
        with open(file_path, "rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except Exception:
        return None

def backup_file(file_path):
    """Creates a recoverable backup of the existing file before replacing it."""
    original = Path(os.path.abspath(file_path))
    if not original.is_file():
        raise FileNotFoundError(f"Source file not found: {file_path}")

    backup_dir = Path(QUARANTINE_DIR) / "Backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Use a secure random suffix to avoid collisions if multiple repairs happen quickly
    import secrets
    suffix = secrets.token_hex(4)
    backup_name = f"{original.name}.{timestamp}.{suffix}.bak"
    backup_path = backup_dir / backup_name
    
    shutil.copy2(original, backup_path)
    # Set backup to read-only for safety
    os.chmod(backup_path, stat.S_IREAD)
    return str(backup_path)

def repair_from_trusted_source(file_path, trusted_source_path, expected_hash):
    """
    Restores a detected file using a verified, trusted replacement file.
    
    Args:
        file_path: Path to the malicious file to be repaired.
        trusted_source_path: Path to the clean replacement file.
        expected_hash: The SHA-256 hash that the replacement file must match.
    """
    original = Path(os.path.abspath(file_path))
    replacement = Path(os.path.abspath(trusted_source_path))
    
    if not replacement.is_file():
        return {"status": "FAILED", "detail": "Trusted replacement file not found."}
    
    # Verify replacement hash
    replacement_hash = _sha256(replacement)
    if not replacement_hash:
        return {"status": "FAILED", "detail": "Could not calculate hash for replacement file."}
        
    if replacement_hash.lower() != expected_hash.lower():
        return {"status": "FAILED", "detail": "Replacement file verification failed (hash mismatch)."}
    
    # Create backup first
    backup_path = None
    try:
        backup_path = backup_file(file_path)
    except Exception as e:
        return {"status": "FAILED", "detail": f"Failed to create backup: {e}"}
    
    try:
        # Perform replacement
        # Ensure we have write permissions if it was read-only
        if original.exists():
            try:
                os.chmod(original, stat.S_IWRITE)
            except Exception:
                pass # Try anyway, might be a permission issue we can't fix here
            
        shutil.copy2(replacement, original)
        
        # Verify restoration
        restored_hash = _sha256(original)
        if not restored_hash or restored_hash.lower() != expected_hash.lower():
            # Try to restore from backup if possible
            if backup_path and os.path.exists(backup_path):
                try:
                    os.chmod(original, stat.S_IWRITE)
                    shutil.copy2(backup_path, original)
                except Exception:
                    pass
            return {"status": "FAILED", "detail": "Restoration failed verification. Original file attempts to be restored from backup."}
            
        return {
            "status": "REPAIRED",
            "detail": f"File successfully restored from trusted source.",
            "backup_path": backup_path,
            "new_hash": restored_hash,
            "original_path": str(original)
        }
    except Exception as e:
        return {"status": "FAILED", "detail": f"Repair operation failed: {e}"}

def get_repair_rules(threat_type):
    """
    Returns validated repair rules for specific infection types.
    Requirement 2B: Support repair rules only for explicitly documented and validated infection types.
    """
    # Placeholder for validated rules. Currently, we don't have automated cleaning rules
    # for specific malware families that are safe without a full file replacement.
    rules = {
        # Example: "InfectionType": {"action": "remove_overlay", "description": "Removes malicious overlay data"}
    }
    return rules.get(threat_type)

def get_repair_eligibility(threat):
    """
    Determines if a threat is eligible for repair.
    """
    path = threat.get("file_path")
    behavior_types = threat.get("behavior_types") or []
    
    # Check if any automated rules apply
    has_rule = False
    for b_type in behavior_types:
        if get_repair_rules(b_type):
            has_rule = True
            break
            
    return {
        "eligible_source": True, # Always eligible for "Restore from Trusted Source"
        "eligible_rule": has_rule,
        "reason": "Restore from a trusted clean backup or use validated repair rules if available."
    }

def validate_pe_structure(file_path):
    """
    Validates the PE file structure without executing the file.
    """
    try:
        import pefile
        pe = pefile.PE(file_path, fast_load=True)
        pe.close()
        return True
    except Exception:
        return False
