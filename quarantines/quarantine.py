import os
import json
import shutil
import stat
from datetime import datetime
from config import QUARANTINE_INDEX_FILE, QUARANTINE_DIR, _normalize_path, DETECTED_MALWARE, DETECTED_SUSPICIOUS
from history.logs import load_log, add_log_entry


def _load_quarantine_index():
    if not os.path.exists(QUARANTINE_INDEX_FILE):
        with open(QUARANTINE_INDEX_FILE, "w") as f:
            json.dump([], f, indent=4)
    with open(QUARANTINE_INDEX_FILE, "r") as f:
        return json.load(f)

def _save_quarantine_index(entries):
    with open(QUARANTINE_INDEX_FILE, "w") as f:
        json.dump(entries, f, indent=4)

def quarantine_file(file_path):
    print(f"Starting quarantine for: {file_path}")
    try:
        # First check if already in quarantine index!
        idx = _load_quarantine_index()
        normalized_file_path = _normalize_path(file_path)
        for entry in idx:
            if _normalize_path(entry.get("original_path")) == normalized_file_path:
                print(f"Already in quarantine: {file_path}")
                return f"{file_path} -> ALREADY IN QUARANTINE"
        
        file_name = os.path.basename(file_path)
        safe_name = file_name + ".quarantine"
        dest_path = os.path.join(QUARANTINE_DIR, safe_name)
        counter = 1
        while os.path.exists(dest_path):
            safe_name = f"{file_name}_{counter}.quarantine"
            dest_path = os.path.join(QUARANTINE_DIR, safe_name)
            counter += 1

        # Move file to quarantine if it exists at original location!
        if os.path.exists(file_path):
            print(f"Moving {file_path} to {dest_path}")
            shutil.move(file_path, dest_path)
        else:
            # Check if file is already in quarantine (maybe from auto scan)
            possible_quarantined_files = os.listdir(QUARANTINE_DIR) if os.path.exists(QUARANTINE_DIR) else []
            for f in possible_quarantined_files:
                if f == safe_name or (file_name in f and f.endswith('.quarantine')):
                    dest_path = os.path.join(QUARANTINE_DIR, f)
                    print(f"Found already quarantined at: {dest_path}")
                    break
        
        if os.path.exists(dest_path):
            os.chmod(dest_path, stat.S_IREAD)  # Read-only
        
        # capture metadata from history log
        prob = None
        result = None
        try:
            hist = load_log()
            for e in reversed(hist):
                if e.get("file_path") == file_path:
                    prob = e.get("probability")
                    result = e.get("result")
                    break
        except Exception:
            pass

        entry = {
            "dest_path": dest_path,
            "original_path": file_path,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "size": os.path.getsize(dest_path) if os.path.exists(dest_path) else 0,
            "result": result,
            "probability": prob,
        }
        idx.append(entry)
        _save_quarantine_index(idx)
        
        # Log quarantine action!
        add_log_entry(file_path, "QUARANTINED", prob, f"Quarantined to {dest_path}")

        print(f"Successfully quarantined: {file_path}")
        return f"{file_path} -> MOVED TO QUARANTINE"
    except Exception as e:
        print(f"Error quarantining {file_path}: {e}")
        return f"Failed to quarantine {file_path}: {e}"
    
def process_quarantine():
    if not DETECTED_MALWARE:
        print("\nNo malware detected.")
        return

    print("\n=== MALWARE DETECTED ===")
    for i, file in enumerate(DETECTED_MALWARE):
        print(f"[{i}] {file}")

    print("\nChoose files to quarantine:")
    print("Example: 0,2,3  or  'all'")

    choice = input("> ")

    if choice.lower() == "all":
        for file in DETECTED_MALWARE:
            print(quarantine_file(file))
        return
    
    if DETECTED_SUSPICIOUS:
        print("\n=== SUSPICIOUS FILES ===")
        for f in DETECTED_SUSPICIOUS:
            print(f" - {f}")
    try:
        indexes = [int(x) for x in choice.split(",")]
        for idx in indexes:
            if 0 <= idx < len(DETECTED_MALWARE):
                print(quarantine_file(DETECTED_MALWARE[idx]))
    except ValueError:
        print("Invalid input. Skipping quarantine.")

def list_quarantine_items():
    entries = _load_quarantine_index()
    # annotate existence so UI can show missing items instead of hiding them
    for e in entries:
        # Check both original dest_path and current quarantine dir
        dest = e.get("dest_path", "")
        if not os.path.exists(dest):
            # Try checking in current QUARANTINE_DIR by filename
            fname = os.path.basename(dest)
            alt_dest = os.path.join(QUARANTINE_DIR, fname)
            e['_exists'] = os.path.exists(alt_dest)
            if e['_exists']:
                e['_alt_dest'] = alt_dest
        else:
            e['_exists'] = True
    return entries

def is_quarantined(file_path: str) -> bool:
    entries = _load_quarantine_index()
    normalized_fp = _normalize_path(file_path)
    return any(_normalize_path(e.get("original_path")) == normalized_fp for e in entries)

def restore_file(dest_path):
    print(f"Restoring file from {dest_path}")
    entries = _load_quarantine_index()
    normalized_dest = _normalize_path(dest_path)
    for i, e in enumerate(entries):
        entry_dest = e.get("dest_path", "")
        if _normalize_path(entry_dest) == normalized_dest:
            original = e.get("original_path")
            prob = e.get("probability")
            # Check if dest_path exists; if not, try QUARANTINE_DIR
            actual_dest = dest_path
            if not os.path.exists(dest_path):
                fname = os.path.basename(entry_dest)
                actual_dest = os.path.join(QUARANTINE_DIR, fname)
                if not os.path.exists(actual_dest):
                    return "File not found in quarantine"
            
            try:
                os.makedirs(os.path.dirname(original), exist_ok=True)
                shutil.move(actual_dest, original)
                # Restore normal permissions!
                os.chmod(original, 0o644)  # Read/write for user, read for others
                entries.pop(i)
                _save_quarantine_index(entries)
                # Log restore action!
                add_log_entry(original, "RESTORED", prob, f"Restored from {actual_dest}")
                print(f"Restored file to: {original}")
                return f"Restored to {original}"
            except Exception as err:
                print(f"Error restoring: {err}")
                return f"Failed to restore: {err}"
    print("Item not found in quarantine index")
    return "Item not found in quarantine index"

def delete_file(dest_path):
    try:
        # Get original path from index first for logging!
        original_path = None
        prob = None
        entries = _load_quarantine_index()
        normalized_dest = _normalize_path(dest_path)
        found_idx = -1
        for i, e in enumerate(entries):
            if _normalize_path(e.get("dest_path")) == normalized_dest:
                original_path = e.get("original_path")
                prob = e.get("probability")
                found_idx = i
                break
        
        # Try deleting the file
        actual_dest = dest_path
        if not os.path.exists(dest_path) and found_idx >= 0:
            # Try alternative path
            entry_dest = entries[found_idx].get("dest_path", "")
            fname = os.path.basename(entry_dest)
            actual_dest = os.path.join(QUARANTINE_DIR, fname)
        
        if os.path.exists(actual_dest):
            os.remove(actual_dest)
        
        # Remove from index
        if found_idx >= 0:
            entries.pop(found_idx)
            _save_quarantine_index(entries)
        
        # Log deletion!
        if original_path:
            add_log_entry(original_path, "DELETED", prob, f"Deleted from quarantine at {actual_dest}")
        
        return "Deleted"
    except Exception as err:
        return f"Failed to delete: {err}"