import dearpygui.dearpygui as dpg
from ui.theme import COLORS
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    import Malware_System as ms
    BACKEND_AVAILABLE = True
except Exception as e:
    print(f"Warning: Could not load Malware_System backend: {e}")
    BACKEND_AVAILABLE = False


def activity_item(title, timestamp, result, tag_suffix, fonts, icons, parent):
    with dpg.table(header_row=False, borders_innerH=False, borders_outerH=False,
                    borders_innerV=False, borders_outerV=False, parent=parent):
        dpg.add_table_column(init_width_or_weight=0.85)
        dpg.add_table_column(init_width_or_weight=0.15)

        with dpg.table_row():
            with dpg.group(horizontal=True):
                if result == "MALICIOUS":
                    icon = icons.get("octagon_alert", icons["clock_check"])
                    icon_color = COLORS["accent_red"]
                elif result == "SUSPICIOUS":
                    icon = icons.get("shield_alert", icons["clock_check"])
                    icon_color = COLORS["accent_orange"]
                elif result == "CLEAN":
                    icon = icons.get("circle_check", icons["clock_check"])
                    icon_color = COLORS["accent_green"]
                elif result in ("QUARANTINED", "RESTORED", "DELETED"):
                    icon = icons.get("shield", icons["clock_check"])
                    icon_color = COLORS["accent_blue"]
                else:
                    icon = icons["clock_check"]
                    icon_color = COLORS["text_secondary"]
                icon_color = COLORS["text_secondary"]

                dpg.add_image(icon, width=20, height=20, tint_color=icon_color)
                with dpg.group():
                    dpg.add_text(title, color=COLORS["text_primary"])
                    dpg.add_text(timestamp, color=COLORS["text_secondary"])

            badge_tag = f"badge_{tag_suffix}"
            with dpg.child_window(width=90, height=24, tag=badge_tag, no_scrollbar=True):
                if result == "MALICIOUS":
                    badge_text, badge_color = "DANGER", COLORS["accent_red"]
                elif result == "SUSPICIOUS":
                    badge_text, badge_color = "WARN", COLORS["accent_orange"]
                elif result == "CLEAN":
                    badge_text, badge_color = "OK", COLORS["accent_green"]
                elif result == "QUARANTINED":
                    badge_text, badge_color = "QUARANTINE", COLORS["accent_blue"]
                elif result == "RESTORED":
                    badge_text, badge_color = "RESTORED", COLORS["accent_green"]
                elif result == "DELETED":
                    badge_text, badge_color = "DELETED", COLORS["accent_red"]
                else:
                    badge_text, badge_color = "INFO", COLORS["accent_blue"]
                dpg.add_text(badge_text, color=badge_color)

            with dpg.theme() as badge_theme:
                with dpg.theme_component(dpg.mvChildWindow):
                    dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 15, 1)
            dpg.bind_item_theme(badge_tag, badge_theme)

    dpg.add_spacer(height=12, parent=parent)


def _rebuild_activity_feed(fonts=None, icons=None):
    """Clear and repopulate the activity feed from the latest log data."""
    if not dpg.does_item_exist("activity_feed_list"):
        return
    # Reuse stored fonts/icons if not passed explicitly
    fonts = fonts or dpg.get_item_user_data("activity_feed_list")[0]
    icons = icons or dpg.get_item_user_data("activity_feed_list")[1]

    dpg.delete_item("activity_feed_list", children_only=True)

    activities = []

    if BACKEND_AVAILABLE:
        log = ms.load_log(limit=10)
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
            elif entry_result == "QUARANTINED":
                title = f"File quarantined: {os.path.basename(entry_file)}"
            elif entry_result == "RESTORED":
                title = f"File restored: {os.path.basename(entry_file)}"
            elif entry_result == "DELETED":
                title = f"File deleted: {os.path.basename(entry_file)}"
            else:
                title = f"Scan activity: {entry_result}"
            activities.append((title, entry_timestamp, entry_result))

    if not activities:
        activities = [
            ("Custom scan completed", "6/20/2026, 12:34:34 AM", "INFO"),
            ("Quick scan completed", "6/18/2026, 9:40:24 PM", "INFO"),
            ("Custom scan completed", "6/18/2026, 9:34:11 PM", "INFO"),
            ("Full scan completed", "6/18/2026, 9:29:37 PM", "INFO"),
        ]

    for i, (title, timestamp, result) in enumerate(activities):
        activity_item(title, timestamp, result, f"item_{i}", fonts, icons, parent="activity_feed_list")


def build_activity_feed(fonts, icons):
    with dpg.child_window(width=480, height=340, tag="activity_feed_card"):
        with dpg.group(horizontal=True):
            dpg.add_image(icons["monitor_cog"], width=22, height=22, tint_color=COLORS["accent_blue"])
            dpg.add_text("Recent Activity", color=COLORS["text_primary"])
        dpg.add_spacer(height=10)

        # Stable inner container we can clear/rebuild later
        with dpg.group(tag="activity_feed_list", user_data=(fonts, icons)):
            pass

    _rebuild_activity_feed(fonts, icons)