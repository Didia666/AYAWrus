import os
import dearpygui.dearpygui as dpg
from ui.theme import COLORS
from ui.layout import register_resize
from ui.scan_layout import _get_themes
from ui.scan_pipeline import _row_width
from ui.table_style import TABLE_ROW_HEIGHT, TABLE_CELL_MUTED_COLOR, apply_table_font

# scan_threats.py

# ---- Detected Threats panel constants (tune here) ----
THREATS_PANEL_HEIGHT = 420     # fixed; the table scrolls inside
THREATS_TABLE_CHROME = 140     # table height = panel height - this (title + footer + padding). Raise if the footer gets cut off
THREATS_TITLE_GAP = 8
THREATS_FOOTER_GAP = 10
NARROW_BREAKPOINT = 1200       # content width below which the Location column is left out (the full path stays in the File Name tooltip)

# ---- Columns (fixed ones in px INCLUDING cell padding, stretch ones as weights) ----
COL_SELECT_W = 55              # "Select" header at the table font size. Raise if the header clips
COL_EXPLAIN_W = 75             # the "Explain" button
COL_CONF_W = 100               # "Confidence" header. Raise if it clips
COL_VERDICT_W = 125            # keeps the longest verdict readable without crowding
COL_NAME_WEIGHT = 2.0
COL_LOCATION_WEIGHT = 3.0
COL_BEHAVIOR_WEIGHT = 1.5
PANEL_PAD_X = 8                # the panel's own left/right padding
TABLE_SCROLLBAR_W = 16         # room kept for the table's scrollbar
FIXED_COL_EXTRA_PX = 96        # padding the fixed columns add on top of their widths

# ---- Rows ----
ROW_PAD_X = 10                 # table cell padding
ROW_PAD_Y = 8                  # more = taller rows
ROW_ITEM_HEIGHT = TABLE_ROW_HEIGHT   # height of the buttons / text cells inside a row (shared: ui/table_style.py)
PILL_ROUNDING = 13
PILL_BG_ALPHA = 40
PILL_BORDER_ALPHA = 160
ROW_ALT_BG = (255, 255, 255, 10)   # alternating row shade
HEADER_BG = (40, 52, 78)                # lighter than the rows so the header reads as a bar, not a black strip
HEADER_TEXT = COLORS["text_secondary"]  # muted header labels
GUTTER_W = 14                           # empty columns on the far left and right (moves content off the walls)

# ---- Empty state (shown instead of the table when there are no threats) ----
EMPTY_TITLE = "No threats detected"
EMPTY_SUBTITLE = "Nothing suspicious was found in this scan"
EMPTY_TOP_SPACER = 90          # pushes the message down so it sits in the middle of the table area. Raise = lower
EMPTY_TITLE_HEIGHT = 30
EMPTY_SUB_HEIGHT = 24

# ---- Footer ----
FOOTER_BUTTON_HEIGHT = 36
SELECT_BUTTON_WIDTH = 120
QUARANTINE_BUTTON_WIDTH = 190
COUNT_WIDTH = 140

_T = {}
# narrow       = what the window width says right now
# table_narrow = what the CURRENT table was built with (rows must match its columns, so rows read this one)
# rows         = every row handed to add_threat_row, so the table can rebuild itself when the width crosses the breakpoint
_state = {"narrow": False, "table_narrow": False, "chk": {}, "fonts": None, "rows": [], "empty": False,
          "cells": [], "row_w": 900}   # wrapped text cells are resized with the table


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
    """Creates the (empty) table with its header and columns. Rows are added later.
    The Location column only exists when the window is wide enough (show=False is ignored by this DPG build,
    so a narrow table is simply built without it)."""
    t = _themes()
    narrow = _state["narrow"]
    _state["table_narrow"] = narrow
    _state["empty"] = False
    if dpg.does_item_exist("threats_empty"):
        dpg.configure_item("threats_empty", show=False)

    with dpg.table(parent=parent, tag="threats_table", header_row=True, row_background=True,
                   borders_innerH=False, borders_outerH=False,
                   borders_innerV=False, borders_outerV=False,
                   scrollY=True, freeze_rows=1, width=-1,
                   height=THREATS_PANEL_HEIGHT - THREATS_TABLE_CHROME):
        dpg.add_table_column(label="", width_fixed=True, init_width_or_weight=GUTTER_W)
        dpg.add_table_column(label="Select", width_fixed=True, init_width_or_weight=COL_SELECT_W)
        dpg.add_table_column(label="Explain", width_fixed=True, init_width_or_weight=COL_EXPLAIN_W)
        dpg.add_table_column(label="File Name", width_stretch=True, init_width_or_weight=COL_NAME_WEIGHT)
        if not narrow:
            dpg.add_table_column(label="Location", width_stretch=True, init_width_or_weight=COL_LOCATION_WEIGHT)
        dpg.add_table_column(label="Confidence", width_fixed=True, init_width_or_weight=COL_CONF_W)
        dpg.add_table_column(label="Behavior", width_stretch=True, init_width_or_weight=COL_BEHAVIOR_WEIGHT)
        dpg.add_table_column(label="Verdict", width_fixed=True, init_width_or_weight=COL_VERDICT_W)
        dpg.add_table_column(label="", width_fixed=True, init_width_or_weight=GUTTER_W)
    dpg.bind_item_theme("threats_table", t["table"])
    apply_table_font("threats_table", _state["fonts"])   # shared table font; scan.py rebuilds this table, so it re-applies every time


def reset_threat_rows():
    """Forget the old checkboxes and rows (scan.py calls this before it rebuilds the table)."""
    _state["chk"].clear()
    _state["rows"].clear()
    _state["cells"].clear()


def _add_wrapped_cell(label, column, color):
    widths = _cell_widths()
    item = dpg.add_text(label, wrap=max(1, widths[column]), color=color)
    _state["cells"].append((item, column))
    return item


def _percent_cell(value):
    try:
        label = f"{float(value):.1%}"
        color = COLORS["accent_red"]
    except (TypeError, ValueError):
        label = "-"
        color = TABLE_CELL_MUTED_COLOR
    _add_wrapped_cell(label, "confidence", color)


def _humanize_behavior_name(name):
    if not name:
        return "-"
    label = str(name).strip().replace("_", " ").replace("-", " ")
    if label.lower() in {"ransom", "ransomware"}:
        return "Ransomware"
    if label.lower() == "pua":
        return "PUA"
    return label.title()


def _behavior_cell(threat):
    behavior_confidence = threat.get("behavior_confidence")
    behavior_types = threat.get("behavior_types") or []

    if isinstance(behavior_types, str):
        behavior_types = [behavior_types]

    # Only labels that passed their configured thresholds
    # are displayed as predicted behaviors.
    labels = [
        _humanize_behavior_name(item)
        for item in behavior_types
        if item and item != "NO_BEHAVIOR_LABEL_PREDICTED"
    ]

    top_candidate = threat.get("behavior_type")
    top_candidate_score = threat.get("behavior_confidence", 0.0)
    color = COLORS["accent_orange"]
    try:
        score = float(behavior_confidence)
        score_text = f"{score:.0%}"
    except (TypeError, ValueError):
        score_text = ""
        color = TABLE_CELL_MUTED_COLOR

    if labels:
        content = f"{score_text} | {', '.join(labels)}" if score_text else ", ".join(labels)
    else:
        content = "-"
        if top_candidate:
            try:
                candidate_score = float(top_candidate_score)
                content = (
                    f"{_humanize_behavior_name(top_candidate)} "
                    f"(candidate: {candidate_score:.1%})"
                )
            except (TypeError, ValueError):
                pass

    item = _add_wrapped_cell(content, "behavior", color)
    with dpg.tooltip(item):
        dpg.add_text("Behavior Analysis", color=COLORS["text_primary"])
        if score_text:
            dpg.add_text(
                f"Reported Confidence: {score_text}",
                color=COLORS["text_secondary"]
            )
        dpg.add_separator()
        if labels:
            dpg.add_text("Predicted Behaviors:", color=COLORS["text_primary"])
            for label in labels:
                dpg.add_text(f"- {label}", color=COLORS["text_secondary"])
        else:
            dpg.add_text(
                "No behavior type was identified.",
                color=COLORS["text_secondary"]
            )


def _draw_threat_row(table, threat, selected, toggle_cb, explain_cb):
    """Draws one row. The cells must match the columns the table was BUILT with (table_narrow)."""
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

        name_text = _add_wrapped_cell(name, "name", COLORS["text_primary"])
        with dpg.tooltip(name_text):
            dpg.add_text(path, color=COLORS["text_secondary"])   # the full path lives here, so hiding Location loses nothing

        loc_text = None
        if not _state["table_narrow"]:
            loc_text = _add_wrapped_cell(path, "location", TABLE_CELL_MUTED_COLOR)
            with dpg.tooltip(loc_text):
                dpg.add_text(path, color=COLORS["text_secondary"])

        _percent_cell(threat.get("probability"))
        _behavior_cell(threat)

        result = str(threat.get("result", ""))
        verdict_color = (
            COLORS["accent_red"] if result == "MALICIOUS"
            else COLORS["accent_orange"]
        )
        _add_wrapped_cell(result, "verdict", verdict_color)
        dpg.add_spacer(width=1)   # right gutter cell


def _cell_widths():
    """Estimate inner text widths from the current panel width and column stretch weights."""
    fixed = 2 * GUTTER_W + COL_SELECT_W + COL_EXPLAIN_W + COL_CONF_W + COL_VERDICT_W
    table_w = _state["row_w"] - 2 * PANEL_PAD_X - TABLE_SCROLLBAR_W
    avail = max(0, table_w - fixed - FIXED_COL_EXTRA_PX)
    weights = COL_NAME_WEIGHT + COL_BEHAVIOR_WEIGHT
    if not _state["table_narrow"]:
        weights += COL_LOCATION_WEIGHT
    name_w = avail * COL_NAME_WEIGHT / weights - 2 * ROW_PAD_X
    loc_w = avail * COL_LOCATION_WEIGHT / weights - 2 * ROW_PAD_X if not _state["table_narrow"] else 1
    behavior_w = avail * COL_BEHAVIOR_WEIGHT / weights - 2 * ROW_PAD_X
    return {
        "name": int(max(1, name_w)),
        "location": int(max(1, loc_w)),
        "confidence": max(1, COL_CONF_W - 2 * ROW_PAD_X),
        "behavior": int(max(1, behavior_w)),
        "verdict": max(1, COL_VERDICT_W - 2 * ROW_PAD_X),
    }


def _refit_cells():
    widths = _cell_widths()
    for item, column in list(_state["cells"]):
        if dpg.does_item_exist(item):
            dpg.configure_item(item, wrap=widths[column])

def add_threat_row(table, threat, selected, toggle_cb, explain_cb):
    """One row. Callbacks come from scan.py, so the selection / quarantine logic stays there.
    The arguments are remembered (references only) so the table can rebuild itself on a width change."""
    _state["rows"].append((threat, selected, toggle_cb, explain_cb))
    _draw_threat_row(table, threat, selected, toggle_cb, explain_cb)


def add_empty_row(table):
    """Kept under its old name so scan.py needs no change. It no longer adds a fake row:
    it hides the table and shows a centered message instead."""
    _state["empty"] = True
    if dpg.does_item_exist(table):
        dpg.configure_item(table, show=False)
    if dpg.does_item_exist("threats_empty"):
        dpg.configure_item("threats_empty", show=True)


def _build_empty_block():
    """The centered 'No threats detected' message. Hidden until add_empty_row shows it.
    Centered with full-width invisible buttons (same trick as the Exclusions empty state)."""
    base = _get_themes()
    fonts = _state["fonts"] or {}
    with dpg.child_window(tag="threats_empty", show=False, width=-1,
                          height=THREATS_PANEL_HEIGHT - THREATS_TABLE_CHROME, border=False,
                          no_scrollbar=True, no_scroll_with_mouse=True):
        dpg.add_spacer(height=EMPTY_TOP_SPACER)
        dpg.add_button(label=EMPTY_TITLE, width=-1, height=EMPTY_TITLE_HEIGHT, tag="threats_empty_title")
        dpg.add_button(label=EMPTY_SUBTITLE, width=-1, height=EMPTY_SUB_HEIGHT, tag="threats_empty_sub")
    dpg.bind_item_theme("threats_empty_title", base["label_on"])
    dpg.bind_item_theme("threats_empty_sub", base["sub"])
    if fonts.get("subheading") is not None:
        dpg.bind_item_font("threats_empty_title", fonts["subheading"])


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
            _build_empty_block()   # lives next to the table (inside the holder); only the table is deleted on a rebuild

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


def _rebuild_for_width():
    """Rebuilds the table (with or without Location) and re-adds the rows it already had.
    Runs only when the window crosses NARROW_BREAKPOINT, not on every pixel of a drag."""
    if not dpg.does_item_exist("threats_table"):
        return
    rows = list(_state["rows"])
    was_empty = _state["empty"]
    _state["chk"].clear()
    _state["cells"].clear()
    dpg.delete_item("threats_table")
    build_threats_table("threats_table_holder")
    for threat, selected, toggle_cb, explain_cb in rows:
        try:
            _draw_threat_row("threats_table", threat, selected, toggle_cb, explain_cb)
        except Exception:
            import traceback
            traceback.print_exc()
    if was_empty and not rows:
        add_empty_row("threats_table")


def _apply_narrow(narrow):
    if narrow == _state["narrow"]:
        return
    _state["narrow"] = narrow
    _rebuild_for_width()


def _resize_threats(content_w, content_h):
    """Called by ui/layout.py whenever the window size changes."""
    row_w = _row_width(content_w)
    if dpg.does_item_exist("threats_container"):
        dpg.configure_item("threats_container", width=row_w, height=THREATS_PANEL_HEIGHT)
    if dpg.does_item_exist("threats_table"):
        dpg.configure_item("threats_table", height=THREATS_PANEL_HEIGHT - THREATS_TABLE_CHROME)
    _state["row_w"] = row_w
    _apply_narrow(content_w < NARROW_BREAKPOINT)
    _refit_cells()