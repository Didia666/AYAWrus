import dearpygui.dearpygui as dpg
from ui.theme import COLORS
import threading
import time
import sys
import os
import psutil
import traceback
from ui.activity_feed import _rebuild_activity_feed, _rebuild_activity_feed_from_data
from ui.dashboard import refresh_dashboard_stats, animate_number
from ui.history import _rebuild_history
from ui.scan_layout import (build_scan_card, apply_card_states, register_scan_layout,
                            build_ready_panel, rebuild_custom_row, reset_ready_state)
from ui.scan_pipeline import build_pipeline_panel, set_pipeline_step
from ui.scrollbar_theme import apply_slim_scrollbar
from ui.scan_explain import init_explain, open_explain
from ui.scan_picker import init_picker, open_picker
from ui.scan_threats import (build_threats_panel, build_threats_table, add_threat_row, add_empty_row,
                             reset_threat_rows, update_selection_ui, apply_selection)
from concurrent.futures import (
    ThreadPoolExecutor,
    wait,
    FIRST_COMPLETED,
)
from system.scanner.xai_scheduler import (
    get_xai_report,
    get_xai_status,
)
from system.scanner.file_scan import classify_file
# Add parent directory to path to import Malware_System
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_api_server_started = False

try:
    import system.quarantines as qq
    import system.config as cfg
    import system.security.exclusions as se
    import system.scanner.file_scan as sf
    import system.scanner.scanner as sc
    import system.notifications.telegram as tg
    import system.history.logs as hl
    import system.history.logs as hs
    from system.history.logs import begin_log_buffer, flush_log_buffer
    from system.notifications import enqueue_threat_notification

    BACKEND_AVAILABLE = True
    BACKEND_LOAD_ERROR = ""
except Exception as e:
    print(f"Warning [ui/scan.py]: Could not load backend dependency while initializing scan UI: {e}")
    BACKEND_AVAILABLE = False
    BACKEND_LOAD_ERROR = f"{type(e).__name__}: {e}"

#scan.py

CARD_GAP = 20
CONTENT_WIDTH = 400 * 3 + CARD_GAP * 2  # 1240 — shared by cards row and empty-state container
SELECTED_SCAN = "quick"
SCAN_IN_PROGRESS = False
CURRENT_CUSTOM_PATH = ""
DETECTED_THREATS = []
SELECTED_QUARANTINE_ITEMS = set()

_PROGRESS_COUNTER_LOCK = threading.Lock()
_PROGRESS_FILES_SCANNED = 0
_PROGRESS_THREATS_FOUND = 0
_PROGRESS_CURRENT_NAME = ""
_PROGRESS_TOTAL_FILES = 0
_PROGRESS_PHASE = "IDLE"
_PROGRESS_START_TIME = 0.0
_PROGRESS_TICKER_RUNNING = False

SCAN_MAX_WORKERS = 4
SCAN_MAX_PENDING = 8

SCAN_TYPES = [
    {"key": "quick", "icon": "zap", "label": "Quick Scan", "subtitle": "Checks common areas"},
    {"key": "full", "icon": "globe", "label": "Full Scan", "subtitle": "Checks all drives and files"},
    {"key": "custom", "icon": "folder_search", "label": "Custom Scan", "subtitle": "Choose specific folders"},
]

# Define malware detection steps with descriptions and icons
DETECTION_STEPS = [
    {"title": "File\nSelected", "icon": "search", "description": "Step 1: The selected file is loaded into the system. Its location and basic information are checked to ensure the file can be safely analyzed."},
    {"title": "File Type\nVerification", "icon": "monitor_cog", "description": "Step 2: The system verifies that the file is a valid Windows executable by examining its internal file signature instead of relying only on the file extension. This helps detect files that may have been renamed to hide their true type."},
    {"title": "PE Analysis", "icon": "chart_area", "description": "Step 3: The internal structure of the executable is examined. The system analyzes important information such as program sections, imported system functions, and data patterns that may indicate suspicious behavior."},
    {"title": "Feature\nExtraction", "icon": "chart_bar", "description": "Step 4: The system collects 168 measurable characteristics from the file, including its structure, metadata, imported functions, and byte patterns. These characteristics act as clues that help distinguish between legitimate software and malware."},
    {"title": "Random\nForest AI", "icon": "shield_cog", "description": "Step 5: The extracted characteristics are analyzed by an Artificial Intelligence (AI) model called Random Forest. The model compares the file's patterns with thousands of previously learned examples of both safe and malicious software before making a decision."},
    {"title": "Prediction", "icon": "shield_check", "description": "Step 6: Based on the analysis, the AI predicts whether the file is likely to be Benign (safe) or Malicious (potentially harmful). It also provides a confidence score that indicates how certain the prediction is."},
    {"title": "Quarantine", "icon": "octagon_alert", "description": "Step 7: If the file is identified as malicious, it is automatically moved to a secure quarantine location where it cannot be executed or interact with other files. This helps prevent potential damage while allowing the file to be reviewed or restored if needed."}
]

SELECTED_STEP = 0
g_icons = None  # Global variable to store icons for step card rebuilding
g_step_elements = []  # List to store (step_card_tag, image_tag, text_tag) for each step



def get_scan_worker_config():
    # Get physical CPU cores, ignoring hyperthreading.
    physical_cores = psutil.cpu_count(logical=False)

    if physical_cores is None:
        physical_cores = max(1, (os.cpu_count() or 2) // 2)

    # Available RAM right now, not total installed RAM.
    available_ram_gb = (
        psutil.virtual_memory().available / (1024 ** 3)
    )

    # Reserve CPU capacity for Windows and other applications.
    cpu_workers = max(1, physical_cores - 1)

    # Limit concurrency when available RAM is low.
    if available_ram_gb < 2:
        ram_workers = 1
    elif available_ram_gb < 4:
        ram_workers = 2
    elif available_ram_gb < 8:
        ram_workers = 3
    else:
        ram_workers = 6

    # Combine CPU and memory limits.
    max_workers = min(
        cpu_workers,
        ram_workers,
        6
    )

    max_workers = max(1, max_workers)

    # Keep only a small number of queued scan tasks.
    max_pending = max_workers * 2

    return max_workers, max_pending




def _select_scan(sender, app_data, user_data):
    global SELECTED_SCAN
    SELECTED_SCAN = user_data
    apply_card_states(SELECTED_SCAN)
    if not SCAN_IN_PROGRESS:
        reset_ready_state()
    _update_start_button()
    _rebuild_custom_path_controls()

def scan_card(key, icon_texture, label, subtitle, fonts, icons):
# layout lives in ui/scan_layout.py
    build_scan_card(key, icon_texture, label, subtitle, key == SELECTED_SCAN)




def _handle_click(sender, app_data):
    # First check for scan type card clicks
    for scan in SCAN_TYPES:
        tag = f"scan_{scan['key']}_card"
        if dpg.is_item_hovered(tag):
            _select_scan(sender, app_data, scan['key'])
            return
    # Now check for step card clicks
    for i, (step_tag, _, _) in enumerate(g_step_elements):
        if dpg.is_item_hovered(step_tag):
            _on_step_click(sender, app_data, i)
            return

def _rebuild_custom_path_controls():
    rebuild_custom_row(SELECTED_SCAN == "custom", CURRENT_CUSTOM_PATH, open_picker)

def _toggle_select_item(sender, app_data, user_data):
    global SELECTED_QUARANTINE_ITEMS
    file_path = user_data
    is_checked = dpg.get_value(sender)  # Get checkbox state
    print(f"Toggling {file_path}: {is_checked}")
    if is_checked:
        SELECTED_QUARANTINE_ITEMS.add(file_path)
    else:
        if file_path in SELECTED_QUARANTINE_ITEMS:
            SELECTED_QUARANTINE_ITEMS.remove(file_path)
    update_selection_ui(len(SELECTED_QUARANTINE_ITEMS), len(DETECTED_THREATS))


def _toggle_select_all(sender, app_data):
    """Select All / Clear. Only fills the same set the checkboxes use, so Quarantine Selected is unchanged."""
    all_paths = {t["file_path"] for t in DETECTED_THREATS}
    if not all_paths:
        return
    if all_paths <= SELECTED_QUARANTINE_ITEMS:
        SELECTED_QUARANTINE_ITEMS.clear()
    else:
        SELECTED_QUARANTINE_ITEMS.update(all_paths)
    apply_selection(SELECTED_QUARANTINE_ITEMS, len(DETECTED_THREATS))

def _quarantine_selected(sender, app_data):
    global DETECTED_THREATS, SELECTED_QUARANTINE_ITEMS
    print(f"Quarantining: {SELECTED_QUARANTINE_ITEMS}")
    if not SELECTED_QUARANTINE_ITEMS:
        print("No items selected!")
        return

    items_to_quarantine = list(SELECTED_QUARANTINE_ITEMS)

    try:
        with dpg.mutex():
            dpg.configure_item("quarantine_btn", enabled=False)
            if dpg.does_item_exist("start_scan_btn"):
                dpg.configure_item("start_scan_btn", enabled=False)
    except Exception:
        pass

    def _worker():
        succeeded = set()
        failed = {}
        for file_path in items_to_quarantine:
            try:
                result = qq.quarantine_file(file_path)
                print(f"Quarantine result for {file_path}: {result}")
                if isinstance(result, str) and (
                    result.endswith(" -> MOVED TO QUARANTINE")
                    or result.endswith(" -> ALREADY IN QUARANTINE")
                ):
                    succeeded.add(file_path)
                else:
                    failed[file_path] = str(result)
            except Exception as exc:
                failed[file_path] = str(exc)
                print(f"Error quarantining {file_path}: {exc}")

        # Retain all failures in the threat list and selected set for retry.
        global DETECTED_THREATS, SELECTED_QUARANTINE_ITEMS
        DETECTED_THREATS = [
            t for t in DETECTED_THREATS
            if t["file_path"] not in succeeded
        ]
        SELECTED_QUARANTINE_ITEMS = set(failed)
        for path, reason in failed.items():
            print(f"QUARANTINE FAILED (still in threat list): {path}: {reason}")

        def _after_ui():
            try:
                with dpg.mutex():
                    _rebuild_threats_table()
            except Exception as e:
                print(f"Quarantine post threats rebuild error: {e}")
            threading.Timer(0.20, _after_history).start()

        def _after_history():
            try:
                with dpg.mutex():
                    _rebuild_history()
            except Exception as e:
                print(f"Quarantine post history rebuild error: {e}")
            threading.Timer(0.20, _after_activity).start()

        def _after_activity():
            try:
                activities = []
                if BACKEND_AVAILABLE:
                    log = hl.load_log(limit=10)
                    for entry in reversed(log):
                        er = entry.get("result", "INFO")
                        ef = entry.get("file_path", "Unknown file")
                        et = entry.get("timestamp", "")
                        if er == "MALICIOUS":
                            title = f"Malware detected: {os.path.basename(ef)}"
                        elif er == "SUSPICIOUS":
                            title = f"Suspicious file: {os.path.basename(ef)}"
                        elif er == "CLEAN":
                            title = f"File scanned: {os.path.basename(ef)}"
                        elif er == "QUARANTINED":
                            title = f"File quarantined: {os.path.basename(ef)}"
                        elif er == "RESTORED":
                            title = f"File restored: {os.path.basename(ef)}"
                        elif er == "DELETED":
                            title = f"File deleted: {os.path.basename(ef)}"
                        else:
                            title = f"Scan activity: {er}"
                        activities.append((title, et, er))
                with dpg.mutex():
                    _rebuild_activity_feed_from_data(activities)
            except Exception as e:
                print(f"Quarantine post activity rebuild error: {e}")
            threading.Timer(0.20, _after_dashboard).start()

        def _after_dashboard():
            threat_score = 0
            active_threats = 0
            files_scanned = 0
            try:
                if BACKEND_AVAILABLE:
                    from system.quarantines.quarantine import list_quarantine_items
                    log = hs.load_log()
                    files_scanned = len(log)
                    q_entries = list_quarantine_items()
                    active_threats = len(q_entries)
                    if q_entries:
                        hs_ = 0
                        for it in q_entries:
                            try:
                                if float(it.get("probability", 0)) >= 0.7:
                                    hs_ += 1
                            except Exception:
                                pass
                        threat_score = min(
                            100,
                            int((hs_ / max(1, active_threats)) * 100 + active_threats * 5),
                        )
            except Exception as e:
                print(f"Quarantine post dashboard preload error: {e}")
            try:
                with dpg.mutex():
                    if dpg.does_item_exist("threat_score_value"):
                        dpg.set_value("threat_score_value", str(threat_score))
                        dpg.set_value("active_threats_value", str(active_threats))
                        dpg.set_value("files_scanned_value", str(files_scanned))
                    dpg.configure_item("quarantine_btn", enabled=True)
                    if dpg.does_item_exist("start_scan_btn"):
                        dpg.configure_item("start_scan_btn", enabled=True)
            except Exception as e:
                print(f"Quarantine post dashboard render error: {e}")

        threading.Timer(0.02, _after_ui).start()

    threading.Thread(target=_worker, daemon=True).start()


def _open_xai_panel(sender, app_data, user_data):
    """
    Open cached XAI without rereading the executable
    or running synchronous analysis.
    """

    threat = user_data

    job_id = threat.get("xai_job_id")

    # Legacy/in-memory report fallback.
    report = threat.get("xai_report")

    if BACKEND_AVAILABLE and job_id:
        try:
            cached = get_xai_report(job_id)

            if cached is not None:
                report = cached

            else:
                state = get_xai_status(job_id)
                status = state.get("status")

                if status == "PENDING":
                    report = {
                        "explanation": (
                            "Background AI explanation is "
                            "still being generated. "
                            "Close this panel and click "
                            "Explain again shortly."
                        ),
                        "scan_steps": [],
                        "suspicious_characteristics": [],
                        "feature_evidence": [],
                        "pe_analysis": {},
                        "recommendations": [],
                    }

                elif status == "ERROR":
                    report = {
                        "explanation": (
                            "Background explanation failed: "
                            + str(state.get("error"))
                        ),
                        "feature_evidence": [],
                        "pe_analysis": {},
                    }

                else:
                    report = {
                        "explanation": (
                            "No cached explanation is "
                            "currently available for "
                            "this detection."
                        ),
                        "feature_evidence": [],
                        "pe_analysis": {},
                    }

        except Exception as e:
            print(f"[XAI UI] Cache lookup failed: {e}")

            report = {
                "explanation": (
                    "Unable to retrieve the AI explanation."
                ),
                "feature_evidence": [],
                "pe_analysis": {},
            }

    elif report is None:
        # Never run expensive XAI synchronously.
        report = {
            "explanation": (
                "No background explanation was scheduled "
                "for this detection."
            ),
            "feature_evidence": [],
            "pe_analysis": {},
        }

    open_explain(threat, report)


_THREAT_CHUNK_SIZE = 15


def _build_threat_rows_chunk(start_idx):
    """Add a batch of threat rows to the table inside one small mutex block."""
    try:
        with dpg.mutex():
            if not dpg.does_item_exist("threats_table"):
                return
            end_idx = min(start_idx + _THREAT_CHUNK_SIZE, len(DETECTED_THREATS))
            for threat_idx in range(start_idx, end_idx):
                add_threat_row("threats_table", DETECTED_THREATS[threat_idx],
                               SELECTED_QUARANTINE_ITEMS, _toggle_select_item, _open_xai_panel)
    except Exception as e:
        print(f"Threat row chunk error at idx {start_idx}: {e}")
        return

    next_idx = start_idx + _THREAT_CHUNK_SIZE
    if next_idx < len(DETECTED_THREATS):
        threading.Timer(0.02, _build_threat_rows_chunk, args=(next_idx,)).start()


def _rebuild_threats_table():
    """Rebuild the threats table header synchronously, then stream rows in chunks."""
    reset_threat_rows()
    if dpg.does_item_exist("threats_table"):
        dpg.delete_item("threats_table")
    build_threats_table("threats_table_holder")
    update_selection_ui(len(SELECTED_QUARANTINE_ITEMS), len(DETECTED_THREATS))

    if not DETECTED_THREATS:
        add_empty_row("threats_table")
        return

    threading.Timer(0.01, _build_threat_rows_chunk, args=(0,)).start()


def _schedule_post_scan_ui_updates():
    """Run post-scan UI rebuilds with all slow I/O done OFF the mutex,
    and larger delays between chunks so the render loop never stalls.
    """

    def _preload_history_then_render():
        def _render():
            try:
                with dpg.mutex():
                    _rebuild_history()
            except Exception as e:
                print(f"Post-scan history render error: {e}")
            threading.Timer(0.22, _preload_activity_then_render).start()

        threading.Timer(0.02, _render).start()

    def _preload_activity_then_render():
        activities = []
        try:
            if BACKEND_AVAILABLE:
                log = hl.load_log(limit=10)
                for entry in reversed(log):
                    entry_result = entry.get("result", "INFO")
                    entry_file = entry.get("file_path", "Unknown file")
                    entry_timestamp = entry.get("timestamp", "")
                    if entry_result == "MALICIOUS":
                        title = f"Malware detected: {os.path.basename(entry_file)}"
                    elif entry_result == "SUSPICIOUS":
                        title = f"Suspicious file: {os.path.basename(entry_file)}"
                    elif entry_result == "CLEAN":
                        title = f"File scanned: {os.path.basename(entry_file)}"
                    elif entry_result == "QUARANTINED":
                        title = f"File quarantined: {os.path.basename(entry_file)}"
                    elif entry_result == "RESTORED":
                        title = f"File restored: {os.path.basename(entry_file)}"
                    elif entry_result == "DELETED":
                        title = f"File deleted: {os.path.basename(entry_file)}"
                    else:
                        title = f"Scan activity: {entry_result}"
                    activities.append((title, entry_timestamp, entry_result))
        except Exception as e:
            print(f"Post-scan activity preload error: {e}")
            activities = []

        def _render():
            try:
                with dpg.mutex():
                    _rebuild_activity_feed_from_data(activities)
            except Exception as e:
                print(f"Post-scan activity render error: {e}")
            threading.Timer(0.22, _preload_dashboard_then_render).start()

        threading.Timer(0.02, _render).start()

    def _preload_dashboard_then_render():
        threat_score = 0
        active_threats = 0
        files_scanned = 0
        try:
            if BACKEND_AVAILABLE:
                from system.quarantines.quarantine import list_quarantine_items
                log = hs.load_log()
                files_scanned = len(log)
                quarantine_entries = list_quarantine_items()
                active_threats = len(quarantine_entries)
                if quarantine_entries:
                    high_severity = 0
                    for item in quarantine_entries:
                        try:
                            if float(item.get("probability", 0)) >= 0.7:
                                high_severity += 1
                        except Exception:
                            pass
                    threat_score = min(
                        100,
                        int(
                            (high_severity / max(1, active_threats)) * 100
                            + active_threats * 5
                        ),
                    )
        except Exception as e:
            print(f"Post-scan dashboard preload error: {e}")

        def _render():
            try:
                with dpg.mutex():
                    if dpg.does_item_exist("threat_score_value"):
                        dpg.set_value("threat_score_value", str(threat_score))
                        dpg.set_value("active_threats_value", str(active_threats))
                        dpg.set_value("files_scanned_value", str(files_scanned))
            except Exception as e:
                print(f"Post-scan dashboard render error: {e}")

        threading.Timer(0.02, _render).start()

    threading.Timer(0.25, _preload_history_then_render).start()


def _reset_progress_counters(start_time):
    global _PROGRESS_FILES_SCANNED
    global _PROGRESS_THREATS_FOUND
    global _PROGRESS_CURRENT_NAME
    global _PROGRESS_TOTAL_FILES
    global _PROGRESS_START_TIME
    global _PROGRESS_PHASE

    with _PROGRESS_COUNTER_LOCK:
        _PROGRESS_FILES_SCANNED = 0
        _PROGRESS_THREATS_FOUND = 0
        _PROGRESS_CURRENT_NAME = ""
        _PROGRESS_TOTAL_FILES = 0
        _PROGRESS_START_TIME = start_time
        _PROGRESS_PHASE = "DISCOVERING"

def _set_discovered_total(total):
    global _PROGRESS_TOTAL_FILES
    global _PROGRESS_PHASE

    with _PROGRESS_COUNTER_LOCK:
        _PROGRESS_TOTAL_FILES = total
        _PROGRESS_PHASE = "SCANNING"


def _bump_files_scanned(name="", delta=1):
    global _PROGRESS_FILES_SCANNED
    global _PROGRESS_CURRENT_NAME

    with _PROGRESS_COUNTER_LOCK:
        _PROGRESS_FILES_SCANNED += delta

        if name:
            _PROGRESS_CURRENT_NAME = name

def _bump_threats_found(delta=1):
    global _PROGRESS_THREATS_FOUND
    with _PROGRESS_COUNTER_LOCK:
        _PROGRESS_THREATS_FOUND += delta


def _snapshot_progress():
    with _PROGRESS_COUNTER_LOCK:
        return (
            _PROGRESS_FILES_SCANNED,
            _PROGRESS_THREATS_FOUND,
            _PROGRESS_CURRENT_NAME,
            _PROGRESS_TOTAL_FILES,
            _PROGRESS_START_TIME,
            _PROGRESS_PHASE,
        )


def _progress_ticker_loop():
    global _PROGRESS_TICKER_RUNNING

    try:
        while True:
            if not SCAN_IN_PROGRESS:
                break

            if SCAN_CANCEL_REQUESTED:
                time.sleep(0.03)
                continue

            (
                files_scanned,
                threats_found,
                cur_name,
                total_files,
                started_at,
                phase,
            ) = _snapshot_progress()

            elapsed = time.time() - started_at

            if phase == "DISCOVERING":
                progress = 0.0
                status = "Discovering files..."

            elif total_files > 0:
                progress = min(
                    0.999,
                    files_scanned / total_files
                )

                status = (
                    f"Scanning: {cur_name} "
                    f"({files_scanned:,}/{total_files:,} files)"
                )

            else:
                progress = 0.0
                status = "No files found"

            try:
                with dpg.mutex():
                    if dpg.does_item_exist("scan_status_text"):
                        dpg.set_value("scan_status_text", status)

                    if dpg.does_item_exist("scan_progress_bar"):
                        dpg.set_value("scan_progress_bar", progress)

                    if dpg.does_item_exist("scan_elapsed_time"):
                        dpg.set_value(
                            "scan_elapsed_time",
                            f"Elapsed: {elapsed:.1f}s"
                        )

                    if dpg.does_item_exist("scan_threat_count"):
                        dpg.set_value(
                            "scan_threat_count",
                            f"Threats found: {threats_found}"
                        )

            except Exception as e:
                print(f"Progress UI error: {e}")

            time.sleep(0.25)

    finally:
        _PROGRESS_TICKER_RUNNING = False

def _iter_scan_paths(scan_type, custom_path=""):
# """
# Enumerates paths using the same rules
# for both counting and actual scanning.
# """

    if scan_type == "quick":
        folders = cfg.QUICK_SCAN_DIRS

    elif scan_type == "full":
        folders = cfg.REGULAR_SCAN_DIRS

    elif scan_type == "custom": 
        if os.path.isfile(custom_path):
            yield custom_path
            return

        folders = [custom_path] if os.path.isdir(custom_path) else []

    else:
        return

    for folder in folders:
        if SCAN_CANCEL_REQUESTED:
            return

        if not os.path.isdir(folder):
            continue

        for root, dirs, files in os.walk(folder):

            if SCAN_CANCEL_REQUESTED:
                return

            if scan_type == "full":
                skip = False

                for skip_dir in cfg.SKIP_DIRS:
                    root_abs = os.path.abspath(root)
                    skip_abs = os.path.abspath(skip_dir)

                    try:
                        if os.path.commonpath(
                            [root_abs, skip_abs]
                        ) == skip_abs:
                            skip = True
                            break
                    except ValueError:
                        continue

                if skip:
                    dirs[:] = []
                    continue

            for filename in files:
                if SCAN_CANCEL_REQUESTED:
                    return

                yield os.path.join(root, filename)


def _update_scan_progress():
    global SCAN_IN_PROGRESS, DETECTED_THREATS, SELECTED_QUARANTINE_ITEMS, SCAN_CANCEL_REQUESTED
    global _PROGRESS_TICKER_RUNNING
    try:
        SCAN_IN_PROGRESS = True
        SCAN_CANCEL_REQUESTED = False
        DETECTED_THREATS = []
        SELECTED_QUARANTINE_ITEMS = set()
        cfg.DETECTED_MALWARE.clear()
        cfg.DETECTED_SUSPICIOUS.clear()

        if BACKEND_AVAILABLE:
            try:
                _st = SELECTED_SCAN or "custom"
                if _st == "custom" and CURRENT_CUSTOM_PATH:
                    _tgt = str(CURRENT_CUSTOM_PATH)
                elif _st == "quick":
                    try:
                        _tgt = ", ".join(d for d in cfg.QUICK_SCAN_DIRS if isinstance(d, str)) if isinstance(cfg.QUICK_SCAN_DIRS, (list, tuple)) else ""
                    except Exception:
                        _tgt = ""
                elif _st == "full":
                    try:
                        _tgt = ", ".join(d for d in cfg.REGULAR_SCAN_DIRS if isinstance(d, str)) if isinstance(cfg.REGULAR_SCAN_DIRS, (list, tuple)) else ""
                    except Exception:
                        _tgt = ""
                else:
                    _tgt = ""
                begin_log_buffer(scan_type=_st, target=_tgt)
            except Exception:
                pass

        with dpg.mutex():
            dpg.set_value("scan_ready_heading", "Scanning...")
            dpg.set_item_label("start_scan_btn", "Scanning...")
            dpg.configure_item("start_scan_btn", enabled=False)

            if dpg.does_item_exist("scan_progress_container"):
                dpg.delete_item("scan_progress_container", children_only=True)

                with dpg.group(parent="scan_progress_container"):
                    dpg.add_text("Starting scan...", color=COLORS["text_secondary"], tag="scan_status_text")
                    dpg.add_spacer(height=20)
                    dpg.add_progress_bar(width=-1, tag="scan_progress_bar")
                    dpg.add_spacer(height=6)
                    dpg.add_text("Elapsed: 0.0s", color=COLORS["text_secondary"], tag="scan_elapsed_time")
                    dpg.add_spacer(height=4)
                    dpg.add_text("Threats found: 0", color=COLORS["text_secondary"], tag="scan_threat_count")

        if not BACKEND_AVAILABLE:
            time.sleep(2)
            with dpg.mutex():
                dpg.set_value("scan_ready_heading", "Scan Complete!")
                if dpg.does_item_exist("scan_status_text"):
                    dpg.set_value(
                        "scan_status_text",
                        f"Backend unavailable: {BACKEND_LOAD_ERROR[:180] or 'unknown initialization error'}",
                    )
                if dpg.does_item_exist("scan_progress_bar"):
                    dpg.set_value("scan_progress_bar", 1.0)
        else:
            start_time = time.time()
            _reset_progress_counters(start_time)
            if not _PROGRESS_TICKER_RUNNING:
                _PROGRESS_TICKER_RUNNING = True
                threading.Thread(target=_progress_ticker_loop, daemon=True).start()

            scan_type = SELECTED_SCAN
            custom_path = CURRENT_CUSTOM_PATH


            # if SCAN_CANCEL_REQUESTED:
            #     # Exit the scan branch through your cancellation
            #     # handling; do not mark it completed.
            #     pass
            # else:
            #     _set_discovered_total(total_files)

            
            
            def scan_path(path):
                """
                Worker thread:
                - Check cancellation
                - Check exclusions
                - Delegate PE validation and analysis to backend
                """
                if SCAN_CANCEL_REQUESTED:
                    return None

                try:
                    if se.is_excluded(path):
                        return None

                    if SCAN_CANCEL_REQUESTED:
                        return None

                    return sf.scan_file(
                        path,
                        auto_quarantine=True
                    )

                except Exception as exc:
                    print(f"[Scan Worker] {path}: {exc}")
                    return None



            def handle_scan_result(path, result):
                """
                Runs in the scan coordinator thread.

                Updates progress and handles detected threats.
                """

                _bump_files_scanned(
                    name=os.path.basename(path)
                )

                if not result:
                    return

                if result.get("result") not in (
                    "MALICIOUS",
                    "SUSPICIOUS"
                ):
                    return

                _bump_threats_found()

                print(
                    "[THREAT DEBUG]",
                    "original_path =", path,
                    "result_path =", result.get("file_path"),
                    "original_name =", result.get("original_name"),
                )
                DETECTED_THREATS.append(result)

                # Desktop/mobile notification
                try:
                    enqueue_threat_notification(
                        result["file_path"],
                        result["result"],
                        result.get("probability"),
                        result.get("category"),
                    )

                except Exception as e:
                    print(f"Notification error: {e}")

                # API notification
                try:
                    from system.api.server import notify_new_malware

                    probability = result.get("probability")

                    if probability is not None:
                        threat_level = int(
                            round(float(probability) * 100)
                        )
                    else:
                        threat_level = (
                            90 if result["result"] == "MALICIOUS"
                            else 55
                        )

                    notify_new_malware(
                        os.path.basename(result["file_path"]),
                        threat_level
                    )

                except Exception as e:
                    print(f"API notification error: {e}")


            # if SELECTED_SCAN == "quick":
            #     for folder in cfg.QUICK_SCAN_DIRS:
            #         if os.path.exists(folder):
            #             for root, dirs, files in os.walk(folder):
            #                 for file in files:
            #                     scan_path(os.path.join(root, file))
            #                     if SCAN_CANCEL_REQUESTED:
            #                         break
            #                 if SCAN_CANCEL_REQUESTED:
            #                     break
            #         if SCAN_CANCEL_REQUESTED:
            #             break

            # elif SELECTED_SCAN == "full":
            #     for folder in cfg.REGULAR_SCAN_DIRS:
            #         if os.path.exists(folder):
            #             for root, dirs, files in os.walk(folder):
            #                 skip = False
            #                 for skip_dir in cfg.SKIP_DIRS:
            #                     if os.path.abspath(root).lower().startswith(os.path.abspath(skip_dir).lower()):
            #                         skip = True
            #                         break
            #                 if skip:
            #                     continue
            #                 for file in files:
            #                     scan_path(os.path.join(root, file))
            #                     if SCAN_CANCEL_REQUESTED:
            #                         break
            #                 if SCAN_CANCEL_REQUESTED:
            #                     break
            #         if SCAN_CANCEL_REQUESTED:
            #             break

            # elif SELECTED_SCAN == "custom" and CURRENT_CUSTOM_PATH:
            #     if os.path.isfile(CURRENT_CUSTOM_PATH):
            #         scan_path(CURRENT_CUSTOM_PATH)
            #     elif os.path.isdir(CURRENT_CUSTOM_PATH):
            #         for root, dirs, files in os.walk(CURRENT_CUSTOM_PATH):
            #             for file in files:
            #                 scan_path(os.path.join(root, file))
            #                 if SCAN_CANCEL_REQUESTED:
            #                     break
            #             if SCAN_CANCEL_REQUESTED:
            #                 break
            # Phase 1: Count files
            scan_type = SELECTED_SCAN
            custom_path = CURRENT_CUSTOM_PATH

            files_to_scan = list(
                _iter_scan_paths(scan_type, custom_path)
            )

            total_files = len(files_to_scan)

            if not SCAN_CANCEL_REQUESTED:

                _set_discovered_total(total_files)

                # Calculate CPU/RAM limits for this scan.
                workers, max_pending = get_scan_worker_config()

                print(
                    f"[AYAWrus] Starting scan: "
                    f"{workers} workers, "
                    f"{max_pending} pending tasks, "
                    f"{total_files} files"
                )

                # Phase 2: Concurrent scanning
                with ThreadPoolExecutor(
                    max_workers=workers,
                    thread_name_prefix="AYAWrusScan"
                ) as executor:

                    path_iterator = iter(files_to_scan)
                    pending = {}

                    def submit_next():
                        if SCAN_CANCEL_REQUESTED:
                            return False

                        try:
                            path = next(path_iterator)
                        except StopIteration:
                            return False

                        future = executor.submit(scan_path, path)
                        pending[future] = path

                        return True

                    # Fill the initial queue.
                    for _ in range(max_pending):
                        if not submit_next():
                            break

                    # Process jobs as they finish.
                    while pending:

                        if SCAN_CANCEL_REQUESTED:
                            for future in pending:
                                future.cancel()
                            break

                        done, _ = wait(
                            pending,
                            timeout=0.10,
                            return_when=FIRST_COMPLETED
                        )

                        for future in done:

                            path = pending.pop(future)

                            if SCAN_CANCEL_REQUESTED:
                                break

                            try:
                                result = future.result()

                            except Exception as e:
                                print(
                                    f"[Scan Executor] "
                                    f"{path}: {e}"
                                )
                                result = None

                            handle_scan_result(
                                path,
                                result
                            )

                            if not SCAN_CANCEL_REQUESTED:
                                submit_next()

            was_cancelled = SCAN_CANCEL_REQUESTED
            SCAN_IN_PROGRESS = False
            time.sleep(0.06)
            files_scanned, threats_found, _n, _e, _s, _phase = _snapshot_progress()
            duration = time.time() - start_time

            if BACKEND_AVAILABLE:
                try:
                    flush_log_buffer()
                except Exception as flush_error:
                    print(f"Post-scan history flush error: {flush_error}")

            if was_cancelled:
                completion_text = (
                    f"Scan cancelled. Processed {files_scanned} files "
                    f"in {duration:.1f}s. "
                    f"{threats_found} threats found."
                )
            else:
                completion_text = (
                    f"Scanned {files_scanned} files "
                    f"in {duration:.1f}s. "
                    f"{threats_found} threats found."
                )
            elapsed_text = f"Elapsed: {duration:.1f}s"
            threat_count_text = f"Threats found: {threats_found}"

            def _apply_completion_status():
                try:
                    with dpg.mutex():
                        dpg.set_value(
                            "scan_ready_heading",
                            "Scan Cancelled" if was_cancelled
                            else "Scan Complete!"
                        )
                        if dpg.does_item_exist("scan_status_text"):
                            dpg.set_value("scan_status_text", completion_text)
                        if dpg.does_item_exist("scan_progress_bar"):
                            if not was_cancelled:
                                dpg.set_value("scan_progress_bar", 1.0)
                        if dpg.does_item_exist("scan_elapsed_time"):
                            dpg.set_value("scan_elapsed_time", elapsed_text)
                        if dpg.does_item_exist("scan_threat_count"):
                            dpg.set_value("scan_threat_count", threat_count_text)
                except Exception as e:
                    print(f"Completion status apply error: {e}")

            threading.Timer(0.01, _apply_completion_status).start()

            if BACKEND_AVAILABLE:
                def _send_completion_notification():
                    try:
                        config = tg.load_config()
                        if config.get("telegram_bot_token") and config.get("telegram_chat_id"):
                            msg = (
                                f"🔍 Scan Complete!\n"
                                f"Scanned {files_scanned} files in {duration:.1f}s\n"
                                f"Threats found: {threats_found}"
                            )
                            tg.send_telegram_notification(msg)
                    except Exception as e:
                        print(f"Error sending Telegram notification: {e}")
                threading.Thread(target=_send_completion_notification, daemon=True).start()

            def _show_threats_container():
                try:
                    with dpg.mutex():
                        if dpg.does_item_exist("threats_container"):
                            dpg.show_item("threats_container")
                except Exception as e:
                    print(f"Show threats container error: {e}")

            def _begin_threats_rebuild():
                try:
                    with dpg.mutex():
                        _rebuild_threats_table()
                except Exception as e:
                    print(f"Begin threats rebuild error: {e}")
                threading.Timer(0.35, _schedule_post_scan_ui_updates).start()

            threading.Timer(0.06, _show_threats_container).start()
            threading.Timer(0.20, _begin_threats_rebuild).start()

    except Exception as e:
        print("=" * 80)
        traceback.print_exc()
        print("=" * 80)
        SCAN_IN_PROGRESS = False

        if BACKEND_AVAILABLE:
            try:
                flush_log_buffer(status="FAILED")
            except Exception as flush_error:
                print(f"Failed-scan history flush error: {flush_error}")

        err_text = f"{type(e).__name__}: {e}"

        def _apply_failure_status():
            try:
                with dpg.mutex():
                    dpg.set_value("scan_ready_heading", "Scan Failed")
                    if dpg.does_item_exist("scan_status_text"):
                        dpg.set_value("scan_status_text", err_text)
            except Exception:
                pass

        threading.Timer(0.01, _apply_failure_status).start()

    finally:
        SCAN_IN_PROGRESS = False

        def _final_flush_if_needed():
            try:
                from system.history.logs import _buffering_active as _ba
                if _ba:
                    flush_log_buffer()
            except Exception:
                pass

        threading.Thread(target=_final_flush_if_needed, daemon=True).start()

        def _re_enable_buttons():
            try:
                with dpg.mutex():
                    dpg.configure_item("start_scan_btn", enabled=True)
                    if dpg.does_item_exist("cancel_scan_btn"):
                        dpg.configure_item("cancel_scan_btn", enabled=False)
                    _update_start_button()
            except Exception as e:
                print(f"Re-enable buttons error: {e}")

        threading.Timer(0.04, _re_enable_buttons).start()

def _start_scan(sender, app_data):
    if SCAN_IN_PROGRESS:
        return

    if SELECTED_SCAN == "custom" and not CURRENT_CUSTOM_PATH:
        open_picker()
        return

    if dpg.does_item_exist("threats_container"):
        dpg.hide_item("threats_container")

    with dpg.mutex():
        dpg.set_value("scan_ready_heading", "Scanning...")
        dpg.set_item_label("start_scan_btn", "Scanning...")
        dpg.configure_item("start_scan_btn", enabled=False)
        if dpg.does_item_exist("cancel_scan_btn"):
            dpg.configure_item("cancel_scan_btn", enabled=True)

        if dpg.does_item_exist("scan_progress_container"):
            dpg.delete_item("scan_progress_container", children_only=True)
            with dpg.group(parent="scan_progress_container"):
                dpg.add_text("Starting scan...", color=COLORS["text_secondary"], tag="scan_status_text")
                dpg.add_spacer(height=20)
                dpg.add_progress_bar(width=-1, tag="scan_progress_bar", default_value=0.0)
                dpg.add_spacer(height=6)
                dpg.add_text("Elapsed: 0.0s", color=COLORS["text_secondary"], tag="scan_elapsed_time")
                dpg.add_spacer(height=4)
                dpg.add_text("Threats found: 0", color=COLORS["text_secondary"], tag="scan_threat_count")

    global SCAN_CANCEL_REQUESTED
    SCAN_CANCEL_REQUESTED = False
    thread = threading.Thread(target=_update_scan_progress, daemon=True)
    thread.start()

def _cancel_scan(sender, app_data):
    global SCAN_CANCEL_REQUESTED
    SCAN_CANCEL_REQUESTED = True
    with dpg.mutex():
        if dpg.does_item_exist("scan_status_text"):
            dpg.set_value("scan_status_text", "Cancel requested. Finishing current file...")
        if dpg.does_item_exist("cancel_scan_btn"):
            dpg.configure_item("cancel_scan_btn", enabled=False)


def _update_start_button():
    if SCAN_IN_PROGRESS:
        return

    button_labels = {
        "quick": "Start Quick Scan",
        "full": "Start Full Scan",
        "custom": "Start Custom Scan"
    }
    dpg.set_item_label("start_scan_btn", button_labels.get(SELECTED_SCAN, "Start Scan"))
    # heading is reset by reset_ready_state() when the card changes (doing it here wipes "Scan Complete!")

def _folder_picked(sender, app_data):
    global CURRENT_CUSTOM_PATH
    path = app_data.get("file_path_name", "")
    if path:
        CURRENT_CUSTOM_PATH = path
        if dpg.does_item_exist("custom_path_display"):
            dpg.set_value("custom_path_display", path)


def _on_step_click(sender, app_data, user_data):
    print(f"_on_step_click called with user_data: {user_data}")
    global SELECTED_STEP
    SELECTED_STEP = user_data
    _update_step_description()

def _update_step_description():
    set_pipeline_step(SELECTED_STEP, DETECTION_STEPS[SELECTED_STEP]["description"])


def build_scan(parent, fonts, icons):
    global g_icons
    g_icons = icons  # Store icons in global variable for later use
    dpg.add_spacer(height=20, parent=parent)
    with dpg.handler_registry():
        dpg.add_mouse_click_handler(callback=_handle_click)

    init_picker(_folder_picked)   # the folder dialog lives in ui/scan_picker.py

    with dpg.group(horizontal=True, parent=parent):
        dpg.add_spacer(width=24)
        with dpg.group():
            dpg.add_text("Virus & Threat Protection", tag="scan_page_title")
            dpg.bind_item_font("scan_page_title", fonts["heading"])
            dpg.add_text("Run a scan to check for malicious files on your system", color=COLORS["text_secondary"])
            dpg.add_spacer(height=15)

            with dpg.group(horizontal=True):
                for i, scan in enumerate(SCAN_TYPES):
                    scan_card(scan["key"], icons[scan["icon"]], scan["label"], scan["subtitle"],
                             fonts, icons)
                    if i < len(SCAN_TYPES) - 1:
                        dpg.add_spacer(width=CARD_GAP)

            dpg.add_spacer(height=CARD_GAP)

            build_ready_panel(icons, fonts, _start_scan, _cancel_scan)
            _rebuild_custom_path_controls()

            dpg.add_spacer(height=20)
            # Detected Threats panel (initially hidden) lives in ui/scan_threats.py
            build_threats_panel(fonts, _quarantine_selected, _toggle_select_all)

            dpg.add_spacer(height=20)
            # Detection Pipeline lives in ui/scan_pipeline.py
            g_step_elements[:] = build_pipeline_panel(icons, fonts, DETECTION_STEPS, SELECTED_STEP)

    # start_scan_btn is themed in ui/scan_layout.py (blue, dimmed when disabled)
    # quarantine_btn is themed in ui/scan_threats.py (blue, dimmed when disabled)

    register_scan_layout()
    init_explain(fonts, icons)
    apply_slim_scrollbar(parent)   # parent is "page_scan", the window that actually scrolls
    _ensure_api_server_started()


def _ensure_api_server_started():
    """Start the Flask API (alerts SSE + /api routes) on a background thread so
    the mobile app can poll /api/alerts/latest or stream /api/alerts/stream.
    Called once when the scan UI builds; subsequent calls are no-ops.
    """
    global _api_server_started
    if _api_server_started or not BACKEND_AVAILABLE:
        return
    try:
        _api_server_started = True
        import system.api.server as srv_mod
        srv_mod.init_db()
        try:
            srv_mod.sync_history_json_to_db()
        except Exception:
            pass

        port = int(os.environ.get("SERVER_PORT", "5001"))

        def _srv_worker():
            try:
                host = os.environ.get("SERVER_HOST", "0.0.0.0")
                srv_mod.app.run(host=host, port=port, threaded=True, use_reloader=False, debug=False)
            except Exception as e:
                print(f"[API Server] Failed to start: {e}")

        t = threading.Thread(target=_srv_worker, daemon=True)
        t.start()
        print(f"[API Server] Started (background thread). Mobile alerts available at http://<host>:{port}/api/alerts/stream")
    except Exception as e:
        print(f"[API Server] Init error (continuing): {e}")
        _api_server_started = False