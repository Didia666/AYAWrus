import os
import json
from datetime import datetime
from system.config import LOG_FILE, _log_buffer, _log_buffer_lock, _buffering_active



def save_log(data):
    with open(LOG_FILE, "w") as f:
        json.dump(data, f, indent=4)

def load_log(limit=None):
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w") as f:
            json.dump([], f, indent=4)
    try:
        with open(LOG_FILE, "r") as f:
            entries = json.load(f)
            if limit is not None:
                return entries[-limit:]
            return entries
    except json.JSONDecodeError as e:
        print(f"Log file is corrupt, creating new one: {e}")
        # Backup corrupt file
        backup_file = LOG_FILE + ".bak"
        if os.path.exists(backup_file):
            os.remove(backup_file)
        os.rename(LOG_FILE, backup_file)
        # Create fresh log
        with open(LOG_FILE, "w") as f:
            json.dump([], f, indent=4)
        return []

def begin_log_buffer():
    """Call once at the start of a scan. Loads existing log into memory
    and switches add_log_entry into buffered mode."""
    global _log_buffer, _buffering_active
    with _log_buffer_lock:
        _log_buffer = load_log()   # one read for the whole scan
        _buffering_active = True

def flush_log_buffer():
    """Call once at the end of a scan. Writes the whole log ONCE."""
    global _buffering_active
    with _log_buffer_lock:
        _buffering_active = False
        save_log(_log_buffer)      # one write for the whole scan

def add_log_entry(file_path, result, probability=None, details=None):
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "file_path": file_path,
        "result": result,
        "probability": probability,
        "details": details
    }
    with _log_buffer_lock:
        if _buffering_active:
            _log_buffer.append(entry)   # in-memory only, no disk I/O
            return
    # fallback: old behavior for one-off calls outside a scan
    log = load_log()
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
