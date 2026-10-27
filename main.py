import dearpygui.dearpygui as dpg
import threading
import traceback

from system.model_load import load_models
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
from ui.layout import init_layout
from ui.background import init_background, set_background_clear_color
from ui.boot import init_boot

# main.py

dpg.create_context()
apply_global_theme()
create_chart_theme()
fonts = load_fonts()
icons = load_icons()
init_background()   # ui/background.py: glow overlay. Created BEFORE the pages so the toast layer ends up on top of it

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
    init_cyberlearn_for_dpg(fonts) 
except Exception:
    traceback.print_exc()

init_boot()   # ui/boot.py: intro animation. Created LAST so it sits on top of every other layer. BOOT_MODE = "never" there turns it off

VIEWPORT_DEFAULT_WIDTH = 1600
VIEWPORT_DEFAULT_HEIGHT = 900
VIEWPORT_MIN_WIDTH = 1200
VIEWPORT_MIN_HEIGHT = 700

dpg.create_viewport(
    title='AYAWrus',
    width=VIEWPORT_DEFAULT_WIDTH,
    height=VIEWPORT_DEFAULT_HEIGHT,
    min_width=VIEWPORT_MIN_WIDTH,
    min_height=VIEWPORT_MIN_HEIGHT,
    resizable=True
)
dpg.setup_dearpygui()
set_background_clear_color()
dpg.show_viewport()
dpg.set_primary_window("primary_window", True)
init_layout()
threading.Thread(
    target=load_models,
    name="AYAWrusModelLoader",
    daemon=True,
).start()

dpg.start_dearpygui()
dpg.destroy_context()
