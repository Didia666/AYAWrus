import dearpygui.dearpygui as dpg
from ui.theme import apply_global_theme
from ui.sidebar import build_sidebar
from ui.dashboard import build_dashboard
from ui.scan import build_scan
from ui.quarantine import build_quarantine
from ui.history import build_history
from ui.exclusions import build_exclusions
from ui.settings import build_settings
from ui.threat_chart import create_chart_theme
from ui.fonts import load_fonts
from ui.icons import load_icons

# main.py

dpg.create_context()
apply_global_theme()
create_chart_theme()
fonts = load_fonts()
icons = load_icons()

with dpg.window(tag="primary_window", no_scrollbar=True):
    dpg.bind_font(fonts["body"])
    with dpg.group(horizontal=True):
        build_sidebar(icons)
        with dpg.group(horizontal=True, tag="main_content"):
            with dpg.child_window(tag="page_container", border=False, width=-1, height=-1):
                with dpg.child_window(tag="page_dashboard", border=False, width=-1, height=-1, show=True):
                    build_dashboard("page_dashboard", fonts, icons)
                with dpg.child_window(tag="page_scan", border=False, width=-1, height=-1, show=False):
                    build_scan("page_scan", fonts, icons)
                with dpg.child_window(tag="page_quarantine", border=False, width=-1, height=-1, show=False):
                    build_quarantine("page_quarantine", fonts, icons)
                with dpg.child_window(tag="page_history", border=False, width=-1, height=-1, show=False):
                    build_history("page_history", fonts, icons)
                with dpg.child_window(tag="page_exclusions", border=False, width=-1, height=-1, show=False):
                    build_exclusions("page_exclusions", fonts, icons)
                with dpg.child_window(tag="page_settings", border=False, width=-1, height=-1, show=False):
                    build_settings("page_settings", fonts, icons)

# Initialize CyberLearn
try: 
    from ui.cyberlearn_assistant_dpg import init_cyberlearn_for_dpg 
    init_cyberlearn_for_dpg() 
except Exception as e: 
    print(f"CyberLearn init failed: {e}")

dpg.create_viewport(
    title='AYAWrus',
    width=1600,
    height=950,
    min_width=1390,
    min_height=850,
    resizable=True
)
dpg.setup_dearpygui()
dpg.show_viewport()
dpg.set_primary_window("primary_window", True)
dpg.start_dearpygui()
dpg.destroy_context()
