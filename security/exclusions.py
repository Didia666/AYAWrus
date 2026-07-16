import os
import json

from config import EXCLUSIONS_FILE

# Exclusions
def _load_exclusions():
    if not os.path.exists(EXCLUSIONS_FILE):
        with open(EXCLUSIONS_FILE, "w") as f:
            json.dump([], f, indent=4)
    with open(EXCLUSIONS_FILE, "r") as f:
        return json.load(f)

def _save_exclusions(items):
    with open(EXCLUSIONS_FILE, "w") as f:
        json.dump(items, f, indent=4)

def list_exclusions():
    return _load_exclusions()

def add_exclusion(path: str):
    items = _load_exclusions()
    if path not in items:
        items.append(path)
        _save_exclusions(items)

def remove_exclusion(path: str):
    items = _load_exclusions()
    items = [p for p in items if p != path]
    _save_exclusions(items)

def is_excluded(p: str, excluded_roots=None) -> bool:
    try:
        p_norm = os.path.abspath(p).lower()
        roots = excluded_roots if excluded_roots is not None else [os.path.abspath(e).lower() for e in _load_exclusions()]
        for ex_norm in roots:
            if p_norm == ex_norm or p_norm.startswith(ex_norm + os.sep):
                return True
    except Exception:
        pass
    return False