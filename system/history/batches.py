import os
import sys
import json
import uuid
import time
from datetime import datetime
from typing import Optional, Dict, Any, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from system.config import LOG_FILE


_BATCH_INDEX_FILE = os.path.join(os.path.dirname(LOG_FILE), "scan_batches.json")

_current_batch: Optional[Dict[str, Any]] = None


def _load_batches() -> List[Dict[str, Any]]:
    if not os.path.exists(_BATCH_INDEX_FILE):
        return []
    try:
        with open(_BATCH_INDEX_FILE, "r") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        return []
    except (json.JSONDecodeError, OSError):
        return []


def _save_batches(batches: List[Dict[str, Any]]) -> None:
    tmp = _BATCH_INDEX_FILE + ".tmp"
    try:
        with open(tmp, "w") as f:
            json.dump(batches, f, indent=2)
        os.replace(tmp, _BATCH_INDEX_FILE)
    except Exception:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass
        raise


def current_batch_id() -> Optional[str]:
    global _current_batch
    if _current_batch is None:
        return None
    return _current_batch.get("id")


def is_batch_active() -> bool:
    return _current_batch is not None


def begin_batch(scan_type: str = "custom", target: str = "") -> Dict[str, Any]:
    global _current_batch
    if _current_batch is not None:
        return _current_batch
    now = datetime.now()
    batch_id = "B" + uuid.uuid4().hex[:15].upper()
    batch: Dict[str, Any] = {
        "id": batch_id,
        "scan_type": scan_type.lower() if scan_type else "custom",
        "target": target or "",
        "started_at_ms": int(now.timestamp() * 1000),
        "started_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "completed_at_ms": None,
        "completed_at": None,
        "elapsed_ms": 0,
        "total_files": 0,
        "clean_count": 0,
        "threat_count": 0,
        "suspicious_count": 0,
        "malicious_count": 0,
        "error_count": 0,
        "status": "RUNNING",
    }
    _current_batch = batch
    return batch


def increment_batch_counters(result: str) -> None:
    global _current_batch
    if _current_batch is None:
        return
    try:
        _current_batch["total_files"] = int(_current_batch.get("total_files", 0)) + 1
        r = (result or "").upper()
        if r == "CLEAN" or r == "EXCLUDED" or r == "SKIP":
            _current_batch["clean_count"] = int(_current_batch.get("clean_count", 0)) + 1
        elif r == "MALICIOUS":
            _current_batch["malicious_count"] = int(_current_batch.get("malicious_count", 0)) + 1
            _current_batch["threat_count"] = int(_current_batch.get("threat_count", 0)) + 1
        elif r == "SUSPICIOUS":
            _current_batch["suspicious_count"] = int(_current_batch.get("suspicious_count", 0)) + 1
            _current_batch["threat_count"] = int(_current_batch.get("threat_count", 0)) + 1
        elif r == "ERROR":
            _current_batch["error_count"] = int(_current_batch.get("error_count", 0)) + 1
        else:
            _current_batch["clean_count"] = int(_current_batch.get("clean_count", 0)) + 1
    except Exception:
        pass


def end_batch(status: str = "COMPLETED") -> Optional[Dict[str, Any]]:
    global _current_batch
    batch = _current_batch
    if batch is None:
        return None
    end_ms = int(time.time() * 1000)
    start_ms = int(batch.get("started_at_ms") or end_ms)
    batch["completed_at_ms"] = end_ms
    batch["completed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    batch["elapsed_ms"] = max(0, end_ms - start_ms)
    batch["status"] = (status or "COMPLETED").upper()
    batches = _load_batches()
    batches.insert(0, batch)
    try:
        _save_batches(batches)
    except Exception:
        pass
    _current_batch = None
    return batch


def list_batches(limit: int = 50) -> List[Dict[str, Any]]:
    batches = _load_batches()
    if limit and limit > 0:
        return batches[: int(limit)]
    return batches


def get_batch(batch_id: str) -> Optional[Dict[str, Any]]:
    if not batch_id:
        return None
    for b in _load_batches():
        if b.get("id") == batch_id:
            return b
    return None


def delete_batch(batch_id: str) -> bool:
    if not batch_id:
        return False
    batches = _load_batches()
    new_batches = [b for b in batches if b.get("id") != batch_id]
    if len(new_batches) == len(batches):
        return False
    _save_batches(new_batches)
    return True
