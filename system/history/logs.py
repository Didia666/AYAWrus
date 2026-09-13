import os
import json
from datetime import datetime
from system.config import LOG_FILE, _log_buffer, _log_buffer_lock, _buffering_active

try:
    from system.history.batches import (
        begin_batch as _begin_batch,
        end_batch as _end_batch,
        increment_batch_counters as _inc_batch,
        current_batch_id as _current_batch_id,
        is_batch_active as _is_batch_active,
    )
    _BATCHES_AVAILABLE = True
except Exception:
    _BATCHES_AVAILABLE = False

    def _begin_batch(*a, **kw):
        return {}

    def _end_batch(*a, **kw):
        return None

    def _inc_batch(*a, **kw):
        pass

    def _current_batch_id():
        return None

    def _is_batch_active():
        return False



def save_log(data):
    tmp_path = LOG_FILE + ".tmp"
    try:
        with open(tmp_path, "w") as f:
            json.dump(data, f, indent=4)
        os.replace(tmp_path, LOG_FILE)
    except Exception:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass
        raise

def _load_log_from_disk():
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w") as f:
            json.dump([], f, indent=4)
        return []
    try:
        with open(LOG_FILE, "r") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"Log file is corrupt, creating new one: {e}")
        backup_file = LOG_FILE + ".bak"
        if os.path.exists(backup_file):
            try:
                os.remove(backup_file)
            except Exception:
                pass
        try:
            os.rename(LOG_FILE, backup_file)
        except Exception:
            pass
        with open(LOG_FILE, "w") as f:
            json.dump([], f, indent=4)
        return []

def load_log(limit=None):
    with _log_buffer_lock:
        if _buffering_active:
            entries = list(_log_buffer)
        else:
            entries = _load_log_from_disk()
    if limit is not None:
        return entries[-limit:]
    return entries

def begin_log_buffer(scan_type: str = "custom", target: str = ""):
    """Call once at the start of a scan. Loads existing log into memory,
    switches add_log_entry into buffered mode, and opens a new scan batch."""
    global _log_buffer, _buffering_active
    with _log_buffer_lock:
        if not _buffering_active:
            _log_buffer = _load_log_from_disk()
            _buffering_active = True
    try:
        _begin_batch(scan_type=scan_type, target=target)
    except Exception:
        pass

def flush_log_buffer(status: str = "COMPLETED"):
    """Call once at the end of a scan. Writes the whole log ONCE,
    closes the current scan batch, and returns a snapshot of the flushed entries."""
    global _buffering_active
    with _log_buffer_lock:
        snapshot = list(_log_buffer)
        if _buffering_active:
            _buffering_active = False
            save_log(_log_buffer)
    try:
        _end_batch(status=status)
    except Exception:
        pass
    return snapshot

def add_log_entry(file_path, result, probability=None, details=None):
    batch_id = None
    try:
        _inc_batch(result)
        if _is_batch_active():
            batch_id = _current_batch_id()
    except Exception:
        batch_id = None
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "file_path": file_path,
        "result": result,
        "probability": probability,
        "details": details,
        "batch_id": batch_id,
    }
    with _log_buffer_lock:
        if _buffering_active:
            _log_buffer.append(entry)
            return
    log = _load_log_from_disk()
    log.append(entry)
    save_log(log)



def view_logs():
    log = load_log()

    # Filter entries: keep only MALICIOUS or SUSPICIOUS
    filtered = [
        entry for entry in log
        if entry["result"] in ("MALICIOUS", "SUSPICIOUS")
    ]

    print("\n=== MALWARE & SUSPICIOUS LOGS ===")

    if not filtered:
        print("No malware or suspicious activity found in logs.")
        return

    for entry in filtered:
        print(f"\nTime: {entry['timestamp']}")
        print(f"File: {entry['file_path']}")
        print(f"Result: {entry['result']}")

        if entry.get("probability") is not None:
            print(f"Probability: {entry['probability']:.4f}")

        if entry.get("details"):
            print(f"Details: {entry['details']}")

        print("-" * 40)
