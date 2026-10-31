import os
import sys
import threading
import traceback
from collections import OrderedDict

import dearpygui.dearpygui as dpg
from ui.theme import COLORS
from ui.layout import register_resize
from ui.scan_layout import _get_themes, _center_indent, PAGE_LEFT_PAD
from ui.scan_pipeline import _row_width
from ui.scan_threats import (_themes as _threat_themes, _flat_button_theme, PILL_ROUNDING,
                             PILL_BG_ALPHA, PILL_BORDER_ALPHA, ROW_PAD_X, GUTTER_W)
from ui.table_style import (TABLE_ROW_HEIGHT, TABLE_PILL_HEIGHT, TABLE_CELL_MUTED_COLOR,
                            TABLE_FONT_KEY, apply_table_font)
from ui.table_text import fit_text, text_width

#history

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    import system.history.logs as hl
    from system.history.batches import list_batches, get_batch
    BACKEND_AVAILABLE = True
except Exception as e:
    print(f"Warning [ui/history.py]: Could not load backend history deps: {e}")
    BACKEND_AVAILABLE = False
    list_batches = None
    get_batch = None

# ---- TEMP test switch (set to False, then delete _fake_files / _fake_batches and the call in _build_batches_from_backend) ----
HISTORY_DEBUG_FAKE = False      # adds 6 FAKE batches (with fake file lists) at the top. UI only, nothing is saved

# ---- Page layout (tune here) ----
HISTORY_HEADER_HEIGHT = 110    # title + subtitle block above the list (same estimate as Quarantine)
HISTORY_BOTTOM_MARGIN = 90     # space under the list so the help button never covers the last card
HISTORY_PANEL_MIN_HEIGHT = 320 # below this the page scrolls instead of squishing
HISTORY_START_W = 1240         # placeholder until ui/layout.py sets the real size
HISTORY_START_H = 520
CARD_W_TRIM = 24               # card width = list width - this (padding + room for the scrollbar). Raise if a card pokes out on the right
CHIP_HEIGHT = 28               # the "N scans" chip next to the title
CHIP_PAD_X = 12

# ---- Batch cards ----
CARD_HEIGHT = 116              # raise if the chip row touches the bottom edge, lower if there's a gap
CARD_PAD_Y = 8                 # DPG default child window padding
ITEM_SPACING_X = 8             # DPG default spacing
ITEM_SPACING_Y = 4
ROW_GAP = 12                   # space between cards
BADGE_SIZE = 48                # icon badge on the left
BADGE_ICON_SIZE = 24
BADGE_LEFT = 22                # distance from the card's left edge to the badge
BADGE_TEXT_GAP = 20            # gap between the badge and the text column
TEXT_COL_LEFT = BADGE_LEFT + BADGE_SIZE + BADGE_TEXT_GAP   # where the text column starts
MID_TOP_SPACER = 4             # pushes the three text rows down (raise if they sit high in the card)
MID_MIN_W = 240
TARGET_HEIGHT = 26             # the clipped path row
RIGHT_W = 190                  # right column (date + status pill)
RIGHT_MARGIN = 22              # gap between the right column and the card's right edge
TEXT_RIGHT_GAP = 16            # minimum gap between the text column and the right column
RIGHT_DATE_H = 26              # height of the date line
STATUS_PILL_H = TABLE_PILL_HEIGHT
STATUS_PILL_W = 140            # fixed, so it can be centered under the date (raise if COMPLETED / CANCELLED clip)
RIGHT_NUDGE_Y = 0              # moves the right block down (+) or up (-) from the exact vertical center
RIGHT_BLOCK_H = RIGHT_DATE_H + ITEM_SPACING_Y + STATUS_PILL_H
RIGHT_TOP = max(0, (CARD_HEIGHT - RIGHT_BLOCK_H) // 2 + RIGHT_NUDGE_Y)   # block is centered in the card
CHIP_ROW_H = TABLE_PILL_HEIGHT
SHOW_TYPE_DOT = True           # small dot in the scan-type color before the title
TYPE_DOT_RADIUS = 5
TYPE_DOT_BOX_H = 24
TYPE_DOT_NUDGE_Y = 1           # raise/lower the dot if it doesn't line up with the title
TARGET_FALLBACK = "No target recorded"

# ---- Ellipsis (long paths end in "...", the full path stays in the tooltip) ----
ELLIPSIS_ENABLED = True        # False = old hard clipping
MEASURE_MIN_FRAME = 40         # DPG can't measure text before this frame, so cards drawn earlier are left untrimmed
PATH_TEXT_MARGIN = 8           # room kept inside the path button so the text never touches its right edge. Raise if "..." touches the edge

# ---- Card colors ----
CARD_BG = COLORS["bg_card"]
CARD_BG_HOVER = (37, 49, 76)
CARD_BORDER = COLORS["border"]
CARD_BORDER_HOVER = COLORS["accent_blue"]
CARD_BORDER_ATTENTION = (*COLORS["accent_red"], 110)          # threats found / scan failed
CARD_BORDER_ATTENTION_HOVER = (*COLORS["accent_red"], 255)
TIP_COLOR = COLORS["text_secondary"]

# ---- Batch state -> (icon keys tried in order, color, tooltip on the icon) ----
STATE_STYLE = {
    "running": (("loader_circle", "scan_search"), COLORS["accent_blue"], "This scan is still running"),
    "failed": (("circle_x", "octagon_alert"), COLORS["accent_red"], "This scan failed or was cancelled"),
    "threats": (("shield_alert", "octagon_alert"), COLORS["accent_red"], "Threats were found in this scan"),
    "empty": (("file_x", "folder_search"), COLORS["text_secondary"], "Nothing was flagged in this scan"),
    "clean": (("shield_check",), COLORS["accent_green"], "No threats were found"),
}

# ---- Empty state (list) ----
EMPTY_TITLE = "No scan history yet"
EMPTY_SUBTITLE = "Run a scan and its summary will show up here"
EMPTY_ICON_SIZE = 48
EMPTY_GAP = 8
EMPTY_TITLE_HEIGHT = 30
EMPTY_SUB_HEIGHT = 24
EMPTY_BLOCK_HEIGHT = EMPTY_ICON_SIZE + EMPTY_GAP + EMPTY_TITLE_HEIGHT + EMPTY_SUB_HEIGHT + 12
EMPTY_BLOCK_BIAS = 20

# ---- Detail view: summary card ----
SUMMARY_H = 196                # raise if the strip at the bottom of the card gets cut off, lower if there's a gap
SUMMARY_STRIP_GAP = 10         # space above the divider line
STRIP_WEIGHTS = (1.3, 1.3, 0.8, 1.5)   # how the four cells (started, completed, duration, batch id) share the width
STRIP_LABELS = ("Started", "Completed", "Duration", "Batch ID")
STRIP_LABELS_UPPERCASE = True
STRIP_LABEL_COLOR = COLORS["text_secondary"]
STRIP_CELL_PAD_X = BADGE_LEFT - 8      # lines the first cell up with the icon badge (8 = the card's own padding)
STRIP_CELL_PAD_Y = 2

# ---- Detail view: layout ----
DETAIL_BACK_W = 200
DETAIL_BACK_H = 34
DETAIL_BACK_GAP = 12           # space under the Back button
DETAIL_SECTION_GAP = 14        # space between the summary card and the "Files scanned" heading
DETAIL_HEADING_H = 28          # height of the heading line
DETAIL_HEADING_GAP = 6
DETAIL_FILL_TRIM = 16          # safety margin so the table panel never makes the page scroll. Raise if a scrollbar appears at the right
DETAIL_PANEL_MIN_H = 220       # the table panel is never shorter than this (the whole detail area scrolls instead)
DETAIL_CHROME_H = (DETAIL_BACK_H + DETAIL_BACK_GAP + SUMMARY_H + DETAIL_SECTION_GAP + DETAIL_HEADING_H
                   + DETAIL_HEADING_GAP + 6 * ITEM_SPACING_Y + DETAIL_FILL_TRIM)   # everything above the table panel
DETAIL_TABLE_CHROME = 2 * CARD_PAD_Y + 4   # table height = panel height - this (raise if the table gets cut off at the bottom)
DETAIL_MAX_FILES = 250         # files shown per batch
DETAIL_TIP_WRAP = 520          # wrap width of the details tooltip on the file name
DETAIL_EMPTY_TITLE = "Nothing was saved for this scan"
DETAIL_EMPTY_SUBTITLE = "Only flagged files, errors and quarantine actions are kept in History"

# ---- Detail view: file table columns (fixed ones in px INCLUDING cell padding, stretch ones as weights) ----
DETAIL_ICON_SIZE = 20
DETAIL_ICON_NUDGE_Y = max(0, (TABLE_ROW_HEIGHT - DETAIL_ICON_SIZE) // 2 - ITEM_SPACING_Y)   # centers the icon on the row text
DETAIL_COL_ICON_W = DETAIL_ICON_SIZE + 2 * ROW_PAD_X
DETAIL_COL_NAME_WEIGHT = 2.0
DETAIL_COL_LOCATION_WEIGHT = 3.0
DETAIL_COL_RESULT_W = 150      # was 170. GUESS: "QUARANTINED" is the widest pill. Raise if it clips
DETAIL_COL_CONF_W = 100        # was 140 (same as Scan). Raise if the "Confidence" header clips
DETAIL_COL_EXPLAIN_W = 75      # was 100 (same as Scan)
DETAIL_COL_BEHAVIOR_CONF_W = 110   # was 115. The header is now "Behavior %". Raise if it clips
DETAIL_COL_TYPE_W = 150        # long types end in "..." (full text in the tooltip)

# ---- Detail table: narrow mode (window below the breakpoint) ----
DETAIL_NARROW_BREAKPOINT = 1150    # content width below which Location is left out and the two behavior columns merge
DETAIL_COL_BEHAVIOR_W_NARROW = 150 # the merged "85% | Ransomware" column (same as Scan)
DETAIL_BEHAVIOR_MARGIN = 16        # room kept inside the merged cell so "..." never touches the border
DETAIL_ICON_SIZE_NARROW = 16       # smaller result icon on narrow
DETAIL_COL_ICON_W_NARROW = 32      # raise if the icon clips
DETAIL_PANEL_PAD_X = 8             # the panel's own left/right padding
DETAIL_TABLE_SCROLLBAR_W = 16      # room kept for the table's scrollbar. Raise if "..." touches the next column
DETAIL_EXTRA_PX_WIDE = 148         # padding the wide table's fixed columns add on top of their widths. Measured at card_w 1251: budget lands 5-9px under the real cell
DETAIL_EXTRA_PX_NARROW = 124       # same for the narrow table. Measured at card_w 852: budget lands 10px under the real cell

# ---- Detail view: result -> (color, icon keys tried in order) ----
RESULT_STYLE = {
    "MALICIOUS": (COLORS["accent_red"], ("shield_alert", "octagon_alert")),
    "SUSPICIOUS": (COLORS["accent_orange"], ("shield_alert", "octagon_alert")),
    "CLEAN": (COLORS["accent_green"], ("shield_check",)),
    "SAFE": (COLORS["accent_green"], ("shield_check",)),
    "BENIGN": (COLORS["accent_green"], ("shield_check",)),
    "QUARANTINED": (COLORS["accent_orange"], ("shield_cog",)),
    "RESTORED": (COLORS["accent_blue"], ("refresh", "shield_check")),
    "DELETED": (COLORS["text_secondary"], ("trash", "circle_x")),
    "ERROR": (COLORS["text_secondary"], ("circle_x", "octagon_alert")),
    "FAILED": (COLORS["text_secondary"], ("circle_x", "octagon_alert")),
}
RESULT_DEFAULT = (COLORS["text_secondary"], ("file_x", "folder_search"))   # any result we don't know

ICON_BADGE_SIZE = 40           # default badge size (the cards pass their own)

GLOBAL_ICONS = None
_BATCH_ROW_MAP = {}
_HISTORY_DETAIL_BATCH = None
_HISTORY_MOUSE_BOUND = False
_LAST_BATCH_LIST = []

_T = {}
_CARD_THEMES = {}
_BADGE_THEMES = {}


def _mid_width(card_w):
    return max(MID_MIN_W, card_w - TEXT_COL_LEFT - RIGHT_W - RIGHT_MARGIN - TEXT_RIGHT_GAP)


def _detail_mid_w(card_w):
    """Path row width in the summary card (no right column there, so it can be wider)."""
    return max(MID_MIN_W, card_w - TEXT_COL_LEFT - RIGHT_MARGIN - TEXT_RIGHT_GAP)


_state = {
    "fonts": None, "row_w": HISTORY_START_W, "panel_h": HISTORY_START_H,
    "card_w": HISTORY_START_W - CARD_W_TRIM, "mid_w": _mid_width(HISTORY_START_W - CARD_W_TRIM),
    "hover": None, "attention": {}, "summary_target": "",   # summary_target = full path of the open batch, re-trimmed on resize
    "narrow": False, "table_narrow": False,   # narrow = what the window says now, table_narrow = what the CURRENT detail table was built with
    "detail_files": [], "detail_cells": [],   # files shown in the detail table (for rebuilds) + (name btn, name, loc btn, path) for re-trimming
}


# ---------------------------------------------------------------------------
# Themes (built once)
# ---------------------------------------------------------------------------

def _pill_theme(color, bg_alpha=PILL_BG_ALPHA, pad_x=CHIP_PAD_X):
    bg = (*color[:3], bg_alpha)
    border = (*color[:3], PILL_BORDER_ALPHA)
    with dpg.theme() as theme:
        with dpg.theme_component(dpg.mvButton):
            dpg.add_theme_color(dpg.mvThemeCol_Button, bg)
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, bg)
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, bg)
            dpg.add_theme_color(dpg.mvThemeCol_Text, color[:3])
            dpg.add_theme_color(dpg.mvThemeCol_Border, border)
            dpg.add_theme_style(dpg.mvStyleVar_FrameBorderSize, 1)
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, PILL_ROUNDING)
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding, pad_x, 0)
    return theme


def _flat_center_theme(color):
    """Invisible button that only shows centered text (like the flat text button, but centered)."""
    with dpg.theme() as theme:
        with dpg.theme_component(dpg.mvButton):
            dpg.add_theme_color(dpg.mvThemeCol_Button, (0, 0, 0, 0))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (0, 0, 0, 0))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (0, 0, 0, 0))
            dpg.add_theme_color(dpg.mvThemeCol_Text, color)
            dpg.add_theme_color(dpg.mvThemeCol_Border, (0, 0, 0, 0))
            dpg.add_theme_style(dpg.mvStyleVar_FrameBorderSize, 0)
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 0, 0)
            dpg.add_theme_style(dpg.mvStyleVar_ButtonTextAlign, 0.5, 0.5)
    return theme


def _themes():
    if _T:
        return _T
    _T["chip"] = _pill_theme(COLORS["accent_blue"])
    _T["chip_red"] = _pill_theme(COLORS["accent_red"])
    _T["chip_orange"] = _pill_theme(COLORS["accent_orange"])
    _T["chip_green"] = _pill_theme(COLORS["accent_green"])
    _T["chip_grey"] = _pill_theme(COLORS["text_secondary"])
    _T["status_neutral"] = _pill_theme(COLORS["text_secondary"])
    _T["status_running"] = _pill_theme(COLORS["accent_blue"])
    _T["status_failed"] = _pill_theme(COLORS["accent_red"])
    _T["muted_text"] = _flat_button_theme(TABLE_CELL_MUTED_COLOR)
    _T["muted_center"] = _flat_center_theme(TABLE_CELL_MUTED_COLOR)
    for name, (color, _icons) in RESULT_STYLE.items():           # table result pills (full cell width, so no side padding)
        _T[f"result_{name}"] = _pill_theme(color, pad_x=0)
    _T["result_OTHER"] = _pill_theme(RESULT_DEFAULT[0], pad_x=0)
    with dpg.theme() as th:                                       # the scrolling list area is see-through, so the cards sit on the page
        with dpg.theme_component(dpg.mvChildWindow):
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, (0, 0, 0, 0))
    _T["scroll"] = th
    with dpg.theme() as th:                                       # the little 4-cell strip in the summary card
        with dpg.theme_component(dpg.mvTable):
            dpg.add_theme_style(dpg.mvStyleVar_CellPadding, STRIP_CELL_PAD_X, STRIP_CELL_PAD_Y)
    _T["strip_table"] = th
    return _T


def _card_theme(attention, hover):
    key = (bool(attention), bool(hover))
    if key not in _CARD_THEMES:
        bg = CARD_BG_HOVER if hover else CARD_BG
        if attention:
            border = CARD_BORDER_ATTENTION_HOVER if hover else CARD_BORDER_ATTENTION
        else:
            border = CARD_BORDER_HOVER if hover else CARD_BORDER
        with dpg.theme() as th:
            with dpg.theme_component(dpg.mvChildWindow):
                dpg.add_theme_color(dpg.mvThemeCol_ChildBg, bg)
                dpg.add_theme_color(dpg.mvThemeCol_Border, border)
        _CARD_THEMES[key] = th
    return _CARD_THEMES[key]


def _badge_theme(color):
    key = tuple(color[:3])
    if key not in _BADGE_THEMES:
        muted = tuple(max(0, min(255, c // 5)) for c in key) + (255,)
        with dpg.theme() as th:
            with dpg.theme_component(dpg.mvChildWindow):
                dpg.add_theme_color(dpg.mvThemeCol_ChildBg, muted)
        _BADGE_THEMES[key] = th
    return _BADGE_THEMES[key]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _icon_for_entry(entry, icons):
    """Kept in case another file imports it. The detail table now uses RESULT_STYLE instead."""
    result_u = str((entry or {}).get("result") or (entry or {}).get("verdict") or "CLEAN").upper()
    if result_u in ("MALICIOUS", "SUSPICIOUS"):
        return (icons.get("octagon_alert") if icons else None, COLORS["accent_red"])
    if result_u in ("QUARANTINED",):
        return (icons.get("shield_cog") if icons else None, COLORS["accent_orange"])
    if result_u in ("ERROR", "FAILED"):
        return (icons.get("octagon_alert") if icons else None, COLORS["text_secondary"])
    return (icons.get("shield_check") if icons else None, COLORS["accent_green"])


def _looks_like_batch(item) -> bool:
    if not isinstance(item, dict):
        return False
    if item.get("file_path") or item.get("fileName"):
        return False
    return any(k in item for k in ("total_files", "totalFiles", "scan_type", "scanType", "clean_count", "cleanCount"))


def _num(batch, snake, camel):
    try:
        return int(batch.get(snake) or batch.get(camel) or 0)
    except (TypeError, ValueError):
        return 0


def _plural(n, word):
    return f"{n:,} {word}" + ("" if n == 1 else "s")


def _cleanup_history_item_tags():
    i = 0
    while i < 400:
        for suffix in ("", "_handler", "_icon_bg", "_open_btn"):
            tag = f"batch_row_{i}{suffix}"
            try:
                if dpg.does_item_exist(tag):
                    dpg.delete_item(tag)
            except Exception:
                pass
        i += 1


def _schedule_history_render(icons=None):
    def _later():
        try:
            with dpg.mutex():
                _render_history_view(icons=icons)
        except Exception as e:
            print(f"[ui/history] render failed: {e}")
    threading.Timer(0.02, _later).start()


def _reset_scroll():
    """Back to the top (so a freshly opened batch isn't shown scrolled down)."""
    try:
        if dpg.does_item_exist("history_scroll"):
            dpg.set_y_scroll("history_scroll", 0)
    except Exception:
        traceback.print_exc()


# ---------------------------------------------------------------------------
# Mouse: click opens a batch, hover highlights a card
# ---------------------------------------------------------------------------

def _history_visible():
    try:
        return dpg.is_item_visible("page_history")
    except Exception:
        return False


def _set_card_theme(tag, hover):
    if dpg.does_item_exist(tag):
        dpg.bind_item_theme(tag, _card_theme(_state["attention"].get(tag, False), hover))


def _clear_hover():
    if _state["hover"]:
        _set_card_theme(_state["hover"], False)
    _state["hover"] = None


def _on_history_mouse_move(sender=None, app_data=None):
    """Highlights the card under the mouse (theme swap only, so nothing moves and nothing can flicker)."""
    try:
        if _HISTORY_DETAIL_BATCH is not None or not _history_visible():
            _clear_hover()
            return
        hot = None
        for tag in list(_BATCH_ROW_MAP):
            if dpg.does_item_exist(tag) and dpg.is_item_hovered(tag):
                hot = tag
                break
        if hot != _state["hover"]:
            if _state["hover"]:
                _set_card_theme(_state["hover"], False)
            if hot:
                _set_card_theme(hot, True)
            _state["hover"] = hot
    except Exception:
        traceback.print_exc()


def _on_history_mouse_click(sender, app_data):
    try:
        from ui.sidebar import CURRENT_PAGE
        if CURRENT_PAGE != "history":
            return
    except Exception:
        pass
    if _HISTORY_DETAIL_BATCH is not None:
        return
    hovered = []
    for tag, batch in list(_BATCH_ROW_MAP.items()):
        try:
            if dpg.does_item_exist(tag) and dpg.is_item_hovered(tag):
                hovered.append((tag, batch))
        except Exception:
            continue
    if not hovered:
        return
    _show_batch_files(hovered[0][1])


def _show_batch_files(batch, icons=None):
    global _HISTORY_DETAIL_BATCH
    if not batch:
        return
    cur = _HISTORY_DETAIL_BATCH
    if cur is not None and cur.get("id") == batch.get("id"):
        return   # already opening this batch
    _HISTORY_DETAIL_BATCH = dict(batch)
    _schedule_history_render(icons)


def _back_to_batches(sender=None, app_data=None, user_data=None):
    global _HISTORY_DETAIL_BATCH
    _HISTORY_DETAIL_BATCH = None
    def _later():
        try:
            with dpg.mutex():
                _rebuild_history()
        except Exception as e:
            print(f"[ui/history] back to batches failed: {e}")
    threading.Timer(0.02, _later).start()


# ---------------------------------------------------------------------------
# Labels, colors, states
# ---------------------------------------------------------------------------

def _scan_type_label(scan_type: str) -> str:
    st = (scan_type or "").lower()
    if st in ("quick", "fast"):
        return "Quick Scan"
    if st in ("full", "regular", "system"):
        return "Full System Scan"
    if st in ("custom",):
        return "Custom Scan"
    if st == "single":
        return "Single File"
    if not st:
        return "Scan"
    return st.capitalize() + " Scan"


def _scan_type_color(scan_type: str):
    st = (scan_type or "").lower()
    if st in ("quick", "fast"):
        return COLORS["accent_blue"]
    if st in ("full", "regular", "system"):
        return COLORS["accent_purple"] if "accent_purple" in COLORS else (156, 80, 220, 255)
    if st in ("custom",):
        return COLORS["accent_orange"]
    return COLORS["text_secondary"]


def _batch_state(batch):
    """running / failed / threats / empty / clean (this drives the icon, the border and the tooltip)."""
    status = str(batch.get("status") or "").upper()
    if status == "RUNNING":
        return "running"
    if status in ("FAILED", "CANCELLED"):
        return "failed"
    if _num(batch, "threat_count", "threatCount") > 0:
        return "threats"
    if _num(batch, "total_files", "totalFiles") == 0:
        return "empty"
    return "clean"


def _first_icon(icons, keys):
    for key in keys:
        tex = (icons or {}).get(key)
        if tex:
            return tex
    return None


def _batch_status_icon(batch, icons):
    keys, color, _tip = STATE_STYLE[_batch_state(batch)]
    return (_first_icon(icons, keys), color)


def _icon_badge(icon_texture, color, tag_prefix, size=ICON_BADGE_SIZE, icon_size=18):
    with dpg.child_window(width=size, height=size, no_scrollbar=True, no_scroll_with_mouse=True,
                          tag=f"{tag_prefix}_icon_bg"):
        if icon_texture:
            pad = max(2, (size - icon_size) // 2)
            dpg.add_image(icon_texture, width=icon_size, height=icon_size, tint_color=color, pos=(pad, pad))
    dpg.bind_item_theme(f"{tag_prefix}_icon_bg", _badge_theme(color))


def _format_elapsed(ms: int) -> str:
    if not ms:
        return "0.0s"
    total = max(0, int(ms)) / 1000.0
    if total < 60:
        return f"{total:.1f}s"
    mins = int(total // 60)
    secs = int(total % 60)
    return f"{mins}m {secs:02d}s"


def _truncate_target(target: str, max_len: int = 68) -> str:
    if not target:
        return ""
    t = str(target).strip()
    if len(t) <= max_len:
        return t
    return t[: max_len - 3] + "..."


def _chips_for(batch):
    """The stat pills of a batch: list of (label, theme key). Used by the list cards and the summary card."""
    total = _num(batch, "total_files", "totalFiles")
    clean = _num(batch, "clean_count", "cleanCount")
    suspicious = _num(batch, "suspicious_count", "suspiciousCount")
    malicious = _num(batch, "malicious_count", "maliciousCount")
    errors = _num(batch, "error_count", "errorCount")
    chips = []
    if malicious > 0:
        chips.append((f"Malicious: {malicious}", "chip_red"))
    if suspicious > 0:
        chips.append((f"Suspicious: {suspicious}", "chip_orange"))
    if clean > 0:
        chips.append((f"Clean: {clean}", "chip_green"))
    if errors > 0:
        chips.append((f"Errors: {errors}", "chip_grey"))
    if not chips:
        chips.append(("Nothing flagged" if total == 0 else f"Results: {total}", "chip_grey"))
    return chips


# ---------------------------------------------------------------------------
# Batch cards
# ---------------------------------------------------------------------------

def _fit_path(btn, full_text, width):
    """Shortens a path button's label to its width ("D:/Games/Ang..."). The full path stays in the tooltip."""
    if not ELLIPSIS_ENABLED or not full_text or dpg.get_frame_count() < MEASURE_MIN_FRAME:
        return
    if not dpg.does_item_exist(btn):
        return
    font = (_state["fonts"] or {}).get(TABLE_FONT_KEY)
    dpg.set_item_label(btn, fit_text(full_text, width - PATH_TEXT_MARGIN, font))


def _batch_row(batch, index, icons):
    tag = f"batch_row_{index}"
    own = _themes()
    fonts = _state["fonts"] or {}
    table_font = fonts.get(TABLE_FONT_KEY)
    sub_font = fonts.get("subheading")
    mono_font = fonts.get("mono_small")

    scan_type = batch.get("scan_type") or batch.get("scanType") or ""
    st_label = _scan_type_label(scan_type)
    st_color = _scan_type_color(scan_type)
    total = _num(batch, "total_files", "totalFiles")
    elapsed = _num(batch, "elapsed_ms", "elapsedMs")
    started = batch.get("started_at") or batch.get("startedAt") or ""
    status = str(batch.get("status") or "").upper()
    batch_id = batch.get("id") or ""
    target = str(batch.get("target") or "")

    state = _batch_state(batch)
    icon, color = _batch_status_icon(batch, icons)
    state_tip = STATE_STYLE[state][2]
    attention = state in ("threats", "failed")
    status_label = status or ("COMPLETED" if total > 0 else "UNKNOWN")
    status_theme = {"running": "status_running", "failed": "status_failed"}.get(state, "status_neutral")

    info_parts = []
    if total > 0:
        info_parts.append(_plural(total, "result"))
    if elapsed > 0:
        info_parts.append(_format_elapsed(elapsed))
    info = ("·  " + "  ·  ".join(info_parts)) if info_parts else ""

    chips = _chips_for(batch)

    card_w = _state["card_w"]
    right_x = card_w - RIGHT_W - RIGHT_MARGIN
    badge_top = max(0, (CARD_HEIGHT - 2 * CARD_PAD_Y - BADGE_SIZE) // 2 - ITEM_SPACING_Y)
    s1 = max(1, BADGE_LEFT - 2 * ITEM_SPACING_X)          # a spacer in a horizontal group costs +8 on each side
    s2 = max(1, BADGE_TEXT_GAP - 2 * ITEM_SPACING_X)

    with dpg.child_window(width=card_w, height=CARD_HEIGHT, tag=tag, no_scrollbar=True, no_scroll_with_mouse=True):
        with dpg.group(horizontal=True):
            dpg.add_spacer(width=s1)
            with dpg.group():
                dpg.add_spacer(height=badge_top)
                _icon_badge(icon, color, tag, size=BADGE_SIZE, icon_size=BADGE_ICON_SIZE)
            with dpg.tooltip(f"{tag}_icon_bg"):
                dpg.add_text(state_tip, color=TIP_COLOR)
            dpg.add_spacer(width=s2)

            with dpg.group(tag=f"{tag}_mid"):
                dpg.add_spacer(height=MID_TOP_SPACER)
                with dpg.group(horizontal=True):                      # row 1: dot, title, files + duration
                    if SHOW_TYPE_DOT:
                        dot_c = (*st_color[:3], 255)
                        with dpg.drawlist(width=TYPE_DOT_RADIUS * 2, height=TYPE_DOT_BOX_H):
                            dpg.draw_circle((TYPE_DOT_RADIUS, TYPE_DOT_BOX_H / 2 + TYPE_DOT_NUDGE_Y),
                                            TYPE_DOT_RADIUS, color=dot_c, fill=dot_c)
                    title = dpg.add_text(st_label, color=COLORS["text_primary"], tag=f"{tag}_title")
                    if sub_font is not None:
                        dpg.bind_item_font(title, sub_font)
                    if batch_id:
                        with dpg.tooltip(title):
                            tip = dpg.add_text(f"Batch ID: {batch_id}", color=TIP_COLOR)
                            if mono_font is not None:
                                dpg.bind_item_font(tip, mono_font)
                    if info:
                        dpg.add_text(info, color=TABLE_CELL_MUTED_COLOR)

                target_btn = dpg.add_button(label=target or TARGET_FALLBACK, width=_state["mid_w"],
                                            height=TARGET_HEIGHT, tag=f"{tag}_target")   # row 2: clipped path
                dpg.bind_item_theme(target_btn, own["muted_text"])
                if target:
                    with dpg.tooltip(target_btn):
                        dpg.add_text(target, color=TIP_COLOR)
                _fit_path(target_btn, target, _state["mid_w"])

                with dpg.group(horizontal=True):                      # row 3: stat chips
                    for label, theme_key in chips:
                        chip = dpg.add_button(label=label, height=CHIP_ROW_H)
                        dpg.bind_item_theme(chip, own[theme_key])

        # the right column goes last on purpose: it is positioned by hand and must not shift the layout above.
        # The whole card is clickable (see _on_history_mouse_click), so there is no Open button.
        with dpg.group(tag=f"{tag}_right", pos=[right_x, RIGHT_TOP]):
            date_btn = dpg.add_button(label=started or "-", width=RIGHT_W, height=RIGHT_DATE_H)   # a flat button, so the text can be centered
            dpg.bind_item_theme(date_btn, own["muted_center"])
            pill = dpg.add_button(label=status_label, width=STATUS_PILL_W, height=STATUS_PILL_H,
                                  indent=(RIGHT_W - STATUS_PILL_W) // 2)
            dpg.bind_item_theme(pill, own[status_theme])

    dpg.bind_item_theme(tag, _card_theme(attention, False))
    if table_font is not None:
        dpg.bind_item_font(tag, table_font)   # everything inside the card inherits it (the title overrides it)
    _state["attention"][tag] = attention
    _BATCH_ROW_MAP[tag] = dict(batch)


def _apply_card_widths():
    card_w = _state["card_w"]
    mid_w = _state["mid_w"]
    right_x = card_w - RIGHT_W - RIGHT_MARGIN
    for tag in list(_BATCH_ROW_MAP):
        if not dpg.does_item_exist(tag):
            continue
        dpg.configure_item(tag, width=card_w)
        if dpg.does_item_exist(f"{tag}_target"):
            dpg.configure_item(f"{tag}_target", width=mid_w)
            _fit_path(f"{tag}_target", str(_BATCH_ROW_MAP[tag].get("target") or ""), mid_w)
        if dpg.does_item_exist(f"{tag}_right"):
            dpg.configure_item(f"{tag}_right", pos=[right_x, RIGHT_TOP])


# ---------------------------------------------------------------------------
# Detail view
# ---------------------------------------------------------------------------

def _detail_panel_h():
    """Height of the file table panel: whatever is left under the summary card (never below the minimum)."""
    return max(DETAIL_PANEL_MIN_H, _state["panel_h"] - DETAIL_CHROME_H)


def _conf_text(entry):
    prob = entry.get("probability")
    if prob is None:
        prob = entry.get("threatLevel")
        if prob is not None:
            try:
                prob = float(prob) / 100.0
            except Exception:
                prob = None
    if prob is None:
        return "-"
    try:
        p = float(prob)
    except (TypeError, ValueError):
        return "-"
    if 0.0 <= p <= 1.0:
        return f"{p:.1%}"
    return f"Score {p:.0f}"


def _behavior_fields(entry):
    """Read structured behavior data, with support for older log detail strings."""
    confidence = entry.get("behavior_confidence")
    behavior_types = entry.get("behavior_types") or []
    behavior_type = entry.get("behavior_type")

    if isinstance(behavior_types, str):
        behavior_types = [
            item.strip()
            for item in behavior_types.split(",")
            if item.strip() and item.strip().lower() != "unknown"
        ]
    elif not isinstance(behavior_types, (list, tuple)):
        behavior_types = []

    details = str(entry.get("details") or entry.get("detail") or "")
    if confidence is None and "behavior_probability=" in details:
        raw_confidence = details.split("behavior_probability=", 1)[1].split(";", 1)[0]
        try:
            confidence = float(raw_confidence)
        except ValueError:
            confidence = None

    if not behavior_types and "behavior_types=" in details:
        raw_types = details.split("behavior_types=", 1)[1].split(";", 1)[0]
        behavior_types = [
            item.strip()
            for item in raw_types.split(",")
            if item.strip() and item.strip().lower() != "unknown"
        ]

    if not behavior_type and behavior_types:
        behavior_type = behavior_types[0]

    return confidence, behavior_type, behavior_types


def _behavior_conf_text(entry):
    confidence, _, _ = _behavior_fields(entry)
    if confidence is None:
        return "-"
    try:
        return f"{float(confidence):.1%}"
    except (TypeError, ValueError):
        return "-"


def _behavior_type_text(entry):
    _, behavior_type, behavior_types = _behavior_fields(entry)
    labels = behavior_types or ([behavior_type] if behavior_type else [])
    if not labels:
        return "-"
    return ", ".join(
        "Ransomware" if str(label).strip().lower() == "ransom"
        else "PUA" if str(label).strip().lower() == "pua"
        else str(label).replace("_", " ").replace("-", " ").title()
        for label in labels
    )


def _open_history_explanation(sender, app_data, entry):
    file_path = entry.get("file_path") or entry.get("fileName")
    if not file_path:
        print("[History] Cannot open explanation: file path is missing.")
        return

    threat = dict(entry)
    threat["file_path"] = file_path
    threat["result"] = entry.get("result") or entry.get("verdict") or "UNKNOWN"
    threat["probability"] = entry.get("probability")
    confidence, behavior_type, behavior_types = _behavior_fields(entry)
    threat["behavior_confidence"] = confidence
    threat["behavior_type"] = behavior_type
    threat["behavior_types"] = behavior_types

    from ui.scan_explain import open_explain

    open_explain(threat, entry.get("xai_report"))


def _build_summary(batch, icons):
    """The summary card at the top of the detail view (an 'opened up' version of the list card)."""
    own = _themes()
    fonts = _state["fonts"] or {}
    table_font = fonts.get(TABLE_FONT_KEY)
    sub_font = fonts.get("subheading")
    mono_font = fonts.get("mono_small")
    tag = "history_detail"

    scan_type = batch.get("scan_type") or batch.get("scanType") or ""
    st_label = _scan_type_label(scan_type)
    st_color = _scan_type_color(scan_type)
    total = _num(batch, "total_files", "totalFiles")
    elapsed = _num(batch, "elapsed_ms", "elapsedMs")
    started = batch.get("started_at") or batch.get("startedAt") or ""
    completed = batch.get("completed_at") or batch.get("completedAt") or ""
    status = str(batch.get("status") or "").upper()
    batch_id = batch.get("id") or ""
    target = str(batch.get("target") or "")

    state = _batch_state(batch)
    icon, color = _batch_status_icon(batch, icons)
    attention = state in ("threats", "failed")
    status_label = status or ("COMPLETED" if total > 0 else "UNKNOWN")
    status_theme = {"running": "status_running", "failed": "status_failed"}.get(state, "status_neutral")
    duration = "-" if state == "running" else _format_elapsed(elapsed)
    chips = _chips_for(batch)

    card_w = _state["card_w"]
    badge_top = max(0, (CARD_HEIGHT - 2 * CARD_PAD_Y - BADGE_SIZE) // 2 - ITEM_SPACING_Y)
    s1 = max(1, BADGE_LEFT - 2 * ITEM_SPACING_X)
    s2 = max(1, BADGE_TEXT_GAP - 2 * ITEM_SPACING_X)

    with dpg.child_window(width=card_w, height=SUMMARY_H, tag=f"{tag}_summary",
                          no_scrollbar=True, no_scroll_with_mouse=True):
        with dpg.group(horizontal=True):
            dpg.add_spacer(width=s1)
            with dpg.group():
                dpg.add_spacer(height=badge_top)
                _icon_badge(icon, color, tag, size=BADGE_SIZE, icon_size=BADGE_ICON_SIZE)
            with dpg.tooltip(f"{tag}_icon_bg"):
                dpg.add_text(STATE_STYLE[state][2], color=TIP_COLOR)
            dpg.add_spacer(width=s2)

            with dpg.group():
                dpg.add_spacer(height=MID_TOP_SPACER)
                with dpg.group(horizontal=True):                      # row 1: dot, title, status pill
                    if SHOW_TYPE_DOT:
                        dot_c = (*st_color[:3], 255)
                        with dpg.drawlist(width=TYPE_DOT_RADIUS * 2, height=TYPE_DOT_BOX_H):
                            dpg.draw_circle((TYPE_DOT_RADIUS, TYPE_DOT_BOX_H / 2 + TYPE_DOT_NUDGE_Y),
                                            TYPE_DOT_RADIUS, color=dot_c, fill=dot_c)
                    title = dpg.add_text(st_label, color=COLORS["text_primary"])
                    if sub_font is not None:
                        dpg.bind_item_font(title, sub_font)
                    pill = dpg.add_button(label=status_label, width=STATUS_PILL_W, height=STATUS_PILL_H)
                    dpg.bind_item_theme(pill, own[status_theme])

                target_btn = dpg.add_button(label=target or TARGET_FALLBACK, width=_detail_mid_w(card_w),
                                            height=TARGET_HEIGHT, tag=f"{tag}_target")   # row 2: clipped path
                dpg.bind_item_theme(target_btn, own["muted_text"])
                if target:
                    with dpg.tooltip(target_btn):
                        dpg.add_text(target, color=TIP_COLOR)
                _state["summary_target"] = target
                _fit_path(target_btn, target, _detail_mid_w(card_w))

                with dpg.group(horizontal=True):                      # row 3: stat chips
                    for label, theme_key in chips:
                        chip = dpg.add_button(label=label, height=CHIP_ROW_H)
                        dpg.bind_item_theme(chip, own[theme_key])

        dpg.add_spacer(height=SUMMARY_STRIP_GAP)
        dpg.add_separator()
        with dpg.table(header_row=False, borders_innerH=False, borders_outerH=False,
                       borders_innerV=False, borders_outerV=False, width=-1, tag=f"{tag}_strip"):
            for weight in STRIP_WEIGHTS:
                dpg.add_table_column(width_stretch=True, init_width_or_weight=weight)
            with dpg.table_row():                                     # labels
                for label in STRIP_LABELS:
                    item = dpg.add_text(label.upper() if STRIP_LABELS_UPPERCASE else label, color=STRIP_LABEL_COLOR)
                    if mono_font is not None:
                        dpg.bind_item_font(item, mono_font)
            with dpg.table_row():                                     # values
                values = (started or "-", completed or "-", duration, batch_id or "-")
                for i, value in enumerate(values):
                    item = dpg.add_text(value, color=COLORS["text_primary"])
                    if i == len(values) - 1 and mono_font is not None:   # the batch id looks like an id
                        dpg.bind_item_font(item, mono_font)
        dpg.bind_item_theme(f"{tag}_strip", own["strip_table"])

    dpg.bind_item_theme(f"{tag}_summary", _card_theme(attention, False))
    if table_font is not None:
        dpg.bind_item_font(f"{tag}_summary", table_font)


def _detail_label_widths():
    """(File Name, Location) pixel budget for the text inside the cells. An estimate from the column constants.
    Narrow table: no Location, the name gets everything."""
    narrow = _state["table_narrow"]
    if narrow:
        fixed = (2 * GUTTER_W + DETAIL_COL_ICON_W_NARROW + DETAIL_COL_EXPLAIN_W + DETAIL_COL_RESULT_W
                 + DETAIL_COL_CONF_W + DETAIL_COL_BEHAVIOR_W_NARROW)
        extra = DETAIL_EXTRA_PX_NARROW
    else:
        fixed = (2 * GUTTER_W + DETAIL_COL_ICON_W + DETAIL_COL_EXPLAIN_W + DETAIL_COL_RESULT_W
                 + DETAIL_COL_CONF_W + DETAIL_COL_BEHAVIOR_CONF_W + DETAIL_COL_TYPE_W)
        extra = DETAIL_EXTRA_PX_WIDE
    table_w = _state["card_w"] - 2 * DETAIL_PANEL_PAD_X - DETAIL_TABLE_SCROLLBAR_W
    avail = max(0, table_w - fixed - extra)
    if narrow:
        return int(avail - 2 * ROW_PAD_X), 0
    total = DETAIL_COL_NAME_WEIGHT + DETAIL_COL_LOCATION_WEIGHT
    return (int(avail * DETAIL_COL_NAME_WEIGHT / total - 2 * ROW_PAD_X),
            int(avail * DETAIL_COL_LOCATION_WEIGHT / total - 2 * ROW_PAD_X))


def _fit_detail_cell(name_btn, name, loc_btn, path, widths):
    """Shortens File Name and Location to their budget. The full text stays in the tooltips."""
    if not ELLIPSIS_ENABLED or dpg.get_frame_count() < MEASURE_MIN_FRAME:
        return
    font = (_state["fonts"] or {}).get(TABLE_FONT_KEY)
    if dpg.does_item_exist(name_btn):
        dpg.set_item_label(name_btn, fit_text(name, widths[0], font))
    if loc_btn is not None and dpg.does_item_exist(loc_btn):
        dpg.set_item_label(loc_btn, fit_text(path, widths[1], font))


def _refit_detail_cells():
    if not _state["detail_cells"]:
        return
    widths = _detail_label_widths()
    for cell in list(_state["detail_cells"]):
        _fit_detail_cell(*cell, widths)


def _merged_behavior_label(entry, font):
    """Narrow table: 'conf | type' in one cell, like the Scan page. The type is trimmed by pixel width."""
    confidence, _, _ = _behavior_fields(entry)
    try:
        conf_txt = f"{float(confidence):.0%}" if confidence is not None else None
    except (TypeError, ValueError):
        conf_txt = None
    type_txt = _behavior_type_text(entry)
    if type_txt == "-":
        return conf_txt or "-"
    prefix = f"{conf_txt} | " if conf_txt else ""
    if not ELLIPSIS_ENABLED:
        return prefix + type_txt
    room = DETAIL_COL_BEHAVIOR_W_NARROW - DETAIL_BEHAVIOR_MARGIN - text_width(prefix, font)
    return prefix + fit_text(type_txt, room, font)


def _detail_file_row(entry, icons):
    """Draws one row. The cells must match the columns the table was BUILT with (table_narrow)."""
    tt = _threat_themes()
    own = _themes()
    narrow = _state["table_narrow"]
    font = (_state["fonts"] or {}).get(TABLE_FONT_KEY)
    res = str(entry.get("result") or entry.get("verdict") or "CLEAN").upper()
    color, icon_keys = RESULT_STYLE.get(res, RESULT_DEFAULT)
    tex = _first_icon(icons, icon_keys)
    path = str(entry.get("file_path") or entry.get("fileName") or "Unknown")
    name = os.path.basename(path) or path
    extra = entry.get("details") or entry.get("detail") or ""
    icon_size = DETAIL_ICON_SIZE_NARROW if narrow else DETAIL_ICON_SIZE
    icon_nudge = max(0, (TABLE_ROW_HEIGHT - icon_size) // 2 - ITEM_SPACING_Y)

    with dpg.table_row(parent="history_detail_table"):
        dpg.add_spacer(width=1)   # left gutter cell

        with dpg.group():         # icon cell (a group, so the nudge spacer and the icon share ONE cell)
            dpg.add_spacer(height=icon_nudge)
            if tex:
                dpg.add_image(tex, width=icon_size, height=icon_size, tint_color=color)

        explain = dpg.add_button(
            label="Explain",
            width=-1,
            height=TABLE_ROW_HEIGHT,
            callback=_open_history_explanation,
            user_data=entry,
        )
        dpg.bind_item_theme(explain, _get_themes()["btn_secondary"])

        name_btn = dpg.add_button(label=name, width=-1, height=TABLE_ROW_HEIGHT)
        dpg.bind_item_theme(name_btn, tt["name"])
        with dpg.tooltip(name_btn):
            dpg.add_text(name, color=COLORS["text_primary"])
            if narrow:   # Location is hidden, so its path moves here
                dpg.add_text(path, color=TIP_COLOR)
            if extra:
                dpg.add_text(str(extra), color=TIP_COLOR, wrap=DETAIL_TIP_WRAP)

        loc_btn = None
        if not narrow:
            loc_btn = dpg.add_button(label=path, width=-1, height=TABLE_ROW_HEIGHT)
            dpg.bind_item_theme(loc_btn, own["muted_text"])
            with dpg.tooltip(loc_btn):
                dpg.add_text(path, color=TIP_COLOR)
        _state["detail_cells"].append((name_btn, name, loc_btn, path))
        _fit_detail_cell(name_btn, name, loc_btn, path, _detail_label_widths())

        pill = dpg.add_button(label=res, width=-1, height=TABLE_PILL_HEIGHT)
        dpg.bind_item_theme(pill, own.get(f"result_{res}", own["result_OTHER"]))

        conf = dpg.add_button(label=_conf_text(entry), width=-1, height=TABLE_ROW_HEIGHT)
        if res == "MALICIOUS":
            dpg.bind_item_theme(conf, tt["conf"])
        elif res == "SUSPICIOUS":
            dpg.bind_item_theme(conf, tt["behavior"])
        else:
            dpg.bind_item_theme(conf, own["muted_text"])

        behavior_conf_value, _, _ = _behavior_fields(entry)
        behavior_type_text = _behavior_type_text(entry)
        has_behavior = behavior_conf_value is not None or behavior_type_text != "-"

        if narrow:
            merged = dpg.add_button(label=_merged_behavior_label(entry, font), width=-1, height=TABLE_ROW_HEIGHT)
            dpg.bind_item_theme(merged, tt["behavior"] if has_behavior else own["muted_text"])
            if has_behavior:
                with dpg.tooltip(merged):
                    dpg.add_text(f"Behavior confidence: {_behavior_conf_text(entry)}", color=TIP_COLOR)
                    dpg.add_text(f"Type: {behavior_type_text}", color=TIP_COLOR)
        else:
            behavior_conf = dpg.add_button(label=_behavior_conf_text(entry), width=-1, height=TABLE_ROW_HEIGHT)
            dpg.bind_item_theme(behavior_conf,
                                tt["behavior"] if behavior_conf_value is not None else own["muted_text"])

            type_label = behavior_type_text
            if ELLIPSIS_ENABLED and behavior_type_text != "-":
                type_label = fit_text(behavior_type_text, DETAIL_COL_TYPE_W - 2 * ROW_PAD_X, font)
            behavior_type = dpg.add_button(label=type_label, width=-1, height=TABLE_ROW_HEIGHT)
            dpg.bind_item_theme(behavior_type,
                                tt["behavior"] if behavior_type_text != "-" else own["muted_text"])
            if behavior_type_text != "-":
                with dpg.tooltip(behavior_type):
                    dpg.add_text(behavior_type_text, color=TIP_COLOR)

        dpg.add_spacer(width=1)   # right gutter cell


def _build_files_table(files, icons, panel_h):
    """Builds the file table inside the detail panel. Location + the second behavior column only exist
    in the wide table (show=False is ignored by this DPG build, so the narrow one is built without them)."""
    tt = _threat_themes()
    narrow = _state["narrow"]
    _state["table_narrow"] = narrow
    _state["detail_files"] = files        # kept so the table can rebuild itself when the width crosses the breakpoint
    _state["detail_cells"].clear()
    with dpg.table(parent="history_detail_panel", tag="history_detail_table", header_row=True, row_background=True,
                   borders_innerH=False, borders_outerH=False,
                   borders_innerV=False, borders_outerV=False,
                   scrollY=True, freeze_rows=1, width=-1,
                   height=max(1, panel_h - DETAIL_TABLE_CHROME)):
        dpg.add_table_column(label="", width_fixed=True, init_width_or_weight=GUTTER_W)
        dpg.add_table_column(label="", width_fixed=True,
                             init_width_or_weight=DETAIL_COL_ICON_W_NARROW if narrow else DETAIL_COL_ICON_W)
        dpg.add_table_column(label="Explain", width_fixed=True, init_width_or_weight=DETAIL_COL_EXPLAIN_W)
        dpg.add_table_column(label="File Name", width_stretch=True, init_width_or_weight=DETAIL_COL_NAME_WEIGHT)
        if not narrow:
            dpg.add_table_column(label="Location", width_stretch=True, init_width_or_weight=DETAIL_COL_LOCATION_WEIGHT)
        dpg.add_table_column(label="Result", width_fixed=True, init_width_or_weight=DETAIL_COL_RESULT_W)
        dpg.add_table_column(label="Confidence", width_fixed=True, init_width_or_weight=DETAIL_COL_CONF_W)
        if narrow:
            dpg.add_table_column(label="Behavior", width_fixed=True, init_width_or_weight=DETAIL_COL_BEHAVIOR_W_NARROW)
        else:
            dpg.add_table_column(label="Behavior %", width_fixed=True, init_width_or_weight=DETAIL_COL_BEHAVIOR_CONF_W)
            dpg.add_table_column(label="Type", width_fixed=True, init_width_or_weight=DETAIL_COL_TYPE_W)
        dpg.add_table_column(label="", width_fixed=True, init_width_or_weight=GUTTER_W)
    dpg.bind_item_theme("history_detail_table", tt["table"])
    apply_table_font("history_detail_table", _state["fonts"])   # shared table font (ui/table_style.py)
    for entry in files:
        try:
            _detail_file_row(entry, icons)
        except Exception:
            traceback.print_exc()


def _rebuild_detail_table():
    """Rebuilds the open detail table (with or without Location). Runs only when the window crosses the breakpoint."""
    if not dpg.does_item_exist("history_detail_table"):
        return
    dpg.delete_item("history_detail_table")
    _build_files_table(_state["detail_files"], GLOBAL_ICONS or {}, _detail_panel_h())
def _build_empty_detail(icons):
    base = _get_themes()
    fonts = _state["fonts"] or {}
    with dpg.group(tag="history_detail_empty"):
        dpg.add_spacer(height=100, tag="history_detail_empty_top")
        icon = _first_icon(icons, ("file_x", "folder_search"))
        if icon:
            dpg.add_image(icon, width=EMPTY_ICON_SIZE, height=EMPTY_ICON_SIZE,
                          tint_color=COLORS["text_secondary"], tag="history_detail_empty_icon")
        dpg.add_spacer(height=EMPTY_GAP)
        dpg.add_button(label=DETAIL_EMPTY_TITLE, width=-1, height=EMPTY_TITLE_HEIGHT, tag="history_detail_empty_title")
        dpg.add_button(label=DETAIL_EMPTY_SUBTITLE, width=-1, height=EMPTY_SUB_HEIGHT, tag="history_detail_empty_sub")
    dpg.bind_item_theme("history_detail_empty_title", base["label_on"])
    dpg.bind_item_theme("history_detail_empty_sub", base["sub"])
    if fonts.get("subheading") is not None:
        dpg.bind_item_font("history_detail_empty_title", fonts["subheading"])


def _apply_detail_layout():
    """Re-sizes the detail view pieces (called when it is built and on every window resize)."""
    card_w = _state["card_w"]
    ph = _detail_panel_h()
    if dpg.does_item_exist("history_detail_summary"):
        dpg.configure_item("history_detail_summary", width=card_w)
    if dpg.does_item_exist("history_detail_target"):
        dpg.configure_item("history_detail_target", width=_detail_mid_w(card_w))
        _fit_path("history_detail_target", _state["summary_target"], _detail_mid_w(card_w))
    if dpg.does_item_exist("history_detail_panel"):
        dpg.configure_item("history_detail_panel", width=card_w, height=ph)
    if dpg.does_item_exist("history_detail_table"):
        dpg.configure_item("history_detail_table", height=max(1, ph - DETAIL_TABLE_CHROME))
        _refit_detail_cells()
    if dpg.does_item_exist("history_detail_empty_top"):
        dpg.configure_item("history_detail_empty_top",
                           height=max(0, ph // 2 - EMPTY_BLOCK_HEIGHT // 2 - EMPTY_BLOCK_BIAS))
    if dpg.does_item_exist("history_detail_empty_icon"):
        dpg.configure_item("history_detail_empty_icon", indent=_center_indent(card_w, EMPTY_ICON_SIZE))


def _render_batch_detail(batch, icons):
    files = _files_for_batch(batch)
    shown = files[:DETAIL_MAX_FILES]
    base = _get_themes()
    fonts = _state["fonts"] or {}

    with dpg.group(parent="history_group"):
        back = dpg.add_button(label="← Back to all batches", width=DETAIL_BACK_W, height=DETAIL_BACK_H,
                              callback=_back_to_batches)
        dpg.bind_item_theme(back, base["btn_secondary"])
        dpg.add_spacer(height=DETAIL_BACK_GAP)

        _build_summary(batch, icons)

        dpg.add_spacer(height=DETAIL_SECTION_GAP)
        with dpg.group(horizontal=True):
            heading = dpg.add_text(f"Saved results ({len(files):,})", color=COLORS["text_primary"])
            if fonts.get("subheading") is not None:
                dpg.bind_item_font(heading, fonts["subheading"])
            if len(files) > DETAIL_MAX_FILES:
                dpg.add_text(f"·  showing the first {DETAIL_MAX_FILES:,}", color=TABLE_CELL_MUTED_COLOR)
        dpg.add_spacer(height=DETAIL_HEADING_GAP)

        ph = _detail_panel_h()
        with dpg.child_window(width=_state["card_w"], height=ph, tag="history_detail_panel",
                              no_scrollbar=True, no_scroll_with_mouse=True):
            if shown:
                _build_files_table(shown, icons, ph)
            else:
                _build_empty_detail(icons)
        dpg.bind_item_theme("history_detail_panel", _card_theme(False, False))
    _apply_detail_layout()


def _group_entries_by_batch(entries):
    """Fallback grouping helper for log entries that don't have explicit batch_id.
    Groups adjacent entries with identical timestamp (minute bucket) if no batch_id."""
    groups = OrderedDict()
    for e in entries:
        bid = e.get("batch_id")
        if bid:
            key = ("id", bid)
        else:
            ts = str(e.get("timestamp") or "")
            minute_ts = ts[:16] if len(ts) >= 16 else ts
            key = ("ts", minute_ts)
        if key not in groups:
            groups[key] = []
        groups[key].append(e)

    out = []
    for k, files in groups.items():
        if k[0] == "id":
            batch_meta = {}
            if BACKEND_AVAILABLE and get_batch is not None:
                try:
                    b = get_batch(k[1])
                    if b:
                        batch_meta = b
                except Exception:
                    pass
            threats = sum(1 for f in files if (f.get("result") or "").upper() in ("MALICIOUS", "SUSPICIOUS"))
            clean = sum(1 for f in files if (f.get("result") or "").upper() in ("CLEAN", "SAFE", "BENIGN"))
            tss = [f.get("timestamp") for f in files if f.get("timestamp")]
            started = tss[0] if tss else ""
            synthetic = {
                "id": batch_meta.get("id") or k[1],
                "scan_type": batch_meta.get("scan_type") or "custom",
                "target": batch_meta.get("target") or (files[0].get("file_path") and os.path.dirname(files[0].get("file_path")) or ""),
                "started_at": batch_meta.get("started_at") or started,
                "started_at_ms": batch_meta.get("started_at_ms") or 0,
                "completed_at": batch_meta.get("completed_at") or "",
                "elapsed_ms": batch_meta.get("elapsed_ms") or 0,
                "total_files": batch_meta.get("total_files") or len(files),
                "clean_count": batch_meta.get("clean_count") or clean,
                "threat_count": batch_meta.get("threat_count") or threats,
                "suspicious_count": batch_meta.get("suspicious_count") or sum(1 for f in files if (f.get("result") or "").upper() == "SUSPICIOUS"),
                "malicious_count": batch_meta.get("malicious_count") or sum(1 for f in files if (f.get("result") or "").upper() == "MALICIOUS"),
                "error_count": batch_meta.get("error_count") or sum(1 for f in files if (f.get("result") or "").upper() == "ERROR"),
                "status": batch_meta.get("status") or "COMPLETED",
            }
            synthetic["__files"] = list(files)
            out.append(synthetic)
        else:
            threats = sum(1 for f in files if (f.get("result") or "").upper() in ("MALICIOUS", "SUSPICIOUS"))
            clean = sum(1 for f in files if (f.get("result") or "").upper() in ("CLEAN", "SAFE", "BENIGN"))
            started = files[0].get("timestamp") or "" if files else ""
            bid_synth = "SYN-" + (k[1] or "").replace(" ", "").replace(":", "").replace("-", "")
            synthetic = {
                "id": bid_synth,
                "scan_type": "auto",
                "target": (files[0].get("file_path") and os.path.dirname(files[0].get("file_path")) or "") if files else "",
                "started_at": started,
                "started_at_ms": 0,
                "completed_at": "",
                "elapsed_ms": 0,
                "total_files": len(files),
                "clean_count": clean,
                "threat_count": threats,
                "suspicious_count": sum(1 for f in files if (f.get("result") or "").upper() == "SUSPICIOUS"),
                "malicious_count": sum(1 for f in files if (f.get("result") or "").upper() == "MALICIOUS"),
                "error_count": sum(1 for f in files if (f.get("result") or "").upper() == "ERROR"),
                "status": "COMPLETED",
                "__files": list(files),
            }
            out.append(synthetic)

    out.sort(key=lambda b: (b.get("started_at_ms") or 0, b.get("started_at") or ""), reverse=True)
    return out


def _files_for_batch(batch):
    if not batch:
        return []
    if "__files" in batch and batch["__files"]:
        return list(batch["__files"])
    bid = batch.get("id")
    entries = []
    if BACKEND_AVAILABLE and hl is not None:
        try:
            entries = hl.load_log() or []
        except Exception:
            entries = []
    if bid:
        matched = [e for e in entries if e.get("batch_id") == bid]
        if matched:
            return matched
    start = str(batch.get("started_at") or batch.get("startedAt") or "")
    end = str(batch.get("completed_at") or batch.get("completedAt") or "")
    if not start:
        return []
    out = []
    for e in entries:
        ts = str(e.get("timestamp") or "")
        if not ts:
            continue
        if ts < start:
            continue
        if end and ts > end:
            continue
        eb = e.get("batch_id")
        if eb and bid and eb != bid:
            continue
        out.append(e)
    return out


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _update_chip(count):
    if dpg.does_item_exist("history_count_chip"):
        dpg.set_item_label("history_count_chip", f"{count} scan" + ("" if count == 1 else "s"))


def _show_chip(visible):
    if dpg.does_item_exist("history_count_chip"):
        dpg.configure_item("history_count_chip", show=visible)


def _apply_empty_layout():
    if dpg.does_item_exist("history_empty_top"):
        dpg.configure_item("history_empty_top",
                           height=max(0, _state["panel_h"] // 2 - EMPTY_BLOCK_HEIGHT // 2 - EMPTY_BLOCK_BIAS))
    if dpg.does_item_exist("history_empty_icon"):
        dpg.configure_item("history_empty_icon", indent=_center_indent(_state["row_w"], EMPTY_ICON_SIZE))


def _build_empty_state(icons):
    base = _get_themes()
    fonts = _state["fonts"] or {}
    with dpg.group(parent="history_group", tag="history_empty"):
        dpg.add_spacer(height=100, tag="history_empty_top")
        icon = (icons or {}).get("history")
        if icon:
            dpg.add_image(icon, width=EMPTY_ICON_SIZE, height=EMPTY_ICON_SIZE,
                          tint_color=COLORS["text_secondary"], tag="history_empty_icon")
        dpg.add_spacer(height=EMPTY_GAP)
        dpg.add_button(label=EMPTY_TITLE, width=-1, height=EMPTY_TITLE_HEIGHT, tag="history_empty_title")
        dpg.add_button(label=EMPTY_SUBTITLE, width=-1, height=EMPTY_SUB_HEIGHT, tag="history_empty_sub")
    dpg.bind_item_theme("history_empty_title", base["label_on"])
    dpg.bind_item_theme("history_empty_sub", base["sub"])
    if fonts.get("subheading") is not None:
        dpg.bind_item_font("history_empty_title", fonts["subheading"])
    _apply_empty_layout()


def _render_batch_list(batches, icons):
    global _BATCH_ROW_MAP, _LAST_BATCH_LIST
    _BATCH_ROW_MAP = {}
    _LAST_BATCH_LIST = list(batches or [])
    _update_chip(len(_LAST_BATCH_LIST))
    if not batches:
        _build_empty_state(icons)
        return

    with dpg.group(parent="history_group"):
        for i, b in enumerate(batches):
            try:
                _batch_row(b, i, icons or {})
            except Exception:
                traceback.print_exc()
            if i < len(batches) - 1:
                dpg.add_spacer(height=ROW_GAP)


def _render_history_view(icons=None):
    global GLOBAL_ICONS, _BATCH_ROW_MAP
    if icons is not None:
        GLOBAL_ICONS = icons
    else:
        icons = GLOBAL_ICONS or {}

    if not dpg.does_item_exist("history_group"):
        return

    _BATCH_ROW_MAP = {}
    _state["hover"] = None
    _state["attention"] = {}
    try:
        dpg.delete_item("history_group", children_only=True)
    except Exception:
        pass
    _cleanup_history_item_tags()

    if _HISTORY_DETAIL_BATCH is not None:
        _show_chip(False)
        _render_batch_detail(_HISTORY_DETAIL_BATCH, icons)
        _reset_scroll()
        return
    _show_chip(True)
    _render_batch_list(_LAST_BATCH_LIST, icons)


# ---------------------------------------------------------------------------
# TEMP fake data (UI only, nothing is saved anywhere)
# ---------------------------------------------------------------------------

_FAKE_NAMES = ["update_check", "setup_helper_v2", "crack_patch_final", "driver_booster", "invoice_final",
               "game_launcher", "UnityCrashHandler64", "readme_viewer"]


def _fake_files(bid, n, folder, started, pattern):
    """n fake file entries; pattern is a list of results that is cycled through."""
    out = []
    for i in range(n):
        res = pattern[i % len(pattern)]
        prob = 0.97 if res == "MALICIOUS" else 0.55 if res == "SUSPICIOUS" else None
        out.append({"timestamp": started, "file_path": f"{folder}\\{_FAKE_NAMES[i % len(_FAKE_NAMES)]}_{i + 1:03d}.exe",
                    "result": res, "probability": prob,
                    "details": "Fake entry for the layout test. This text is long on purpose so the tooltip has to wrap onto several lines." if i % 4 == 2 else None,
                    "batch_id": bid})
    return out


def _fake_batches():
    """Six FAKE batches that cover every card state (threats, clean, no files, failed, cancelled, running)."""
    def batch(bid, scan_type, target, started, status, total, clean, mal, sus, err, elapsed, files):
        return {
            "id": bid, "scan_type": scan_type, "target": target, "started_at": started, "started_at_ms": 0,
            "completed_at": None if status == "RUNNING" else started, "elapsed_ms": elapsed, "total_files": total,
            "clean_count": clean, "threat_count": mal + sus, "suspicious_count": sus, "malicious_count": mal,
            "error_count": err, "status": status, "__files": files,
        }
    long_target = r"C:\Users\Kay\Downloads, C:\Users\Kay\Desktop, C:\Users\Kay\AppData\Local\Temp, D:\Games\Some Very Long Folder Name"
    return [
        batch("BFAKE000000000001", "quick", long_target, "2026-10-09 09:12:44", "COMPLETED", 86, 81, 3, 2, 0, 12400,
              _fake_files("BFAKE000000000001", 40, r"C:\Users\Kay\Downloads", "2026-10-09 09:12:44",
                          ["CLEAN", "CLEAN", "MALICIOUS", "CLEAN", "SUSPICIOUS", "CLEAN", "QUARANTINED", "RESTORED", "DELETED", "ERROR"])),
        batch("BFAKE000000000002", "full", "C:\\, D:\\", "2026-10-08 22:05:10", "COMPLETED", 1204, 1204, 0, 0, 0, 312000,
              _fake_files("BFAKE000000000002", 30, r"C:\Program Files\Some App", "2026-10-08 22:05:10", ["CLEAN"])),
        batch("BFAKE000000000003", "custom", r"D:\Empty Folder", "2026-01-15 10:00:00", "COMPLETED", 0, 0, 0, 0, 0, 300, []),
        batch("BFAKE000000000004", "custom", r"E:\USB Drive", "2026-10-07 18:40:02", "FAILED", 12, 8, 0, 0, 4, 2100,
              _fake_files("BFAKE000000000004", 12, r"E:\USB Drive", "2026-10-07 18:40:02", ["CLEAN", "CLEAN", "ERROR"])),
        batch("BFAKE000000000005", "quick", r"C:\Users\Kay\Documents", "2026-10-06 08:15:30", "CANCELLED", 230, 230, 0, 0, 0, 8000,
              _fake_files("BFAKE000000000005", 20, r"C:\Users\Kay\Documents", "2026-10-06 08:15:30", ["CLEAN"])),
        batch("BFAKE000000000006", "full", "C:\\", "2026-10-09 10:30:00", "RUNNING", 340, 338, 2, 0, 0, 0,
              _fake_files("BFAKE000000000006", 10, r"C:\Windows\Temp", "2026-10-09 10:30:00", ["CLEAN", "CLEAN", "MALICIOUS"])),
    ]


# ---------------------------------------------------------------------------
# Data + public entry points
# ---------------------------------------------------------------------------

def _build_batches_from_backend(limit=50):
    batches = []
    if BACKEND_AVAILABLE and list_batches is not None:
        try:
            batches = list_batches(limit=limit) or []
        except Exception as b_err:
            print(f"[ui/history] list_batches failed: {b_err}")
            batches = []
    if not batches and BACKEND_AVAILABLE and hl is not None:
        try:
            entries = hl.load_log(limit=max(2000, limit * 60)) or []
            entries = list(reversed(entries))
            batches = _group_entries_by_batch(entries)[:limit]
        except Exception as err:
            print(f"[ui/history] synthetic batch group failed: {err}")
    return batches


def _rebuild_history_from_data(entries, icons=None):
    """Compatibility wrapper. File-level logs must not replace the batch list."""
    if isinstance(entries, list) and entries and _looks_like_batch(entries[0]):
        global _LAST_BATCH_LIST, _HISTORY_DETAIL_BATCH
        _HISTORY_DETAIL_BATCH = None
        _LAST_BATCH_LIST = list(entries)
        _render_history_view(icons=icons)
        return
    _rebuild_history(icons=icons)


def _rebuild_history(icons=None, limit=50):
    global GLOBAL_ICONS, _LAST_BATCH_LIST, _HISTORY_DETAIL_BATCH
    if icons is not None:
        GLOBAL_ICONS = icons
    else:
        icons = GLOBAL_ICONS
    _HISTORY_DETAIL_BATCH = None
    _LAST_BATCH_LIST = _build_batches_from_backend(limit=limit)
    _render_history_view(icons=icons)


def _resize_history(content_w, content_h):
    """Called by ui/layout.py whenever the window size changes."""
    row_w = _row_width(content_w)   # same width as the Scan page cards, so the edges line up
    panel_h = max(HISTORY_PANEL_MIN_HEIGHT, content_h - HISTORY_HEADER_HEIGHT - HISTORY_BOTTOM_MARGIN)
    card_w = row_w - CARD_W_TRIM
    _state["row_w"] = row_w
    _state["panel_h"] = panel_h
    _state["card_w"] = card_w
    _state["mid_w"] = _mid_width(card_w)   # new cards read these, so a rebuild never snaps back

    if dpg.does_item_exist("history_scroll"):
        dpg.configure_item("history_scroll", width=row_w, height=panel_h)
    _apply_card_widths()
    _apply_empty_layout()
    narrow = content_w < DETAIL_NARROW_BREAKPOINT
    if narrow != _state["narrow"]:   # only fires when the window crosses the breakpoint, not on every pixel of a drag
        _state["narrow"] = narrow
        _rebuild_detail_table()
    _apply_detail_layout()


def build_history(parent, fonts, icons):
    global GLOBAL_ICONS, _HISTORY_MOUSE_BOUND
    GLOBAL_ICONS = icons
    _state["fonts"] = fonts
    ct = _themes()
    dpg.add_spacer(height=20, parent=parent)
    if not _HISTORY_MOUSE_BOUND:
        try:
            with dpg.handler_registry():
                dpg.add_mouse_click_handler(callback=_on_history_mouse_click)
                dpg.add_mouse_move_handler(callback=_on_history_mouse_move)
                dpg.add_mouse_wheel_handler(callback=_on_history_mouse_move)   # cards scroll under a still mouse
            _HISTORY_MOUSE_BOUND = True
        except Exception as e:
            print(f"[ui/history] mouse handler bind failed: {e}")
    with dpg.group(horizontal=True, parent=parent):
        dpg.add_spacer(width=PAGE_LEFT_PAD)
        with dpg.group():
            with dpg.group(horizontal=True):
                dpg.add_text("Protection History", tag="history_page_title")
                dpg.bind_item_font("history_page_title", fonts["heading"])
                dpg.add_button(label="0 scans", tag="history_count_chip", height=CHIP_HEIGHT)
            dpg.bind_item_theme("history_count_chip", ct["chip"])
            dpg.add_text("Each scan is one batch. Click a batch to see the results saved from that run.",
                         color=COLORS["text_secondary"])
            dpg.add_spacer(height=15)

            with dpg.child_window(width=HISTORY_START_W, height=HISTORY_START_H, border=False, tag="history_scroll"):
                with dpg.group(tag="history_group"):
                    pass
            dpg.bind_item_theme("history_scroll", ct["scroll"])
            _rebuild_history(icons)

    register_resize("history", _resize_history)