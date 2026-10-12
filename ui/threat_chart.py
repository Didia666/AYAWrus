import dearpygui.dearpygui as dpg
from ui.theme import COLORS
import sys
import os
from datetime import datetime, timedelta

#threat_chart.py

# ---- Threat chart constants (tune here) ----
THREAT_HEADER_ICON_SIZE = 24   # was 22
THREAT_Y_MIN_TOP = 5           # empty chart still shows 0-5 instead of a weird -0.5 to 0.5
THREAT_Y_MAX_TICKS = 6         # roughly how many horizontal lines/labels on the y-axis
THREAT_PLOT_DEFAULT_HEIGHT = 260
THREAT_LIMITS_FRAME_DELAY = 3  # frames to wait before re-applying the axis limits

# Add parent directory to path to import Malware_System
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    import system.history.logs as hs
    BACKEND_AVAILABLE = True
except Exception as e:
    print(f"Warning: Could not load history backend: {e}")
    BACKEND_AVAILABLE = False


def _y_axis_scale(max_value):
    """Returns (top, step): a whole-number y-axis from 0 up to top, ticks every step."""
    top = max(THREAT_Y_MIN_TOP, max_value + 1)
    step = max(1, -(-top // THREAT_Y_MAX_TICKS))   # ceil division
    top = -(-top // step) * step                   # round top up to a multiple of step
    return top, step


def _apply_threat_limits(day_count, y_top):
    """Pins the chart to x: first-to-last day, y: 0 to y_top. Safe to call repeatedly."""
    if dpg.does_item_exist("threat_x_axis"):
        dpg.set_axis_limits("threat_x_axis", -0.5, day_count - 0.5)
    if dpg.does_item_exist("threat_y_axis"):
        dpg.set_axis_limits("threat_y_axis", 0, y_top)


def build_threat_chart(fonts, icons):
    with dpg.child_window(width=758, height=340, tag="threat_chart_card", no_scrollbar=True):
        with dpg.group(horizontal=True):
            dpg.add_image(icons["chart_area"], width=THREAT_HEADER_ICON_SIZE, height=THREAT_HEADER_ICON_SIZE,
                          tint_color=COLORS["accent_blue"])
            dpg.add_text("Threat Index (Weekly)", tag="threat_chart_title", color=COLORS["text_primary"])
            dpg.bind_item_font("threat_chart_title", fonts["subheading"])
        dpg.add_spacer(height=10)

        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        threat_values = [0, 0, 0, 0, 0, 0, 0]
        x_values = list(range(len(days)))

        # Get real data from history log - limit to last 10000 entries to avoid huge load
        if BACKEND_AVAILABLE:
            log = hs.load_log(limit=10000)
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

        y_top, y_step = _y_axis_scale(max(threat_values))

        with dpg.plot(width=-1, height=THREAT_PLOT_DEFAULT_HEIGHT, tag="threat_plot",
                      no_menus=True, no_box_select=True, no_mouse_pos=True):
            dpg.add_plot_legend(show=False)

            x_axis = dpg.add_plot_axis(dpg.mvXAxis, no_gridlines=True, lock_min=True, lock_max=True,
                                       tag="threat_x_axis")
            dpg.set_axis_ticks(x_axis, tuple((day, i) for i, day in enumerate(days)))

            y_axis = dpg.add_plot_axis(dpg.mvYAxis, label="", lock_min=True, lock_max=True,
                                       tag="threat_y_axis")
            dpg.add_line_series(x_values, threat_values, parent=y_axis, tag="threat_line_series")
            dpg.set_axis_ticks(y_axis, tuple((str(v), v) for v in range(0, y_top + 1, y_step)))

        # Set the limits now, and once more a few frames later (in case DPG's first auto-fit overrides them)
        _apply_threat_limits(len(days), y_top)
        dpg.set_frame_callback(dpg.get_frame_count() + THREAT_LIMITS_FRAME_DELAY,
                               lambda: _apply_threat_limits(len(days), y_top))

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