import dearpygui.dearpygui as dpg
from ui.activity_feed import build_activity_feed
from ui.threat_chart import build_threat_chart, create_chart_theme
from ui.theme import COLORS
import threading
import time
import sys
import os
# Add parent directory to path to import Malware_System
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    import system.history.logs as hs
    BACKEND_AVAILABLE = True
except Exception as e:
    print(f"Warning: Could not load history backend: {e}")
    BACKEND_AVAILABLE = False

CARD_GAP = 20
# dashboard.py

def animate_number(tag, target_value, duration=0.6, is_int=True):
    def _animate():
        steps = 30
        for i in range(steps + 1):
            progress = i / steps
            current = target_value * progress
            display_val = int(current) if is_int else round(current, 1)
            try:
                dpg.set_value(tag, str(display_val))
            except:
                pass
            time.sleep(duration / steps)
        try:
            dpg.set_value(tag, str(target_value))
        except:
            pass
    threading.Thread(target=_animate, daemon=True).start()

def stat_card(icon_texture, label, value, subtitle, color, tag_prefix, fonts):
    with dpg.child_window(width=400, height=140, tag=f"{tag_prefix}_card"):
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

def build_dashboard(parent, fonts, icons):
    dpg.add_spacer(height=20, parent=parent)
    with dpg.group(horizontal=True, parent=parent):
        dpg.add_spacer(width=24)
        with dpg.group():
            dpg.add_text("System Overview", tag="dashboard_page_title")
            dpg.bind_item_font("dashboard_page_title", fonts["heading"])
            dpg.add_text("Real-time threat monitoring and analytics", color=COLORS["text_secondary"])
            dpg.add_spacer(height=15)

            # Get real data from backend
            threat_score = 0
            active_threats = 0
            files_scanned = 0
            
            if BACKEND_AVAILABLE:
                log = hs.load_log()
                files_scanned = len(log)
                
                threats = [e for e in log if e.get("result") in ["MALICIOUS", "SUSPICIOUS"]]
                active_threats = len(threats)
                
                # Calculate threat score
                if threats:
                    high_severity = sum(1 for t in threats if (t.get("probability") or 0) >= 0.7)
                    threat_score = min(100, int((high_severity / max(1, len(threats))) * 100 + len(threats) * 5))

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
