import math
import time
import threading
from contextlib import contextmanager
import dearpygui.dearpygui as dpg
from ui.theme import COLORS
from ui.layout import register_resize
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
TAB_OUT_ACTIVE = 150           # how far the active tab sticks out (icon + label)
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
    ("suspicious", "octagon_alert", "Suspicious"),
    ("explanation", "search", "Explanation"),
    ("actions", "circle_check", "Actions"),
    ("learn", "chart_bar", "Learn Why"),
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
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 9)
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 0, 0)
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
    if not report:
        _empty_page("No detailed AI explanation is available for this file.")


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
    items = (report or {}).get("suspicious_characteristics") or []
    if not items:
        return _empty_page("No suspicious characteristics were recorded for this file.")
    for item in items:
        desc = _clean(item.get("description"))
        with _card(_card_h(TITLE_H, _text_h(desc))):
            dpg.add_text(_clean(item.get("title")), color=COLORS["accent_orange"])
            dpg.add_text(desc, wrap=0, color=COLORS["text_secondary"])


def _page_explanation(report):
    text = _clean((report or {}).get("explanation"))
    if not text:
        return _empty_page("No detailed explanation is available for this file.")
    with _card(_card_h(_text_h(text))):
        dpg.add_text(text, wrap=0, color=COLORS["text_primary"])


def _page_actions(report):
    recs = (report or {}).get("recommendations") or []
    if not recs:
        return _empty_page("No recommended actions are available for this file.")
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


def _build_pages(threat, report):
    builders = [
        lambda: _page_overview(threat, report), lambda: _page_steps(report),
        lambda: _page_suspicious(report), lambda: _page_explanation(report),
        lambda: _page_actions(report), lambda: _page_learn(report),
    ]
    for i, build in enumerate(builders):
        with dpg.group(tag=f"xai_page_{i}", parent=CONTENT, show=(i == _s["sel"])):
            build()


# ---------------------------------------------------------------------------
# Open / close / tabs
# ---------------------------------------------------------------------------

def _destroy():
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


def _on_tab(sender, app_data, user_data):
    _select_tab(user_data)


def open_explain(threat, report):
    """Opens the popup for one threat. 'report' is the XAI report dict, or None."""
    print(f"[explain] open_explain called | ready={_s['ready']}")
    if not _s["ready"]:
        return
    if dpg.does_item_exist(POPUP) or dpg.does_item_exist(BACKDROP):
        _destroy()
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
        _build_pages(threat, report)
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
        time.sleep(FRAME_SECONDS)
        now = time.time()
        dt = min(MAX_DT, now - last)
        last = now
        mode = _s["mode"]
        if mode == "closed":
            continue
        if mode == "open" and not _s["animating"] and _s["veil_t0"] is None:
            continue
        try:
            with dpg.mutex():
                _tick(now, dt)
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