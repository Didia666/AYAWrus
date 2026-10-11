import os
import time
import threading
import traceback
import dearpygui.dearpygui as dpg
from ui.theme import COLORS
from ui.layout import register_resize
from ui.scrollbar_theme import (SCROLL_SIZE, SCROLL_ROUNDING, SCROLL_TRACK,
                                SCROLL_GRAB, SCROLL_GRAB_HOVER, SCROLL_GRAB_ACTIVE)

# scan_picker.py

# ---- Size (tune here) ----
PICK_W_RATIO = 0.60
PICK_MIN_W = 640
PICK_MAX_W = 900
PICK_H_RATIO = 0.70
PICK_MIN_H = 420
PICK_MAX_H = 720
PICK_MARGIN = 24               # never closer than this to the window edges

# ---- Look ----
PICK_ROUNDING = 14
PICK_FRAME_ROUNDING = 8
PICK_WINDOW_PAD = 16
PICK_FRAME_PAD_X = 12
PICK_FRAME_PAD_Y = 8           # input and button height
PICK_ITEM_SPACING_Y = 6
PICK_CELL_PAD_X = 8
PICK_CELL_PAD_Y = 7            # row height (raise for taller rows)
PICK_BORDER = (56, 130, 246, 90)
ROW_SELECTED = (56, 130, 246, 70)
ROW_HOVER = (255, 255, 255, 18)
BTN_HOVER = (76, 150, 246)
BTN_ACTIVE = (46, 120, 236)

# ---- Behavior ----
FADE_SECONDS = 0.15
FRAME_SECONDS = 0.016
CLOSE_WATCH_GRACE = 0.40       # don't check "was it closed" this soon after opening
PICKER_TITLE = "Select Folder"

# ---- X button (sits on the dialog's title bar) ----
CLOSE_W = 26
CLOSE_H = 18
CLOSE_RIGHT = 8                # gap from the dialog's right edge
CLOSE_TOP = 2                  # gap from the dialog's top edge. Raise or lower if it doesn't line up with the title bar

PICKER = "custom_scan_picker"  # same tag the scan code already uses
ALPHA_STYLE = "picker_alpha_style"
CLOSE_LAYER = "picker_close_layer"
CLOSE_RECT = "picker_close_rect"
CLOSE_TEXT = "picker_close_text"

_T = {}
_s = {"ready": False, "user_cb": None, "last": "", "mode": "closed",
      "t0": 0.0, "opened_at": 0.0}


def _drive_root():
    """Root of the drive the app lives on (D:\\ for you). Falls back to '/' on non-Windows."""
    drive = os.path.splitdrive(os.path.abspath(__file__))[0]
    return (drive + os.sep) if drive else os.sep


def _start_path():
    last = _s["last"]
    return last if last and os.path.isdir(last) else _drive_root()


def _themes():
    if _T:
        return _T
    c = COLORS
    with dpg.theme() as th:
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_style(dpg.mvStyleVar_Alpha, 1.0, tag=ALPHA_STYLE)
            dpg.add_theme_color(dpg.mvThemeCol_WindowBg, c["bg_card"])
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, (0, 0, 0, 0))
            dpg.add_theme_color(dpg.mvThemeCol_PopupBg, c["bg_card"])
            dpg.add_theme_color(dpg.mvThemeCol_Border, PICK_BORDER)
            dpg.add_theme_color(dpg.mvThemeCol_Text, c["text_primary"])
            dpg.add_theme_color(dpg.mvThemeCol_TitleBg, c["bg_card"])
            dpg.add_theme_color(dpg.mvThemeCol_TitleBgActive, c["bg_card"])
            dpg.add_theme_color(dpg.mvThemeCol_TitleBgCollapsed, c["bg_card"])
            dpg.add_theme_color(dpg.mvThemeCol_FrameBg, c["bg_sidebar"])
            dpg.add_theme_color(dpg.mvThemeCol_FrameBgHovered, c["bg_main"])
            dpg.add_theme_color(dpg.mvThemeCol_FrameBgActive, c["bg_main"])
            dpg.add_theme_color(dpg.mvThemeCol_Button, c["accent_blue"])
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, BTN_HOVER)
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, BTN_ACTIVE)
            dpg.add_theme_color(dpg.mvThemeCol_Header, ROW_SELECTED)
            dpg.add_theme_color(dpg.mvThemeCol_HeaderHovered, ROW_HOVER)
            dpg.add_theme_color(dpg.mvThemeCol_HeaderActive, ROW_SELECTED)
            dpg.add_theme_color(dpg.mvThemeCol_TableHeaderBg, c["bg_card"])   # blends the header bar into the window
            dpg.add_theme_color(dpg.mvThemeCol_TableBorderStrong, c["border"])
            dpg.add_theme_color(dpg.mvThemeCol_TableBorderLight, c["border"])
            dpg.add_theme_color(dpg.mvThemeCol_TableRowBg, (0, 0, 0, 0))
            dpg.add_theme_color(dpg.mvThemeCol_TableRowBgAlt, (255, 255, 255, 8))
            dpg.add_theme_color(dpg.mvThemeCol_Separator, c["border"])
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarBg, SCROLL_TRACK)
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarGrab, SCROLL_GRAB)
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarGrabHovered, SCROLL_GRAB_HOVER)
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarGrabActive, SCROLL_GRAB_ACTIVE)
            dpg.add_theme_style(dpg.mvStyleVar_WindowRounding, PICK_ROUNDING)
            dpg.add_theme_style(dpg.mvStyleVar_ChildRounding, 8)
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, PICK_FRAME_ROUNDING)
            dpg.add_theme_style(dpg.mvStyleVar_WindowBorderSize, 1)
            dpg.add_theme_style(dpg.mvStyleVar_FrameBorderSize, 1)
            dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, PICK_WINDOW_PAD, PICK_WINDOW_PAD)
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding, PICK_FRAME_PAD_X, PICK_FRAME_PAD_Y)
            dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, 8, PICK_ITEM_SPACING_Y)
            dpg.add_theme_style(dpg.mvStyleVar_CellPadding, PICK_CELL_PAD_X, PICK_CELL_PAD_Y)
            dpg.add_theme_style(dpg.mvStyleVar_ScrollbarSize, SCROLL_SIZE)
            dpg.add_theme_style(dpg.mvStyleVar_ScrollbarRounding, SCROLL_ROUNDING)
        for comp in (dpg.mvChildWindow, dpg.mvFileDialog):
            with dpg.theme_component(comp):
                dpg.add_theme_color(dpg.mvThemeCol_ScrollbarBg, SCROLL_TRACK)
                dpg.add_theme_color(dpg.mvThemeCol_ScrollbarGrab, SCROLL_GRAB)
                dpg.add_theme_color(dpg.mvThemeCol_ScrollbarGrabHovered, SCROLL_GRAB_HOVER)
                dpg.add_theme_color(dpg.mvThemeCol_ScrollbarGrabActive, SCROLL_GRAB_ACTIVE)
                dpg.add_theme_style(dpg.mvStyleVar_ScrollbarSize, SCROLL_SIZE)
                dpg.add_theme_style(dpg.mvStyleVar_ScrollbarRounding, SCROLL_ROUNDING)
    _T["dialog"] = th
    return _T


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------

def _geometry():
    vw = dpg.get_viewport_client_width()
    vh = dpg.get_viewport_client_height()
    w = int(max(PICK_MIN_W, min(PICK_MAX_W, vw * PICK_W_RATIO)))
    h = int(max(PICK_MIN_H, min(PICK_MAX_H, vh * PICK_H_RATIO)))
    w = min(w, vw - 2 * PICK_MARGIN)
    h = min(h, vh - 2 * PICK_MARGIN)
    return vw, vh, w, h, (vw - w) // 2, (vh - h) // 2


def _layout():
    """Re-sizes and re-centers the dialog and backdrop (on open and on every window resize)."""
    vw, vh, w, h, x, y = _geometry()
    if dpg.does_item_exist(PICKER):
        dpg.configure_item(PICKER, width=w, height=h)
        try:
            dpg.configure_item(PICKER, pos=[x, y])
        except Exception:
            pass   # if this build of DPG won't move the dialog, it keeps its own position
        _x_place()


def _set_alpha(a):
    try:
        dpg.set_value(ALPHA_STYLE, [a, 0])
    except Exception:
        traceback.print_exc()


# ---------------------------------------------------------------------------
# Open / close
# ---------------------------------------------------------------------------

def _remember(app_data):
    try:
        path = (app_data or {}).get("file_path_name") or (app_data or {}).get("current_path") or ""
        if path and os.path.isdir(path):
            _s["last"] = path
    except Exception:
        pass


def _on_pick(sender, app_data, user_data=None):
    _remember(app_data)
    cb = _s["user_cb"]
    if cb:
        cb(sender, app_data)     # the scan code's own _folder_picked, untouched
    _close()


def _on_cancel(sender=None, app_data=None, user_data=None):
    _close()


def _close():
    _x_show(False)
    _s["mode"] = "closed"


def _on_x(sender=None, app_data=None, user_data=None):
    if dpg.does_item_exist(PICKER):
        dpg.configure_item(PICKER, show=False)
    _close()


def _x_show(visible):
    """Shows/hides the drawn X by changing its opacity (show=False is ignored on viewport drawlists)."""
    _s["x_on"] = visible
    if dpg.does_item_exist(CLOSE_RECT):
        dpg.configure_item(CLOSE_RECT, fill=(*COLORS["accent_red"], 60 if visible else 0))
    if dpg.does_item_exist(CLOSE_TEXT):
        dpg.configure_item(CLOSE_TEXT, color=(*COLORS["text_primary"], 255 if visible else 0))


def _x_rect():
    vw, vh, w, h, x, y = _geometry()
    x0 = x + w - CLOSE_W - CLOSE_RIGHT
    y0 = y + CLOSE_TOP
    return x0, y0, x0 + CLOSE_W, y0 + CLOSE_H


def _x_place():
    """Moves the drawn X to the dialog's top-right corner."""
    if not dpg.does_item_exist(CLOSE_RECT):
        return
    x0, y0, x1, y1 = _x_rect()
    dpg.configure_item(CLOSE_RECT, pmin=(x0, y0), pmax=(x1, y1))
    try:
        tw, th = dpg.get_text_size("X")
    except Exception:
        tw, th = 10, 18
    dpg.configure_item(CLOSE_TEXT, pos=(x0 + (CLOSE_W - tw) / 2, y0 + (CLOSE_H - th) / 2))


def _mouse_over_x():
    mx, my = dpg.get_mouse_pos(local=False)
    x0, y0, x1, y1 = _x_rect()
    return x0 <= mx <= x1 and y0 <= my <= y1


def _on_global_click(sender=None, app_data=None):
    if _s["mode"] == "open" and _s.get("x_on") and _mouse_over_x():
        _on_x()


def _build_dialog():
    if dpg.does_item_exist(PICKER):
        dpg.delete_item(PICKER)
    vw, vh, w, h, x, y = _geometry()
    dpg.add_file_dialog(directory_selector=True, show=True, modal=True, tag=PICKER,
                        label=PICKER_TITLE, callback=_on_pick, cancel_callback=_on_cancel,
                        default_path=_start_path(), width=w, height=h, min_size=[320, 240])
    dpg.bind_item_theme(PICKER, _T["dialog"])


def open_picker(sender=None, app_data=None, user_data=None):
    """Select Path / Start Custom Scan call this instead of show_item. If anything fails, the plain dialog is shown."""
    if not _s["ready"]:
        return
    try:
        _set_alpha(0.0)
        _build_dialog()      # created after the backdrop, so it sits on top of it
        _x_show(False)          # shown again when the fade finishes
        _layout()
        now = time.time()
        _s["t0"] = now
        _s["opened_at"] = now
        _s["mode"] = "open"
    except Exception:
        traceback.print_exc()
        _close()
        if dpg.does_item_exist(PICKER):
            dpg.configure_item(PICKER, show=True)


def _on_escape(sender=None, app_data=None):
    if _s["mode"] == "open" and dpg.does_item_exist(PICKER):
        dpg.configure_item(PICKER, show=False)
        _close()   # clean up now (X included) instead of waiting for the watcher


def _ticker_loop():
    while True:
        time.sleep(FRAME_SECONDS)
        if _s["mode"] != "open":
            continue
        try:
            with dpg.mutex():
                now = time.time()
                t = min(1.0, (now - _s["t0"]) / FADE_SECONDS)
                if t < 1.0 or _s["t0"] > 0:
                    _set_alpha(1.0 - (1.0 - t) ** 2)
                    if t >= 1.0:
                        _s["t0"] = -1.0          # fade finished, stop touching the alpha
                        _x_show(True)
                if _s.get("x_on") and dpg.does_item_exist(CLOSE_RECT):
                    hot = _mouse_over_x()
                    dpg.configure_item(CLOSE_RECT, fill=(*COLORS["accent_red"], 210 if hot else 60))
                # closed through the window's own X, or Esc: remove the backdrop
                if now - _s["opened_at"] > CLOSE_WATCH_GRACE:
                    if not dpg.does_item_exist(PICKER) or not dpg.get_item_configuration(PICKER).get("show", True):
                        _close()
        except Exception:
            pass


def _on_resize(content_w, content_h):
    if _s["mode"] == "open":
        _layout()


def init_picker(folder_picked_cb):
    """Call once from build_scan, in place of the old dpg.file_dialog block."""
    if _s["ready"]:
        return
    _s["user_cb"] = folder_picked_cb
    _themes()
    try:
        dpg.add_file_dialog(directory_selector=True, show=False, tag=PICKER, callback=_on_pick,
                            cancel_callback=_on_cancel, default_path=_start_path(),
                            width=PICK_MIN_W, height=PICK_MIN_H)
        dpg.bind_item_theme(PICKER, _T["dialog"])
    except Exception:
        traceback.print_exc()
    with dpg.viewport_drawlist(front=True, tag=CLOSE_LAYER):
        dpg.draw_rectangle((0, 0), (CLOSE_W, CLOSE_H), color=(0, 0, 0, 0),
                           fill=(*COLORS["accent_red"], 60), rounding=8, tag=CLOSE_RECT)
        dpg.draw_text((0, 0), "X", color=COLORS["text_primary"], size=18, tag=CLOSE_TEXT)
    _x_show(False)   # starts invisible
    with dpg.handler_registry():
        dpg.add_key_press_handler(dpg.mvKey_Escape, callback=_on_escape)
        dpg.add_mouse_click_handler(button=0, callback=_on_global_click)
    register_resize("scan_picker", _on_resize)
    threading.Thread(target=_ticker_loop, daemon=True).start()
    _s["ready"] = True