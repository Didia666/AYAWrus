import os
import threading
# ===========================================
# PATHS
# ===========================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SELECTED_FEATURES_FILE = os.path.join(BASE_DIR, "selected_features.pkl")

# ===========================================
# QUARANTINE
# ===========================================

QUARANTINE_DIR = os.path.join(BASE_DIR, "Quarantine")
QUARANTINE_INDEX_FILE = os.path.join(QUARANTINE_DIR, "quarantine_index.json")
DETECTED_MALWARE = []
DETECTED_SUSPICIOUS = []

os.makedirs(QUARANTINE_DIR, exist_ok=True)
print(f"Quarantine folder: {QUARANTINE_DIR}")
# Create folder if it doesn't exist

if not os.path.exists(QUARANTINE_DIR):
    os.makedirs(QUARANTINE_DIR)

def _normalize_path(path):
    """Normalize path for consistent comparison"""
    if not path:
        return ""
    try:
        return os.path.normcase(os.path.abspath(os.path.normpath(path)))
    except Exception:
        return str(path)
    
# ===========================================
# ALLOWED AND EXCLUSIONS
# ===========================================

ALLOWED_THREATS_FILE = os.path.join(BASE_DIR, "allowed_threats.json")
EXCLUSIONS_FILE = os.path.join(BASE_DIR, "exclusions.json")

# ===========================================
# HISTORY LOG
# ===========================================

LOG_FILE = os.path.join(BASE_DIR, "history_log.json")
_log_buffer = []
_log_buffer_lock = threading.Lock()
_buffering_active = False

# ===========================================
# NOTIFICATIONS
# ===========================================

CONFIG_FILE = "../config.json"


# ===========================================
# DIRECTORIES
# ===========================================

def current_user_profile():
    up = os.environ.get("USERPROFILE")
    if up and isinstance(up, str) and os.path.isdir(up):
        return up
    # fallback
    return os.path.expanduser("~")

user_profile = current_user_profile()

QUICK_SCAN_DIRS = [
    os.path.join(user_profile, "Downloads"),
    os.path.join(user_profile, "Desktop"),
    os.path.join(user_profile, "AppData", "Local", "Temp"),
    os.path.join(os.environ.get("WINDIR", "C:\Windows"), "Temp"),
]

REGULAR_SCAN_DIRS = [
    os.environ.get("SystemDrive", "C:") + "\\"
]

SKIP_DIRS = [
    os.path.join(os.environ.get("WINDIR", "C:\Windows")),
    os.path.join(os.environ.get("ProgramFiles", "C:\Program Files")),
    os.path.join(os.environ.get("ProgramFiles(x86)", "C:\Program Files (x86)")),
    os.path.join(os.environ.get("SystemDrive", "C:") + "\$Recycle.Bin"),
    os.path.join(os.environ.get("SystemDrive", "C:") + "\System Volume Information")
]