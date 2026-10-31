import traceback
import dearpygui.dearpygui as dpg
from ui.theme import COLORS
from ui.layout import register_resize
from ui.help_widgets import HELP_CONTENT_PANE_TAG, HELP_INSET_BG, child_card_theme
from ui import (help_getting_started, help_dashboard, help_scan, help_scan_results, help_explain, help_quarantine,
                help_history, help_exclusions, help_settings)

# help_manual.py
# The Help tab shell: topic list on the left, scrolling content on the right.
# To add a topic: create ui/help_<name>.py with a build_topic(fonts, icons) function,
# import it above, and add one entry to HELP_TOPICS below.

# ---- Help manual layout constants (tune here) ----
HELP_LEFT_PAD = 24             # same as the dashboard
HELP_RIGHT_MARGIN = 16
ITEM_SPACING_X = 8             # DPG's default horizontal item spacing
HELP_HEADER_HEIGHT = 110       # title + subtitle block above the panes
HELP_BOTTOM_MARGIN = 24

HELP_LIST_WIDTH = 240          # left topic list
HELP_PANE_GAP = 20             # gap between list and content
HELP_PANE_MIN_WIDTH = 420
HELP_PANE_MIN_HEIGHT = 360     # below this the page scrolls instead of squishing
HELP_LIST_PADDING = (10, 12)
HELP_CONTENT_PADDING = (20, 16)

HELP_TOPIC_HEIGHT = 36         # same as the sidebar buttons
HELP_TOPIC_WIDTH = HELP_LIST_WIDTH - 40
HELP_TOPIC_GAP = 4
HELP_TOPIC_PADDING = (8, 8)
HELP_TOPIC_ICON_SIZE = 18
HELP_INDICATOR_WIDTH = 3
HELP_TOPIC_ACTIVE_BG = (42, 56, 88)
HELP_DEFAULT_TOPIC = "getting_started"
HELP_TOPIC_ERROR_TEXT = "This section could not be loaded. Check the terminal for details."

HELP_TOPICS = [
    {"key": "getting_started", "label": "Getting Started", "icon": "play", "build": help_getting_started.build_topic},
    {"key": "dashboard", "label": "Dashboard", "icon": "layout_dashboard", "build": help_dashboard.build_topic},
    {"key": "scan", "label": "Scan", "icon": "scan_search", "build": help_scan.build_topic},
    {"key": "scan_results", "label": "Scan Results", "icon": "shield_alert", "build": help_scan_results.build_topic},
    {"key": "explain", "label": "Explain a Threat", "icon": "monitor_cog", "build": help_explain.build_topic},
    {"key": "quarantine", "label": "Quarantine", "icon": "shield_cog", "build": help_quarantine.build_topic},
    {"key": "history", "label": "History", "icon": "history", "build": help_history.build_topic},
    {"key": "exclusions", "label": "Exclusions", "icon": "sliders_horizontal", "build": help_exclusions.build_topic},
    {"key": "settings", "label": "Settings", "icon": "settings", "build": help_settings.build_topic},
]

_current_topic = HELP_DEFAULT_TOPIC


def _topic_theme(is_active):
    bg = HELP_TOPIC_ACTIVE_BG if is_active else HELP_INSET_BG
    return child_card_theme(bg, COLORS["border"], HELP_TOPIC_PADDING)


def _topic_row(topic, icons, is_active):
    tag = f"help_topic_{topic['key']}"
    with dpg.group(horizontal=True):
        with dpg.drawlist(width=HELP_INDICATOR_WIDTH, height=HELP_TOPIC_HEIGHT):
            dpg.draw_rectangle((0, 0), (HELP_INDICATOR_WIDTH, HELP_TOPIC_HEIGHT),
                               fill=COLORS["accent_blue"], color=COLORS["accent_blue"],
                               show=is_active, tag=f"{tag}_indicator")
        with dpg.child_window(width=HELP_TOPIC_WIDTH, height=HELP_TOPIC_HEIGHT, tag=f"{tag}_bg", no_scrollbar=True):
            with dpg.group(horizontal=True):
                dpg.add_spacer(width=8)
                icon = icons.get(topic["icon"])
                if icon:
                    dpg.add_image(icon, width=HELP_TOPIC_ICON_SIZE, height=HELP_TOPIC_ICON_SIZE,
                                  tint_color=COLORS["accent_blue"] if is_active else COLORS["text_secondary"],
                                  tag=f"{tag}_icon")
                dpg.add_spacer(width=8)
                dpg.add_text(topic["label"],
                             color=COLORS["text_primary"] if is_active else COLORS["text_secondary"],
                             tag=f"{tag}_text")
    dpg.bind_item_theme(f"{tag}_bg", _topic_theme(is_active))


def _select_topic(key):
    global _current_topic
    _current_topic = key
    for topic in HELP_TOPICS:
        k = topic["key"]
        active = k == key
        tag = f"help_topic_{k}"
        dpg.configure_item(f"{tag}_indicator", show=active)
        if dpg.does_item_exist(f"{tag}_icon"):
            dpg.configure_item(f"{tag}_icon", tint_color=COLORS["accent_blue"] if active else COLORS["text_secondary"])
        dpg.configure_item(f"{tag}_text", color=COLORS["text_primary"] if active else COLORS["text_secondary"])
        dpg.bind_item_theme(f"{tag}_bg", _topic_theme(active))
        dpg.configure_item(f"help_content_{k}", show=active)
    dpg.set_y_scroll(HELP_CONTENT_PANE_TAG, 0)


def _handle_click(sender, app_data):
    for topic in HELP_TOPICS:
        if dpg.is_item_hovered(f"help_topic_{topic['key']}_bg"):
            _select_topic(topic["key"])
            return


def _resize_help(content_w, content_h):
    """Called by ui/layout.py whenever the window size changes."""
    usable_w = content_w - HELP_LEFT_PAD - ITEM_SPACING_X - HELP_RIGHT_MARGIN
    gap = HELP_PANE_GAP + 2 * ITEM_SPACING_X   # a spacer in a horizontal group gets spacing on both sides
    pane_w = max(HELP_PANE_MIN_WIDTH, usable_w - HELP_LIST_WIDTH - gap)
    pane_h = max(HELP_PANE_MIN_HEIGHT, content_h - HELP_HEADER_HEIGHT - HELP_BOTTOM_MARGIN)
    if dpg.does_item_exist("help_list_pane"):
        dpg.configure_item("help_list_pane", height=pane_h)
    if dpg.does_item_exist(HELP_CONTENT_PANE_TAG):
        dpg.configure_item(HELP_CONTENT_PANE_TAG, width=pane_w, height=pane_h)


def build_help(parent, fonts, icons):
    dpg.add_spacer(height=20, parent=parent)
    with dpg.group(horizontal=True, parent=parent):
        dpg.add_spacer(width=HELP_LEFT_PAD)
        with dpg.group():
            dpg.add_text("User Manual", tag="help_page_title")
            dpg.bind_item_font("help_page_title", fonts["heading"])
            dpg.add_text("How to use AYAWrus, one screen at a time.", color=COLORS["text_secondary"])
            dpg.add_spacer(height=15)

            with dpg.group(horizontal=True):
                # ---- left: topic list ----
                with dpg.child_window(width=HELP_LIST_WIDTH, height=HELP_PANE_MIN_HEIGHT,
                                      tag="help_list_pane", no_scrollbar=True):
                    for i, topic in enumerate(HELP_TOPICS):
                        _topic_row(topic, icons, topic["key"] == HELP_DEFAULT_TOPIC)
                        if i < len(HELP_TOPICS) - 1:
                            dpg.add_spacer(height=HELP_TOPIC_GAP)
                dpg.bind_item_theme("help_list_pane",
                                    child_card_theme(COLORS["bg_card"], COLORS["border"], HELP_LIST_PADDING))

                dpg.add_spacer(width=HELP_PANE_GAP)

                # ---- right: content (one group per topic, only the selected one is shown) ----
                with dpg.child_window(width=HELP_PANE_MIN_WIDTH, height=HELP_PANE_MIN_HEIGHT,
                                      tag=HELP_CONTENT_PANE_TAG):
                    for topic in HELP_TOPICS:
                        with dpg.group(tag=f"help_content_{topic['key']}", show=topic["key"] == HELP_DEFAULT_TOPIC):
                            try:
                                topic["build"](fonts, icons)
                            except Exception:
                                traceback.print_exc()
                                dpg.add_text(HELP_TOPIC_ERROR_TEXT, color=COLORS["accent_red"])
                dpg.bind_item_theme(HELP_CONTENT_PANE_TAG,
                                    child_card_theme(COLORS["bg_card"], COLORS["border"], HELP_CONTENT_PADDING))

    with dpg.handler_registry():
        dpg.add_mouse_click_handler(button=dpg.mvMouseButton_Left, callback=_handle_click)

    register_resize("help_manual", _resize_help)