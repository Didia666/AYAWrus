import dearpygui.dearpygui as dpg
from ui.theme import COLORS
import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path to import Malware_System
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    import Malware_System as ms
    BACKEND_AVAILABLE = True
except Exception as e:
    print(f"Warning: Could not load Malware_System backend: {e}")
    BACKEND_AVAILABLE = False


def build_threat_chart(fonts, icons):
    with dpg.child_window(width=758, height=340, tag="threat_chart_card"):
        with dpg.group(horizontal=True):
            dpg.add_image(icons["chart_area"], width=22, height=22, tint_color=COLORS["accent_blue"])
            dpg.add_text("Threat Index (Weekly)", color=COLORS["text_primary"])
        dpg.add_spacer(height=10)

        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        threat_values = [0, 0, 0, 0, 0, 0, 0]
        x_values = list(range(len(days)))

        # Get real data from history log - limit to last 10000 entries to avoid huge load
        if BACKEND_AVAILABLE:
            log = ms.load_log(limit=10000)
            today = datetime.now().date()
            for entry in log:
                try:
                    entry_date_str = entry.get("timestamp")
                    if entry_date_str:
                        entry_dt = datetime.strptime(entry_date_str.split(" ")[0], "%Y-%m-%d")
                        entry_date = entry_dt.date()
                        days_diff = (today - entry_date).days
                        if 0 <= days_diff < 7:
                            # Monday is 0, Sunday is 6
                            weekday = entry_dt.weekday()
                            # Increment threat count if it's a malicious or suspicious entry
                            if entry.get("result") in ["MALICIOUS", "SUSPICIOUS"]:
                                threat_values[weekday] += 1
                except Exception as e:
                    continue

        with dpg.plot(width=-1, height=260, no_mouse_pos=True, tag="threat_plot"):
            dpg.add_plot_legend(show=False)

            x_axis = dpg.add_plot_axis(dpg.mvXAxis, no_gridlines=True)
            dpg.set_axis_ticks(x_axis, tuple((day, i) for i, day in enumerate(days)))

            with dpg.plot_axis(dpg.mvYAxis, label="") as y_axis:
                dpg.add_line_series(x_values, threat_values, parent=y_axis, tag="threat_line_series")

        dpg.bind_item_theme("threat_line_series", "threat_line_theme")
        dpg.bind_item_theme("threat_plot", "threat_plot_theme")


def create_chart_theme():
    """Call once at startup, before build_threat_chart — registers plot color themes."""
    with dpg.theme(tag="threat_line_theme"):
        with dpg.theme_component(dpg.mvLineSeries):
            dpg.add_theme_color(dpg.mvPlotCol_Line, COLORS["accent_blue"], category=dpg.mvThemeCat_Plots)

    with dpg.theme(tag="threat_plot_theme"):
        with dpg.theme_component(dpg.mvPlot):
            dpg.add_theme_color(dpg.mvPlotCol_PlotBg, COLORS["bg_card"], category=dpg.mvThemeCat_Plots)
            dpg.add_theme_color(dpg.mvPlotCol_FrameBg, COLORS["bg_card"], category=dpg.mvThemeCat_Plots)
            dpg.add_theme_color(dpg.mvPlotCol_PlotBorder, COLORS["border"], category=dpg.mvThemeCat_Plots)