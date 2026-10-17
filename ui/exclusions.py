import dearpygui.dearpygui as dpg
import traceback
from ui.theme import COLORS
from ui.layout import register_resize
from ui.scan_layout import _get_themes, _center_indent, PAGE_LEFT_PAD, CHILD_PAD_X, ITEM_SPACING_X
from ui.scan_pipeline import _row_width
from ui.scan_threats import _themes as _threat_themes, _flat_button_theme, PILL_BG_ALPHA, GUTTER_W, ROW_PAD_X
from ui.table_style import TABLE_ROW_HEIGHT, TABLE_PILL_HEIGHT, TABLE_CELL_MUTED_COLOR, apply_table_font
from ui.table_text import fit_text
from ui.quarantine import _pill_theme   # same pill look as Quarantine (used for the chip and the status pills)
from ui.confirm_dialog import init_confirm, ask_confirm
from ui.toast import init_toast, show_toast
from ui.exclusion_picker import init_exclusion_picker, open_exclusion_picker
import sys
import os

# Add parent directory to path to import Malware_System
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    import system.security.allowed as sa
    import system.security.exclusions as se
    BACKEND_AVAILABLE = True
except Exception as e:
    print(f"Warning [ui/exclusions.py]: Could not load backend dependency 'security.allowed' or 'security.exclusions': {e}")
    BACKEND_AVAILABLE = False

# exclusions.py

# ---- Page text ----
PAGE_SUBTITLE = "Folders skipped during scans and real-time protection, including everything inside them"
ADD_TITLE = "Add an exclusion"
ADD_HELPER = "Pick a folder or paste its path below"
ADD_INPUT_HINT = "Or paste a folder path here..."
LIST_TITLE = "Current Exclusions"

# ---- Add card (tune here) ----
ADD_CARD_HEIGHT = 148          # raise if the bottom row touches the card edge, lower if there's a gap
ADD_CARD_START_W = 1240        # placeholder until ui/layout.py sets the real width
ADD_SIDE_PAD = 16              # left/right padding inside the card
ADD_TOP_PAD = 6                # space above the header row
ADD_HEADER_GAP = 12            # space between the header row and the input row

# header badge (rounded blue square with the folder icon)
ADD_BADGE_SIZE = 44
ADD_BADGE_ICON = 24
ADD_BADGE_ROUNDING = 12
ADD_BADGE_BG_ALPHA = 45        # how strong the blue tint is (0-255)

# input row
ADD_ROW_HEIGHT = 38            # same as the Scan page buttons
ADD_SELECT_W = 150
ADD_BTN_W = 96
ADD_INPUT_START_W = 600
ADD_INPUT_MIN_W = 200
ADD_INPUT_PAD_X = 12
ADD_INPUT_PAD_Y = 10           # input height = font size (18) + 2 * this, so 10 matches the 38px buttons
ADD_WIDTH_TRIM = 2             # safety so the row never overflows the card

# ---- List panel layout (tune here) ----
LIST_PAGE_HEADER_HEIGHT = 110  # title + subtitle block at the top (same estimate as Quarantine)
LIST_GAP_ABOVE = 20            # space between the add card and the list header
LIST_HEADER_HEIGHT = 44        # "Current Exclusions" row + the gap under it (raise if the panel runs off the bottom)
LIST_BOTTOM_MARGIN = 90        # space under the panel so the help button never covers the last rows
LIST_PANEL_MIN_HEIGHT = 240    # below this the page scrolls instead of squishing
LIST_PANEL_START_H = 320       # placeholder until ui/layout.py sets the real height
LIST_CHILD_PAD_Y = 8           # DPG default child window padding
LIST_TABLE_CHROME = 2 * LIST_CHILD_PAD_Y + 4   # table height = panel height - this (raise if the table gets cut off at the bottom)

# ---- Counter chip next to the list title ----
CHIP_HEIGHT = 28
CHIP_PAD_X = 12

# ---- Table rows (shared look: change the basics in ui/table_style.py) ----
ROW_HEIGHT = TABLE_ROW_HEIGHT
PILL_HEIGHT = TABLE_PILL_HEIGHT
CELL_MUTED_COLOR = TABLE_CELL_MUTED_COLOR

# ---- Columns (fixed ones in px INCLUDING cell padding, stretch ones as weights) ----
ICON_SIZE = 20
ROW_ITEM_SPACING_Y = 4         # DPG default vertical item spacing
ICON_NUDGE_Y = max(0, (ROW_HEIGHT - ICON_SIZE) // 2 - ROW_ITEM_SPACING_Y)   # centers the icon on the row text
COL_ICON_W = ICON_SIZE + 2 * ROW_PAD_X
COL_NAME_WEIGHT = 2.0
COL_LOCATION_WEIGHT = 3.0
COL_STATUS_W = 170
REMOVE_BTN_W = 96
COL_ACTIONS_W = REMOVE_BTN_W + 2 * ROW_PAD_X + 8   # +8 = safety so the button never clips

# ---- Ellipsis (long names end in "...", the full text stays in the tooltip) ----
ELLIPSIS_ENABLED = True        # False = old hard clipping
MEASURE_MIN_FRAME = 40         # DPG can't measure text before this frame, so rows drawn earlier are left untrimmed
PANEL_PAD_X = 8               # the list panel's own left/right padding (DPG default)
TABLE_SCROLLBAR_W = 16         # room kept for the table's scrollbar. Raise if "..." touches the next column
FIXED_COL_EXTRA_PX = 80        # padding the 5 fixed columns add on top of their widths. Measured at 924 and 1324: estimate lands 0-9px under the real cell, so text never overflows

# ---- Status (is the folder still on disk?) ----
CHECK_PATHS_EXIST = True       # False = skip the disk check, every row shows ACTIVE
SKIP_CHECK_FOR_UNC = True      # network paths (\\server\share) can freeze the UI when offline, so don't check them
STATUS_ACTIVE = "ACTIVE"
STATUS_MISSING = "NOT FOUND"
STATUS_UNCHECKED = "NOT CHECKED"
STATUS_STYLE = {               # label -> color
    STATUS_ACTIVE: COLORS["accent_green"],
    STATUS_MISSING: COLORS["accent_orange"],
    STATUS_UNCHECKED: COLORS["text_secondary"],
}
ICON_COLORS = {                # folder icon tint per status
    STATUS_ACTIVE: COLORS["accent_blue"],
    STATUS_MISSING: COLORS["accent_orange"],
    STATUS_UNCHECKED: COLORS["text_secondary"],
}
LOCATION_ROOT_LABEL = "Drive root"   # shown as the location when the excluded folder IS a drive (D:\)

# ---- Tooltips ----
TIP_COLOR = COLORS["text_secondary"]
TIP_REMOVE = "Stop skipping this folder (it will be scanned again)"
TIP_ACTIVE = "This folder and everything inside it is skipped by scans"
TIP_MISSING = "This folder wasn't found on disk when the list was loaded"
TIP_UNCHECKED = "Network path: not checked, to keep the app responsive"

# ---- Path cleanup + checks on Add ----
CLEAN_QUOTES = "\"'"           # quotes stripped from both ends (Explorer's "Copy as path" adds them)
NORMALIZE_SLASHES = True       # D:/Games -> D:\Games
BLOCK_MISSING_PATH = False     # True = refuse a folder that isn't on disk. False = save it anyway (it shows NOT FOUND)

# ---- Remove confirmation (the popup itself lives in ui/confirm_dialog.py) ----
CONFIRM_REMOVE_TITLE = "Remove exclusion?"
CONFIRM_REMOVE_MESSAGE = "{name} will be scanned again from now on."
CONFIRM_REMOVE_LABEL = "Remove"

# ---- Toast messages (the toast itself lives in ui/toast.py) ----
TOAST_NAME_MAX_CHARS = 28      # long folder names are shortened with "..." so the toast stays on one line
MSG_ADDED = "{name} added to exclusions"
MSG_EMPTY = "Enter or pick a folder first"
MSG_DUPLICATE = "{name} is already excluded"
MSG_NOT_FOUND = "Folder not found, check the path"
MSG_NOT_FOLDER = "That's a file, exclusions are for folders"
MSG_ADD_FAILED = "Couldn't add {name} (see terminal)"
MSG_REMOVED = "{name} removed from exclusions"
MSG_REMOVE_FAILED = "Couldn't remove {name} (see terminal)"
MSG_NO_BACKEND = "Backend not loaded, nothing was changed"

# ---- Empty state ----
EMPTY_TITLE = "No exclusions yet"
EMPTY_SUBTITLE = "Folders you add above will be skipped by scans"
EMPTY_ICON_SIZE = 48
EMPTY_GAP = 8
EMPTY_TITLE_HEIGHT = 30
EMPTY_SUB_HEIGHT = 24
EMPTY_BLOCK_HEIGHT = EMPTY_ICON_SIZE + EMPTY_GAP + EMPTY_TITLE_HEIGHT + EMPTY_SUB_HEIGHT + 12
EMPTY_BLOCK_BIAS = 20          # raises the block slightly above the exact center

_T = {}
_state = {"row_w": ADD_CARD_START_W, "panel_h": LIST_PANEL_START_H, "icons": None, "fonts": None,
          "cells": []}   # cells = (folder button, full name, location button, full parent path), re-trimmed on resize


# ---------------------------------------------------------------------------
# Themes (built once)
# ---------------------------------------------------------------------------

def _themes():
    if _T:
        return _T
    with dpg.theme() as badge:
        with dpg.theme_component(dpg.mvChildWindow):
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, (*COLORS["accent_blue"], ADD_BADGE_BG_ALPHA))
            dpg.add_theme_color(dpg.mvThemeCol_Border, (0, 0, 0, 0))
            dpg.add_theme_style(dpg.mvStyleVar_ChildBorderSize, 0)
            dpg.add_theme_style(dpg.mvStyleVar_ChildRounding, ADD_BADGE_ROUNDING)
            dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 0, 0)
    _T["badge"] = badge

    with dpg.theme() as inp:
        with dpg.theme_component(dpg.mvInputText):
            dpg.add_theme_color(dpg.mvThemeCol_FrameBg, COLORS["bg_sidebar"])
            dpg.add_theme_color(dpg.mvThemeCol_Border, COLORS["border"])
            dpg.add_theme_color(dpg.mvThemeCol_Text, COLORS["text_primary"])
            dpg.add_theme_style(dpg.mvStyleVar_FrameBorderSize, 1)
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding, ADD_INPUT_PAD_X, ADD_INPUT_PAD_Y)
    _T["input"] = inp

    _T["chip"] = _pill_theme(COLORS["accent_blue"], PILL_BG_ALPHA, CHIP_PAD_X)
    for label, color in STATUS_STYLE.items():
        _T[f"status_{label}"] = _pill_theme(color, PILL_BG_ALPHA)
    _T["cell_muted"] = _flat_button_theme(CELL_MUTED_COLOR)   # location text
    return _T


# ---------------------------------------------------------------------------
# Path helpers (UI only: they never change what is stored)
# ---------------------------------------------------------------------------

def _split_path(path):
    """Returns (folder name, parent folder) for display."""
    clean = path.rstrip("\\/") if len(path) > 3 else path   # keep "D:\" as it is
    name = os.path.basename(clean) or path
    parent = os.path.dirname(clean) if name != path else ""
    return name, (parent or LOCATION_ROOT_LABEL)


def _status_for(path):
    """ACTIVE / NOT FOUND / NOT CHECKED. Only reads the disk, changes nothing."""
    if not CHECK_PATHS_EXIST:
        return STATUS_ACTIVE
    if SKIP_CHECK_FOR_UNC and path.startswith("\\\\"):
        return STATUS_UNCHECKED
    try:
        return STATUS_ACTIVE if os.path.exists(path) else STATUS_MISSING
    except Exception:
        traceback.print_exc()
        return STATUS_UNCHECKED


# ---------------------------------------------------------------------------
# Actions (logic unchanged in this step, except Remove now takes the path)
# ---------------------------------------------------------------------------

def _short(name):
    if len(name) <= TOAST_NAME_MAX_CHARS:
        return name
    return name[:TOAST_NAME_MAX_CHARS - 3] + "..."


def _clean_path(raw):
    """Tidies what the user typed or pasted BEFORE it is saved: no spaces or quotes around it, backslashes
    instead of slashes, no trailing backslash ("D:\\" stays), and a bare "D:" becomes "D:\\".
    The result is a normal Windows path. The backend lowercases and abspath()s everything when it compares
    anyway (is_excluded in system/security/exclusions.py), so nothing changes for it. Existing entries are never rewritten."""
    path = (raw or "").strip()
    while len(path) >= 2 and path[0] == path[-1] and path[0] in CLEAN_QUOTES:
        path = path[1:-1].strip()
    if NORMALIZE_SLASHES:
        path = path.replace("/", "\\")
    if len(path) > 3:
        path = path.rstrip("\\")
    if len(path) == 2 and path[1] == ":":
        path += "\\"
    return path


def _path_problem(path):
    """Returns a toast message if the path shouldn't be added, otherwise None. It only reads the disk."""
    if not BLOCK_MISSING_PATH:
        return None
    if SKIP_CHECK_FOR_UNC and path.startswith("\\\\"):
        return None   # network paths aren't checked (they can freeze the UI when offline)
    try:
        if os.path.isdir(path):
            return None
        return MSG_NOT_FOLDER if os.path.exists(path) else MSG_NOT_FOUND
    except Exception:
        traceback.print_exc()
        return None   # if the check itself breaks, don't block the user


def _add_exclusion(sender=None, app_data=None, user_data=None):
    """Add button and Enter key both land here."""
    path = _clean_path(dpg.get_value("exclusion_input"))
    if not path:
        show_toast(MSG_EMPTY, "warning")
        return
    if not BACKEND_AVAILABLE:
        show_toast(MSG_NO_BACKEND, "warning")
        return

    name = _short(_split_path(path)[0])
    try:
        existing = se.list_exclusions()
    except Exception:
        traceback.print_exc()
        show_toast(MSG_ADD_FAILED.format(name=name), "error")
        return

    # duplicates are compared case-insensitively and ignoring a trailing slash (the backend only skips exact matches)
    if path.lower() in {_clean_path(p).lower() for p in existing}:
        show_toast(MSG_DUPLICATE.format(name=name), "info")
        return

    problem = _path_problem(path)
    if problem:
        show_toast(problem, "warning")
        return

    try:
        se.add_exclusion(path)
        landed = path in se.list_exclusions()   # add_exclusion returns nothing, so confirm it really got saved
    except Exception:
        traceback.print_exc()
        show_toast(MSG_ADD_FAILED.format(name=name), "error")
        return

    if landed:
        dpg.set_value("exclusion_input", "")
        show_toast(MSG_ADDED.format(name=name), "success")
    else:
        print(f"[exclusions] add_exclusion ran but the path is not in the list: {path}")
        show_toast(MSG_ADD_FAILED.format(name=name), "error")
    _rebuild_list()


def _ask_remove(sender, app_data, user_data):
    """The Remove button lands here first. Only the popup's confirm button runs _remove_exclusion."""
    path = user_data
    name = _split_path(path)[0]
    ask_confirm(CONFIRM_REMOVE_TITLE, CONFIRM_REMOVE_MESSAGE.format(name=name),
                on_confirm=_remove_exclusion, user_data=path,
                confirm_label=CONFIRM_REMOVE_LABEL, danger=False)


def _remove_exclusion(sender, app_data, user_data):
    path = user_data   # the stored path itself (not a row index, which could go stale)
    name = _short(_split_path(path)[0])
    if not BACKEND_AVAILABLE:
        show_toast(MSG_NO_BACKEND, "warning")
        return
    try:
        se.remove_exclusion(path)
        gone = path not in se.list_exclusions()
    except Exception:
        traceback.print_exc()
        show_toast(MSG_REMOVE_FAILED.format(name=name), "error")
        return
    if gone:
        show_toast(MSG_REMOVED.format(name=name), "success")
    else:
        print(f"[exclusions] remove_exclusion ran but the path is still in the list: {path}")
        show_toast(MSG_REMOVE_FAILED.format(name=name), "error")
    _rebuild_list()

def _folder_picked(sender, app_data):
    path = app_data.get("file_path_name", "")
    if path:
        dpg.set_value("exclusion_input", path)


# ---------------------------------------------------------------------------
# Table
# ---------------------------------------------------------------------------

def _label_widths():
    """(Folder, Location) pixel budget for the text inside the cells. An estimate from the column constants."""
    fixed = 2 * GUTTER_W + COL_ICON_W + COL_STATUS_W + COL_ACTIONS_W
    table_w = _state["row_w"] - 2 * PANEL_PAD_X - TABLE_SCROLLBAR_W
    avail = max(0, table_w - fixed - FIXED_COL_EXTRA_PX)
    total = COL_NAME_WEIGHT + COL_LOCATION_WEIGHT
    name_w = avail * COL_NAME_WEIGHT / total - 2 * ROW_PAD_X
    loc_w = avail * COL_LOCATION_WEIGHT / total - 2 * ROW_PAD_X
    return int(name_w), int(loc_w)


def _fit_cell(name_btn, name, loc_btn, parent, widths):
    """Shortens the two text cells to their budget. The full text stays in the tooltips."""
    if not ELLIPSIS_ENABLED or dpg.get_frame_count() < MEASURE_MIN_FRAME:
        return
    font = (_state["fonts"] or {}).get("table")
    if dpg.does_item_exist(name_btn):
        dpg.set_item_label(name_btn, fit_text(name, widths[0], font))
    if dpg.does_item_exist(loc_btn):
        dpg.set_item_label(loc_btn, fit_text(parent, widths[1], font))


def _refit_cells():
    widths = _label_widths()
    for cell in list(_state["cells"]):
        _fit_cell(*cell, widths)


def _build_table():
    """Creates a fresh, empty table with its columns. Theme and font are re-bound every time."""
    tt = _threat_themes()
    with dpg.table(parent="exclusions_container", tag="exclusions_table", header_row=True, row_background=True,
                   borders_innerH=False, borders_outerH=False,
                   borders_innerV=False, borders_outerV=False,
                   scrollY=True, freeze_rows=1, width=-1,
                   height=max(1, _state["panel_h"] - LIST_TABLE_CHROME)):
        dpg.add_table_column(label="", width_fixed=True, init_width_or_weight=GUTTER_W)
        dpg.add_table_column(label="", width_fixed=True, init_width_or_weight=COL_ICON_W)
        dpg.add_table_column(label="Folder", width_stretch=True, init_width_or_weight=COL_NAME_WEIGHT)
        dpg.add_table_column(label="Location", width_stretch=True, init_width_or_weight=COL_LOCATION_WEIGHT)
        dpg.add_table_column(label="Status", width_fixed=True, init_width_or_weight=COL_STATUS_W)
        dpg.add_table_column(label="Actions", width_fixed=True, init_width_or_weight=COL_ACTIONS_W)
        dpg.add_table_column(label="", width_fixed=True, init_width_or_weight=GUTTER_W)
    dpg.bind_item_theme("exclusions_table", tt["table"])
    apply_table_font("exclusions_table", _state["fonts"])   # shared table font (ui/table_style.py)


def _add_row(path):
    tt = _threat_themes()
    t = _themes()
    base = _get_themes()
    icons = _state["icons"]
    status = _status_for(path)
    name, parent = _split_path(path)

    with dpg.table_row(parent="exclusions_table"):
        dpg.add_spacer(width=1)   # left gutter cell

        with dpg.group():         # icon cell (a group, so the nudge spacer and the icon share ONE cell)
            dpg.add_spacer(height=ICON_NUDGE_Y)
            folder = icons.get("folder") if icons else None
            if folder:
                dpg.add_image(folder, width=ICON_SIZE, height=ICON_SIZE, tint_color=ICON_COLORS[status])

        name_btn = dpg.add_button(label=name, width=-1, height=ROW_HEIGHT)
        dpg.bind_item_theme(name_btn, tt["name"])
        with dpg.tooltip(name_btn):
            dpg.add_text(path, color=COLORS["text_primary"])
            if status == STATUS_MISSING:
                dpg.add_text(TIP_MISSING, color=COLORS["accent_orange"])

        loc_btn = dpg.add_button(label=parent, width=-1, height=ROW_HEIGHT)
        dpg.bind_item_theme(loc_btn, t["cell_muted"])
        with dpg.tooltip(loc_btn):
            dpg.add_text(parent, color=TIP_COLOR)
        _state["cells"].append((name_btn, name, loc_btn, parent))
        _fit_cell(name_btn, name, loc_btn, parent, _label_widths())

        pill = dpg.add_button(label=status, width=-1, height=PILL_HEIGHT)
        dpg.bind_item_theme(pill, t[f"status_{status}"])
        tip = {STATUS_ACTIVE: TIP_ACTIVE, STATUS_MISSING: TIP_MISSING, STATUS_UNCHECKED: TIP_UNCHECKED}[status]
        with dpg.tooltip(pill):
            dpg.add_text(tip, color=TIP_COLOR)

        remove = dpg.add_button(label="Remove", width=REMOVE_BTN_W, height=ROW_HEIGHT,
                                callback=_ask_remove, user_data=path)
        dpg.bind_item_theme(remove, base["btn_secondary"])
        with dpg.tooltip(remove):
            dpg.add_text(TIP_REMOVE, color=TIP_COLOR)

        dpg.add_spacer(width=1)   # right gutter cell


def _update_chip(count):
    if dpg.does_item_exist("exclusions_count_chip"):
        dpg.set_item_label("exclusions_count_chip", f"{count} folder" + ("" if count == 1 else "s"))


def _rebuild_list():
    """Deletes and rebuilds the table (theme and font get re-bound in _build_table)."""
    if not dpg.does_item_exist("exclusions_container"):
        return
    _state["cells"].clear()
    if dpg.does_item_exist("exclusions_table"):
        dpg.delete_item("exclusions_table")
    _build_table()

    items = []
    if BACKEND_AVAILABLE:
        try:
            items = se.list_exclusions()
        except Exception:
            traceback.print_exc()

    has_items = bool(items)
    dpg.configure_item("exclusions_table", show=has_items)
    if dpg.does_item_exist("exclusions_empty"):
        dpg.configure_item("exclusions_empty", show=not has_items)
    _update_chip(len(items))

    for path in items:
        _add_row(path)


# ---------------------------------------------------------------------------
# Resize
# ---------------------------------------------------------------------------

def _input_width(row_w):
    inner = row_w - 2 * CHILD_PAD_X
    avail = inner - 2 * ADD_SIDE_PAD - ADD_SELECT_W - ADD_BTN_W - 2 * ITEM_SPACING_X - ADD_WIDTH_TRIM
    return max(ADD_INPUT_MIN_W, int(avail))


def _resize_exclusions(content_w, content_h):
    """Called by ui/layout.py whenever the window size changes."""
    row_w = _row_width(content_w)   # same edges as Scan / Quarantine / History
    panel_h = max(LIST_PANEL_MIN_HEIGHT,
                  content_h - LIST_PAGE_HEADER_HEIGHT - ADD_CARD_HEIGHT - LIST_GAP_ABOVE
                  - LIST_HEADER_HEIGHT - LIST_BOTTOM_MARGIN)
    _state["row_w"] = row_w
    _state["panel_h"] = panel_h   # _rebuild_list reads this, so a rebuild never snaps back

    if dpg.does_item_exist("add_exclusion_card"):
        dpg.configure_item("add_exclusion_card", width=row_w)
    if dpg.does_item_exist("exclusion_input"):
        dpg.configure_item("exclusion_input", width=_input_width(row_w))
    if dpg.does_item_exist("exclusions_container"):
        dpg.configure_item("exclusions_container", width=row_w, height=panel_h)
    if dpg.does_item_exist("exclusions_table"):
        dpg.configure_item("exclusions_table", height=max(1, panel_h - LIST_TABLE_CHROME))
    _refit_cells()
    if dpg.does_item_exist("exclusions_empty_top"):
        dpg.configure_item("exclusions_empty_top",
                           height=max(0, panel_h // 2 - EMPTY_BLOCK_HEIGHT // 2 - EMPTY_BLOCK_BIAS))
    if dpg.does_item_exist("exclusions_empty_icon"):
        dpg.configure_item("exclusions_empty_icon", indent=_center_indent(row_w, EMPTY_ICON_SIZE))


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def _build_empty_state(fonts, icons):
    """The 'nothing here' block. Hidden while there are items. Centered with full-width invisible buttons."""
    t = _get_themes()
    with dpg.group(tag="exclusions_empty", show=False):
        dpg.add_spacer(height=100, tag="exclusions_empty_top")
        icon = icons.get("folder") if icons else None
        if icon:
            dpg.add_image(icon, width=EMPTY_ICON_SIZE, height=EMPTY_ICON_SIZE,
                          tint_color=COLORS["accent_blue"], tag="exclusions_empty_icon")
        dpg.add_spacer(height=EMPTY_GAP)
        dpg.add_button(label=EMPTY_TITLE, width=-1, height=EMPTY_TITLE_HEIGHT, tag="exclusions_empty_title")
        dpg.add_button(label=EMPTY_SUBTITLE, width=-1, height=EMPTY_SUB_HEIGHT, tag="exclusions_empty_sub")
    dpg.bind_item_theme("exclusions_empty_title", t["label_on"])
    dpg.bind_item_theme("exclusions_empty_sub", t["sub"])
    if fonts and fonts.get("subheading") is not None:
        dpg.bind_item_font("exclusions_empty_title", fonts["subheading"])


def build_exclusions(parent, fonts, icons):
    _state["icons"] = icons
    _state["fonts"] = fonts
    init_confirm(fonts)   # safe to call again: Quarantine calls these too
    init_toast()
    t = _themes()
    base = _get_themes()   # shared themes from ui/scan_layout.py (card_on, btn_secondary, btn_start)
    folder_icon = icons.get("folder") if icons else None

    dpg.add_spacer(height=20, parent=parent)
    with dpg.group(horizontal=True, parent=parent):
        dpg.add_spacer(width=PAGE_LEFT_PAD)
        with dpg.group():
            dpg.add_text("Exclusions", tag="exclusions_page_title")
            dpg.bind_item_font("exclusions_page_title", fonts["heading"])
            dpg.add_text(PAGE_SUBTITLE, color=COLORS["text_secondary"])
            dpg.add_spacer(height=15)

            init_exclusion_picker(_folder_picked)   # our styled dialog lives in ui/exclusion_picker.py

            # ---- Add card: blue border like the selected Scan card ----
            with dpg.child_window(width=ADD_CARD_START_W, height=ADD_CARD_HEIGHT, tag="add_exclusion_card",
                                  no_scrollbar=True, no_scroll_with_mouse=True):
                dpg.add_spacer(height=ADD_TOP_PAD)

                with dpg.group(horizontal=True, indent=ADD_SIDE_PAD):
                    with dpg.child_window(width=ADD_BADGE_SIZE, height=ADD_BADGE_SIZE, tag="add_exclusion_badge",
                                          no_scrollbar=True, no_scroll_with_mouse=True):
                        if folder_icon:
                            pad = (ADD_BADGE_SIZE - ADD_BADGE_ICON) // 2
                            dpg.add_image(folder_icon, width=ADD_BADGE_ICON, height=ADD_BADGE_ICON,
                                          tint_color=COLORS["accent_blue"], pos=(pad, pad))
                    with dpg.group():
                        dpg.add_text(ADD_TITLE, color=COLORS["text_primary"], tag="add_exclusion_title")
                        dpg.add_text(ADD_HELPER, color=COLORS["text_secondary"])

                dpg.add_spacer(height=ADD_HEADER_GAP)

                with dpg.group(horizontal=True, indent=ADD_SIDE_PAD):
                    dpg.add_button(label="Select Folder", tag="select_folder_btn", width=ADD_SELECT_W,
                                   height=ADD_ROW_HEIGHT,
                                   callback=open_exclusion_picker)
                    dpg.add_input_text(hint=ADD_INPUT_HINT, tag="exclusion_input", width=ADD_INPUT_START_W,
                                      on_enter=True, callback=_add_exclusion)
                    dpg.add_button(label="Add", tag="add_exclusion_btn", width=ADD_BTN_W,
                                   height=ADD_ROW_HEIGHT, callback=_add_exclusion)

            dpg.bind_item_theme("add_exclusion_card", base["card_on"])
            dpg.bind_item_theme("add_exclusion_badge", t["badge"])
            dpg.bind_item_theme("select_folder_btn", base["btn_secondary"])
            dpg.bind_item_theme("add_exclusion_btn", base["btn_start"])
            dpg.bind_item_theme("exclusion_input", t["input"])
            if fonts.get("subheading") is not None:
                dpg.bind_item_font("add_exclusion_title", fonts["subheading"])

            # ---- List header: title + chip ----
            dpg.add_spacer(height=LIST_GAP_ABOVE)
            with dpg.group(horizontal=True):
                dpg.add_text(LIST_TITLE, tag="exclusions_list_title", color=COLORS["text_primary"])
                dpg.add_button(label="0 folders", tag="exclusions_count_chip", height=CHIP_HEIGHT)
            dpg.bind_item_theme("exclusions_count_chip", t["chip"])
            if fonts.get("subheading") is not None:
                dpg.bind_item_font("exclusions_list_title", fonts["subheading"])
            dpg.add_spacer(height=10)

            # ---- List panel: the table scrolls INSIDE this ----
            with dpg.child_window(width=ADD_CARD_START_W, height=LIST_PANEL_START_H, tag="exclusions_container",
                                  no_scrollbar=True, no_scroll_with_mouse=True):
                _build_empty_state(fonts, icons)
            _rebuild_list()

    register_resize("exclusions", _resize_exclusions)