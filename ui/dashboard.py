from logging import log

import dearpygui.dearpygui as dpg
from ui.activity_feed import build_activity_feed
from ui.threat_chart import build_threat_chart, create_chart_theme
from ui.theme import COLORS
from ui.layout import register_resize
import threading
import time
import sys
import os
# Add parent directory to path to import Malware_System
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    import system.history.logs as hs
    import system.quarantines.quarantine as qq
    BACKEND_AVAILABLE = True
except Exception as e:
    print(f"Warning: Could not load dashboard backend: {e}")
    BACKEND_AVAILABLE = False

# ---- Dashboard layout constants (tune here) ----
CARD_GAP = 20                  # visual gap between cards (DPG adds item spacing on top, handled below)
ITEM_SPACING_X = 8             # DPG's default horizontal item spacing
DASH_LEFT_PAD = 24             # the spacer at the left of the page
DASH_RIGHT_MARGIN = 16         # breathing room on the right (raise it if a horizontal scrollbar appears)
DASH_HEADER_HEIGHT = 110       # estimated height of title + subtitle block above the cards
DASH_BOTTOM_MARGIN = 24        # space left below the bottom row

STAT_CARD_PREFIXES = ("threat_score", "active_threats", "files_scanned")
STAT_CARD_MIN_WIDTH = 260
STAT_CARD_HEIGHT_RATIO = 0.19  # share of the content height
STAT_CARD_MIN_HEIGHT = 165
STAT_CARD_MAX_HEIGHT = 210

CHART_WIDTH_RATIO = 0.60       # chart gets 60%, feed gets the rest
CHART_MIN_WIDTH = 480
FEED_MIN_WIDTH = 340
BOTTOM_ROW_MIN_HEIGHT = 300    # below this the page scrolls instead of squishing
THREAT_PLOT_HEADER_OFFSET = 75 # chart card height minus this = plot height (title row + padding)
# dashboard.py

def animate_number(tag, target_value, duration=0.6, is_int=True):
    def _animate():
        steps = 30
        for i in range(steps + 1):
            progress = i / steps
            current = target_value * progress
            display_val = int(current) if is_int else round(current, 1)
            alive = True
            try:
                with dpg.mutex():
                    if dpg.does_item_exist(tag):
                        dpg.set_value(tag, str(display_val))
                    else:
                        alive = False
            except Exception:
                return
            if not alive:
                return
            time.sleep(duration / steps)
        try:
            with dpg.mutex():
                if dpg.does_item_exist(tag):
                    dpg.set_value(tag, str(target_value))
        except Exception:
            pass
    threading.Thread(target=_animate, daemon=True).start()

def _get_dashboard_stats():
    """Returns threat_score, active_threats, files_scanned."""
    threat_score = 0
    active_threats = 0
    files_scanned = 0

    if BACKEND_AVAILABLE:
        # Files scanned comes from history
        log = hs.load_log()
        files_scanned = len(log)

        quarantine_entries = qq.list_quarantine_items()

        print("Dashboard quarantine entries:", quarantine_entries)
        print("Dashboard active threats:", len(quarantine_entries))

        active_threats = len(quarantine_entries)

        # Calculate threat score
        if quarantine_entries:
            high_severity = 0

            for item in quarantine_entries:
                try:
                    if float(item.get("probability", 0)) >= 0.7:
                        high_severity += 1
                except Exception:
                    pass

            threat_score = min(
                100,
                int(
                    (high_severity / max(1, active_threats)) * 100
                    + active_threats * 5
                ),
            )

    return threat_score, active_threats, files_scanned


def refresh_dashboard_stats():
    """Refresh the dashboard stat cards."""

    if not dpg.does_item_exist("threat_score_value"):
        return

    threat_score, active_threats, files_scanned = _get_dashboard_stats()

    animate_number("threat_score_value", threat_score)
    animate_number("active_threats_value", active_threats)
    animate_number("files_scanned_value", files_scanned)

def stat_card(icon_texture, label, value, subtitle, color, tag_prefix, fonts):
    with dpg.child_window(width=400, height=STAT_CARD_MIN_HEIGHT, tag=f"{tag_prefix}_card", no_scrollbar=True):
        with dpg.group(horizontal=True):
            if icon_texture:
                dpg.add_image(icon_texture, width=26, height=26, tint_color=color)
            dpg.add_text(label.upper(), color=COLORS["text_secondary"])

        dpg.add_spacer(height=10)
        value_tag = f"{tag_prefix}_value"
        dpg.add_text("0", tag=value_tag, color=color)
        dpg.bind_item_font(value_tag, fonts["number_large"])

        dpg.add_spacer(height=5)
        dpg.add_text(subtitle, color=COLORS["text_secondary"])

    with dpg.theme() as hover_theme:
        with dpg.theme_component(dpg.mvChildWindow):
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, COLORS["bg_card"])
    dpg.bind_item_theme(f"{tag_prefix}_card", hover_theme)

    animate_number(value_tag, value)

def _resize_dashboard(content_w, content_h):
    """Called by ui/layout.py whenever the window size changes."""
    usable_w = content_w - DASH_LEFT_PAD - ITEM_SPACING_X - DASH_RIGHT_MARGIN
    gap = CARD_GAP + 2 * ITEM_SPACING_X  # a spacer in a horizontal group gets spacing on both sides

    # Row 1: three equal stat cards
    stat_w = max(STAT_CARD_MIN_WIDTH, int((usable_w - 2 * gap) / 3))
    stat_h = int(content_h * STAT_CARD_HEIGHT_RATIO)
    stat_h = max(STAT_CARD_MIN_HEIGHT, min(STAT_CARD_MAX_HEIGHT, stat_h))
    for prefix in STAT_CARD_PREFIXES:
        tag = f"{prefix}_card"
        if dpg.does_item_exist(tag):
            dpg.configure_item(tag, width=stat_w, height=stat_h)

    # Row 2: chart (wider) + feed, filling the rest of the height
    bottom_h = content_h - DASH_HEADER_HEIGHT - stat_h - CARD_GAP - DASH_BOTTOM_MARGIN
    bottom_h = max(BOTTOM_ROW_MIN_HEIGHT, bottom_h)
    row_w = usable_w - gap
    chart_w = max(CHART_MIN_WIDTH, int(row_w * CHART_WIDTH_RATIO))
    feed_w = max(FEED_MIN_WIDTH, row_w - chart_w)

    if dpg.does_item_exist("threat_chart_card"):
        dpg.configure_item("threat_chart_card", width=chart_w, height=bottom_h)
    if dpg.does_item_exist("threat_plot"):
        dpg.configure_item("threat_plot", height=bottom_h - THREAT_PLOT_HEADER_OFFSET)
    if dpg.does_item_exist("activity_feed_card"):
        dpg.configure_item("activity_feed_card", width=feed_w, height=bottom_h)


def build_dashboard(parent, fonts, icons):
    dpg.add_spacer(height=20, parent=parent)
    with dpg.group(horizontal=True, parent=parent):
        dpg.add_spacer(width=24)
        with dpg.group():
            dpg.add_text("System Overview", tag="dashboard_page_title")
            dpg.bind_item_font("dashboard_page_title", fonts["heading"])
            dpg.add_text("Real-time threat monitoring and analytics", color=COLORS["text_secondary"])
            dpg.add_spacer(height=15)

            # Get dashboard statistics
            threat_score, active_threats, files_scanned = _get_dashboard_stats()

            # Determine threat score icon and color
            if threat_score >= 70:
                threat_icon = icons.get("shield_alert")
                threat_color = COLORS["accent_red"]
            elif threat_score >= 30:
                threat_icon = icons.get("shield_alert")
                threat_color = COLORS["accent_orange"]
            else:
                threat_icon = icons.get("shield_check")
                threat_color = COLORS["accent_green"]

            # Determine active threats icon and color
            if active_threats > 0:
                threats_icon = icons.get("octagon_alert")
                threats_color = COLORS["accent_red"]
            else:
                threats_icon = icons.get("circle_check")
                threats_color = COLORS["accent_green"]

            files_icon = icons.get("chart_bar")
            files_color = COLORS["accent_blue"]

            with dpg.group(horizontal=True):
                stat_card(threat_icon, "Threat Score", threat_score, "Action recommended", threat_color, "threat_score", fonts)
                dpg.add_spacer(width=CARD_GAP)
                stat_card(threats_icon, "Active Threats", active_threats, "Threats in quarantine", threats_color, "active_threats", fonts)
                dpg.add_spacer(width=CARD_GAP)
                stat_card(files_icon, "Files Scanned", files_scanned, "Total files processed by ML", files_color, "files_scanned", fonts)

            dpg.add_spacer(height=CARD_GAP)
            with dpg.group(horizontal=True):
                build_threat_chart(fonts, icons)
                dpg.add_spacer(width=CARD_GAP)
                build_activity_feed(fonts, icons)

    register_resize("dashboard", _resize_dashboard)
