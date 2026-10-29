import dearpygui.dearpygui as dpg
from ui.theme import COLORS
from ui.layout import register_resize
import sys
import os
from datetime import datetime

#activity_feed.py

# ---- Activity feed constants (tune here) ----
ACTIVITY_ICON_SIZE = 24
ACTIVITY_HEADER_ICON_SIZE = 24

ACTIVITY_BADGE_WIDTH = 120          # the oblong; fits "QUARANTINE" in the small mono font
ACTIVITY_BADGE_HEIGHT = 30
ACTIVITY_BADGE_ROUNDING = 14        # higher = rounder oblong
ACTIVITY_BADGE_BG_ALPHA = 35        # how filled the oblong is (0 = see-through, 255 = solid)
ACTIVITY_BADGE_BORDER_ALPHA = 150   # how visible the oblong outline is
ACTIVITY_BADGE_COLUMN_WIDTH = ACTIVITY_BADGE_WIDTH + 16   # wide layout: badge + table cell padding

ACTIVITY_ROW_HEIGHT = 56            # wide layout: height of one row (fits title + timestamp)
ACTIVITY_BADGE_TOP_OFFSET = (ACTIVITY_ROW_HEIGHT - ACTIVITY_BADGE_HEIGHT) // 2   # vertically centers the badge
ACTIVITY_NARROW_TS_OFFSET = 4       # narrow layout: nudges the timestamp down so it lines up with the badge
ACTIVITY_ROW_SPACING = 12           # gap between rows

FEED_NARROW_BREAKPOINT = 460        # feed card narrower than this (px) = badge drops under the title
FEED_MODE_FRAME_DELAY = 2           # frames to wait after a resize before switching (lets the dashboard size the card first)

# result -> (icon name, badge text, color name from theme.py COLORS)
ACTIVITY_STATUS_STYLES = {
    "MALICIOUS":   ("octagon_alert", "DANGER",     "accent_red"),
    "SUSPICIOUS":  ("shield_alert",  "WARN",       "accent_orange"),
    "CLEAN":       ("circle_check",  "OK",         "accent_green"),
    "CLEANED":     ("circle_check",  "CLEANED",    "accent_green"),
    "QUARANTINED": ("shield_cog",    "QUARANTINE", "accent_blue"),
    "RESTORED":    ("refresh",       "RESTORED",   "accent_green"),
    "DELETED":     ("trash",         "DELETED",    "accent_red"),
}
ACTIVITY_DEFAULT_STYLE = ("clock_check", "INFO", "accent_blue")

# Add parent directory to path to import the backend
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    import system.history.logs as hl
    BACKEND_AVAILABLE = True
except Exception as e:
    print(f"Warning [ui/activity_feed.py]: Could not load backend dependency 'history.logs': {e}")
    BACKEND_AVAILABLE = False

# (wide_tag, narrow_tag) for every row currently on screen
_ROW_TAGS = []
# color name -> theme, so we don't create a new theme for every badge
_BADGE_THEMES = {}


def _get_badge_theme(color_name):
    if color_name in _BADGE_THEMES:
        return _BADGE_THEMES[color_name]

    color = COLORS[color_name]
    bg = (*color, ACTIVITY_BADGE_BG_ALPHA)
    border = (*color, ACTIVITY_BADGE_BORDER_ALPHA)

    with dpg.theme() as badge_theme:
        with dpg.theme_component(dpg.mvButton):
            # same color for normal/hover/pressed, so the badge never reacts like a real button
            dpg.add_theme_color(dpg.mvThemeCol_Button, bg)
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, bg)
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, bg)
            dpg.add_theme_color(dpg.mvThemeCol_Text, color)
            dpg.add_theme_color(dpg.mvThemeCol_Border, border)
            dpg.add_theme_style(dpg.mvStyleVar_FrameBorderSize, 1)
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, ACTIVITY_BADGE_ROUNDING)

    _BADGE_THEMES[color_name] = badge_theme
    return badge_theme


def _add_badge(text, color_name, fonts):
    """A non-clickable button used as a badge. A button centers its own text, so no width math needed."""
    badge = dpg.add_button(label=text, width=ACTIVITY_BADGE_WIDTH, height=ACTIVITY_BADGE_HEIGHT)
    dpg.bind_item_font(badge, fonts["mono_small"])
    dpg.bind_item_theme(badge, _get_badge_theme(color_name))
    return badge


def _is_narrow():
    if not dpg.does_item_exist("activity_feed_card"):
        return True
    return dpg.get_item_width("activity_feed_card") < FEED_NARROW_BREAKPOINT


def _apply_feed_mode():
    """Shows the wide or narrow version of every row, depending on the feed card's width."""
    narrow = _is_narrow()
    for wide_tag, narrow_tag in _ROW_TAGS:
        if dpg.does_item_exist(wide_tag):
            dpg.configure_item(wide_tag, show=not narrow)
        if dpg.does_item_exist(narrow_tag):
            dpg.configure_item(narrow_tag, show=narrow)


def _on_layout_resize(content_w, content_h):
    # The dashboard sizes the feed card in its own resize handler, which can run AFTER this one.
    # So we wait a couple of frames, then read the card's final width.
    dpg.set_frame_callback(dpg.get_frame_count() + FEED_MODE_FRAME_DELAY, lambda *args: _apply_feed_mode())


def activity_item(title, timestamp, result, tag_suffix, fonts, icons, parent):
    icon_name, badge_text, color_name = ACTIVITY_STATUS_STYLES.get(result, ACTIVITY_DEFAULT_STYLE)
    icon = icons.get(icon_name, icons["clock_check"])
    color = COLORS[color_name]

    wide_tag = f"feed_wide_{tag_suffix}"
    narrow_tag = f"feed_narrow_{tag_suffix}"
    _ROW_TAGS.append((wide_tag, narrow_tag))
    narrow = _is_narrow()

    # ---- WIDE version: icon + title on the left, badge on the right ----
    with dpg.group(tag=wide_tag, show=not narrow, parent=parent):
        with dpg.table(header_row=False, borders_innerH=False, borders_outerH=False,
                       borders_innerV=False, borders_outerV=False):
            dpg.add_table_column(width_stretch=True, init_width_or_weight=1.0)
            dpg.add_table_column(width_fixed=True, init_width_or_weight=ACTIVITY_BADGE_COLUMN_WIDTH)

            with dpg.table_row():
                # Clipping box: if the title is too long it gets cut here instead of running under the badge
                with dpg.child_window(width=-1, height=ACTIVITY_ROW_HEIGHT, border=False, no_scrollbar=True):
                    with dpg.group(horizontal=True):
                        dpg.add_image(icon, width=ACTIVITY_ICON_SIZE, height=ACTIVITY_ICON_SIZE, tint_color=color)
                        with dpg.group():
                            dpg.add_text(title, color=COLORS["text_primary"])
                            dpg.add_text(timestamp, color=COLORS["text_secondary"])

                # ONE group = ONE table cell (spacer + badge)
                with dpg.group():
                    dpg.add_spacer(height=ACTIVITY_BADGE_TOP_OFFSET)
                    _add_badge(badge_text, color_name, fonts)

    # ---- NARROW version: title on top (wraps if long), timestamp + badge underneath ----
    with dpg.group(tag=narrow_tag, show=narrow, parent=parent):
        with dpg.group(horizontal=True):
            dpg.add_image(icon, width=ACTIVITY_ICON_SIZE, height=ACTIVITY_ICON_SIZE, tint_color=color)
            with dpg.group():
                dpg.add_text(title, wrap=0, color=COLORS["text_primary"])
                with dpg.group(horizontal=True):
                    with dpg.group():
                        dpg.add_spacer(height=ACTIVITY_NARROW_TS_OFFSET)
                        dpg.add_text(timestamp, color=COLORS["text_secondary"])
                    _add_badge(badge_text, color_name, fonts)

    dpg.add_spacer(height=ACTIVITY_ROW_SPACING, parent=parent)


def _rebuild_activity_feed_from_data(activities, fonts=None, icons=None):
    """Clear and repopulate the activity feed using pre-loaded activity data."""
    if not dpg.does_item_exist("activity_feed_list"):
        return
    fonts = fonts or dpg.get_item_user_data("activity_feed_list")[0]
    icons = icons or dpg.get_item_user_data("activity_feed_list")[1]

    dpg.delete_item("activity_feed_list", children_only=True)
    _ROW_TAGS.clear()

    if not activities:
        activities = [
            ("Custom scan completed", "6/20/2026, 12:34:34 AM", "INFO"),
            ("Quick scan completed", "6/18/2026, 9:40:24 PM", "INFO"),
            ("Custom scan completed", "6/18/2026, 9:34:11 PM", "INFO"),
            ("Full scan completed", "6/18/2026, 9:29:37 PM", "INFO"),
        ]

    for i, (title, timestamp, result) in enumerate(activities):
        activity_item(title, timestamp, result, f"item_{i}", fonts, icons, parent="activity_feed_list")


def _rebuild_activity_feed(fonts=None, icons=None):
    """Clear and repopulate the activity feed from the latest log data."""
    if not dpg.does_item_exist("activity_feed_list"):
        return
    fonts = fonts or dpg.get_item_user_data("activity_feed_list")[0]
    icons = icons or dpg.get_item_user_data("activity_feed_list")[1]

    activities = []

    if BACKEND_AVAILABLE:
        log = hl.load_log(limit=10)
        for entry in reversed(log):
            entry_result = entry.get("result", "INFO")
            entry_file = entry.get("file_path", "Unknown file")
            entry_timestamp = entry.get("timestamp", "")
            if entry_result == "MALICIOUS":
                title = f"Malware detected: {os.path.basename(entry_file)}"
            elif entry_result == "SUSPICIOUS":
                title = f"Suspicious file: {os.path.basename(entry_file)}"
            elif entry_result == "CLEAN":
                title = f"File scanned: {os.path.basename(entry_file)}"
            elif entry_result == "CLEANED":
                title = f"Malware cleaned: {os.path.basename(entry_file)}"
            elif entry_result == "QUARANTINED":
                title = f"File quarantined: {os.path.basename(entry_file)}"
            elif entry_result == "RESTORED":
                title = f"File restored: {os.path.basename(entry_file)}"
            elif entry_result == "DELETED":
                title = f"File deleted: {os.path.basename(entry_file)}"
            else:
                title = f"Scan activity: {entry_result}"
            activities.append((title, entry_timestamp, entry_result))

    _rebuild_activity_feed_from_data(activities, fonts, icons)


def build_activity_feed(fonts, icons):
    with dpg.child_window(width=480, height=340, tag="activity_feed_card"):
        with dpg.group(horizontal=True):
            dpg.add_image(icons["monitor_cog"], width=ACTIVITY_HEADER_ICON_SIZE, height=ACTIVITY_HEADER_ICON_SIZE,
                          tint_color=COLORS["accent_blue"])
            dpg.add_text("Recent Activity", tag="activity_feed_title", color=COLORS["text_primary"])
            dpg.bind_item_font("activity_feed_title", fonts["subheading"])
        dpg.add_spacer(height=10)

        # Stable inner container we can clear/rebuild later
        with dpg.group(tag="activity_feed_list", user_data=(fonts, icons)):
            pass

    _rebuild_activity_feed(fonts, icons)
    register_resize("activity_feed", _on_layout_resize)