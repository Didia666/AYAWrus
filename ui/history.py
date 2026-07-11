import dearpygui.dearpygui as dpg
from ui.theme import COLORS
import sys
import os

# Add parent directory to path to import Malware_System
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    import Malware_System as ms
    BACKEND_AVAILABLE = True
except Exception as e:
    print(f"Warning: Could not load Malware_System backend: {e}")
    BACKEND_AVAILABLE = False

# history.py
ROW_WIDTH = 1240
ROW_HEIGHT = 70
ROW_GAP = 12
BADGE_TOP_OFFSET = 5
ICON_BADGE_SIZE = 36
DATE_COLUMN_WIDTH = 190
GLOBAL_ICONS = None  # Store icons globally for _rebuild_history!

def _icon_for_entry(entry, icons):
    result = entry.get("result", "CLEAN")
    if result in ["MALICIOUS", "SUSPICIOUS"]:
        return icons.get("octagon_alert"), COLORS["accent_red"]
    elif result == "QUARANTINED":
        return icons.get("shield_cog"), COLORS["accent_orange"]
    elif result == "RESTORED":
        return icons.get("shield_check"), COLORS["accent_green"]
    elif result == "DELETED":
        return icons.get("shield_cog"), COLORS["accent_red"]
    return icons.get("shield_check"), COLORS["accent_green"]

def _icon_badge(icon_texture, color, tag_prefix):
    with dpg.child_window(width=ICON_BADGE_SIZE, height=ICON_BADGE_SIZE, no_scrollbar=True, tag=f"{tag_prefix}_icon_bg"):
        if icon_texture:
            dpg.add_image(icon_texture, width=18, height=18, tint_color=color, pos=(9, 10))

    with dpg.theme() as badge_theme:
        with dpg.theme_component(dpg.mvChildWindow):
            muted = tuple(c // 5 for c in color)
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, muted)
    dpg.bind_item_theme(f"{tag_prefix}_icon_bg", badge_theme)

def _history_row(entry, index, icons):
    tag_prefix = f"history_row_{index}"
    with dpg.child_window(width=ROW_WIDTH, height=ROW_HEIGHT, tag=tag_prefix, no_scrollbar=True, no_scroll_with_mouse=True):
        with dpg.group(horizontal=True):
            dpg.add_spacer(width=12)
            with dpg.group():
                dpg.add_spacer(height=BADGE_TOP_OFFSET)
                icon, color = _icon_for_entry(entry, icons)
                _icon_badge(icon, color, tag_prefix)
            dpg.add_spacer(width=12)
            with dpg.group():
                dpg.add_spacer(height=6)
                result = entry.get("result", "CLEAN")
                file_path = entry.get("file_path", "Unknown")
                dpg.add_text(f"{result}: {os.path.basename(file_path)}", color=COLORS["text_primary"])
                details = f"{file_path}"
                if entry.get("probability") is not None:
                    details += f" (Probability: {entry['probability']:.2%})"
                if entry.get("details"):
                    details += f" | {entry['details']}"
                dpg.add_text(details, color=COLORS["text_secondary"])

        timestamp = entry.get("timestamp", "Unknown")
        dpg.add_text(timestamp, color=COLORS["text_secondary"],
                    pos=(ROW_WIDTH - DATE_COLUMN_WIDTH, 26))

def _rebuild_history(icons=None):
    global GLOBAL_ICONS
    if icons is not None:
        GLOBAL_ICONS = icons
    else:
        icons = GLOBAL_ICONS
        if icons is None:
            return  # Can't rebuild without icons!
        
    if dpg.does_item_exist("history_group"):
        dpg.delete_item("history_group", children_only=True)
        
        entries = []
        if BACKEND_AVAILABLE:
            entries = ms.load_log()
            # Reverse to show newest first
            entries = list(reversed(entries))
        
        if not entries:
            with dpg.group(parent="history_group"):
                dpg.add_text("No scan history yet", color=COLORS["text_secondary"])
        else:
            for i, entry in enumerate(entries):
                _history_row(entry, i, icons)
                if i < len(entries) - 1:
                    dpg.add_spacer(height=ROW_GAP, parent="history_group")

def build_history(parent, fonts, icons):
    global GLOBAL_ICONS
    GLOBAL_ICONS = icons
    dpg.add_spacer(height=20, parent=parent)
    with dpg.group(horizontal=True, parent=parent):
        dpg.add_spacer(width=24)
        with dpg.group():
            dpg.add_text("Protection History", tag="history_page_title")
            dpg.bind_item_font("history_page_title", fonts["heading"])
            dpg.add_text("A complete log of recent security events and actions", color=COLORS["text_secondary"])
            dpg.add_spacer(height=15)

            with dpg.group(tag="history_group"):
                pass
            _rebuild_history(icons)
