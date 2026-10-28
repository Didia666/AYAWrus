"""
scan_targets.py - the "Likely Targets" tab inside the Explain popup.
UI SKELETON ONLY: no backend, no threads, no model calls. Fake data lives in ui/scan_targets_mock.py.

=====================================================================================
BACKEND HOOKS (for Diane / Kitchi): you do NOT edit the UI code in this folder.
You only call these 3 functions from this file:

  1. register_backend_handlers(on_open=fn(file_path), on_rescan=fn(file_path))
       Call once at startup.
       on_open   -> we call it ONCE per file, the first time the user opens the "Likely Targets" tab.
                    Start your heavy analysis here (the UI never blocks on it).
       on_rescan -> we call it when the user presses Rescan. Re-run the analysis.

  2. set_likely_targets_data(data_dict, file_path=None)
       Call this with the JSON below whenever you have something to show:
       first with "state": "loading" (+ categories, so the chips appear),
       then again with "state": "done" (+ files). Same function for partial / error / etc.
       Must run on the UI thread (a DPG callback). From a worker thread, wrap it:
           with dpg.mutex():
               set_likely_targets_data(data)
       file_path=None means "the file whose Explain popup is open right now".

  3. That's it. The UI re-draws itself from the dict. No other UI changes needed.

JSON the UI reads (every widget below has a  # JSON: <field>  comment):
{
  "sample": "suspicious.exe",           # file name
  "state": "done",                      # loading | done | partial | cancelled | error | unsupported
  "message": "optional banner text",    # OPTIONAL: overrides the default text for partial/cancelled/error/unsupported
  "scan_complete": true,
  "files_scanned": 52340,
  "files_skipped_permission": 87,
  "at_risk_count": 142,
  "last_scanned": "06:53",              # HH:MM, shown next to Rescan
  "categories": {                       # drives the chips AND the category headers
    "documents": {"score": 0.92, "source": "rule+model", "count": 98}   # "count" is NEW (shown as "documents (98 files)")
  },
  "flagged": ["documents", "images"],   # chips in this list are red, the rest are grey
  "by_folder": {"C:\\\\Users\\\\Kay\\\\Documents": 98},   # folder -> total at-risk files (shown inside the folder node)
  "files": [                            # the UI sorts these (risk, then score) and groups them (category, then folder)
    {"path": "...", "category": "documents", "risk": "high",   # high | medium | low
     "score": 0.93, "reason": "..."}
  ]
}
=====================================================================================
"""
import ntpath
import traceback
import dearpygui.dearpygui as dpg
from ui.theme import COLORS
from ui.table_style import TABLE_PILL_HEIGHT, apply_table_font

# scan_targets.py

# ---- Dev switch (set False before shipping; the mock file is then never even imported) ----
DEV_MODE = False                  # shows the mock-state dropdown + loads a mock when no real data exists
DEV_DEFAULT_MOCK = "Scary sample"

# ---- List behavior ----
PAGE_SIZE = 50                   # rows created per folder before "Show more" (keeps DPG from making thousands of widgets)

# ---- Sizes (tune here) ----
CHIPS_PER_ROW = 4
CHIP_HEIGHT = 30
CHIP_PAD_X = 14
RISK_COL_W = 84                  # width of the risk pill column
ROW_BUTTON_H = TABLE_PILL_HEIGHT # file row height (matches the pill so text lines up)
BANNER_H = 40
RESCAN_W = 100
RESCAN_H = 30
NOTE_ICON_SIZE = 16
EMPTY_ICON_SIZE = 40
EMPTY_TOP_PAD = 12
DEV_COMBO_W = 220
FOOTER_MAIN_FONT = "table"        # "Last scanned" line (fonts.py keys: body 18 / table 20 / subheading 20 bold / heading 26)
FOOTER_STATS_FONT = "table"       # the "52,340 files scanned | ..." line

# ---- Category header style (the "documents (222 files)" bars) ----
HEADER_FONT = "subheading"       # fonts.py key for the category name
HEADER_PAD_X = 12                # inner padding, makes the bar taller/roomier
HEADER_PAD_Y = 8
HEADER_ROUNDING = 8
HEADER_TINT_ALPHA = 28           # background tint (0-255)
HEADER_HOVER_ALPHA = 55
HEADER_ACTIVE_ALPHA = 75
HEADER_BORDER_ALPHA = 150
HEADER_GAP = 6                   # space under each category bar

# ---- Folder row style (the rows inside a category) ----
FOLDER_FONT = "body"             # needed so folders don't inherit the bigger header font
FOLDER_PAD_X = 8
FOLDER_PAD_Y = 5
FOLDER_ROUNDING = 6
FOLDER_HOVER = (255, 255, 255, 18)
FOLDER_ACTIVE = (255, 255, 255, 28)

# ---- Colors ----
RISK_LOW_COLOR = (234, 179, 8)   # yellow (theme.py has no yellow)
ROW_HOVER = (255, 255, 255, 14)
MUTED = COLORS["text_secondary"]

RISK_ORDER = {"high": 0, "medium": 1, "low": 2}   # sort order, highest risk first

# ---- Default texts per state (data["message"] overrides these) ----
STATE_MESSAGES = {
    "partial": "Partial results: scan limit reached",
    "cancelled": "Scan cancelled: showing what was found so far",
    "error": "Something went wrong, showing saved results only",
    "unsupported": "Detailed analysis only works for .exe/.dll right now",
}
BANNER_STATES = {"partial": "orange", "cancelled": "orange", "error": "red"}   # state -> banner color name

# ---- Tags ----
PAGE = "tgt_page"
BANNER = "tgt_banner"
CHIPS = "tgt_chips"
LIST = "tgt_list"
FOOTER = "tgt_footer"

_S = {"fonts": {}, "path": None, "opened": False, "dirty": True}
_DATA = {}                       # file_path -> latest data dict for that file
_STARTED = set()                 # files whose analysis was already requested (so flipping tabs doesn't re-trigger)
_HANDLERS = {"on_open": None, "on_rescan": None}
_T = {}


# =====================================================================================
# PUBLIC HOOKS (see the big comment at the top of this file)
# =====================================================================================

def register_backend_handlers(on_open=None, on_rescan=None):
    """HOOK 1: backend registers what should run when the tab opens / Rescan is pressed."""
    _HANDLERS["on_open"] = on_open
    _HANDLERS["on_rescan"] = on_rescan


def set_likely_targets_data(data, file_path=None):
    """HOOK 2: backend hands the UI a data dict (shape documented at the top). UI re-draws from it."""
    path = file_path or _S["path"]
    if path is None:
        return
    _DATA[path] = data
    if path == _S["path"] and dpg.does_item_exist(PAGE):
        if _S["opened"]:
            _render()
        else:
            _S["dirty"] = True      # tab not opened yet, draw it when it is


def on_targets_tab_opened(file_path):
    """Called by scan_explain.py when the user clicks the Likely Targets tab (NOT when Explain opens)."""
    _S["opened"] = True
    if _S["dirty"] and dpg.does_item_exist(PAGE):
        _render()
    if not file_path or file_path in _STARTED:
        return
    _STARTED.add(file_path)         # once per file, even if the user flips tabs
    _call_handler("on_open", file_path)


def _call_handler(name, file_path):
    fn = _HANDLERS.get(name)
    if fn is None:
        return
    try:
        fn(file_path)
    except Exception:
        traceback.print_exc()


# =====================================================================================
# Themes (built once)
# =====================================================================================

def _pill_theme(color, pad_x=0):
    with dpg.theme() as th:
        with dpg.theme_component(dpg.mvButton):
            for col in (dpg.mvThemeCol_Button, dpg.mvThemeCol_ButtonHovered, dpg.mvThemeCol_ButtonActive):
                dpg.add_theme_color(col, (*color, 40))
            dpg.add_theme_color(dpg.mvThemeCol_Text, color)
            dpg.add_theme_color(dpg.mvThemeCol_Border, (*color, 160))
            dpg.add_theme_style(dpg.mvStyleVar_FrameBorderSize, 1)
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 9)
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding, pad_x, 0)
    return th


def _flat_theme(text_color, pad_x=8):
    with dpg.theme() as th:
        with dpg.theme_component(dpg.mvButton):
            dpg.add_theme_color(dpg.mvThemeCol_Button, (0, 0, 0, 0))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, ROW_HOVER)
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, ROW_HOVER)
            dpg.add_theme_color(dpg.mvThemeCol_Text, text_color)
            dpg.add_theme_style(dpg.mvStyleVar_FrameBorderSize, 0)
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 6)
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding, pad_x, 0)
            dpg.add_theme_style(dpg.mvStyleVar_ButtonTextAlign, 0.0, 0.5)
    return th


def _banner_theme(color):
    with dpg.theme() as th:
        with dpg.theme_component(dpg.mvChildWindow):
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, (*color, 28))
            dpg.add_theme_color(dpg.mvThemeCol_Border, (*color, 150))
            dpg.add_theme_style(dpg.mvStyleVar_ChildRounding, 8)
            dpg.add_theme_style(dpg.mvStyleVar_ChildBorderSize, 1)
            dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 12, 8)
    return th


def _header_theme(color):
    """Category bar: flagged categories get the red tint + border (matches their chip), others stay grey."""
    with dpg.theme() as th:
        with dpg.theme_component(dpg.mvCollapsingHeader):
            dpg.add_theme_color(dpg.mvThemeCol_Header, (*color, HEADER_TINT_ALPHA))
            dpg.add_theme_color(dpg.mvThemeCol_HeaderHovered, (*color, HEADER_HOVER_ALPHA))
            dpg.add_theme_color(dpg.mvThemeCol_HeaderActive, (*color, HEADER_ACTIVE_ALPHA))
            dpg.add_theme_color(dpg.mvThemeCol_Border, (*color, HEADER_BORDER_ALPHA))
            dpg.add_theme_style(dpg.mvStyleVar_FrameBorderSize, 1)
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, HEADER_ROUNDING)
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding, HEADER_PAD_X, HEADER_PAD_Y)
    return th


def _folder_theme():
    """Folder rows: no bar, just a soft highlight on hover + a bit more breathing room."""
    with dpg.theme() as th:
        with dpg.theme_component(dpg.mvTreeNode):
            dpg.add_theme_color(dpg.mvThemeCol_HeaderHovered, FOLDER_HOVER)
            dpg.add_theme_color(dpg.mvThemeCol_HeaderActive, FOLDER_ACTIVE)
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, FOLDER_ROUNDING)
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding, FOLDER_PAD_X, FOLDER_PAD_Y)
    return th


def _themes():
    if _T:
        return _T
    c = COLORS
    _T["risk_high"] = _pill_theme(c["accent_red"])
    _T["risk_medium"] = _pill_theme(c["accent_orange"])
    _T["risk_low"] = _pill_theme(RISK_LOW_COLOR)
    _T["chip_flagged"] = _pill_theme(c["accent_red"], CHIP_PAD_X)
    _T["chip_quiet"] = _pill_theme(MUTED, CHIP_PAD_X)
    _T["rescan"] = _pill_theme(c["accent_blue"])
    _T["row"] = _flat_theme(c["text_primary"])
    _T["more"] = _flat_theme(c["accent_blue"])
    _T["banner_orange"] = _banner_theme(c["accent_orange"])
    _T["banner_red"] = _banner_theme(c["accent_red"])
    _T["header_flagged"] = _header_theme(c["accent_red"])
    _T["header_quiet"] = _header_theme(MUTED)
    _T["folder"] = _folder_theme()
    return _T


def _font(item, key):
    f = _S["fonts"].get(key)
    if f is not None:
        dpg.bind_item_font(item, f)


# =====================================================================================
# Page skeleton (static parts, built once when Explain opens; cheap)
# =====================================================================================

def build_likely_targets_page(threat, fonts):
    """Called by scan_explain.py inside the page group for this tab. Only builds empty containers;
    the real content is drawn the first time the tab is opened."""
    _S["fonts"] = fonts or {}
    _S["path"] = (threat or {}).get("file_path")
    _S["opened"] = False
    _S["dirty"] = True
    _themes()
    _ensure_dev_default()

    with dpg.group(tag=PAGE):
        if DEV_MODE:
            _build_dev_row()
        _build_note()
        dpg.add_spacer(height=4)
        dpg.add_group(tag=BANNER)          # filled by _render_banner
        dpg.add_group(tag=CHIPS)           # filled by _render_chips
        dpg.add_spacer(height=4)
        dpg.add_group(tag=LIST)            # filled by _render_list / spinner / empty state
        dpg.add_spacer(height=4)
        dpg.add_separator()
        dpg.add_group(tag=FOOTER)          # filled by _render_footer


def _build_note():
    # always visible, small. Static text, no JSON field.
    with dpg.group(horizontal=True):
        if dpg.does_item_exist("tex_triangle_alert"):
            dpg.add_image("tex_triangle_alert", width=NOTE_ICON_SIZE, height=NOTE_ICON_SIZE,
                          tint_color=COLORS["accent_orange"])
        t = dpg.add_text("Predictions, not confirmed damage", color=MUTED)
        _font(t, "mono_small")


# ---- dev only ----

def _ensure_dev_default():
    if DEV_MODE and _S["path"] not in _DATA:
        from ui.scan_targets_mock import get_mock
        _DATA[_S["path"]] = get_mock(DEV_DEFAULT_MOCK)


def _build_dev_row():
    from ui.scan_targets_mock import MOCKS
    with dpg.group(horizontal=True):
        t = dpg.add_text("DEV  mock state:", color=COLORS["accent_orange"])
        _font(t, "mono_small")
        dpg.add_combo(items=list(MOCKS.keys()), default_value=DEV_DEFAULT_MOCK,
                      width=DEV_COMBO_W, callback=_on_mock_pick)
    dpg.add_spacer(height=2)


def _on_mock_pick(sender, app_data):
    from ui.scan_targets_mock import get_mock
    set_likely_targets_data(get_mock(app_data), _S["path"])


# =====================================================================================
# Rendering (everything below reads the data dict)
# =====================================================================================

def _render():
    _S["dirty"] = False
    for tag in (BANNER, CHIPS, LIST, FOOTER):
        if dpg.does_item_exist(tag):
            dpg.delete_item(tag, children_only=True)
    data = _DATA.get(_S["path"])
    if not data:
        dpg.add_text("Waiting for analysis...", parent=LIST, color=MUTED)
        return
    try:
        state = str(data.get("state", "done")).lower()            # JSON: state
        message = data.get("message")                              # JSON: message (optional)
        _render_banner(state, message)
        if state != "unsupported":
            _render_chips(data)
        _render_list_area(state, data, message)
        _render_footer(state, data)
    except Exception:
        traceback.print_exc()
        dpg.add_text("Couldn't display these results (unexpected data).", parent=LIST,
                     color=COLORS["accent_red"])


def _render_banner(state, message):
    kind = BANNER_STATES.get(state)
    if kind is None:
        return
    color = COLORS["accent_orange"] if kind == "orange" else COLORS["accent_red"]
    with dpg.child_window(parent=BANNER, width=-1, height=BANNER_H, border=True,
                          no_scrollbar=True) as box:
        dpg.add_text(message or STATE_MESSAGES[state], color=color)     # JSON: message / state
    dpg.bind_item_theme(box, _T["banner_" + kind])
    dpg.add_spacer(height=4, parent=BANNER)


def _render_chips(data):
    cats = data.get("categories") or {}                  # JSON: categories
    if not cats:
        return
    flagged = set(data.get("flagged") or [])             # JSON: flagged
    ordered = sorted(cats.items(), key=lambda kv: -_to_float((kv[1] or {}).get("score")))
    for start in range(0, len(ordered), CHIPS_PER_ROW):
        with dpg.group(horizontal=True, parent=CHIPS):
            for name, info in ordered[start:start + CHIPS_PER_ROW]:
                info = info or {}
                pct = round(_to_float(info.get("score")) * 100)            # JSON: categories.<name>.score
                chip = dpg.add_button(label=f"{name} {pct}%", height=CHIP_HEIGHT)
                dpg.bind_item_theme(chip, _T["chip_flagged" if name in flagged else "chip_quiet"])
                with dpg.tooltip(chip):
                    dpg.add_text(f"source: {info.get('source', '-')}")     # JSON: categories.<name>.source
    dpg.add_spacer(height=4, parent=CHIPS)


def _render_list_area(state, data, message):
    files = data.get("files") or []                      # JSON: files
    if state == "loading":
        # JSON: state == "loading" -> chips stay, only this area shows the spinner
        with dpg.group(horizontal=True, parent=LIST):
            dpg.add_loading_indicator(circle_count=8, radius=3.0, color=COLORS["accent_blue"])
            dpg.add_text("Checking this PC for at-risk files...", color=MUTED)
    elif state == "unsupported":
        _empty_state("file_x", MUTED, message or STATE_MESSAGES["unsupported"],
                     "Try an .exe or .dll file.")
    elif files:
        with dpg.group(parent=LIST):
            _render_list(data)
    elif state == "done":
        _empty_state("circle_check", COLORS["accent_green"], "No file-targeting behavior found",
                     "Nothing in this file suggests it goes after your documents, images or other personal files.")
    else:
        dpg.add_text("No at-risk files found so far.", parent=LIST, color=MUTED)


def _empty_state(icon_key, color, title, sub=""):
    with dpg.group(parent=LIST):
        dpg.add_spacer(height=EMPTY_TOP_PAD)
        tex = f"tex_{icon_key}"
        if dpg.does_item_exist(tex):
            dpg.add_image(tex, width=EMPTY_ICON_SIZE, height=EMPTY_ICON_SIZE, tint_color=color)
        head = dpg.add_text(title, color=COLORS["text_primary"])
        _font(head, "subheading")
        if sub:
            dpg.add_text(sub, wrap=0, color=MUTED)


def _render_list(data):
    categories = data.get("categories") or {}            # JSON: categories
    folder_totals = data.get("by_folder") or {}          # JSON: by_folder
    files = sorted(data.get("files") or [], key=_sort_key)   # JSON: files (risk first, then score)

    grouped = {}                                         # category -> folder -> [files]
    for f in files:
        cat = str(f.get("category", "other"))            # JSON: files[].category
        folder = ntpath.dirname(str(f.get("path", "")))  # JSON: files[].path (folder part)
        grouped.setdefault(cat, {}).setdefault(folder, []).append(f)

    flagged = set(data.get("flagged") or [])             # JSON: flagged (tints the header like its chip)
    for cat in sorted(grouped, key=lambda c: -_to_float((categories.get(c) or {}).get("score"))):
        shown_total = sum(len(v) for v in grouped[cat].values())
        count = (categories.get(cat) or {}).get("count", shown_total)       # JSON: categories.<name>.count
        with dpg.collapsing_header(label=f"{cat} ({count} files)", default_open=False) as header:
            for folder, rows in grouped[cat].items():
                _build_folder(folder, rows, folder_totals.get(folder))
        dpg.bind_item_theme(header, _T["header_flagged" if cat in flagged else "header_quiet"])
        _font(header, HEADER_FONT)
        dpg.add_spacer(height=HEADER_GAP)


def _build_folder(folder, rows, folder_total):
    leaf = ntpath.basename(folder) or folder
    with dpg.tree_node(label=f"{leaf} ({len(rows)})", default_open=False) as node:
        dpg.bind_item_theme(node, _T["folder"])
        _font(node, FOLDER_FONT)
        # full folder path (JSON: files[].path) + true total (JSON: by_folder)
        extra = f"   |   {folder_total} at-risk in total" if folder_total and folder_total != len(rows) else ""
        t = dpg.add_text(folder + extra, wrap=0, color=MUTED)
        _font(t, "mono_small")

        state = {"files": rows, "shown": 0, "table": None, "button": None}
        with dpg.table(header_row=False, policy=dpg.mvTable_SizingStretchProp) as tbl:
            dpg.add_table_column(width_fixed=True, init_width_or_weight=RISK_COL_W)
            dpg.add_table_column()
        apply_table_font(tbl, _S["fonts"])
        state["table"] = tbl
        _add_rows(state)
        if state["shown"] < len(rows):
            btn = dpg.add_button(label="", callback=_show_more, user_data=state)
            dpg.bind_item_theme(btn, _T["more"])
            state["button"] = btn
            dpg.set_item_label(btn, f"Show more ({len(rows) - state['shown']} left)")


def _add_rows(state):
    start = state["shown"]
    end = min(start + PAGE_SIZE, len(state["files"]))
    for f in state["files"][start:end]:
        _add_file_row(state["table"], f)
    state["shown"] = end


def _show_more(sender, app_data, state):
    _add_rows(state)
    left = len(state["files"]) - state["shown"]
    if left <= 0:
        dpg.delete_item(state["button"])
    else:
        dpg.set_item_label(state["button"], f"Show more ({left} left)")


def _add_file_row(table, f):
    risk = str(f.get("risk", "low")).lower()                 # JSON: files[].risk
    path = str(f.get("path", ""))                             # JSON: files[].path
    name = ntpath.basename(path) or path
    reason = str(f.get("reason") or "No reason provided")     # JSON: files[].reason
    score = f.get("score")                                    # JSON: files[].score
    reason_text = reason if score is None else f"{reason}   (score {_to_float(score):.2f})"
    reason_id = dpg.generate_uuid()

    with dpg.table_row(parent=table):
        pill = dpg.add_button(label=risk, width=-1, height=ROW_BUTTON_H)
        dpg.bind_item_theme(pill, _T.get("risk_" + risk, _T["risk_low"]))
        with dpg.group():
            btn = dpg.add_button(label=name, width=-1, height=ROW_BUTTON_H,
                                 callback=_toggle_reason, user_data=reason_id)
            dpg.bind_item_theme(btn, _T["row"])
            with dpg.tooltip(btn):
                dpg.add_text(path)
            dpg.add_text(reason_text, tag=reason_id, wrap=0, show=False, color=MUTED)


def _toggle_reason(sender, app_data, reason_id):
    if dpg.does_item_exist(reason_id):
        dpg.configure_item(reason_id, show=not dpg.is_item_shown(reason_id))


def _render_footer(state, data):
    last = data.get("last_scanned")                           # JSON: last_scanned
    parts = []
    if data.get("files_scanned") is not None:                 # JSON: files_scanned
        parts.append(f"{int(_to_float(data['files_scanned'])):,} files scanned")
    if data.get("files_skipped_permission"):                  # JSON: files_skipped_permission
        parts.append(f"{int(_to_float(data['files_skipped_permission']))} skipped (no permission)")
    if data.get("at_risk_count") is not None:                 # JSON: at_risk_count
        parts.append(f"{int(_to_float(data['at_risk_count']))} at risk")

    with dpg.table(parent=FOOTER, header_row=False, policy=dpg.mvTable_SizingStretchProp):
        dpg.add_table_column()
        dpg.add_table_column(width_fixed=True, init_width_or_weight=RESCAN_W + 8)
        with dpg.table_row():
            with dpg.group():
                t = dpg.add_text(f"Last scanned {last}" if last else "Not scanned yet", color=COLORS["text_primary"])
                _font(t, FOOTER_MAIN_FONT)
                if parts:
                    t = dpg.add_text("  |  ".join(parts), wrap=0, color=MUTED)
                    _font(t, FOOTER_STATS_FONT)
            btn = dpg.add_button(label="Rescan", width=RESCAN_W, height=RESCAN_H, callback=_on_rescan,
                                 enabled=state not in ("loading", "unsupported"))
            dpg.bind_item_theme(btn, _T["rescan"])


def _on_rescan(sender, app_data):
    _call_handler("on_rescan", _S["path"])     # HOOK: backend re-runs the analysis and calls set_likely_targets_data again


# ---- small helpers ----

def _to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _sort_key(f):
    return (RISK_ORDER.get(str(f.get("risk", "")).lower(), 3), -_to_float(f.get("score")))