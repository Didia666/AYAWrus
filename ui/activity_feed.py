import dearpygui.dearpygui as dpg
from ui.theme import COLORS
import sys
import os
from datetime import datetime

# Add parent directory to path to import Malware_System
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    import Malware_System as ms
    BACKEND_AVAILABLE = True
except Exception as e:
    print(f"Warning: Could not load Malware_System backend: {e}")
    BACKEND_AVAILABLE = False


def activity_item(title, timestamp, result, tag_suffix, fonts, icons):
    with dpg.table(header_row=False, borders_innerH=False, borders_outerH=False,
                    borders_innerV=False, borders_outerV=False):
        dpg.add_table_column(init_width_or_weight=0.85)
        dpg.add_table_column(init_width_or_weight=0.15)

        with dpg.table_row():
            with dpg.group(horizontal=True):
                # Choose icon based on result
                if result == "MALICIOUS":
                    icon = icons.get("octagon_alert", icons["clock_check"])
                    icon_color = COLORS["accent_red"]
                elif result == "SUSPICIOUS":
                    icon = icons.get("shield_alert", icons["clock_check"])
                    icon_color = COLORS["accent_orange"]
                elif result == "CLEAN":
                    icon = icons.get("circle_check", icons["clock_check"])
                    icon_color = COLORS["accent_green"]
                else:
                    icon = icons["clock_check"]
                    icon_color = COLORS["text_secondary"]
                
                dpg.add_image(icon, width=20, height=20, tint_color=icon_color)
                with dpg.group():
                    dpg.add_text(title, color=COLORS["text_primary"])
                    dpg.add_text(timestamp, color=COLORS["text_secondary"])

            badge_tag = f"badge_{tag_suffix}"
            with dpg.child_window(width=60, height=24, tag=badge_tag, no_scrollbar=True):
                if result == "MALICIOUS":
                    badge_text = "DANGER"
                    badge_color = COLORS["accent_red"]
                elif result == "SUSPICIOUS":
                    badge_text = "WARN"
                    badge_color = COLORS["accent_orange"]
                elif result == "CLEAN":
                    badge_text = "OK"
                    badge_color = COLORS["accent_green"]
                else:
                    badge_text = "INFO"
                    badge_color = COLORS["accent_blue"]
                dpg.add_text(badge_text, color=badge_color)

            with dpg.theme() as badge_theme:
                with dpg.theme_component(dpg.mvChildWindow):
                    dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 15, 1)
            dpg.bind_item_theme(badge_tag, badge_theme)

    dpg.add_spacer(height=12)


def build_activity_feed(fonts, icons):
    with dpg.child_window(width=480, height=340, tag="activity_feed_card"):
        with dpg.group(horizontal=True):
            dpg.add_image(icons["monitor_cog"], width=22, height=22, tint_color=COLORS["accent_blue"])
            dpg.add_text("Recent Activity", color=COLORS["text_primary"])
        dpg.add_spacer(height=10)

        activities = []
        if BACKEND_AVAILABLE:
            log = ms.load_log()
            # Reverse log to get most recent first, take last 10
            for entry in reversed(log[-10:]):
                entry_result = entry.get("result", "INFO")
                entry_file = entry.get("file_path", "Unknown file")
                entry_timestamp = entry.get("timestamp", "")
                # Create a readable title
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
        
        # If no real activities, use defaults
        if not activities:
            activities = [
                ("Custom scan completed", "6/20/2026, 12:34:34 AM", "INFO"),
                ("Quick scan completed", "6/18/2026, 9:40:24 PM", "INFO"),
                ("Custom scan completed", "6/18/2026, 9:34:11 PM", "INFO"),
                ("Full scan completed", "6/18/2026, 9:29:37 PM", "INFO"),
            ]

        for i, (title, timestamp, result) in enumerate(activities):
            activity_item(title, timestamp, result, f"item_{i}", fonts, icons)