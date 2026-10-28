"""
scan_targets_mock.py - FAKE data for the "Likely Targets" tab. DEV ONLY.

Each function below returns a dict in the exact JSON shape the tab reads
(see the big comment at the top of ui/scan_targets.py).
Nothing here touches the real filesystem, the model, or any threads.
Safe to delete once DEV_MODE = False in scan_targets.py.
"""
import ntpath
import random

# ---- Fake data tuning (change here) ----
SEED = 7                        # same seed = same fake files every run
USER_DIR = "C:\\Users\\Kay"
HIGH_MIN_SCORE = 0.75           # score >= this -> "high"
MEDIUM_MIN_SCORE = 0.50         # score >= this -> "medium", below -> "low"
PARTIAL_FILE_CAP = 120          # how many files the "Partial" mock keeps
ERROR_SAVED_FILE_COUNT = 40     # how many "saved results" the "Error" mock keeps
FILES_SCANNED = 52340
FILES_SKIPPED = 87
LAST_SCANNED = "06:53"

_NAME_WORDS = ["thesis", "budget", "report", "notes", "resume", "invoice", "slides", "lab",
               "draft", "final", "schedule", "grades", "proposal", "chapter", "summary", "scan"]

# category -> how the fake files for it are generated
_SPEC = {
    "documents": {
        "score": 0.92, "source": "rule+model",
        "exts": [".docx", ".xlsx", ".pdf", ".pptx", ".txt"],
        "folders": [("Documents", 120), ("Desktop", 40), ("Downloads", 60)],   # (subfolder, how many files)
        "reasons": [
            "extension list found in sample + {folder} folder hinted",
            "sample contains a list of office file extensions",
            "{folder} is a common target folder for this kind of behavior",
        ],
    },
    "images": {
        "score": 0.71, "source": "model",
        "exts": [".jpg", ".png", ".heic"],
        "folders": [("Pictures", 70), ("Pictures\\Screenshots", 30)],
        "reasons": [
            "model predicts image targeting from the sample's behavior",
            "image extensions seen in sample strings",
        ],
    },
}

# a few fixed rows so the demo always shows the same top items
_HAND_PICKED = [
    ("Documents", "thesis.docx", "documents", 0.93, "extension list found in sample + Documents folder hinted"),
    ("Documents", "budget.xlsx", "documents", 0.91, "extension list found in sample + Documents folder hinted"),
    ("Pictures", "family_trip.jpg", "images", 0.74, "model predicts image targeting from the sample's behavior"),
]


def _risk_for(score):
    if score >= HIGH_MIN_SCORE:
        return "high"
    if score >= MEDIUM_MIN_SCORE:
        return "medium"
    return "low"


def _make_files(rng):
    files = []
    for sub, name, cat, score, reason in _HAND_PICKED:
        files.append({"path": f"{USER_DIR}\\{sub}\\{name}", "category": cat,
                      "risk": _risk_for(score), "score": score, "reason": reason})
    for cat, spec in _SPEC.items():
        for sub, n in spec["folders"]:
            for i in range(n):
                score = max(0.05, min(0.99, spec["score"] + rng.uniform(-0.40, 0.07)))
                files.append({
                    "path": f"{USER_DIR}\\{sub}\\{rng.choice(_NAME_WORDS)}_{i + 1}{rng.choice(spec['exts'])}",
                    "category": cat,
                    "risk": _risk_for(score),
                    "score": round(score, 2),
                    "reason": rng.choice(spec["reasons"]).format(folder=sub.split("\\")[-1]),
                })
    return files


def _recount(data):
    """Keeps the counts consistent with whatever files the mock ended up with."""
    counts, by_folder = {}, {}
    for f in data["files"]:
        counts[f["category"]] = counts.get(f["category"], 0) + 1
        folder = ntpath.dirname(f["path"])
        by_folder[folder] = by_folder.get(folder, 0) + 1
    for name, info in data["categories"].items():
        info["count"] = counts.get(name, 0)
    data["at_risk_count"] = len(data["files"])
    data["by_folder"] = by_folder
    return data


def scary():
    data = {
        "sample": "suspicious.exe", "state": "done", "scan_complete": True,
        "files_scanned": FILES_SCANNED, "files_skipped_permission": FILES_SKIPPED,
        "at_risk_count": 0, "last_scanned": LAST_SCANNED,
        "categories": {
            "documents": {"score": 0.92, "source": "rule+model"},
            "images": {"score": 0.71, "source": "model"},
            "media": {"score": 0.08, "source": "model"},
        },
        "flagged": ["documents", "images"],
        "by_folder": {},
        "files": _make_files(random.Random(SEED)),
    }
    return _recount(data)


def clean():
    return {
        "sample": "game.exe", "state": "done", "scan_complete": True,
        "files_scanned": FILES_SCANNED, "files_skipped_permission": FILES_SKIPPED,
        "at_risk_count": 0, "last_scanned": LAST_SCANNED,
        "categories": {
            "documents": {"score": 0.03, "source": "model", "count": 0},
            "images": {"score": 0.02, "source": "model", "count": 0},
        },
        "flagged": [], "by_folder": {}, "files": [],
    }


def partial():
    data = scary()
    data["files"] = random.Random(SEED).sample(data["files"], PARTIAL_FILE_CAP)
    data.update(state="partial", scan_complete=False, files_scanned=18400,
                message="Partial results: scan limit reached")
    return _recount(data)


def loading():
    data = scary()
    data["files"] = []
    data.update(state="loading", last_scanned=None, files_scanned=None, files_skipped_permission=None)
    _recount(data)
    data["at_risk_count"] = None       # unknown while loading
    return data


def error():
    data = scary()
    data["files"] = random.Random(SEED).sample(data["files"], ERROR_SAVED_FILE_COUNT)
    data.update(state="error", scan_complete=False,
                message="File moved or deleted; showing saved results only")
    return _recount(data)


def unsupported():
    return {
        "sample": "notes.txt", "state": "unsupported", "scan_complete": False,
        "files_scanned": None, "files_skipped_permission": None, "at_risk_count": None,
        "last_scanned": None, "categories": {}, "flagged": [], "by_folder": {}, "files": [],
    }


# label shown in the dev dropdown -> function that builds that mock
MOCKS = {
    "Scary sample": scary,
    "Clean file": clean,
    "Partial": partial,
    "Loading": loading,
    "Error": error,
    "Unsupported": unsupported,
}


def get_mock(name):
    return MOCKS[name]()