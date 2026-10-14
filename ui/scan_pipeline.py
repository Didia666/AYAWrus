import math
import time
import threading
import dearpygui.dearpygui as dpg
from ui.theme import COLORS
from ui.layout import register_resize
from ui.scan_layout import (_get_themes, PAGE_LEFT_PAD, PAGE_RIGHT_MARGIN, ITEM_SPACING_X,
                            CHILD_PAD_X, CARD_GAP, SCAN_KEYS, SCAN_CARD_MIN_WIDTH)

# scan_pipeline.py

# ---- Pipeline layout constants (tune here) ----
EXPANDED_WEIGHT = 3.0          # selected card = this many shares, every other card = 1 share
PIPE_CARD_HEIGHT = 112         # raise if the title touches the bottom edge
PIPE_CARD_GAP = ITEM_SPACING_X # real gap between cards (DPG's item spacing)
PIPE_WIDTH_TRIM = 2            # safety margin so the row never overflows
CHILD_PAD_Y = 8                # DPG default child window padding
ITEM_SPACING_Y = 4             # DPG default vertical item spacing

PIPE_ICON_SIZE = 32
PIPE_ICON_TITLE_GAP = 4
PIPE_EXPANDED_ICON_TOP = 12    # spacer above the icon when the card is expanded (icon + title block)
TITLE_FALLBACK_CHAR_WIDTH = 9  # only used if DPG can't measure text
DESC_FONT_KEY = "table"        # font of the step description below the cards (Inter 20). None = the old small default
TITLE_FONT_KEY = "table"       # font of the title inside a card ("Quarantine"). None = the old small default

# ---- Tooltips (shown on hover, only on cards that are NOT the selected one) ----
TIP_ENABLED = True                       # False = no tooltips at all
TIP_TEXT_FORMAT = "Step {num}: {title}"  # {num} = 1..7, {title} = the step title on one line
TIP_TEXT_COLOR = COLORS["text_primary"]

# ---- Animation ----
ANIM_DURATION = 0.22           # seconds for a click expand/collapse
ANIM_TAU = ANIM_DURATION / 4   # ease-out speed (reaches ~98% at ANIM_DURATION)
ANIM_FRAME_SECONDS = 0.016     # ~60 fps ticker
ANIM_MAX_DT = 0.05
TEXT_SYNC_TOLERANCE = 0.5      # px; re-center a title when its drawn width differs from the stored one by more than this
ANIM_SNAP_PX = 0.6
TITLE_FADE_START = 0.45        # title starts fading in once the card is this far expanded (0 to 1)

# ---- Step number badge ----
BADGE_W = 22
BADGE_H = 20
BADGE_MARGIN = 5               # distance from the card's top-right corner
BADGE_ROUNDING = 6
BADGE_BG_OFF = (38, 50, 74)

# ---- Panel + description box ----
PIPE_TITLE_GAP = 6
PIPE_DESC_GAP = 8
PIPE_HEADER_HEIGHT = 60        # heading + gaps above the cards (raise if the description box gets cut off)
PIPE_PANEL_EXTRA = 26          # bottom breathing room inside the panel
PIPE_BOTTOM_MARGIN = 90        # space under the panel so the help button never covers it
DESC_PAD_Y = 6
DESC_SIDE_PAD = 14
DESC_WRAP_TRIM = 6
DESC_BOX_EXTRA = 6
DESC_LINE_HEIGHT_FALLBACK = 22
DESC_CHAR_WIDTH_FALLBACK = 8

_THEMES = {}
_s = {
    "steps": [], "elements": [], "n": 0, "sel": 0,
    "inner_w": 800, "col_w": 100.0, "exp_w": 300.0,
    "cur": [], "tgt": [], "tw": {},
    "animating": False, "ticker_started": False, "fonts": {},
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _one_line(title):
    return title.replace("\n", " ")


def _indent(outer_w, inner_w):
    """Indent that centers an item of inner_w inside a child window of outer_w."""
    return max(0, int((outer_w - inner_w) // 2) - CHILD_PAD_X)


def _row_width(content_w):
    """Same row width as the three scan cards and the Ready panel, so the edges line up."""
    usable_w = content_w - PAGE_LEFT_PAD - ITEM_SPACING_X - PAGE_RIGHT_MARGIN
    gap = CARD_GAP + 2 * ITEM_SPACING_X
    count = len(SCAN_KEYS)
    card_w = max(SCAN_CARD_MIN_WIDTH, int((usable_w - (count - 1) * gap) / count))
    return count * card_w + (count - 1) * gap


def _text_width(i):
    if i not in _s["tw"]:
        title = _one_line(_s["steps"][i]["title"])
        font = _s["fonts"].get(TITLE_FONT_KEY) if TITLE_FONT_KEY else None
        try:
            size = dpg.get_text_size(title, font=font) if font is not None else dpg.get_text_size(title)
        except Exception:
            size = None
        _s["tw"][i] = size[0] if size else len(title) * TITLE_FALLBACK_CHAR_WIDTH
    return _s["tw"][i]


def _lerp(a, b, p):
    return a + (b - a) * p


def _badge_theme(bg, fg):
    with dpg.theme() as theme:
        with dpg.theme_component(dpg.mvButton):
            dpg.add_theme_color(dpg.mvThemeCol_Button, bg)
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, bg)
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, bg)
            dpg.add_theme_color(dpg.mvThemeCol_Text, fg)
            dpg.add_theme_color(dpg.mvThemeCol_Border, (0, 0, 0, 0))
            dpg.add_theme_style(dpg.mvStyleVar_FrameBorderSize, 0)
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, BADGE_ROUNDING)
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 0, 0)
    return theme


def _own_themes():
    if _THEMES:
        return _THEMES
    _THEMES["badge_on"] = _badge_theme(COLORS["accent_blue"], COLORS["text_primary"])
    _THEMES["badge_off"] = _badge_theme(BADGE_BG_OFF, COLORS["text_secondary"])
    return _THEMES


# ---------------------------------------------------------------------------
# Tooltips
# ---------------------------------------------------------------------------

def _make_tip(i):
    """Creates the hover tooltip for step i (attached to its card)."""
    tip_tag = f"step_tip_{i}"
    if dpg.does_item_exist(tip_tag):
        return
    text = TIP_TEXT_FORMAT.format(num=i + 1, title=_one_line(_s["steps"][i]["title"]))
    with dpg.tooltip(f"step_{i}", tag=tip_tag):
        dpg.add_text(text, color=TIP_TEXT_COLOR)


def _refresh_tooltips():
    """Every card gets a tooltip except the selected one (it already shows its own title)."""
    try:
        for i in range(_s["n"]):
            tip_tag = f"step_tip_{i}"
            want = TIP_ENABLED and i != _s["sel"]
            exists = dpg.does_item_exist(tip_tag)
            if want and not exists:
                _make_tip(i)
            elif not want and exists:
                dpg.delete_item(tip_tag)
    except Exception:
        import traceback
        traceback.print_exc()


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def _build_card(i, step, icons, is_active):
    t = _get_themes()
    own = _own_themes()
    step_tag = f"step_{i}"
    img_tag = f"step_img_{i}"
    txt_tag = f"step_txt_{i}"
    badge_tag = f"step_badge_{i}"

    with dpg.child_window(width=130, height=PIPE_CARD_HEIGHT, tag=step_tag,
                          no_scrollbar=True, no_scroll_with_mouse=True):
        dpg.add_spacer(height=PIPE_EXPANDED_ICON_TOP, tag=f"step_pad_{i}")
        dpg.add_image(icons[step["icon"]], width=PIPE_ICON_SIZE, height=PIPE_ICON_SIZE,
                      tint_color=COLORS["accent_blue"] if is_active else COLORS["text_secondary"],
                      tag=img_tag)
        dpg.add_spacer(height=PIPE_ICON_TITLE_GAP)
        dpg.add_text(_one_line(step["title"]), tag=txt_tag,
                     color=COLORS["text_primary"] if is_active else COLORS["text_secondary"])
        # the badge goes last on purpose: it is positioned by hand and must not shift the layout above
        dpg.add_button(label=str(i + 1), tag=badge_tag, width=BADGE_W, height=BADGE_H, pos=[100, BADGE_MARGIN])

    dpg.bind_item_theme(step_tag, t["card_on"] if is_active else t["card_off"])
    dpg.bind_item_theme(badge_tag, own["badge_on"] if is_active else own["badge_off"])
    mono = _s["fonts"].get("mono_small")
    if mono is not None:
        dpg.bind_item_font(badge_tag, mono)
    title_font = _s["fonts"].get(TITLE_FONT_KEY) if TITLE_FONT_KEY else None
    if title_font is not None:
        dpg.bind_item_font(txt_tag, title_font)   # the number badge keeps its own mono font
    return (step_tag, img_tag, txt_tag)


def build_pipeline_panel(icons, fonts, steps, selected):
    """Builds the whole Detection Pipeline panel. Returns the (card, icon, title) tag tuples
    that scan.py keeps in g_step_elements for click detection."""
    _s["steps"] = steps
    _s["n"] = len(steps)
    _s["sel"] = selected
    _s["fonts"] = fonts or {}
    _s["tw"] = {}
    _s["cur"] = []
    _s["tgt"] = []

    elements = []
    with dpg.child_window(width=900, height=400, tag="how_it_works_container",
                          no_scrollbar=True, no_scroll_with_mouse=True):
        title = dpg.add_text("Detection Pipeline", color=COLORS["text_primary"])
        if _s["fonts"].get("heading") is not None:
            dpg.bind_item_font(title, _s["fonts"]["heading"])
        dpg.add_spacer(height=PIPE_TITLE_GAP)

        with dpg.group(horizontal=True, tag="steps_group"):
            for i, step in enumerate(steps):
                elements.append(_build_card(i, step, icons, i == selected))

        dpg.add_spacer(height=PIPE_DESC_GAP)
        with dpg.child_window(width=-1, height=80, border=True, tag="step_description_child",
                              no_scrollbar=True, no_scroll_with_mouse=True):
            dpg.add_spacer(height=DESC_PAD_Y)
            dpg.add_text(steps[selected]["description"], color=COLORS["text_secondary"],
                         wrap=700, tag="step_description_text", indent=DESC_SIDE_PAD)
            desc_font = _s["fonts"].get(DESC_FONT_KEY) if DESC_FONT_KEY else None
            if desc_font is not None:
                dpg.bind_item_font("step_description_text", desc_font)

    dpg.add_spacer(height=PIPE_BOTTOM_MARGIN)

    _s["elements"] = elements
    _refresh_tooltips()
    register_resize("scan_pipeline", _resize_pipeline)
    _start_ticker()
    return elements


# ---------------------------------------------------------------------------
# Sizing + animation
# ---------------------------------------------------------------------------

def _recalc(snap):
    n = _s["n"]
    if n == 0:
        return
    units = (n - 1) + EXPANDED_WEIGHT
    unit = (_s["inner_w"] - (n - 1) * PIPE_CARD_GAP) / units
    _s["col_w"] = unit
    _s["exp_w"] = unit * EXPANDED_WEIGHT
    _s["tgt"] = [_s["exp_w"] if i == _s["sel"] else _s["col_w"] for i in range(n)]
    if snap or len(_s["cur"]) != n:
        _s["cur"] = list(_s["tgt"])
        _s["animating"] = False
    else:
        _s["animating"] = True


def _title_color(i, p):
    base = COLORS["text_primary"] if i == _s["sel"] else COLORS["text_secondary"]
    fade = (p - TITLE_FADE_START) / max(0.01, 1.0 - TITLE_FADE_START)
    alpha = int(255 * max(0.0, min(1.0, fade)))
    return (base[0], base[1], base[2], alpha)


def _apply_all():
    """Pushes the current animated widths to the widgets."""
    if not _s["elements"] or len(_s["cur"]) != len(_s["elements"]):
        return
    col, exp = _s["col_w"], _s["exp_w"]
    span = max(1.0, exp - col)
    collapsed_top = int(PIPE_CARD_HEIGHT / 2 - PIPE_ICON_SIZE / 2 - CHILD_PAD_Y - ITEM_SPACING_Y)
    for i, (step_tag, img_tag, txt_tag) in enumerate(_s["elements"]):
        if not dpg.does_item_exist(step_tag):
            continue
        w = _s["cur"][i]
        p = max(0.0, min(1.0, (w - col) / span))
        dpg.configure_item(step_tag, width=int(round(w)))
        dpg.configure_item(img_tag, indent=_indent(w, PIPE_ICON_SIZE))
        dpg.configure_item(f"step_pad_{i}", height=int(_lerp(collapsed_top, PIPE_EXPANDED_ICON_TOP, p)))
        dpg.configure_item(txt_tag, indent=_indent(w, _text_width(i)), color=_title_color(i, p))
        dpg.configure_item(f"step_badge_{i}", pos=[int(w) - BADGE_W - BADGE_MARGIN, BADGE_MARGIN])


def _tick(dt):
    k = 1.0 - math.exp(-dt / ANIM_TAU)
    done = True
    for i in range(len(_s["cur"])):
        d = _s["tgt"][i] - _s["cur"][i]
        if abs(d) <= ANIM_SNAP_PX:
            _s["cur"][i] = _s["tgt"][i]
        else:
            _s["cur"][i] += d * k
            done = False
    _apply_all()
    if done:
        _s["animating"] = False


def _sync_text_widths():
    """Replaces the startup measurement with the width DPG actually drew, then re-centers the titles."""
    changed = False
    for i, (_, _, txt_tag) in enumerate(_s["elements"]):
        if not dpg.does_item_exist(txt_tag):
            continue
        drawn_w = dpg.get_item_rect_size(txt_tag)[0]
        if drawn_w > 0 and abs(drawn_w - _s["tw"].get(i, -1.0)) > TEXT_SYNC_TOLERANCE:
            _s["tw"][i] = drawn_w
            changed = True
    if changed:
        _apply_all()


def _ticker_loop():
    last = time.monotonic()
    last_text_sync = 0.0

    while True:
        animating = _s["animating"]

        # High frequency only while animating.
        interval = (
            ANIM_FRAME_SECONDS if animating
            else 0.50
        )

        time.sleep(interval)

        now = time.monotonic()
        dt = min(ANIM_MAX_DT, now - last)
        last = now

        try:
            with dpg.mutex():

                # Check text sizes twice per second.
                if now - last_text_sync >= 0.50:
                    _sync_text_widths()
                    last_text_sync = now

                if _s["animating"]:
                    _tick(dt)

        except Exception:
            import traceback
            traceback.print_exc()


def _start_ticker():
    if _s["ticker_started"]:
        return
    _s["ticker_started"] = True
    threading.Thread(target=_ticker_loop, daemon=True).start()


def _resize_pipeline(content_w, content_h):
    """Called by ui/layout.py whenever the window size changes."""
    row_w = _row_width(content_w)
    inner = row_w - 2 * CHILD_PAD_X
    _s["inner_w"] = inner - PIPE_WIDTH_TRIM
    _recalc(snap=True)

    # description box: tall enough for the LONGEST description at this width, so it never jumps
    desc_wrap = inner - 2 * CHILD_PAD_X - 2 * DESC_SIDE_PAD - DESC_WRAP_TRIM
    max_h = 0
    for step in _s["steps"]:
        desc_font = _s["fonts"].get(DESC_FONT_KEY) if DESC_FONT_KEY else None
        try:
            if desc_font is not None:
                size = dpg.get_text_size(step["description"], wrap_width=desc_wrap, font=desc_font)
            else:
                size = dpg.get_text_size(step["description"], wrap_width=desc_wrap)
        except Exception:
            size = None
        if size:
            h = size[1]
        else:
            lines = int(len(step["description"]) * DESC_CHAR_WIDTH_FALLBACK / max(1, desc_wrap)) + 1
            h = lines * DESC_LINE_HEIGHT_FALLBACK
        max_h = max(max_h, h)
    box_h = int(max_h + 2 * DESC_PAD_Y + 2 * CHILD_PAD_Y + DESC_BOX_EXTRA)
    panel_h = PIPE_HEADER_HEIGHT + PIPE_CARD_HEIGHT + PIPE_DESC_GAP + box_h + PIPE_PANEL_EXTRA

    if dpg.does_item_exist("how_it_works_container"):
        dpg.configure_item("how_it_works_container", width=row_w, height=panel_h)
    if dpg.does_item_exist("step_description_child"):
        dpg.configure_item("step_description_child", height=box_h)
    if dpg.does_item_exist("step_description_text"):
        dpg.configure_item("step_description_text", wrap=desc_wrap)

    _apply_all()


# ---------------------------------------------------------------------------
# Selection (called from scan.py's _update_step_description)
# ---------------------------------------------------------------------------

def set_pipeline_step(index, description):
    t = _get_themes()
    own = _own_themes()
    _s["sel"] = index
    if dpg.does_item_exist("step_description_text"):
        dpg.set_value("step_description_text", description)
    for i, (step_tag, img_tag, txt_tag) in enumerate(_s["elements"]):
        on = i == index
        dpg.bind_item_theme(step_tag, t["card_on"] if on else t["card_off"])
        dpg.bind_item_theme(f"step_badge_{i}", own["badge_on"] if on else own["badge_off"])
        dpg.configure_item(img_tag, tint_color=COLORS["accent_blue"] if on else COLORS["text_secondary"])
    _recalc(snap=False)
    _refresh_tooltips()