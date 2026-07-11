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

# exclusions.py
CARD_WIDTH = 1240
ROW_HEIGHT = 50
ROW_GAP = 10

def _add_exclusion(sender, app_data, user_data):
    path = dpg.get_value("exclusion_input").strip()
    if path:
        if BACKEND_AVAILABLE:
            ms.add_exclusion(path)
        dpg.set_value("exclusion_input", "")
        _render_list()

def _remove_exclusion(sender, app_data, user_data):
    index = user_data
    if BACKEND_AVAILABLE:
        exclusions = ms.list_exclusions()
        if index < len(exclusions):
            ms.remove_exclusion(exclusions[index])
    _render_list()

def _folder_picked(sender, app_data):
    path = app_data.get("file_path_name", "")
    if path:
        dpg.set_value("exclusion_input", path)

def _render_list():
    if dpg.does_item_exist("exclusions_count_text"):
        exclusions = []
        if BACKEND_AVAILABLE:
            exclusions = ms.list_exclusions()
        count = len(exclusions)
        dpg.set_value("exclusions_count_text", f"Current Exclusions ({count})")
    
    if dpg.does_item_exist("exclusions_list_group"):
        dpg.delete_item("exclusions_list_group", children_only=True)
        
        exclusions = []
        if BACKEND_AVAILABLE:
            exclusions = ms.list_exclusions()
        
        for i, path in enumerate(exclusions):
            with dpg.child_window(width=CARD_WIDTH, height=ROW_HEIGHT, no_scrollbar=True,
                                  no_scroll_with_mouse=True, parent="exclusions_list_group",
                                  tag=f"exclusion_row_{i}"):
                with dpg.group(horizontal=True):
                    dpg.add_spacer(width=12)
                    dpg.add_text(path, color=COLORS["text_secondary"], pos=(54, (ROW_HEIGHT - 16) // 2 - 3))

                dpg.add_button(label="Remove", width=80, height=24, tag=f"exclusion_remove_{i}",
                              callback=_remove_exclusion, user_data=i, pos=(CARD_WIDTH - 100, 13))

            with dpg.theme() as row_theme:
                with dpg.theme_component(dpg.mvChildWindow):
                    dpg.add_theme_color(dpg.mvThemeCol_ChildBg, COLORS["bg_card"])
                    dpg.add_theme_color(dpg.mvThemeCol_Border, COLORS["border"])
            dpg.bind_item_theme(f"exclusion_row_{i}", row_theme)

            dpg.add_spacer(height=ROW_GAP, parent="exclusions_list_group")

def build_exclusions(parent, fonts, icons):
    dpg.add_spacer(height=20, parent=parent)
    with dpg.group(horizontal=True, parent=parent):
        dpg.add_spacer(width=24)
        with dpg.group():
            dpg.add_text("Exclusions", tag="exclusions_page_title")
            dpg.bind_item_font("exclusions_page_title", fonts["heading"])
            dpg.add_text("Items that will be skipped during scans and real-time protection", color=COLORS["text_secondary"])
            dpg.add_spacer(height=15)

            with dpg.file_dialog(directory_selector=True, show=False, callback=_folder_picked,
                                 tag="folder_picker_dialog", width=700, height=400):
                pass

            with dpg.child_window(width=CARD_WIDTH, height=170, tag="add_exclusion_card", no_scrollbar=True, no_scroll_with_mouse=True):
                dpg.add_spacer(height=15)
                with dpg.group(horizontal=True):
                    dpg.add_spacer(width=15)
                    dpg.add_text("Add an exclusion", color=COLORS["text_primary"])
                dpg.add_spacer(height=12)

                with dpg.group(horizontal=True):
                    dpg.add_spacer(width=15)
                    dpg.add_button(label="Select Folder", tag="select_folder_btn", width=200, height=36,
                                  callback=lambda: dpg.show_item("folder_picker_dialog"))

                dpg.add_spacer(height=12)
                with dpg.group(horizontal=True):
                    dpg.add_spacer(width=15)
                    dpg.add_input_text(hint="Or enter path manually...", tag="exclusion_input",
                                      width=CARD_WIDTH - 170)
                    dpg.add_spacer(width=10)
                    dpg.add_button(label="Add", tag="add_exclusion_btn", callback=_add_exclusion, width=90, height=36)

            with dpg.theme() as card_theme:
                with dpg.theme_component(dpg.mvChildWindow):
                    dpg.add_theme_color(dpg.mvThemeCol_ChildBg, COLORS["bg_card"])
                    dpg.add_theme_color(dpg.mvThemeCol_Border, COLORS["border"])
            dpg.bind_item_theme("add_exclusion_card", card_theme)

            with dpg.theme() as folder_btn_theme:
                with dpg.theme_component(dpg.mvButton):
                    dpg.add_theme_color(dpg.mvThemeCol_Button, tuple(c // 4 for c in COLORS["accent_red"]))
                    dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, tuple(c // 3 for c in COLORS["accent_red"]))
                    dpg.add_theme_color(dpg.mvThemeCol_Text, COLORS["accent_red"])
                    dpg.add_theme_color(dpg.mvThemeCol_Border, COLORS["accent_red"])
            dpg.bind_item_theme("select_folder_btn", folder_btn_theme)

            with dpg.theme() as add_btn_theme:
                with dpg.theme_component(dpg.mvButton):
                    dpg.add_theme_color(dpg.mvThemeCol_Button, COLORS["accent_blue"])
                    dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, tuple(min(c + 20, 255) for c in COLORS["accent_blue"]))
            dpg.bind_item_theme("add_exclusion_btn", add_btn_theme)

            with dpg.theme() as input_theme:
                with dpg.theme_component(dpg.mvInputText):
                    dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 8, 10)
            dpg.bind_item_theme("exclusion_input", input_theme)

            dpg.add_spacer(height=20)
            dpg.add_text("Current Exclusions (0)", tag="exclusions_count_text", color=COLORS["text_primary"])
            dpg.add_spacer(height=10)

            with dpg.group(tag="exclusions_list_group"):
                pass

    _render_list()
