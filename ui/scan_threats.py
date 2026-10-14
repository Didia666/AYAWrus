import os
import dearpygui.dearpygui as dpg
from ui.theme import COLORS
from ui.layout import register_resize
from ui.scan_layout import _get_themes
from ui.scan_pipeline import _row_width
from ui.table_style import TABLE_ROW_HEIGHT, TABLE_PILL_HEIGHT, TABLE_CELL_MUTED_COLOR, apply_table_font

# scan_threats.py

# ---- Detected Threats panel constants (tune here) ----
THREATS_PANEL_HEIGHT = 420     # fixed; the table scrolls inside
THREATS_TABLE_CHROME = 140     # table height = panel height - this (title + footer + padding). Raise if the footer gets cut off
THREATS_TITLE_GAP = 8
THREATS_FOOTER_GAP = 10
NARROW_BREAKPOINT = 1100       # content width below which the Location column hides (about a 1360px window)

# ---- Columns (fixed ones in px, stretch ones as weights) ----
COL_SELECT_W = 80              # widened for the bigger table font (the "Select" header would clip at 64)
COL_EXPLAIN_W = 110
COL_CONF_W = 150               # "Confidence" header needs room at the table font size
COL_BEHAVIOR_W = 220           # include the behavioral score plus the inferred behavior label
COL_TYPE_W = 180               # retired: the type is folded into the behavior cell
COL_NAME_WEIGHT = 2.0
COL_LOCATION_WEIGHT = 3.0

# ---- Rows ----
ROW_PAD_X = 10                 # table cell padding
ROW_PAD_Y = 8                  # more = taller rows
ROW_ITEM_HEIGHT = TABLE_ROW_HEIGHT   # height of the buttons / text cells inside a row (shared: ui/table_style.py)
PILL_HEIGHT = TABLE_PILL_HEIGHT      # shared: ui/table_style.py
PILL_ROUNDING = 13
PILL_BG_ALPHA = 40
PILL_BORDER_ALPHA = 160
ROW_ALT_BG = (255, 255, 255, 10)   # alternating row shade
HEADER_BG = (40, 52, 78)                # lighter than the rows so the header reads as a bar, not a black strip
HEADER_TEXT = COLORS["text_secondary"]  # muted header labels
GUTTER_W = 14                           # empty columns on the far left and right (moves content off the walls)

# ---- Footer ----
FOOTER_BUTTON_HEIGHT = 36
SELECT_BUTTON_WIDTH = 130
QUARANTINE_BUTTON_WIDTH = 200
COUNT_WIDTH = 140

_T = {}
_state = {"narrow": False, "chk": {}, "fonts": None}


# ---------------------------------------------------------------------------
# Themes (built once)
# ---------------------------------------------------------------------------

def _flat_button_theme(color):
    """Invisible, left-aligned button: shows only text, centered vertically, never reacts."""
    with dpg.theme() as theme:
        with dpg.theme_component(dpg.mvButton):
            dpg.add_theme_color(dpg.mvThemeCol_Button, (0, 0, 0, 0))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (0, 0, 0, 0))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (0, 0, 0, 0))
            dpg.add_theme_color(dpg.mvThemeCol_Text, color)
            dpg.add_theme_color(dpg.mvThemeCol_Border, (0, 0, 0, 0))
            dpg.add_theme_style(dpg.mvStyleVar_FrameBorderSize, 0)
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 0, 0)
            dpg.add_theme_style(dpg.mvStyleVar_ButtonTextAlign, 0.0, 0.5)
    return theme


def _pill_theme(color):
    bg = (*color, PILL_BG_ALPHA)
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
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 0, 0)
    return theme


def _table_theme():
    with dpg.theme() as theme:
        with dpg.theme_component(dpg.mvTable):
            dpg.add_theme_color(dpg.mvThemeCol_TableHeaderBg, HEADER_BG)
            dpg.add_theme_color(dpg.mvThemeCol_Text, HEADER_TEXT)
            dpg.add_theme_color(dpg.mvThemeCol_TableBorderStrong, COLORS["border"])
            dpg.add_theme_color(dpg.mvThemeCol_TableBorderLight, COLORS["border"])
            dpg.add_theme_color(dpg.mvThemeCol_TableRowBg, (0, 0, 0, 0))
            dpg.add_theme_color(dpg.mvThemeCol_TableRowBgAlt, ROW_ALT_BG)
            dpg.add_theme_style(dpg.mvStyleVar_CellPadding, ROW_PAD_X, ROW_PAD_Y)
    return theme


def _themes():
    if _T:
        return _T
    _T["name"] = _flat_button_theme(COLORS["text_primary"])
    _T["path"] = _flat_button_theme(TABLE_CELL_MUTED_COLOR)   # location text: lighter grey (shared: ui/table_style.py)
    _T["conf"] = _flat_button_theme(COLORS["accent_red"])
    _T["behavior"] = _flat_button_theme(COLORS["accent_orange"])
    _T["dash"] = _flat_button_theme(TABLE_CELL_MUTED_COLOR)   # "-" cells and the "N selected" counter
    _T["pill_MALICIOUS"] = _pill_theme(COLORS["accent_red"])
    _T["pill_SUSPICIOUS"] = _pill_theme(COLORS["accent_orange"])
    _T["table"] = _table_theme()
    return _T


# ---------------------------------------------------------------------------
# Table
# ---------------------------------------------------------------------------

def build_threats_table(parent):
    """Creates the (empty) table with its header and columns. Rows are added later."""
    t = _themes()
    with dpg.table(parent=parent, tag="threats_table", header_row=True, row_background=True,
                   borders_innerH=False, borders_outerH=False,
                   borders_innerV=False, borders_outerV=False,
                   scrollY=True, freeze_rows=1, width=-1,
                   height=THREATS_PANEL_HEIGHT - THREATS_TABLE_CHROME):
        dpg.add_table_column(label="", width_fixed=True, init_width_or_weight=GUTTER_W)
        dpg.add_table_column(label="Select", width_fixed=True, init_width_or_weight=COL_SELECT_W)
        dpg.add_table_column(label="Explain", width_fixed=True, init_width_or_weight=COL_EXPLAIN_W)
        dpg.add_table_column(label="File Name", width_stretch=True, init_width_or_weight=COL_NAME_WEIGHT)
        dpg.add_table_column(label="Location", width_stretch=True, init_width_or_weight=COL_LOCATION_WEIGHT,
                             tag="threat_col_location", show=not _state["narrow"])
        dpg.add_table_column(label="Confidence", width_fixed=True, init_width_or_weight=COL_CONF_W)
        dpg.add_table_column(label="Behavior", width_fixed=True, init_width_or_weight=COL_BEHAVIOR_W)
        dpg.add_table_column(label="", width_fixed=True, init_width_or_weight=GUTTER_W)
    dpg.bind_item_theme("threats_table", t["table"])
    apply_table_font("threats_table", _state["fonts"])   # shared table font; scan.py rebuilds this table, so it re-applies every time


def reset_threat_rows():
    """Forget the old checkboxes (call before the table is rebuilt)."""
    _state["chk"].clear()


def _percent_button(value, theme_key):
    t = _themes()
    try:
        label = f"{float(value):.1%}"
        key = theme_key
    except (TypeError, ValueError):
        label = "-"
        key = "dash"
    btn = dpg.add_button(label=label, width=-1, height=ROW_ITEM_HEIGHT)
    dpg.bind_item_theme(btn, t[key])


def _humanize_behavior_name(name):
    if not name:
        return "-"
    label = str(name).strip().replace("_", " ").replace("-", " ")
    if label.lower() in {"ransom", "ransomware"}:
        return "Ransomware"
    if label.lower() == "pua":
        return "PUA"
    return label.title()


def _format_behavior_type(threat):
    behavior_types = threat.get("behavior_types") or []
    if isinstance(behavior_types, str):
        return behavior_types
    if behavior_types:
        labels = [_humanize_behavior_name(item) for item in behavior_types if item]
        return ", ".join(labels)
    behavior_type = threat.get("behavior_type")
    return _humanize_behavior_name(behavior_type) if behavior_type else "-"


def _behavior_score_button(threat):
    t = _themes()
    behavior_confidence = threat.get("behavior_confidence")
    behavior_label = _format_behavior_type(threat)

    try:
        score = float(behavior_confidence)
        label = f"{score:.1%} - {behavior_label}"
        key = "behavior"
    except (TypeError, ValueError):
        label = "-"
        key = "dash"

    btn = dpg.add_button(label=label, width=-1, height=ROW_ITEM_HEIGHT)
    dpg.bind_item_theme(btn, t[key])
    if behavior_label != "-":
        with dpg.tooltip(btn):
            dpg.add_text(threat.get("behavior_result", ""), color=COLORS["text_secondary"])
    return btn


def add_threat_row(table, threat, selected, toggle_cb, explain_cb):
    """One row. Callbacks come from scan.py, so the selection / quarantine logic stays there."""
    t = _themes()
    base = _get_themes()
    path = threat.get("file_path", "")
    name = os.path.basename(path) or path

    with dpg.table_row(parent=table):
        dpg.add_spacer(width=1)   # left gutter cell
        chk = dpg.add_checkbox(default_value=path in selected, callback=toggle_cb, user_data=path)
        _state["chk"][path] = chk

        explain = dpg.add_button(label="Explain", width=-1, height=ROW_ITEM_HEIGHT,
                                 callback=explain_cb, user_data=threat)
        dpg.bind_item_theme(explain, base["btn_secondary"])

        name_btn = dpg.add_button(label=name, width=-1, height=ROW_ITEM_HEIGHT)
        dpg.bind_item_theme(name_btn, t["name"])
        with dpg.tooltip(name_btn):
            dpg.add_text(path, color=COLORS["text_secondary"])

        loc_btn = dpg.add_button(label=path, width=-1, height=ROW_ITEM_HEIGHT)
        dpg.bind_item_theme(loc_btn, t["path"])

        _percent_button(threat.get("probability"), "conf")
        _behavior_score_button(threat)

        result = str(threat.get("result", ""))
        pill = dpg.add_button(label=result, width=-1, height=PILL_HEIGHT)
        dpg.bind_item_theme(pill, t.get(f"pill_{result}", t["pill_SUSPICIOUS"]))
        dpg.add_spacer(width=1)   # right gutter cell


def add_empty_row(table):
    with dpg.table_row(parent=table):
        dpg.add_text("")
        dpg.add_text("")
        dpg.add_text("")
        dpg.add_text("No threats detected", color=COLORS["text_secondary"])
        for _ in range(5):
            dpg.add_text("")


# ---------------------------------------------------------------------------
# Selection UI (the selection itself lives in scan.py)
# ---------------------------------------------------------------------------

def update_selection_ui(count, total):
    if dpg.does_item_exist("threat_selected_count"):
        dpg.set_item_label("threat_selected_count", f"{count} selected")
    if dpg.does_item_exist("select_all_btn"):
        all_on = total > 0 and count >= total
        dpg.set_item_label("select_all_btn", "Clear" if all_on else "Select All")


def apply_selection(selected, total):
    """Ticks / unticks every row that exists, then refreshes the counter and button."""
    for path, tag in list(_state["chk"].items()):
        if dpg.does_item_exist(tag):
            dpg.set_value(tag, path in selected)
    update_selection_ui(len(selected), total)


# ---------------------------------------------------------------------------
# Panel + resize
# ---------------------------------------------------------------------------

def build_threats_panel(fonts, quarantine_cb, select_all_cb):
    """The hidden 'Detected Threats' panel. Call it where the old threats_container block was."""
    t = _themes()
    base = _get_themes()
    _state["fonts"] = fonts   # build_threats_table reads it (scan.py rebuilds the table without passing fonts)
    with dpg.child_window(width=900, height=THREATS_PANEL_HEIGHT, tag="threats_container", show=False,
                          no_scrollbar=True, no_scroll_with_mouse=True):
        title = dpg.add_text("Detected Threats", color=COLORS["text_primary"])
        if fonts and fonts.get("heading") is not None:
            dpg.bind_item_font(title, fonts["heading"])
        dpg.add_spacer(height=THREATS_TITLE_GAP)

        with dpg.group(tag="threats_table_holder"):
            pass

        dpg.add_spacer(height=THREATS_FOOTER_GAP)
        with dpg.group(horizontal=True, tag="threats_footer"):
            dpg.add_button(label="Select All", tag="select_all_btn", width=SELECT_BUTTON_WIDTH,
                           height=FOOTER_BUTTON_HEIGHT, callback=select_all_cb)
            dpg.add_button(label="Quarantine Selected", tag="quarantine_btn", width=QUARANTINE_BUTTON_WIDTH,
                           height=FOOTER_BUTTON_HEIGHT, callback=quarantine_cb)
            dpg.add_button(label="0 selected", tag="threat_selected_count", width=COUNT_WIDTH,
                           height=FOOTER_BUTTON_HEIGHT)

    dpg.bind_item_theme("select_all_btn", base["btn_secondary"])
    dpg.bind_item_theme("quarantine_btn", base["btn_start"])
    dpg.bind_item_theme("threat_selected_count", t["dash"])

    build_threats_table("threats_table_holder")
    register_resize("scan_threats", _resize_threats)


def _apply_narrow(narrow):
    _state["narrow"] = narrow
    if dpg.does_item_exist("threat_col_location"):
        dpg.configure_item("threat_col_location", show=not narrow)


def _resize_threats(content_w, content_h):
    """Called by ui/layout.py whenever the window size changes."""
    row_w = _row_width(content_w)
    if dpg.does_item_exist("threats_container"):
        dpg.configure_item("threats_container", width=row_w, height=THREATS_PANEL_HEIGHT)
    if dpg.does_item_exist("threats_table"):
        dpg.configure_item("threats_table", height=THREATS_PANEL_HEIGHT - THREATS_TABLE_CHROME)
    _apply_narrow(content_w < NARROW_BREAKPOINT)