import dearpygui.dearpygui as dpg
from ui.theme import COLORS
from ui.activity_feed import _get_badge_theme

# help_widgets.py
# Shared building blocks for the Help manual. Every function adds its items to whatever container is
# currently open (the "with" block it is called inside), so topic files just call them one after another.

# ---- Manual widget constants (tune here) ----
HELP_CONTENT_PANE_TAG = "help_content_pane"   # the scrolling right-hand pane (created in help_manual.py)

HELP_BODY_COLOR = (203, 213, 225)             # body text, a touch brighter than text_secondary for long reading
HELP_INSET_BG = COLORS["bg_main"]             # darker "inset" fill for tip boxes, mini cards and diagrams

HELP_PARAGRAPH_GAP = 8
HELP_SECTION_GAP = 26                         # empty space above each section heading
HELP_SECTION_AFTER_GAP = 10                   # space between the heading line and its content
HELP_ROW_GAP = 10                             # space after each numbered row

# tip kind -> (icon name, color name from theme.py COLORS)
HELP_TIP_KINDS = {
    "tip":  ("zap", "accent_blue"),
    "note": ("triangle_alert", "accent_orange"),
}
HELP_TIP_BG_ALPHA = 30
HELP_TIP_BORDER_ALPHA = 150
HELP_TIP_ICON_SIZE = 20
HELP_TIP_PADDING = (12, 10)
HELP_TIP_GAP_AFTER = 12

HELP_CALLOUT_RADIUS = 12            # numbered circles (1, 2, 3...)
HELP_CALLOUT_TEXT_SCALE = 1.25      # number size relative to the radius
HELP_CALLOUT_TEXT_DX = 0.28         # nudge the number left/up so it looks centered. Tweak if it's off
HELP_CALLOUT_TEXT_DY = 0.5

HELP_CHIP_HEIGHT = 26
HELP_CHIP_MIN_WIDTH = 70
HELP_CHIP_CHAR_WIDTH = 10           # rough pixel width per character in the small mono font
HELP_CHIP_PADDING = 24

HELP_MINI_CARD_WIDTH = 300
HELP_MINI_CARD_HEIGHT = 150
HELP_MINI_CARD_PADDING = (12, 10)
HELP_MINI_ICON_SIZE = 20

HELP_FAKE_BUTTON_HEIGHT = 32         # pictures of buttons / input boxes (replicas, not clickable)
HELP_FAKE_BUTTON_PAD = 28            # extra width around the label when no width is given
HELP_FAKE_ROUNDING = 6
HELP_FAKE_TEXT_SIZE = 18             # matches FONT_BODY_SIZE in ui/fonts.py
HELP_FAKE_INPUT_BG = COLORS["bg_sidebar"]
HELP_FAKE_INPUT_PAD_X = 12

_THEME_CACHE = {}


def child_card_theme(bg, border, padding):
    """A child-window theme (background, border color, inner padding). Cached so we don't make duplicates."""
    key = (bg, border, padding)
    if key not in _THEME_CACHE:
        with dpg.theme() as theme:
            with dpg.theme_component(dpg.mvChildWindow):
                dpg.add_theme_color(dpg.mvThemeCol_ChildBg, bg)
                dpg.add_theme_color(dpg.mvThemeCol_Border, border)
                dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, padding[0], padding[1])
        _THEME_CACHE[key] = theme
    return _THEME_CACHE[key]


# ---------- text ----------

def gap(height=HELP_PARAGRAPH_GAP):
    dpg.add_spacer(height=height)


def page_heading(title, subtitle, fonts):
    t = dpg.add_text(title)
    dpg.bind_item_font(t, fonts["heading"])
    dpg.add_text(subtitle, wrap=0, color=COLORS["text_secondary"])
    gap()


def section_heading(text, fonts):
    dpg.add_spacer(height=HELP_SECTION_GAP)
    t = dpg.add_text(text, color=COLORS["text_primary"])
    dpg.bind_item_font(t, fonts["subheading"])
    dpg.add_separator()
    dpg.add_spacer(height=HELP_SECTION_AFTER_GAP)


def paragraph(text, color=None):
    dpg.add_text(text, wrap=0, color=color or HELP_BODY_COLOR)
    gap()


# ---------- numbered callouts ----------

def draw_callout(cx, cy, number, color_name="accent_blue", radius=HELP_CALLOUT_RADIUS, parent=0):
    """Draws a numbered circle inside a drawlist (parent=0 means 'the drawlist I'm currently inside')."""
    color = COLORS[color_name]
    dpg.draw_circle((cx, cy), radius, color=HELP_INSET_BG, fill=color, thickness=1.5, parent=parent)
    size = radius * HELP_CALLOUT_TEXT_SCALE
    dpg.draw_text((cx - size * HELP_CALLOUT_TEXT_DX, cy - size * HELP_CALLOUT_TEXT_DY), str(number),
                  color=COLORS["text_primary"], size=size, parent=parent)


def callout_badge(number, color_name="accent_blue", radius=HELP_CALLOUT_RADIUS):
    size = radius * 2 + 2
    with dpg.drawlist(width=size, height=size):
        draw_callout(size / 2, size / 2, number, color_name, radius)


def numbered_row(number, title, text, color_name="accent_blue"):
    """[1]  Title
            Explanation text that wraps to the pane width."""
    with dpg.group(horizontal=True):
        callout_badge(number, color_name)
        with dpg.group():
            dpg.add_text(title, color=COLORS["text_primary"])
            dpg.add_text(text, wrap=0, color=HELP_BODY_COLOR)
    dpg.add_spacer(height=HELP_ROW_GAP)


# ---------- tip / note boxes ----------

def tip_box(kind, title, text, icons):
    icon_name, color_name = HELP_TIP_KINDS[kind]
    color = COLORS[color_name]
    theme = child_card_theme((*color, HELP_TIP_BG_ALPHA), (*color, HELP_TIP_BORDER_ALPHA), HELP_TIP_PADDING)
    with dpg.child_window(width=-1, auto_resize_y=True, border=True) as box:
        with dpg.group(horizontal=True):
            icon = icons.get(icon_name)
            if icon:
                dpg.add_image(icon, width=HELP_TIP_ICON_SIZE, height=HELP_TIP_ICON_SIZE, tint_color=color)
            with dpg.group():
                dpg.add_text(title, color=color)
                dpg.add_text(text, wrap=0, color=HELP_BODY_COLOR)
    dpg.bind_item_theme(box, theme)
    dpg.add_spacer(height=HELP_TIP_GAP_AFTER)


# ---------- chips (same look as the Recent Activity badges) ----------

def chip(text, color_name, fonts):
    width = max(HELP_CHIP_MIN_WIDTH, len(text) * HELP_CHIP_CHAR_WIDTH + HELP_CHIP_PADDING)
    btn = dpg.add_button(label=text, width=width, height=HELP_CHIP_HEIGHT)
    dpg.bind_item_font(btn, fonts["mono_small"])
    dpg.bind_item_theme(btn, _get_badge_theme(color_name))
    return btn


def chip_row(label, chips, fonts):
    """label + a row of colored chips, e.g. chip_row("Number color:", [("0-29", "accent_green"), ...], fonts)"""
    with dpg.group(horizontal=True):
        dpg.add_text(label, color=COLORS["text_secondary"])
        for text, color_name in chips:
            chip(text, color_name, fonts)
    gap()


# ---------- mini replica of a dashboard stat card ----------

def mini_stat_card(icon_name, label, value, caption, color_name, fonts, icons):
    color = COLORS[color_name]
    with dpg.child_window(width=HELP_MINI_CARD_WIDTH, height=HELP_MINI_CARD_HEIGHT, no_scrollbar=True) as card:
        with dpg.group(horizontal=True):
            icon = icons.get(icon_name)
            if icon:
                dpg.add_image(icon, width=HELP_MINI_ICON_SIZE, height=HELP_MINI_ICON_SIZE, tint_color=color)
            dpg.add_text(label.upper(), color=COLORS["text_secondary"])
        v = dpg.add_text(str(value), color=color)
        dpg.bind_item_font(v, fonts["heading"])
        dpg.add_text(caption, wrap=0, color=COLORS["text_secondary"])
    dpg.bind_item_theme(card, child_card_theme(HELP_INSET_BG, COLORS["border"], HELP_MINI_CARD_PADDING))
    return card



# ---------- pictures of buttons and input boxes (not clickable) ----------

def _measure(text):
    try:
        size = dpg.get_text_size(text)
    except Exception:
        size = None
    return size if size else (len(text) * 9, HELP_FAKE_TEXT_SIZE)


def fake_button(label, bg, fg, width=None, height=HELP_FAKE_BUTTON_HEIGHT):
    """A picture of a button. bg / fg are plain colors. Returns the width it used."""
    tw, th = _measure(label)
    w = int(width or (tw + HELP_FAKE_BUTTON_PAD))
    with dpg.drawlist(width=w, height=height):
        dpg.draw_rectangle((0, 0), (w, height), color=(0, 0, 0, 0), fill=bg, rounding=HELP_FAKE_ROUNDING)
        dpg.draw_text(((w - tw) / 2, (height - th) / 2), label, color=fg, size=HELP_FAKE_TEXT_SIZE)
    return w


def fake_input(hint, width, height=HELP_FAKE_BUTTON_HEIGHT):
    """A picture of an empty read-only input box showing a hint."""
    tw, th = _measure(hint)
    w = int(width)
    with dpg.drawlist(width=w, height=height):
        dpg.draw_rectangle((0, 0), (w - 1, height - 1), color=COLORS["border"], fill=HELP_FAKE_INPUT_BG,
                           rounding=HELP_FAKE_ROUNDING)
        dpg.draw_text((HELP_FAKE_INPUT_PAD_X, (height - th) / 2), hint, color=COLORS["text_secondary"],
                      size=HELP_FAKE_TEXT_SIZE)