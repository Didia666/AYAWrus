import os
import json
from datetime import datetime
from system.config import ALLOWED_THREATS_FILE
from system.quarantines.quarantine import quarantine_file

def _load_allowed_threats():
    if not os.path.exists(ALLOWED_THREATS_FILE):
        with open(ALLOWED_THREATS_FILE, "w") as f:
            json.dump([], f, indent=4)
    with open(ALLOWED_THREATS_FILE, "r") as f:
        return json.load(f)

def _save_allowed_threats(items):
    with open(ALLOWED_THREATS_FILE, "w") as f:
        json.dump(items, f, indent=4)

def list_allowed_threats():
    return _load_allowed_threats()

def is_allowed(file_path: str) -> bool:
    return any(x.get("path") == file_path for x in _load_allowed_threats())

def allow_threat(file_path: str, severity: str, result: str):
    items = _load_allowed_threats()
    if not any(x.get("path") == file_path for x in items):
        items.append({
            "path": file_path,
            "severity": severity,
            "result": result,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        _save_allowed_threats(items)
    return "Allowed"

def disallow_threat(file_path: str):
    items = _load_allowed_threats()
    items = [x for x in items if x.get("path") != file_path]
    _save_allowed_threats(items)
    # if the file still exists at original path, quarantine it
    try:
        if os.path.exists(file_path):
            quarantine_file(file_path)
            return "Moved to quarantine"
    except Exception:
        pass
    return "Removed from allowed"
