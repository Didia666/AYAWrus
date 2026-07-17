import os
import threading
# ===========================================
# PATHS
# ===========================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SELECTED_FEATURES_FILE = os.path.join(BASE_DIR, "selected_features.pkl")


# ===========================================
# SCANNINNG
# ===========================================


HEADER_PEEK_SIZE = 4096  # enough for magic to fingerprint almost anything
KNOWN_SKIP_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".mp3", ".mp4", ".pdf", ".zip",
                   ".dll", ".sys", ".ttf", ".woff", ".ico", ".avi", ".mkv", ".wav"}
KNOWN_SCRIPT_EXTS = {".ps1", ".bat", ".cmd", ".vbs", ".py", ".sh"}
SUS_WRODS = [
    "powershell",
    "cmd.exe",
    "downloadstring",
    "base64",
    "invoke-webrequest",
    "start-process",
    "reg add",
    "taskkill",
]


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
    
def normalize_user_path(path: str) -> str:
    try:
        if not isinstance(path, str):
            return path
        p = os.path.abspath(path)
        parts = p.split(os.sep)
        # Windows: C:\Users\<name>\...
        if len(parts) > 3 and parts[1].lower() == "users":
            cur = os.path.basename(current_user_profile())
            if parts[2].lower() != cur.lower():
                candidate = os.sep.join([parts[0], parts[1], cur] + parts[3:])
                if os.path.exists(candidate):
                    return candidate
        return path
    except Exception:
        return path
    
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

# ===========================================
# TELEGRAM
# ===========================================
CONFIG_FILE = "../config.json"