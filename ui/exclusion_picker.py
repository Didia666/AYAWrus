import os
import traceback
import dearpygui.dearpygui as dpg
from ui.layout import register_resize
from ui.scan_picker import _themes as _picker_themes, _drive_root   # read-only: Scan's dialog theme + drive helper

# exclusion_picker.py
# The folder dialog for the Exclusions tab. Same look as the Scan page's picker (the theme is shared),
# but separate tags and callback, so neither dialog can interfere with the other.

# ---- Size (tune here) ----
EXPICK_W_RATIO = 0.55
EXPICK_MIN_W = 600
EXPICK_MAX_W = 820
EXPICK_H_RATIO = 0.65
EXPICK_MIN_H = 400
EXPICK_MAX_H = 640
EXPICK_MARGIN = 24             # never closer than this to the window edges
EXPICK_MIN_SIZE = [320, 240]   # smallest size the dialog can be dragged to

# ---- Text ----
EXPICK_TITLE = "Choose a folder to exclude"

EXPICK = "exclusion_folder_picker"   # own tag, different from Scan's "custom_scan_picker"

_s = {"ready": False, "open": False, "user_cb": None, "last": ""}


def _start_path():
    """Opens where you last picked, otherwise at the root of the drive the app lives on."""
    last = _s["last"]
    return last if last and os.path.isdir(last) else _drive_root()


def _geometry():
    vw = dpg.get_viewport_client_width()
    vh = dpg.get_viewport_client_height()
    w = int(max(EXPICK_MIN_W, min(EXPICK_MAX_W, vw * EXPICK_W_RATIO)))
    h = int(max(EXPICK_MIN_H, min(EXPICK_MAX_H, vh * EXPICK_H_RATIO)))
    w = min(w, vw - 2 * EXPICK_MARGIN)
    h = min(h, vh - 2 * EXPICK_MARGIN)
    return w, h, (vw - w) // 2, (vh - h) // 2


def _layout():
    """Re-sizes and re-centers the dialog (on open and on every window resize)."""
    if not dpg.does_item_exist(EXPICK):
        return
    w, h, x, y = _geometry()
    dpg.configure_item(EXPICK, width=w, height=h)
    try:
        dpg.set_item_pos(EXPICK, [x, y])
    except Exception:
        traceback.print_exc()   # if this DPG build won't move the dialog, it keeps its own position


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

def _on_pick(sender, app_data, user_data=None):
    try:
        path = (app_data or {}).get("file_path_name") or (app_data or {}).get("current_path") or ""
        if path and os.path.isdir(path):
            _s["last"] = path
    except Exception:
        traceback.print_exc()
    _s["open"] = False
    cb = _s["user_cb"]
    if cb:
        cb(sender, app_data)   # exclusions.py's own _folder_picked, untouched


def _on_cancel(sender=None, app_data=None, user_data=None):
    _s["open"] = False


def _on_escape(sender=None, app_data=None):
    if _s["open"] and dpg.does_item_exist(EXPICK):
        dpg.configure_item(EXPICK, show=False)
        _s["open"] = False


def _on_resize(content_w, content_h):
    if _s["open"]:
        _layout()


# ---------------------------------------------------------------------------
# Open / init
# ---------------------------------------------------------------------------

def open_exclusion_picker(sender=None, app_data=None, user_data=None):
    """The Select Folder button calls this. Rebuilt on every open so it always starts at the right folder."""
    if not _s["ready"]:
        print("[exclusion_picker] not initialised, call init_exclusion_picker first")
        return
    try:
        if dpg.does_item_exist(EXPICK):
            dpg.delete_item(EXPICK)
        w, h, x, y = _geometry()
        dpg.add_file_dialog(directory_selector=True, show=True, modal=True, tag=EXPICK,
                            label=EXPICK_TITLE, callback=_on_pick, cancel_callback=_on_cancel,
                            default_path=_start_path(), width=w, height=h, min_size=EXPICK_MIN_SIZE)
        dpg.bind_item_theme(EXPICK, _picker_themes()["dialog"])
        _layout()
        _s["open"] = True
    except Exception:
        traceback.print_exc()
        _s["open"] = False


def init_exclusion_picker(folder_picked_cb):
    """Call once from build_exclusions, in place of the old stock dpg.file_dialog block."""
    if _s["ready"]:
        return
    _s["user_cb"] = folder_picked_cb
    _picker_themes()   # make sure Scan's dialog theme exists (it is cached, so this is free if Scan built it)
    with dpg.handler_registry():
        dpg.add_key_press_handler(dpg.mvKey_Escape, callback=_on_escape)
    register_resize("exclusion_picker", _on_resize)
    _s["ready"] = True