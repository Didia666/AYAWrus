import math
import time
import threading
from contextlib import contextmanager
import dearpygui.dearpygui as dpg
from concurrent.futures import ThreadPoolExecutor
from system.xai.shap_explainer import generate_shap_explanation
from ui.theme import COLORS
from ui.layout import register_resize
from ui.scan_targets import build_likely_targets_page, on_targets_tab_opened
from ui.scrollbar_theme import (SCROLL_SIZE, SCROLL_ROUNDING, SCROLL_TRACK,
                                SCROLL_GRAB, SCROLL_GRAB_HOVER, SCROLL_GRAB_ACTIVE)

# scan_explain.py

# ---- Popup size (tune here) ----
POP_W_RATIO = 0.62
POP_MIN_W = 700
POP_MAX_W = 980
POP_H_RATIO = 0.82
POP_MIN_H = 520
POP_MAX_H = 760
POP_MARGIN = 24                # never closer than this to the window edges
POP_PAD = 18                   # inner padding of the popup
POP_ROUNDING = 14
PAGE_BG = COLORS["bg_card"]    # popup body color. The active tab uses the same color, which is what makes it merge
CARD_BG = COLORS["bg_main"]    # cards inside the pages
BACKDROP_ALPHA = 150           # 0 = no dimming, 255 = black
CLOSE_ON_OUTSIDE_CLICK = True
CLOSE_GRACE_SECONDS = 0.30     # clicks this soon after opening are ignored

# ---- Header ----
HEADER_TITLE_H = 30
CLOSE_W = 30
CLOSE_H = 30
BODY_TOP = 84                  # where the page content starts (raise if the subtitle touches it)

# ---- Tabs (they stick out past the popup's right edge) ----
TAB_OUT_INACTIVE = 44          # how far an inactive tab sticks out
TAB_OUT_ACTIVE = 190           # how far the active tab sticks out (icon + label)
TAB_H = 44
TAB_GAP = 6
TAB_TOP_OFFSET = 90            # first tab's distance below the popup's top edge
TAB_ICON_SIZE = 20
TAB_ICON_PAD = 12              # icon distance from the tab's visible left edge
TAB_LABEL_PAD_X = 2 + TAB_ICON_PAD + TAB_ICON_SIZE + 8   # label start (2 = active overlap)
TAB_LABEL_MIN_OUT = 110        # label only shows once the tab sticks out at least this far
TAB_OVERLAP_ON = 2             # active tab covers the popup's edge by this much (hides the seam). Raise to 3 if you see a line
TAB_OVERLAP_OFF = 1
TAB_ROUNDING = 8
TAB_INACTIVE_BG = COLORS["bg_sidebar"]
TAB_HOVER = (255, 255, 255, 14)

# ---- Pieces inside the pages ----
CHIP_HEIGHT = 92
STEP_BADGE = 30
ICON_BULLET = 18

# ---- Animation ----
SLIDE_OPEN_SECONDS = 0.25      # slide up from below
SLIDE_CLOSE_SECONDS = 0.18     # slide back down
TAB_TAU = 0.055                # tab widening speed (smaller = faster)
TAB_SNAP_PX = 0.6
FADE_SECONDS = 0.14            # page fade when switching tabs
FRAME_SECONDS = 0.016
MAX_DT = 0.05

# (key, icon key from icons.py, label)
TABS = [
    ("overview", "shield_alert", "Overview"),
    ("steps", "monitor_cog", "Scan Steps"),
    ("suspicious", "octagon_alert", "PE Analysis"),
    ("shap", "chart_bar", "SHAP Explanation"),
    ("actions", "circle_check", "Actions"),
    ("learn", "chart_bar", "Learn Why"),
    ("targets", "crosshair", "Likely Targets"),
]

POPUP = "xai_popup"
BACKDROP = "xai_backdrop"
BACKDROP_BTN = "xai_backdrop_btn"
CONTENT = "xai_content"
VEIL = "xai_veil"
VEIL_COLOR = "xai_veil_color"
TITLE_BTN = "xai_title_btn"
CLOSE_BTN = "xai_close_btn"

_T = {}
_s = {
    "ready": False, "fonts": {}, "mode": "closed",   # closed / opening / open / closing
    "sel": 0, "opened_at": 0.0, "slide_t0": 0.0, "slide_from": 0.0, "cur_y": 0.0,
    "tab_cur": [], "tab_tgt": [], "animating": False, "labels": [],
    "veil_t0": None, "geo": None,
}
_shap_executor = ThreadPoolExecutor(
    max_workers=1,
    thread_name_prefix="AYAWrusSHAP"
)

_shap_future = None
_shap_request_id = 0
_shap_future_request_id = None
_shap_future_path = None

_shap_lock = threading.Lock()

_s["shap_file_path"] = None

_REPL = {"\u2192": "->", "\u2190": "<-", "\u2713": "", "\u200d": "", "\u200b": ""}


def _clean(text):
    """Display-only: drops emoji and glyphs the font can't draw (they'd show as '?')."""
    if text is None:
        return ""
    out = []
    for ch in str(text):
        if ch in _REPL:
            out.append(_REPL[ch])
            continue
        code = ord(ch)
        if ch in "\n\t" or code <= 0xFF or 0x2000 <= code <= 0x206F:
            out.append(ch)
    return "".join(out).strip()


def _font(item, key):
    f = _s["fonts"].get(key)
    if f is not None:
        dpg.bind_item_font(item, f)


def _lerp(a, b, p):
    return a + (b - a) * p


# ---------------------------------------------------------------------------
# Themes (built once)
# ---------------------------------------------------------------------------

def _flat_theme(color):
    with dpg.theme() as th:
        with dpg.theme_component(dpg.mvButton):
            for c in (dpg.mvThemeCol_Button, dpg.mvThemeCol_ButtonHovered, dpg.mvThemeCol_ButtonActive,
                      dpg.mvThemeCol_Border):
                dpg.add_theme_color(c, (0, 0, 0, 0))
            dpg.add_theme_color(dpg.mvThemeCol_Text, color)
            dpg.add_theme_style(dpg.mvStyleVar_FrameBorderSize, 0)
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 0, 0)
            dpg.add_theme_style(dpg.mvStyleVar_ButtonTextAlign, 0.0, 0.5)
    return th


def _tab_window_theme(bg, border, border_size):
    with dpg.theme() as th:
        with dpg.theme_component(dpg.mvWindowAppItem):
            dpg.add_theme_color(dpg.mvThemeCol_WindowBg, bg)
            dpg.add_theme_color(dpg.mvThemeCol_Border, border)
            dpg.add_theme_style(dpg.mvStyleVar_WindowRounding, TAB_ROUNDING)
            dpg.add_theme_style(dpg.mvStyleVar_WindowBorderSize, border_size)
            dpg.add_theme_style(dpg.mvStyleVar_WindowMinSize, 8, 8)   # DPG's default minimum (about 100px) makes tabs too big
            dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 0, 0)
    return th


def _tab_button_theme(text):
    with dpg.theme() as th:
        with dpg.theme_component(dpg.mvButton):
            dpg.add_theme_color(dpg.mvThemeCol_Button, (0, 0, 0, 0))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, TAB_HOVER)
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, TAB_HOVER)
            dpg.add_theme_color(dpg.mvThemeCol_Text, text)
            dpg.add_theme_style(dpg.mvStyleVar_FrameBorderSize, 0)
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, TAB_ROUNDING)
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding, TAB_LABEL_PAD_X, 0)
            dpg.add_theme_style(dpg.mvStyleVar_ButtonTextAlign, 0.0, 0.5)
    return th


def _themes():
    if _T:
        return _T
    c = COLORS
    # the popup itself = the page
    with dpg.theme() as th:
        with dpg.theme_component(dpg.mvWindowAppItem):
            dpg.add_theme_color(dpg.mvThemeCol_WindowBg, PAGE_BG)
            dpg.add_theme_color(dpg.mvThemeCol_Border, (56, 130, 246, 90))
            dpg.add_theme_style(dpg.mvStyleVar_WindowRounding, POP_ROUNDING)
            dpg.add_theme_style(dpg.mvStyleVar_WindowBorderSize, 1)
            dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, POP_PAD, POP_PAD)
    _T["window"] = th

    with dpg.theme() as th:
        with dpg.theme_component(dpg.mvWindowAppItem):
            dpg.add_theme_color(dpg.mvThemeCol_WindowBg, (0, 0, 0, BACKDROP_ALPHA))
            dpg.add_theme_style(dpg.mvStyleVar_WindowRounding, 0)
            dpg.add_theme_style(dpg.mvStyleVar_WindowBorderSize, 0)
            dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 0, 0)
    _T["backdrop"] = th
    _T["invisible"] = _flat_theme(c["text_primary"])

    # scrolling page area: transparent, no border, slim scrollbar
    with dpg.theme() as th:
        with dpg.theme_component(dpg.mvChildWindow):
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, (0, 0, 0, 0))
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarBg, SCROLL_TRACK)
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarGrab, SCROLL_GRAB)
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarGrabHovered, SCROLL_GRAB_HOVER)
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarGrabActive, SCROLL_GRAB_ACTIVE)
            dpg.add_theme_style(dpg.mvStyleVar_ScrollbarSize, SCROLL_SIZE)
            dpg.add_theme_style(dpg.mvStyleVar_ScrollbarRounding, SCROLL_ROUNDING)
            dpg.add_theme_style(dpg.mvStyleVar_ChildBorderSize, 0)
            dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 0, 0)
            dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, 8, 8)
    _T["content"] = th

    with dpg.theme() as th:
        with dpg.theme_component(dpg.mvChildWindow):
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, CARD_BG)
            dpg.add_theme_color(dpg.mvThemeCol_Border, c["border"])
            dpg.add_theme_style(dpg.mvStyleVar_ChildRounding, 8)
            dpg.add_theme_style(dpg.mvStyleVar_ChildBorderSize, 1)
            dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 12, 10)
    _T["card"] = th

    # page fade (covers the page, alpha animates down when switching tabs)
    with dpg.theme() as th:
        with dpg.theme_component(dpg.mvChildWindow):
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, (*PAGE_BG, 255), tag=VEIL_COLOR)
            dpg.add_theme_style(dpg.mvStyleVar_ChildBorderSize, 0)
    _T["veil"] = th

    with dpg.theme() as th:
        with dpg.theme_component(dpg.mvButton):
            dpg.add_theme_color(dpg.mvThemeCol_Button, (*c["accent_red"], 45))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (*c["accent_red"], 210))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (*c["accent_red"], 255))
            dpg.add_theme_color(dpg.mvThemeCol_Text, c["text_primary"])
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 0, 0)
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 8)
    _T["close"] = th

    with dpg.theme() as th:
        with dpg.theme_component(dpg.mvButton):
            for col in (dpg.mvThemeCol_Button, dpg.mvThemeCol_ButtonHovered, dpg.mvThemeCol_ButtonActive):
                dpg.add_theme_color(col, (*c["accent_blue"], 40))
            dpg.add_theme_color(dpg.mvThemeCol_Text, c["accent_blue"])
            dpg.add_theme_color(dpg.mvThemeCol_Border, (*c["accent_blue"], 160))
            dpg.add_theme_style(dpg.mvStyleVar_FrameBorderSize, 1)
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 8)
    _T["num"] = th

    _T["title"] = _flat_theme(c["text_primary"])
    _T["tabwin_on"] = _tab_window_theme(PAGE_BG, (0, 0, 0, 0), 0)
    _T["tabwin_off"] = _tab_window_theme(TAB_INACTIVE_BG, c["border"], 1)
    _T["tabbtn_on"] = _tab_button_theme(c["text_primary"])
    _T["tabbtn_off"] = _tab_button_theme(c["text_secondary"])
    return _T


# ---------------------------------------------------------------------------
# Geometry + layout
# ---------------------------------------------------------------------------

def _geometry():
    vw = dpg.get_viewport_client_width()
    vh = dpg.get_viewport_client_height()
    w = int(max(POP_MIN_W, min(POP_MAX_W, vw * POP_W_RATIO)))
    h = int(max(POP_MIN_H, min(POP_MAX_H, vh * POP_H_RATIO)))
    w = min(w, vw - 2 * POP_MARGIN - TAB_OUT_ACTIVE)      # leave room for the tabs sticking out
    h = min(h, vh - 2 * POP_MARGIN)
    return {
        "vw": vw, "vh": vh, "w": w, "h": h,
        "x": (vw - (w + TAB_OUT_ACTIVE)) // 2,             # popup + tabs are centered as one block
        "y": (vh - h) // 2,
        "cw": w - 2 * POP_PAD,
        "bh": h - BODY_TOP - POP_PAD,
    }


def _layout():
    """Sizes everything from the current window size (used on open and on every resize)."""
    g = _geometry()
    _s["geo"] = g
    if dpg.does_item_exist(BACKDROP):
        dpg.configure_item(BACKDROP, width=g["vw"], height=g["vh"])
        dpg.configure_item(BACKDROP_BTN, width=g["vw"], height=g["vh"])
    if not dpg.does_item_exist(POPUP):
        return
    dpg.configure_item(POPUP, width=g["w"], height=g["h"])
    dpg.configure_item(TITLE_BTN, width=g["w"] - 2 * POP_PAD - CLOSE_W - 8)
    dpg.configure_item(CLOSE_BTN, pos=[g["w"] - POP_PAD - CLOSE_W, POP_PAD])
    for tag in (CONTENT, VEIL):
        dpg.configure_item(tag, width=g["cw"], height=g["bh"], pos=[POP_PAD, BODY_TOP])
    if _s["mode"] == "open":
        _s["cur_y"] = float(g["y"])
        dpg.configure_item(POPUP, pos=[g["x"], g["y"]])
    _apply_tabs()


def _apply_tabs():
    """Places every tab window against the popup's right edge (follows the popup while it slides)."""
    g = _s["geo"]
    if not g or len(_s["tab_cur"]) != len(TABS):
        return
    right = g["x"] + g["w"]
    top = int(_s["cur_y"])
    span = max(1.0, TAB_OUT_ACTIVE - TAB_OUT_INACTIVE)
    for i, (_key, _icon, title) in enumerate(TABS):
        win = f"xai_tabwin_{i}"
        if not dpg.does_item_exist(win):
            continue
        out = _s["tab_cur"][i]
        p = max(0.0, min(1.0, (out - TAB_OUT_INACTIVE) / span))
        ov = int(round(_lerp(TAB_OVERLAP_OFF, TAB_OVERLAP_ON, p)))
        y = top + TAB_TOP_OFFSET + i * (TAB_H + TAB_GAP)
        dpg.configure_item(win, pos=[right - ov, y], width=int(round(out)) + ov, height=TAB_H)
        icon = f"xai_tab_icon_{i}"
        if dpg.does_item_exist(icon):
            dpg.configure_item(icon, pos=[ov + TAB_ICON_PAD, (TAB_H - TAB_ICON_SIZE) // 2])
        label = title if out >= TAB_LABEL_MIN_OUT else ""
        if _s["labels"][i] != label:
            _s["labels"][i] = label
            dpg.set_item_label(f"xai_tab_{i}", label)


# ---------------------------------------------------------------------------
# Page building blocks
# ---------------------------------------------------------------------------

# ---- Card measuring (cards use measured heights instead of auto-size) ----
CARD_PAD_Y = 10                # card top/bottom padding (matches the card theme)
CARD_PAD_X = 12                # card left/right padding (matches the card theme)
CARD_EXTRA = 4                 # a little safety room at the bottom of every card
LINE_GAP = 8                   # vertical gap between items inside a card
CAPTION_H = 20                 # height of a small mono caption
TITLE_H = 22                   # height of a one-line title
WRAP_SAFETY = 8                # wrap width is reduced by this so measuring never underestimates


def _caption(text):
    t = dpg.add_text(text.upper(), color=COLORS["text_secondary"])
    _font(t, "mono_small")


def _wrap_w(extra=0):
    """Width available to text inside a card (extra = space used by a badge/icon beside it)."""
    g = _s["geo"] or _geometry()
    return max(120, g["cw"] - SCROLL_SIZE - 2 * CARD_PAD_X - 2 - WRAP_SAFETY - extra)


def _text_h(text, extra=0):
    try:
        size = dpg.get_text_size(text, wrap_width=_wrap_w(extra))
    except Exception:
        size = None
    if size:
        return size[1]
    lines = int(len(text) * 8 / _wrap_w(extra)) + 1
    return lines * TITLE_H


def _card_h(*parts):
    """Card height from the heights of the items inside it."""
    return int(2 * CARD_PAD_Y + sum(parts) + LINE_GAP * (len(parts) - 1) + CARD_EXTRA)


@contextmanager
def _card(height):
    with dpg.child_window(width=-1, height=height, border=True,
                          no_scrollbar=True, no_scroll_with_mouse=True) as c:
        dpg.bind_item_theme(c, _T["card"])
        yield c


def _empty_page(text):
    dpg.add_text(_clean(text), wrap=0, color=COLORS["text_secondary"])


def _risk_color(risk):
    r = str(risk).lower()
    if "high" in r:
        return COLORS["accent_red"]
    if "low" in r:
        return COLORS["accent_green"]
    return COLORS["accent_orange"]


def _page_overview(threat, report):
    result = str(threat.get("result", ""))
    report = report or {}
    pred = _clean(report.get("prediction")) or result.title() or "-"
    try:
        if report.get("confidence") is not None:
            conf = f"{float(report['confidence']):.1f}%"
        else:
            conf = f"{float(threat.get('probability')) * 100:.1f}%"
    except (TypeError, ValueError):
        conf = "-"
    risk = _clean(report.get("risk_level")) or "-"
    pred_color = COLORS["accent_red"] if "malic" in pred.lower() else COLORS["accent_orange"]
    chips = [("Prediction", pred, pred_color), ("Confidence", conf, COLORS["text_primary"]),
             ("Risk level", risk, _risk_color(risk) if risk != "-" else COLORS["text_secondary"])]

    with dpg.table(header_row=False, policy=dpg.mvTable_SizingStretchSame):
        for _ in chips:
            dpg.add_table_column()
        with dpg.table_row():
            for cap, val, col in chips:
                with dpg.child_window(width=-1, height=CHIP_HEIGHT, border=True,
                                      no_scrollbar=True, no_scroll_with_mouse=True) as chip:
                    _caption(cap)
                    v = dpg.add_text(val, color=col)
                    _font(v, "heading")
                dpg.bind_item_theme(chip, _T["card"])

    path = _clean(threat.get("file_path", ""))
    cat = _clean(threat.get("category")) if threat.get("category") else ""
    parts = [CAPTION_H, _text_h(path)]
    if cat:
        parts += [CAPTION_H, TITLE_H]
    with _card(_card_h(*parts)):
        _caption("Location")
        dpg.add_text(path, wrap=0, color=COLORS["text_primary"])
        if cat:
            _caption("Category")
            dpg.add_text(cat, wrap=0, color=COLORS["text_primary"])
    # Brief explanation in Overview
    explanation = _clean(
        (report or {}).get("explanation")
    )

    if explanation:

        dpg.add_spacer(height=12)

        with _card(
            _card_h(
                TITLE_H,
                _text_h(explanation)
            )
        ):
            dpg.add_text(
                "Why was this file flagged?",
                color=COLORS["accent_blue"]
            )

            dpg.add_text(
                explanation,
                wrap=0,
                color=COLORS["text_secondary"]
            )

    else:
        dpg.add_spacer(height=12)

        dpg.add_text(
            "A detailed explanation is not available "
            "for this detection.",
            wrap=0,
            color=COLORS["text_secondary"]
        )

    # Guide users to the other tabs.
    dpg.add_spacer(height=10)

    dpg.add_text(
        "For more details, visit PE Analysis to review "
        "the file's characteristics or SHAP Explanation "
        "to examine the model's decision.",
        wrap=0,
        color=COLORS["text_secondary"]
    )


def _page_steps(report):
    steps = (report or {}).get("scan_steps") or []
    if not steps:
        return _empty_page("No scan steps were recorded for this file.")
    side = STEP_BADGE + 8
    for i, step in enumerate(steps, 1):
        title = _clean(step.get("title"))
        desc = _clean(step.get("description"))
        h = max(STEP_BADGE, TITLE_H + LINE_GAP + _text_h(desc, side))
        with _card(int(2 * CARD_PAD_Y + h + CARD_EXTRA)):
            with dpg.group(horizontal=True):
                b = dpg.add_button(label=str(i), width=STEP_BADGE, height=STEP_BADGE)
                dpg.bind_item_theme(b, _T["num"])
                with dpg.group():
                    dpg.add_text(title, color=COLORS["text_primary"])
                    dpg.add_text(desc, wrap=0, color=COLORS["text_secondary"])


def _page_suspicious(report):
    report = report or {}
    pe = report.get("pe_analysis") or {}

    def display(value):
        return "N/A" if value is None else str(value)

    def add_metric_card(label, value, description=""):
        value_text = display(value)

        with _card(_card_h(
            CAPTION_H,
            TITLE_H,
            _text_h(description) if description else 0
        )):
            _caption(label)

            dpg.add_text(
                value_text,
                color=COLORS["text_primary"]
            )

            if description:
                dpg.add_text(
                    description,
                    color=COLORS["text_secondary"],
                    wrap=0
                )

    # PE Analysis heading
    dpg.add_text(
        "PE Analysis",
        color=COLORS["text_primary"]
    )

    if pe:
        file_size = pe.get("file_size")

        if file_size is not None:
            if file_size >= 1024 * 1024:
                size_text = f"{file_size / (1024 * 1024):.2f} MB"
            elif file_size >= 1024:
                size_text = f"{file_size / 1024:.2f} KB"
            else:
                size_text = f"{file_size} bytes"
        else:
            size_text = "N/A"

        entropy = pe.get("entropy")

        metrics = [
            (
                "File Size",
                size_text,
                "How much storage space this file takes."
            ),
            (
                "File Entropy",
                f"{entropy:.3f} / 8.0" if entropy is not None else "N/A",
                "How random or scrambled the file's data appears."
            ),
        ]

        if pe.get("is_pe"):
            metrics.extend([
                (
                    "Architecture",
                    pe.get("architecture"),
                    "The type of computer processor this program is designed for."
                ),
                (
                    "PE Sections",
                    pe.get("section_count"),
                    "The internal parts that make up this Windows program."
                ),
                (
                    "Imported DLL Count",
                    pe.get("dll_count"),
                    "The number of unique Windows libraries the file references."
                ),
                (
                    "Imported Function Count",
                    pe.get("import_count"),
                    "The number of functions requested from those libraries."
                ),
            ])
            

        else:
            dpg.add_text(
                "PE structure unavailable for this file.",
                color=COLORS["text_secondary"],
                wrap=0
            )

        with dpg.table(header_row=False, policy=dpg.mvTable_SizingStretchSame, width=-1):
            dpg.add_table_column()
            dpg.add_table_column()
            for row_start in range(0, len(metrics), 2):
                with dpg.table_row():
                    add_metric_card(*metrics[row_start])
                    if row_start + 1 < len(metrics):
                        add_metric_card(*metrics[row_start + 1])
        # Compact, collapsible DLL list
        if pe.get("is_pe"):
            dll_names = pe.get("dll_names") or []
            dll_count = pe.get("dll_count")

            count_text = (
                str(dll_count)
                if dll_count is not None
                else "N/A"
            )

            with dpg.collapsing_header(
                label=f"Imported DLLs ({count_text})",
                default_open=False
            ):
                if dll_names:
                    with dpg.child_window(
                        width=-1,
                        height=min(180, max(55, len(dll_names) * 24 + 12)),
                        border=False
                    ):
                        for dll_name in dll_names:
                            dpg.add_text(
                                dll_name,
                                color=COLORS["text_secondary"]
                            )
                else:
                    dpg.add_text(
                        "No imported DLLs reported.",
                        color=COLORS["text_secondary"]
                    )

    else:
        dpg.add_text(
            "No structured PE analysis available.",
            color=COLORS["text_secondary"]
        )

    # Preserve your existing suspicious findings
    items = report.get("suspicious_characteristics") or []

    if items:
        dpg.add_separator()

        dpg.add_text(
            "Characteristics Worth Reviewing",
            color=COLORS["text_primary"]
        )

        dpg.add_text(
            "These are file characteristics that may deserve attention. "
            "They do not necessarily mean the file is malicious.",
            color=COLORS["text_secondary"],
            wrap=0
        )
        

        for item in items:
            desc = _clean(item.get("description"))

            with _card(_card_h(TITLE_H, _text_h(desc))):
                dpg.add_text(
                    _clean(item.get("title")),
                    color=COLORS["accent_orange"]
                )

                dpg.add_text(
                    desc,
                    wrap=0,
                    color=COLORS["text_secondary"]
                )

def _page_shap(threat, report):
    dpg.add_text(
        "SHAP Explanation",
        color=COLORS["text_primary"]
    )

    description = (
        "SHAP helps explain why AYAWrus made its prediction.\n\n"
        "Think of it as showing which clues the AI used "
        "when deciding whether a file may be dangerous.\n\n"
        "Some features push the prediction toward malware, "
        "while others push it toward benign."
    )

    with _card(_card_h(TITLE_H, _text_h(description))):
        dpg.add_text(
            "What is SHAP?",
            color=COLORS["accent_blue"]
        )

        dpg.add_text(
            description,
            color=COLORS["text_secondary"],
            wrap=0
        )

    button_description = (
        "When you press Generate Explanation, AYAWrus "
        "will analyze this file using its trained malware "
        "detection model and calculate which features "
        "contributed most to its prediction.\n\n"
        "This process runs in the background and may "
        "take some time. The file will not be executed."
    )

    button_height = 30
    button_spacer_height = 12
    with _card(_card_h(
        TITLE_H,
        _text_h(button_description),
        button_spacer_height,
        button_height
    )):
        dpg.add_text(
            "Generate a Model Explanation",
            color=COLORS["text_primary"]
        )

        dpg.add_text(
            button_description,
            color=COLORS["text_secondary"],
            wrap=0
        )

        dpg.add_spacer(height=button_spacer_height)

        dpg.add_button(
            label="Generate Explanation",
            tag="shap_generate_button",
            height=button_height,
            callback=_start_shap,
            user_data=threat.get("file_path")
        )

    dpg.add_spacer(height=10)

    dpg.add_text(
        "Ready to generate an explanation.",
        tag="shap_status",
        color=COLORS["text_secondary"]
    )

    with dpg.group(tag="shap_results"):
        pass

def _start_shap(sender, app_data, file_path):
    global _shap_future
    global _shap_request_id
    global _shap_future_request_id
    global _shap_future_path

    if not file_path:
        dpg.set_value(
            "shap_status",
            "The file path is unavailable."
        )
        return

    if file_path != _s.get("shap_file_path"):
        return

    with _shap_lock:
        # Do not queue another expensive computation.
        if (
            _shap_future is not None
            and not _shap_future.done()
        ):
            dpg.set_value(
                "shap_status",
                "Another SHAP explanation is still processing. "
                "Please wait for it to finish."
            )
            return

        # New unique request
        _shap_request_id += 1
        request_id = _shap_request_id

        _shap_future_request_id = request_id
        _shap_future_path = file_path

        try:
            _shap_future = _shap_executor.submit(
                generate_shap_explanation,
                file_path
            )
        except RuntimeError as exc:
            _shap_future = None
            _shap_future_request_id = None
            _shap_future_path = None
            dpg.set_value(
                "shap_status",
                f"Unable to start SHAP: {exc}"
            )
            return

    if dpg.does_item_exist("shap_generate_button"):
        dpg.configure_item(
            "shap_generate_button",
            enabled=False
        )

    if dpg.does_item_exist("shap_status"):
        dpg.set_value(
            "shap_status",
            "Generating SHAP explanation... Please wait."
        )

    if dpg.does_item_exist("shap_results"):
        dpg.delete_item(
            "shap_results",
            children_only=True
        )
def _poll_shap_result():
    global _shap_future
    global _shap_future_request_id
    global _shap_future_path

    with _shap_lock:
        future = _shap_future

        if future is None or not future.done():
            return

        completed_request_id = _shap_future_request_id
        completed_file_path = _shap_future_path

        # Clear completed worker tracking.
        _shap_future = None
        _shap_future_request_id = None
        _shap_future_path = None

        current_request_id = _shap_request_id

    # Reject old requests.
    if completed_request_id != current_request_id:
        return

    # Reject results belonging to another file.
    if completed_file_path != _s.get("shap_file_path"):
        return

    # Reject results if the popup is closing or closed.
    if _s["mode"] not in ("open", "opening"):
        return

    # Reject results if their UI has been destroyed.
    if not (
        dpg.does_item_exist("shap_results")
        and dpg.does_item_exist("shap_status")
    ):
        return


    try:
        result = future.result()

    except Exception as exc:
        dpg.set_value(
            "shap_status",
            f"Unable to generate explanation: {exc}"
        )

        if dpg.does_item_exist("shap_generate_button"):
            dpg.configure_item(
                "shap_generate_button",
                enabled=True
            )

        return

    if dpg.does_item_exist("shap_generate_button"):
        dpg.configure_item(
            "shap_generate_button",
            enabled=True
        )
        

    dpg.set_value(
        "shap_status",
        "Explanation generated successfully."
    )

    dpg.delete_item(
        "shap_results",
        children_only=True
    )

    with dpg.group(parent="shap_results"):
        probability = result["model_probability"] * 100
        baseline = result["baseline_probability"] * 100
        total_effect = result["total_contribution"] * 100
        reconstructed = result["reconstructed_probability"] * 100

        dpg.add_text(
            f"Model malware score: {probability:.2f}%"
        )

        with dpg.collapsing_header(
            label="Advanced Explanation Details",
            default_open=False
        ):
            dpg.add_text(
                f"Baseline model estimate: {baseline:.2f}%\n"
                f"Combined feature contribution: "
                f"{total_effect:+.2f} percentage points\n"
                f"Reconstructed model estimate: {reconstructed:.2f}%",
                color=COLORS["text_secondary"]
            )

            dpg.add_text(
                "These values show how the explanation's "
                "feature contributions combine to reproduce "
                "the model's estimate. They are primarily "
                "intended for technical review.",
                wrap=0,
                color=COLORS["text_secondary"]
            )

        dpg.add_text(
            "The baseline is the model's expected score before attributing this "
            "file's feature values. "
            "Adding the signed SHAP effects gives this file's score. A positive "
            "effect pushes the score toward malware; a negative effect pushes it "
            "toward benign. These are model explanations, not proof of malicious "
            "intent or a guarantee that a file is safe.",
            wrap=0,
            color=COLORS["text_secondary"]
        )

        dpg.add_spacer(height=10)

        dpg.add_text(
            "What Influenced This Prediction?",
            color=COLORS["text_primary"]
        )

        dpg.add_text(
            "AYAWrus examined several groups of file characteristics. "
            "The results below show which groups influenced the model "
            "the most and whether they increased or decreased its "
            "malware estimate.",
            wrap=0,
            color=COLORS["text_secondary"]
        )

        dpg.add_spacer(height=8)

        for group in result["feature_groups"]:
            direction = group["direction"]
            color = (
                COLORS["accent_red"]
                if direction == "toward_malware"
                else COLORS["accent_green"]
                if direction == "toward_benign"
                else COLORS["text_secondary"]
            )

            group_name = group["label"]
            net_effect = group["net_contribution"] * 100
            impact = group["absolute_impact"] * 100
            share = group["impact_share"] * 100
            if direction == "toward_malware":
                direction_text = "Increases the malware estimate"
            elif direction == "toward_benign":
                direction_text = "Decreases the malware estimate"
            else:
                direction_text = "Contains mixed or balanced effects"

            details = (
                f"{direction_text}\n"
                f"Overall change: {net_effect:+.2f} percentage points\n"
                f"Share of total measured influence: {share:.1f}%"
            )
            card_height = _card_h(
                TITLE_H,
                _text_h(group["description"]),
                _text_h(details),
            )
            with _card(card_height):
                dpg.add_text(
                    group_name,
                    color=color,
                )
                dpg.add_text(
                    group["description"],
                    wrap=0,
                    color=COLORS["text_secondary"],
                )
                dpg.add_text(
                    details,
                    wrap=0,
                    color=COLORS["text_primary"],
                )

def _page_explanation(report):
    text = _clean((report or {}).get("explanation"))
    if not text:
        return _empty_page("No detailed explanation is available for this file.")
    with _card(_card_h(_text_h(text))):
        dpg.add_text(text, wrap=0, color=COLORS["text_primary"])


def _page_actions(threat, report, repair_cb=None, quarantine_cb=None):
    recs = (report or {}).get("recommendations") or []
    
    dpg.add_text("Recommended Actions", color=COLORS["text_primary"])
    dpg.add_text("Based on the analysis, AYAWrus suggests the following steps to protect your system.", 
                 color=COLORS["text_secondary"], wrap=0)
    dpg.add_spacer(height=10)

    # Add Action Buttons
    t = _themes()
    with _card(100):
        dpg.add_text("Immediate Actions", color=COLORS["text_primary"])
        with dpg.group(horizontal=True):
            if repair_cb:
                repair_btn = dpg.add_button(label="Attempt Repair", width=140, height=35, 
                                            callback=repair_cb, user_data=threat)
                dpg.bind_item_theme(repair_btn, t["num"])
            
            if quarantine_cb:
                quarantine_btn = dpg.add_button(label="Quarantine File", width=140, height=35, 
                                                callback=quarantine_cb, user_data=threat)
                dpg.bind_item_theme(quarantine_btn, t["close"])

    dpg.add_spacer(height=15)
    dpg.add_text("Educational Advice", color=COLORS["text_primary"])
    
    if not recs:
        dpg.add_text("No specific educational recommendations are available for this file.", 
                     color=COLORS["text_secondary"], wrap=0)
        return

    side = ICON_BULLET + 8
    for rec in recs:
        text = _clean(rec)
        with _card(_card_h(max(ICON_BULLET, _text_h(text, side)))):
            with dpg.group(horizontal=True):
                if dpg.does_item_exist("tex_circle_check"):
                    dpg.add_image("tex_circle_check", width=ICON_BULLET, height=ICON_BULLET,
                                  tint_color=COLORS["accent_green"])
                dpg.add_text(text, wrap=0, color=COLORS["text_primary"])


def _page_learn(report):
    topics = (report or {}).get("educational_topics") or {}
    if not topics:
        return _empty_page("No learning topics are available for this file.")
    for topic in topics.values():
        content = _clean(topic.get("content"))
        with _card(_card_h(TITLE_H, _text_h(content))):
            dpg.add_text(_clean(topic.get("title")), color=COLORS["accent_green"])
            dpg.add_text(content, wrap=0, color=COLORS["text_secondary"])


def _build_pages(threat, report, repair_cb=None, quarantine_cb=None):
    builders = [
        lambda: _page_overview(threat, report),
        lambda: _page_steps(report),
        lambda: _page_suspicious(report),
        lambda: _page_shap(threat, report),
        lambda: _page_actions(threat, report, repair_cb, quarantine_cb),
        lambda: _page_learn(report),
        lambda: build_likely_targets_page(threat, _s["fonts"]),
    ]
    for i, build in enumerate(builders):
        with dpg.group(tag=f"xai_page_{i}", parent=CONTENT, show=(i == _s["sel"])):
            build()


# ---------------------------------------------------------------------------
# Open / close / tabs
# ---------------------------------------------------------------------------

def _destroy():
    global _shap_request_id

    with _shap_lock:
        _shap_request_id += 1

    _s["shap_file_path"] = None

    
    for i in range(len(TABS)):
        win = f"xai_tabwin_{i}"
        if dpg.does_item_exist(win):
            dpg.delete_item(win)
    for tag in (POPUP, BACKDROP):
        if dpg.does_item_exist(tag):
            dpg.delete_item(tag)
    _s["mode"] = "closed"
    _s["veil_t0"] = None


def _start_close():
    if _s["mode"] not in ("open", "opening"):
        return
    _s["slide_from"] = _s["cur_y"]
    _s["slide_t0"] = time.time()
    _s["mode"] = "closing"


def _backdrop_click(sender=None, app_data=None):
    if not CLOSE_ON_OUTSIDE_CLICK:
        return
    if time.time() - _s["opened_at"] < CLOSE_GRACE_SECONDS:
        return
    _start_close()


def _on_escape(sender=None, app_data=None):
    if _s["mode"] == "open":
        _start_close()


def _style_tabs():
    for i in range(len(TABS)):
        on = i == _s["sel"]
        dpg.bind_item_theme(f"xai_tabwin_{i}", _T["tabwin_on"] if on else _T["tabwin_off"])
        dpg.bind_item_theme(f"xai_tab_{i}", _T["tabbtn_on"] if on else _T["tabbtn_off"])
        icon = f"xai_tab_icon_{i}"
        if dpg.does_item_exist(icon):
            dpg.configure_item(icon, tint_color=COLORS["accent_blue"] if on else COLORS["text_secondary"])


def _select_tab(i):
    if i == _s["sel"] or not dpg.does_item_exist(POPUP):
        return
    dpg.configure_item(f"xai_page_{_s['sel']}", show=False)
    dpg.configure_item(f"xai_page_{i}", show=True)
    _s["sel"] = i
    _s["tab_tgt"] = [TAB_OUT_ACTIVE if k == i else TAB_OUT_INACTIVE for k in range(len(TABS))]
    _s["animating"] = True
    _style_tabs()
    dpg.set_y_scroll(CONTENT, 0)
    dpg.set_value(VEIL_COLOR, [*PAGE_BG, 255])
    dpg.configure_item(VEIL, show=True)
    _s["veil_t0"] = time.time()
    if TABS[i][0] == "targets":
        on_targets_tab_opened(_s.get("shap_file_path"))   # heavy analysis starts HERE, not when Explain opens


def _on_tab(sender, app_data, user_data):
    _select_tab(user_data)


def open_explain(threat, report, repair_cb=None, quarantine_cb=None):
    """Opens the popup for one threat. 'report' is the XAI report dict, or None."""
    print(f"[explain] open_explain called | ready={_s['ready']}")
    if not _s["ready"]:
        return
    if dpg.does_item_exist(POPUP) or dpg.does_item_exist(BACKDROP):
        _destroy()
    global _shap_request_id

    with _shap_lock:
        _shap_request_id += 1

    _s["shap_file_path"] = threat.get("file_path")
    t = _themes()
    g = _geometry()
    _s["geo"] = g
    _s["sel"] = 0
    _s["tab_cur"] = [TAB_OUT_ACTIVE] + [TAB_OUT_INACTIVE] * (len(TABS) - 1)
    _s["tab_tgt"] = list(_s["tab_cur"])
    _s["labels"] = [None] * len(TABS)
    _s["animating"] = False
    _s["veil_t0"] = None
    _s["cur_y"] = float(g["vh"])

    path = threat.get("file_path", "")
    name = _clean(path.replace("\\", "/").split("/")[-1]) or "Unknown file"
    sub = "AI Explanation"
    if threat.get("category"):
        sub += "  -  " + _clean(threat.get("category"))

    # 1) dim backdrop (clicking it closes the popup)
    with dpg.window(tag=BACKDROP, no_title_bar=True, no_move=True, no_resize=True, no_scrollbar=True,
                    no_collapse=True,
                    pos=(0, 0), width=g["vw"], height=g["vh"]):
        dpg.add_button(tag=BACKDROP_BTN, width=g["vw"], height=g["vh"], callback=_backdrop_click)
    dpg.bind_item_theme(BACKDROP, t["backdrop"])
    dpg.bind_item_theme(BACKDROP_BTN, t["invisible"])

    # 2) the popup = the page (starts below the screen, the ticker slides it up)
    with dpg.window(tag=POPUP, no_title_bar=True, no_move=True, no_resize=True, no_scrollbar=True,
                    no_collapse=True,
                    width=g["w"], height=g["h"], pos=(g["x"], g["vh"])):
        title = dpg.add_button(label=name, tag=TITLE_BTN, width=g["w"] - 2 * POP_PAD - CLOSE_W - 8,
                               height=HEADER_TITLE_H)
        dpg.bind_item_theme(title, t["title"])
        _font(title, "subheading")
        dpg.add_text(sub, color=COLORS["text_secondary"])
        close = dpg.add_button(label="X", tag=CLOSE_BTN, width=CLOSE_W, height=CLOSE_H,
                               pos=[g["w"] - POP_PAD - CLOSE_W, POP_PAD], callback=_start_close)
        dpg.bind_item_theme(close, t["close"])
        _font(close, "subheading")

        with dpg.child_window(tag=CONTENT, width=g["cw"], height=g["bh"], pos=[POP_PAD, BODY_TOP], border=False):
            pass
        with dpg.child_window(tag=VEIL, width=g["cw"], height=g["bh"], pos=[POP_PAD, BODY_TOP],
                              border=False, no_scrollbar=True, show=False):
            pass
        dpg.bind_item_theme(CONTENT, t["content"])
        dpg.bind_item_theme(VEIL, t["veil"])
    dpg.bind_item_theme(POPUP, t["window"])

    # 3) the tabs: small separate windows glued to the popup's right edge (created last = drawn on top)
    for i, (_key, icon, label) in enumerate(TABS):
        with dpg.window(tag=f"xai_tabwin_{i}", no_title_bar=True, no_move=True, no_resize=True,
                        no_scrollbar=True, no_scroll_with_mouse=True, no_collapse=True,
                        min_size=[8, 8],
                        width=TAB_OUT_INACTIVE + TAB_OVERLAP_ON, height=TAB_H,
                        pos=(g["x"] + g["w"], g["vh"])):
            b = dpg.add_button(label="", tag=f"xai_tab_{i}", width=-1, height=TAB_H,
                               callback=_on_tab, user_data=i, pos=[0, 0])
            with dpg.tooltip(b):
                dpg.add_text(label)
            if dpg.does_item_exist(f"tex_{icon}"):
                dpg.add_image(f"tex_{icon}", width=TAB_ICON_SIZE, height=TAB_ICON_SIZE,
                              tag=f"xai_tab_icon_{i}")

    _s["mode"] = "opening"
    try:
        _build_pages(threat, report, repair_cb, quarantine_cb)
        _style_tabs()
        _layout()
    except Exception:
        import traceback
        traceback.print_exc()
        _destroy()   # a failed build removes itself instead of sitting off-screen
        return

    print(f"[explain] built | popup={dpg.does_item_exist(POPUP)} backdrop={dpg.does_item_exist(BACKDROP)} mode={_s['mode']}")

    now = time.time()
    _s["opened_at"] = now
    _s["slide_t0"] = now


# ---------------------------------------------------------------------------
# Animation ticker
# ---------------------------------------------------------------------------

def _tick(now, dt):
    mode = _s["mode"]
    g = _geometry()
    _s["geo"] = g
    if mode in ("opening", "closing"):
        dur = SLIDE_OPEN_SECONDS if mode == "opening" else SLIDE_CLOSE_SECONDS
        t = min(1.0, (now - _s["slide_t0"]) / dur)
        if mode == "opening":
            e = 1.0 - (1.0 - t) ** 3
            y = g["vh"] + (g["y"] - g["vh"]) * e
        else:
            e = t * t
            y = _s["slide_from"] + (g["vh"] - _s["slide_from"]) * e
        _s["cur_y"] = y
        if dpg.does_item_exist(POPUP):
            dpg.configure_item(POPUP, pos=[g["x"], int(y)])
        _apply_tabs()       # same frame as the popup, so the tabs never lag behind
        if t >= 1.0:
            if mode == "opening":
                _s["mode"] = "open"
            else:
                _destroy()
                return

    if _s["animating"]:
        k = 1.0 - math.exp(-dt / TAB_TAU)
        done = True
        for i in range(len(_s["tab_cur"])):
            d = _s["tab_tgt"][i] - _s["tab_cur"][i]
            if abs(d) <= TAB_SNAP_PX:
                _s["tab_cur"][i] = _s["tab_tgt"][i]
            else:
                _s["tab_cur"][i] += d * k
                done = False
        _apply_tabs()
        if done:
            _s["animating"] = False

    if _s["veil_t0"] is not None and dpg.does_item_exist(VEIL):
        t = (now - _s["veil_t0"]) / FADE_SECONDS
        if t >= 1.0:
            dpg.configure_item(VEIL, show=False)
            _s["veil_t0"] = None
        else:
            dpg.set_value(VEIL_COLOR, [*PAGE_BG, int(255 * (1.0 - t))])


def _ticker_loop():
    last = time.time()

    while True:
        mode = _s["mode"]

        if (
            mode == "closed"
            or (
                mode == "open"
                and not _s["animating"]
                and _s["veil_t0"] is None
            )
        ):
            time.sleep(0.10)
        else:
            time.sleep(FRAME_SECONDS)
        now = time.time()
        dt = min(MAX_DT, now - last)
        last = now
        mode = _s["mode"]
        if mode == "closed":
            continue
        if (
            mode == "open"
            and not _s["animating"]
            and _s["veil_t0"] is None
            and not (
                _shap_future is not None
                and _shap_future.done()
            )
        ):
            continue
        try:
            with dpg.mutex():
                _tick(now, dt)
                _poll_shap_result()
        except Exception:
            import traceback
            traceback.print_exc()
            # fail-safe: never leave the popup stuck off-screen
            try:
                g = _geometry()
                if _s["mode"] in ("opening", "open") and dpg.does_item_exist(POPUP):
                    _s["cur_y"] = float(g["y"])
                    dpg.configure_item(POPUP, pos=[g["x"], g["y"]])
                    _s["mode"] = "open"
                    _apply_tabs()
                elif _s["mode"] == "closing":
                    _destroy()
            except Exception:
                pass


def _on_resize(content_w, content_h):
    if _s["mode"] != "closed":
        _layout()


def init_explain(fonts, icons=None):
    """Call once from build_scan."""
    if _s["ready"]:
        return
    _s["fonts"] = fonts or {}
    with dpg.handler_registry():
        dpg.add_key_press_handler(dpg.mvKey_Escape, callback=_on_escape)
    register_resize("scan_explain", _on_resize)
    threading.Thread(target=_ticker_loop, daemon=True).start()
    _s["ready"] = True