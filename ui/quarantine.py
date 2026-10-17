import dearpygui.dearpygui as dpg
from ui.theme import COLORS
from ui.layout import register_resize
from ui.scan_layout import _get_themes, _center_indent, PAGE_LEFT_PAD
from ui.scan_pipeline import _row_width
from ui.scan_threats import (_themes as _threat_themes, _flat_button_theme, PILL_ROUNDING,
                             PILL_BG_ALPHA, PILL_BORDER_ALPHA, GUTTER_W, ROW_PAD_X)
from ui.table_style import TABLE_ROW_HEIGHT, TABLE_PILL_HEIGHT, TABLE_CELL_MUTED_COLOR, apply_table_font
from ui.table_text import fit_text
from ui.confirm_dialog import init_confirm, ask_confirm
from ui.toast import init_toast, show_toast
import sys
import os

# Add parent directory to path to import Malware_System
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    import system.quarantines.quarantine as qq
    BACKEND_AVAILABLE = True
except Exception as e:
    print(f"Warning [ui/quarantine.py]: Could not load backend dependency 'quarantines.quarantine': {e}")
    BACKEND_AVAILABLE = False

# quarantine.py
# The table look is shared with the Scan page's Detected Threats table (ui/scan_threats.py): same header bar,
# row shading, flat text buttons and gutters. Font size, row height and cell colors are local to this file.

# ---- Panel layout (tune here) ----
QUAR_HEADER_HEIGHT = 110       # title + subtitle block above the panel (same estimate as the dashboard)
QUAR_BOTTOM_MARGIN = 90        # space under the panel so the help button never covers the last rows
QUAR_PANEL_MIN_HEIGHT = 320    # below this the page scrolls instead of squishing
QUAR_PANEL_START_W = 1240      # placeholder size until ui/layout.py sets the real one
QUAR_PANEL_START_H = 520
QUAR_CHILD_PAD_Y = 8           # DPG default child window padding
QUAR_TABLE_CHROME = 2 * QUAR_CHILD_PAD_Y + 4   # table height = panel height - this (raise if the table gets cut off at the bottom)

# ---- Table text + rows (shared with the other tables: change these in ui/table_style.py) ----
QUAR_ROW_HEIGHT = TABLE_ROW_HEIGHT
QUAR_PILL_HEIGHT = TABLE_PILL_HEIGHT
CELL_MUTED_COLOR = TABLE_CELL_MUTED_COLOR

# ---- Counter chip next to the title ----
CHIP_HEIGHT = 28               # raise or lower if it doesn't line up with the title
CHIP_PAD_X = 12

# ---- Columns (fixed ones in px INCLUDING cell padding, stretch ones as weights) ----
LOCK_ICON_SIZE = 20
ROW_ITEM_SPACING_Y = 4         # DPG default vertical item spacing
LOCK_NUDGE_Y = max(0, (QUAR_ROW_HEIGHT - LOCK_ICON_SIZE) // 2 - ROW_ITEM_SPACING_Y)   # centers the lock on the row text
COL_ICON_W = LOCK_ICON_SIZE + 2 * ROW_PAD_X
COL_NAME_WEIGHT = 2.0
COL_LOCATION_WEIGHT = 3.0
COL_DATE_W = 200
COL_RISK_W = 120
RESTORE_BTN_W = 96
DELETE_BTN_W = 88
ACTION_BTN_GAP = 8
COL_ACTIONS_W = RESTORE_BTN_W + DELETE_BTN_W + ACTION_BTN_GAP + 2 * ROW_PAD_X + 8   # +8 = safety so buttons never clip

# ---- Narrow mode (window below the breakpoint): Location is left out and the other columns get tighter ----
QUAR_NARROW_BREAKPOINT = 1100  # content width below which the table is rebuilt without the Location column (full path moves into the name tooltip)
LOCK_ICON_SIZE_NARROW = 16     # smaller lock. It stays visible because the orange "missing" warning matters at a glance
COL_ICON_W_NARROW = 32         # lock column. Raise if the lock gets clipped
COL_DATE_W_NARROW = 185        # "2026-10-17 20:57:48" measures about 160px. Raise if the date clips
RESTORE_BTN_W_NARROW = 84
DELETE_BTN_W_NARROW = 76
COL_ACTIONS_W_NARROW = RESTORE_BTN_W_NARROW + DELETE_BTN_W_NARROW + ACTION_BTN_GAP + 2 * ROW_PAD_X + 4   # +4 safety (wide mode uses +8)

# ---- Ellipsis (long names end in "...", the full text stays in the tooltip) ----
ELLIPSIS_ENABLED = True        # False = old hard clipping
MEASURE_MIN_FRAME = 40         # DPG can't measure text before this frame, so rows drawn earlier are left untrimmed
PANEL_PAD_X = 8                # the panel's own left/right padding (DPG default)
TABLE_SCROLLBAR_W = 16         # room kept for the table's scrollbar. Raise if "..." touches the next column
FIXED_COL_EXTRA_PX = 96        # padding the 6 fixed columns add on top of their widths. Measured at 924 and 1324: estimate lands 2-10px under the real cell, so text never overflows

# ---- Risk levels ----
RISK_SEVERE_MIN = 0.9          # probability at or above this = SEVERE
RISK_HIGH_MIN = 0.7
RISK_MEDIUM_MIN = 0.4          # anything below this = LOW
RISK_MISSING_LABEL = "HIGH"    # label for records with no confidence score ("UNKNOWN" is the honest alternative)
SEVERE_BG_ALPHA = 90           # SEVERE pill is more solid than the others
RISK_STYLE = {                 # label -> (color, background alpha)
    "SEVERE": (COLORS["accent_red"], SEVERE_BG_ALPHA),
    "HIGH": (COLORS["accent_red"], PILL_BG_ALPHA),
    "MEDIUM": (COLORS["accent_orange"], PILL_BG_ALPHA),
    "LOW": (COLORS["accent_green"], PILL_BG_ALPHA),
    "UNKNOWN": (COLORS["text_secondary"], PILL_BG_ALPHA),
}

# ---- Lock icon + missing-file hint ----
LOCK_COLOR = COLORS["accent_red"]
LOCK_COLOR_MISSING = COLORS["accent_orange"]
SHOW_MISSING_HINT = True       # orange lock + tooltip line when the quarantined copy is missing from disk

# ---- Tooltips ----
TIP_COLOR = COLORS["text_secondary"]
TIP_RESTORE = "Move this file back to its original location"
TIP_DELETE = "Permanently delete the quarantined file"
TIP_MISSING = "Not found in the quarantine folder when this list was loaded"
TIP_NO_SCORE = "No confidence score was recorded for this file"
TIP_SCORE = "Confidence: {score:.1%}"

# ---- Delete confirmation (the popup itself lives in ui/confirm_dialog.py) ----
CONFIRM_DELETE_TITLE = "Delete permanently?"
CONFIRM_DELETE_MESSAGE = "{name} will be permanently removed from quarantine. This can't be undone."
CONFIRM_DELETE_LABEL = "Delete"

# ---- Empty state ----
EMPTY_TITLE = "Nothing in quarantine"
EMPTY_SUBTITLE = "Files you quarantine from a scan will show up here"
EMPTY_ICON_SIZE = 48
EMPTY_GAP = 8
EMPTY_TITLE_HEIGHT = 30
EMPTY_SUB_HEIGHT = 24
EMPTY_BLOCK_HEIGHT = EMPTY_ICON_SIZE + EMPTY_GAP + EMPTY_TITLE_HEIGHT + EMPTY_SUB_HEIGHT + 12
EMPTY_BLOCK_BIAS = 20          # raises the block slightly above the exact center

# ---- Toast messages (the toast itself lives in ui/toast.py) ----
TOAST_NAME_MAX_CHARS = 28      # long file names are shortened with "..." so the toast stays on one line
MSG_RESTORED = "{name} restored to its original location"
MSG_RESTORE_MISSING = "Can't restore {name}: the file is missing"
MSG_RESTORE_GONE = "{name} is no longer in the quarantine list"
MSG_RESTORE_FAILED = "Couldn't restore {name} (see terminal)"
MSG_DELETED = "{name} permanently deleted"
MSG_DELETED_RECORD_ONLY = "{name} removed (the file was already gone)"
MSG_DELETE_FAILED = "Couldn't delete {name} (see terminal)"
MSG_NO_BACKEND = "Backend not loaded, nothing was changed"
MSG_UNKNOWN = "{name}: {result}"   # used if the backend returns text we don't recognise

# What system/quarantines/quarantine.py returns. If your partner rewords these, update them here.
RESULT_RESTORED_PREFIX = "Restored"
RESULT_NOT_FOUND = "File not found in quarantine"
RESULT_DELETED = "Deleted"
RESULT_FAILED_PREFIX = "Failed"

_T = {}
# narrow       = what the window width says right now
# table_narrow = what the CURRENT table was built with (rows must match its columns, so rows read this one)
# cells        = (name button, full name, location button or None, full path), re-trimmed on resize
_state = {"panel_w": QUAR_PANEL_START_W, "panel_h": QUAR_PANEL_START_H, "icons": None, "fonts": None,
          "narrow": False, "table_narrow": False, "cells": []}
_row_info = {}   # dest_path -> {"name", "missing"}; filled when rows are built, read by the toast messages


def _short(name):
    if len(name) <= TOAST_NAME_MAX_CHARS:
        return name
    return name[:TOAST_NAME_MAX_CHARS - 3] + "..."


def _toast_restore(result, info):
    """Turns what qq.restore_file returned into a toast. It only reads the result, nothing else."""
    name = _short(info.get("name", "File"))
    text = str(result)
    if result is None and not BACKEND_AVAILABLE:
        show_toast(MSG_NO_BACKEND, "warning")
    elif result is None:
        show_toast(MSG_RESTORE_GONE.format(name=name), "warning")   # the backend returns None when the record isn't in its list
    elif text.startswith(RESULT_RESTORED_PREFIX):
        show_toast(MSG_RESTORED.format(name=name), "success")
    elif text == RESULT_NOT_FOUND:
        show_toast(MSG_RESTORE_MISSING.format(name=name), "warning")
    elif text.startswith(RESULT_FAILED_PREFIX):
        show_toast(MSG_RESTORE_FAILED.format(name=name), "error")
    else:
        show_toast(MSG_UNKNOWN.format(name=name, result=text), "info")


def _toast_delete(result, info):
    """Turns what qq.delete_file returned into a toast. It only reads the result, nothing else."""
    name = _short(info.get("name", "File"))
    text = str(result)
    if result is None:
        show_toast(MSG_NO_BACKEND, "warning")   # delete_file always returns text, so None only means the backend isn't loaded
    elif text == RESULT_DELETED:
        if info.get("missing"):
            show_toast(MSG_DELETED_RECORD_ONLY.format(name=name), "info")
        else:
            show_toast(MSG_DELETED.format(name=name), "success")
    elif text.startswith(RESULT_FAILED_PREFIX):
        show_toast(MSG_DELETE_FAILED.format(name=name), "error")
    else:
        show_toast(MSG_UNKNOWN.format(name=name, result=text), "info")


# ---------------------------------------------------------------------------
# Themes (built once)
# ---------------------------------------------------------------------------

def _pill_theme(color, bg_alpha, pad_x=0):
    bg = (*color, bg_alpha)
    border = (*color, PILL_BORDER_ALPHA)
    with dpg.theme() as theme:
        with dpg.theme_component(dpg.mvButton):
            dpg.add_theme_color(dpg.mvThemeCol_Button, bg)
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, bg)
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, bg)
            dpg.add_theme_color(dpg.mvThemeCol_Text, color)
            dpg.add_theme_color(dpg.mvThemeCol_Border, border)
            dpg.add_theme_style(dpg.mvStyleVar_FrameBorderSize, 1)
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, PILL_ROUNDING)
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding, pad_x, 0)
    return theme


def _themes():
    if _T:
        return _T
    for level, (color, alpha) in RISK_STYLE.items():
        _T[f"risk_{level}"] = _pill_theme(color, alpha)
    _T["chip"] = _pill_theme(COLORS["accent_blue"], PILL_BG_ALPHA, CHIP_PAD_X)
    _T["cell_muted"] = _flat_button_theme(CELL_MUTED_COLOR)   # location + date text
    return _T


# ---------------------------------------------------------------------------
# Risk
# ---------------------------------------------------------------------------

def _risk_for(prob):
    """Returns (label, probability as a float or None)."""
    if prob is None:
        return RISK_MISSING_LABEL, None
    try:
        p = float(prob)
    except (TypeError, ValueError):
        return RISK_MISSING_LABEL, None
    if p >= RISK_SEVERE_MIN:
        return "SEVERE", p
    if p >= RISK_HIGH_MIN:
        return "HIGH", p
    if p >= RISK_MEDIUM_MIN:
        return "MEDIUM", p
    return "LOW", p


def _risk_badge(risk):
    """Draws one risk pill in the current cell. Kept under the old name in case another file imports it."""
    ct = _themes()
    pill = dpg.add_button(label=risk, width=-1, height=QUAR_PILL_HEIGHT)
    dpg.bind_item_theme(pill, ct.get(f"risk_{risk}", ct["risk_UNKNOWN"]))
    return pill


# ---------------------------------------------------------------------------
# Actions (the real logic: unchanged)
# ---------------------------------------------------------------------------

def _restore_file(sender, app_data, user_data):
    dest_path = user_data
    info = _row_info.get(dest_path, {})   # toast only
    print(f"Restoring: {dest_path}")

    result = None   # toast only: stays None if the backend isn't loaded
    if BACKEND_AVAILABLE:
        result = qq.restore_file(dest_path)
        print(f"Restore result: {result}")
    _toast_restore(result, info)   # toast only

    _rebuild_quarantine_table()

    from ui.history import _rebuild_history
    _rebuild_history()

    from ui.dashboard import refresh_dashboard_stats
    refresh_dashboard_stats()

def _delete_file(sender, app_data, user_data):
    dest_path = user_data
    info = _row_info.get(dest_path, {})   # toast only
    print(f"Deleting: {dest_path}")

    result = None   # toast only: stays None if the backend isn't loaded
    if BACKEND_AVAILABLE:
        result = qq.delete_file(dest_path)
        print(f"Delete result: {result}")
    _toast_delete(result, info)   # toast only

    _rebuild_quarantine_table()

    from ui.history import _rebuild_history
    _rebuild_history()

    from ui.dashboard import refresh_dashboard_stats
    refresh_dashboard_stats()


def _ask_delete(sender, app_data, user_data):
    """The Delete button lands here first. It asks, and only the popup's confirm button runs _delete_file.
    The popup lives in ui/confirm_dialog.py (ask_confirm)."""
    dest_path, name = user_data
    ask_confirm(CONFIRM_DELETE_TITLE, CONFIRM_DELETE_MESSAGE.format(name=name),
                on_confirm=_delete_file, user_data=dest_path,
                confirm_label=CONFIRM_DELETE_LABEL, danger=True)


# ---------------------------------------------------------------------------
# Table
# ---------------------------------------------------------------------------

def _col_widths(narrow):
    """(lock column, date column, actions column) for the wide or narrow table."""
    if narrow:
        return COL_ICON_W_NARROW, COL_DATE_W_NARROW, COL_ACTIONS_W_NARROW
    return COL_ICON_W, COL_DATE_W, COL_ACTIONS_W


def _label_widths():
    """(Threat Name, Location) pixel budget for the text inside the cells. An estimate from the column constants.
    Narrow table: no Location, the name gets everything."""
    narrow = _state["table_narrow"]
    icon_w, date_w, actions_w = _col_widths(narrow)
    fixed = 2 * GUTTER_W + icon_w + date_w + COL_RISK_W + actions_w
    table_w = _state["panel_w"] - 2 * PANEL_PAD_X - TABLE_SCROLLBAR_W
    avail = max(0, table_w - fixed - FIXED_COL_EXTRA_PX)
    if narrow:
        return int(avail - 2 * ROW_PAD_X), 0
    total = COL_NAME_WEIGHT + COL_LOCATION_WEIGHT
    return (int(avail * COL_NAME_WEIGHT / total - 2 * ROW_PAD_X),
            int(avail * COL_LOCATION_WEIGHT / total - 2 * ROW_PAD_X))


def _fit_cell(name_btn, name, loc_btn, path, widths):
    """Shortens the text cells to their budget. The full text stays in the tooltips."""
    if not ELLIPSIS_ENABLED or dpg.get_frame_count() < MEASURE_MIN_FRAME:
        return
    font = (_state["fonts"] or {}).get("table")
    if dpg.does_item_exist(name_btn):
        dpg.set_item_label(name_btn, fit_text(name, widths[0], font))
    if loc_btn is not None and dpg.does_item_exist(loc_btn):
        dpg.set_item_label(loc_btn, fit_text(path, widths[1], font))


def _refit_cells():
    widths = _label_widths()
    for cell in list(_state["cells"]):
        _fit_cell(*cell, widths)



def _build_table():
    """Creates a fresh, empty table with its columns. Theme and font are re-bound every time.
    The Location column only exists in the wide table (show=False is ignored by this DPG build)."""
    tt = _threat_themes()
    narrow = _state["narrow"]
    _state["table_narrow"] = narrow
    icon_w, date_w, actions_w = _col_widths(narrow)
    with dpg.table(parent="quarantine_container", tag="quarantine_table", header_row=True, row_background=True,
                   borders_innerH=False, borders_outerH=False,
                   borders_innerV=False, borders_outerV=False,
                   scrollY=True, freeze_rows=1, width=-1,
                   height=max(1, _state["panel_h"] - QUAR_TABLE_CHROME)):
        dpg.add_table_column(label="", width_fixed=True, init_width_or_weight=GUTTER_W)
        dpg.add_table_column(label="", width_fixed=True, init_width_or_weight=icon_w)
        dpg.add_table_column(label="Threat Name", width_stretch=True, init_width_or_weight=COL_NAME_WEIGHT)
        if not narrow:
            dpg.add_table_column(label="Original Location", width_stretch=True, init_width_or_weight=COL_LOCATION_WEIGHT)
        dpg.add_table_column(label="Date Detected", width_fixed=True, init_width_or_weight=date_w)
        dpg.add_table_column(label="Risk", width_fixed=True, init_width_or_weight=COL_RISK_W)
        dpg.add_table_column(label="Actions", width_fixed=True, init_width_or_weight=actions_w)
        dpg.add_table_column(label="", width_fixed=True, init_width_or_weight=GUTTER_W)
    dpg.bind_item_theme("quarantine_table", tt["table"])
    apply_table_font("quarantine_table", _state["fonts"])   # shared table font (ui/table_style.py)


def _add_row(entry):
    tt = _threat_themes()
    ct = _themes()
    base = _get_themes()
    icons = _state["icons"]
    path = entry.get("original_path", "Unknown")
    name = os.path.basename(path) or path
    dest = entry.get("dest_path")
    missing = SHOW_MISSING_HINT and not entry.get("_exists", True)
    label, prob = _risk_for(entry.get("probability"))
    _row_info[dest] = {"name": name, "missing": not entry.get("_exists", True)}   # read by the toast messages
    narrow = _state["table_narrow"]   # the table's mode, so the cells always match its columns
    lock_size = LOCK_ICON_SIZE_NARROW if narrow else LOCK_ICON_SIZE
    lock_nudge = max(0, (QUAR_ROW_HEIGHT - lock_size) // 2 - ROW_ITEM_SPACING_Y)
    restore_w = RESTORE_BTN_W_NARROW if narrow else RESTORE_BTN_W
    delete_w = DELETE_BTN_W_NARROW if narrow else DELETE_BTN_W

    with dpg.table_row(parent="quarantine_table"):
        dpg.add_spacer(width=1)   # left gutter cell

        with dpg.group():         # lock icon cell (a group, so the nudge spacer and the icon share ONE cell)
            dpg.add_spacer(height=lock_nudge)
            lock = icons.get("lock") if icons else None
            if lock:
                dpg.add_image(lock, width=lock_size, height=lock_size,
                              tint_color=LOCK_COLOR_MISSING if missing else LOCK_COLOR)

        name_btn = dpg.add_button(label=name, width=-1, height=QUAR_ROW_HEIGHT)
        dpg.bind_item_theme(name_btn, tt["name"])
        with dpg.tooltip(name_btn):
            dpg.add_text(name, color=COLORS["text_primary"])
            if narrow:   # Location is hidden, so its path moves here
                dpg.add_text(path, color=TIP_COLOR)
            if missing:
                dpg.add_text(TIP_MISSING, color=COLORS["accent_orange"])

        loc_btn = None
        if not narrow:
            loc_btn = dpg.add_button(label=path, width=-1, height=QUAR_ROW_HEIGHT)
            dpg.bind_item_theme(loc_btn, ct["cell_muted"])
            with dpg.tooltip(loc_btn):
                dpg.add_text(path, color=TIP_COLOR)
        _state["cells"].append((name_btn, name, loc_btn, path))
        _fit_cell(name_btn, name, loc_btn, path, _label_widths())

        date_btn = dpg.add_button(label=str(entry.get("timestamp", "Unknown")), width=-1, height=QUAR_ROW_HEIGHT)
        dpg.bind_item_theme(date_btn, ct["cell_muted"])

        pill = _risk_badge(label)
        with dpg.tooltip(pill):
            dpg.add_text(TIP_NO_SCORE if prob is None else TIP_SCORE.format(score=prob), color=TIP_COLOR)

        with dpg.group(horizontal=True):
            restore = dpg.add_button(label="Restore", width=restore_w, height=QUAR_ROW_HEIGHT,
                                     callback=_restore_file, user_data=dest)
            dpg.bind_item_theme(restore, base["btn_secondary"])
            with dpg.tooltip(restore):
                dpg.add_text(TIP_RESTORE, color=TIP_COLOR)
            delete = dpg.add_button(label="Delete", width=delete_w, height=QUAR_ROW_HEIGHT,
                                    callback=_ask_delete, user_data=(dest, name))
            dpg.bind_item_theme(delete, base["btn_cancel"])
            with dpg.tooltip(delete):
                dpg.add_text(TIP_DELETE, color=TIP_COLOR)

        dpg.add_spacer(width=1)   # right gutter cell


def _update_chip(count):
    if dpg.does_item_exist("quarantine_count_chip"):
        dpg.set_item_label("quarantine_count_chip", f"{count} item" + ("" if count == 1 else "s"))


def _rebuild_quarantine_table():
    """Called by the sidebar every time the tab opens, and after Restore / Delete."""
    if not dpg.does_item_exist("quarantine_container"):
        return
    if dpg.does_item_exist("quarantine_table"):
        dpg.delete_item("quarantine_table")
    _row_info.clear()   # rows are rebuilt below; the callbacks read this BEFORE they trigger a rebuild
    _state["cells"].clear()
    _build_table()

    entries = []
    if BACKEND_AVAILABLE:
        entries = qq.list_quarantine_items()
        print(f"Quarantine entries: {len(entries)}")

    has_items = bool(entries)
    dpg.configure_item("quarantine_table", show=has_items)
    if dpg.does_item_exist("quarantine_empty"):
        dpg.configure_item("quarantine_empty", show=not has_items)
    _update_chip(len(entries))

    for entry in entries:
        _add_row(entry)


# ---------------------------------------------------------------------------
# Resize
# ---------------------------------------------------------------------------

def _resize_quarantine(content_w, content_h):
    """Called by ui/layout.py whenever the window size changes."""
    row_w = _row_width(content_w)   # same width as the Scan page cards, so the edges line up
    panel_h = max(QUAR_PANEL_MIN_HEIGHT, content_h - QUAR_HEADER_HEIGHT - QUAR_BOTTOM_MARGIN)
    _state["panel_w"] = row_w
    _state["panel_h"] = panel_h    # _rebuild_quarantine_table reads this, so a rebuild never snaps back

    if dpg.does_item_exist("quarantine_container"):
        dpg.configure_item("quarantine_container", width=row_w, height=panel_h)
    if dpg.does_item_exist("quarantine_table"):
        dpg.configure_item("quarantine_table", height=max(1, panel_h - QUAR_TABLE_CHROME))
    narrow = content_w < QUAR_NARROW_BREAKPOINT
    if narrow != _state["narrow"]:   # only fires when the window crosses the breakpoint, not on every pixel of a drag
        _state["narrow"] = narrow
        _rebuild_quarantine_table()
    _refit_cells()
    if dpg.does_item_exist("quarantine_empty_top"):
        dpg.configure_item("quarantine_empty_top",
                           height=max(0, panel_h // 2 - EMPTY_BLOCK_HEIGHT // 2 - EMPTY_BLOCK_BIAS))
    if dpg.does_item_exist("quarantine_empty_icon"):
        dpg.configure_item("quarantine_empty_icon", indent=_center_indent(row_w, EMPTY_ICON_SIZE))


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def _build_empty_state(fonts, icons):
    """The 'nothing here' block. Hidden while there are items. Centered with full-width invisible buttons."""
    t = _get_themes()
    with dpg.group(tag="quarantine_empty", show=False):
        dpg.add_spacer(height=100, tag="quarantine_empty_top")
        icon = icons.get("shield_check") if icons else None
        if icon:
            dpg.add_image(icon, width=EMPTY_ICON_SIZE, height=EMPTY_ICON_SIZE,
                          tint_color=COLORS["accent_green"], tag="quarantine_empty_icon")
        dpg.add_spacer(height=EMPTY_GAP)
        dpg.add_button(label=EMPTY_TITLE, width=-1, height=EMPTY_TITLE_HEIGHT, tag="quarantine_empty_title")
        dpg.add_button(label=EMPTY_SUBTITLE, width=-1, height=EMPTY_SUB_HEIGHT, tag="quarantine_empty_sub")
    dpg.bind_item_theme("quarantine_empty_title", t["label_on"])
    dpg.bind_item_theme("quarantine_empty_sub", t["sub"])
    if fonts and fonts.get("subheading") is not None:
        dpg.bind_item_font("quarantine_empty_title", fonts["subheading"])


def build_quarantine(parent, fonts, icons):
    _state["icons"] = icons
    _state["fonts"] = fonts
    init_confirm(fonts)
    init_toast()
    ct = _themes()

    dpg.add_spacer(height=20, parent=parent)
    with dpg.group(horizontal=True, parent=parent):
        dpg.add_spacer(width=PAGE_LEFT_PAD)
        with dpg.group():
            with dpg.group(horizontal=True):
                dpg.add_text("Quarantine", tag="quarantine_page_title")
                dpg.bind_item_font("quarantine_page_title", fonts["heading"])
                dpg.add_button(label="0 items", tag="quarantine_count_chip", height=CHIP_HEIGHT)
            dpg.bind_item_theme("quarantine_count_chip", ct["chip"])
            dpg.add_text("Isolated files that are potentially harmful to your system", color=COLORS["text_secondary"])
            dpg.add_spacer(height=15)

            with dpg.child_window(width=QUAR_PANEL_START_W, height=QUAR_PANEL_START_H, tag="quarantine_container",
                                  no_scrollbar=True, no_scroll_with_mouse=True):
                _build_empty_state(fonts, icons)
            _rebuild_quarantine_table()

    register_resize("quarantine", _resize_quarantine)