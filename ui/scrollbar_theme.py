import dearpygui.dearpygui as dpg
from ui.theme import COLORS

# scrollbar_theme.py

# ---- Slim scrollbar constants (tune here) ----
SCROLL_SIZE = 8                              # thickness in px (same as the chat)
SCROLL_ROUNDING = 8
SCROLL_TRACK = (0, 0, 0, 0)                  # transparent track, so only the thumb shows
SCROLL_GRAB = COLORS["border"]               # resting thumb. If it's too faint on your screen, try (70, 86, 118)
SCROLL_GRAB_HOVER = (80, 96, 128)            # same hover color as the chat
SCROLL_GRAB_ACTIVE = COLORS["accent_blue"]   # while dragging

_theme = None


def _build_theme():
    with dpg.theme() as theme:
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarBg, SCROLL_TRACK)
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarGrab, SCROLL_GRAB)
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarGrabHovered, SCROLL_GRAB_HOVER)
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarGrabActive, SCROLL_GRAB_ACTIVE)
            dpg.add_theme_style(dpg.mvStyleVar_ScrollbarSize, SCROLL_SIZE)
            dpg.add_theme_style(dpg.mvStyleVar_ScrollbarRounding, SCROLL_ROUNDING)
    return theme


def apply_slim_scrollbar(tag):
    """Gives a window/child window (and anything scrollable inside it) the slim scrollbar.
    Built once, reused for every page that calls it."""
    global _theme
    if _theme is None:
        _theme = _build_theme()
    if dpg.does_item_exist(tag):
        dpg.bind_item_theme(tag, _theme)