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

# quarantine.py
TABLE_HEIGHT = 500
ROW_ICON_GAP = 6
ACTION_BTN_GAP = 4

THREAT_HEADER_PAD = 9
LOCATION_HEADER_PAD = 0
DATE_HEADER_PAD = 0
RISK_HEADER_PAD = 0
ACTIONS_HEADER_PAD = 0

def _risk_badge(risk):
    color = COLORS["accent_red"] if risk in ["HIGH", "SEVERE"] else COLORS["accent_orange"]
    with dpg.group(horizontal=True):
        dpg.add_text(risk, color=color)

def _restore_file(sender, app_data, user_data):
    dest_path = user_data
    print(f"Restoring: {dest_path}")
    if BACKEND_AVAILABLE:
        result = ms.restore_file(dest_path)
        print(f"Restore result: {result}")
    _rebuild_quarantine_table()
    # Refresh history
    from ui.history import _rebuild_history
    _rebuild_history()

def _delete_file(sender, app_data, user_data):
    dest_path = user_data
    print(f"Deleting: {dest_path}")
    if BACKEND_AVAILABLE:
        result = ms.delete_file(dest_path)
        print(f"Delete result: {result}")
    _rebuild_quarantine_table()
    # Refresh history
    from ui.history import _rebuild_history
    _rebuild_history()

def _rebuild_quarantine_table():
    if dpg.does_item_exist("quarantine_table"):
        # Delete and recreate the entire table to fix any issues
        dpg.delete_item("quarantine_table")
        with dpg.table(header_row=True, borders_innerH=True, borders_outerH=False,
                      borders_innerV=False, borders_outerV=False,
                      scrollY=True, height=TABLE_HEIGHT, width=-1,
                      tag="quarantine_table", parent="quarantine_container"):
            pass
    
    if dpg.does_item_exist("quarantine_table"):
        dpg.delete_item("quarantine_table", children_only=True)
        
        dpg.add_table_column(label=" " * THREAT_HEADER_PAD + "THREAT NAME", width_stretch=True, init_width_or_weight=0.28, parent="quarantine_table")
        dpg.add_table_column(label=" " * LOCATION_HEADER_PAD + "ORIGINAL LOCATION", width_stretch=True, init_width_or_weight=0.36, parent="quarantine_table")
        dpg.add_table_column(label=" " * DATE_HEADER_PAD + "DATE DETECTED", width_stretch=True, init_width_or_weight=0.14, parent="quarantine_table")
        dpg.add_table_column(label=" " * RISK_HEADER_PAD + "RISK", width_stretch=True, init_width_or_weight=0.10, parent="quarantine_table")
        dpg.add_table_column(label=" " * ACTIONS_HEADER_PAD + "ACTIONS", width_stretch=True, init_width_or_weight=0.12, parent="quarantine_table")
        
        entries = []
        if BACKEND_AVAILABLE:
            entries = ms.list_quarantine_items()
            print(f"Quarantine entries: {len(entries)}")
        
        if not entries:
            with dpg.table_row(parent="quarantine_table"):
                # Add empty cells for all 5 columns
                dpg.add_text("No items in quarantine", color=COLORS["text_secondary"])
                for _ in range(4):
                    dpg.add_text("")
        else:
            for entry in entries:
                with dpg.table_row(parent="quarantine_table"):
                    with dpg.group(horizontal=True):
                        dpg.add_text(f"🔒", color=COLORS["accent_red"])
                        dpg.add_spacer(width=ROW_ICON_GAP)
                        dpg.add_text(os.path.basename(entry.get("original_path", "Unknown")), color=COLORS["text_primary"])
                    
                    dpg.add_text(entry.get("original_path", "Unknown"), color=COLORS["text_secondary"])
                    dpg.add_text(entry.get("timestamp", "Unknown"), color=COLORS["text_secondary"])
                    
                    risk = "HIGH"
                    prob = entry.get("probability")
                    if prob is not None:
                        try:
                            prob_float = float(prob)
                            if prob_float >= 0.9:
                                risk = "SEVERE"
                            elif prob_float >= 0.7:
                                risk = "HIGH"
                            elif prob_float >= 0.4:
                                risk = "MEDIUM"
                            elif prob_float >= 0.2:
                                risk = "LOW"
                        except:
                            pass
                    _risk_badge(risk)
                    
                    with dpg.group(horizontal=True):
                        dpg.add_button(label="Restore", callback=_restore_file, user_data=entry.get("dest_path"), tag=f"restore_btn_{id(entry)}")
                        dpg.add_spacer(width=ACTION_BTN_GAP)
                        dpg.add_button(label="Delete", callback=_delete_file, user_data=entry.get("dest_path"), tag=f"delete_btn_{id(entry)}")

def build_quarantine(parent, fonts, icons):
    dpg.add_spacer(height=20, parent=parent)
    with dpg.group(horizontal=True, parent=parent):
        dpg.add_spacer(width=24)
        with dpg.group():
            dpg.add_text("Quarantine", tag="quarantine_page_title")
            dpg.bind_item_font("quarantine_page_title", fonts["heading"])
            dpg.add_text("Isolated files that are potentially harmful to your system", color=COLORS["text_secondary"])
            dpg.add_spacer(height=15)

            with dpg.child_window(width=1240, height=TABLE_HEIGHT + 20, tag="quarantine_container"):
                with dpg.table(header_row=True, borders_innerH=True, borders_outerH=False,
                              borders_innerV=False, borders_outerV=False,
                              scrollY=True, height=TABLE_HEIGHT, width=-1,
                              tag="quarantine_table"):
                    pass
                _rebuild_quarantine_table()

    with dpg.theme() as table_theme:
        with dpg.theme_component(dpg.mvTable):
            dpg.add_theme_style(dpg.mvStyleVar_CellPadding, 8, 10)
    dpg.bind_item_theme("quarantine_table", table_theme)

    with dpg.theme() as container_theme:
        with dpg.theme_component(dpg.mvChildWindow):
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, COLORS["bg_card"])
            dpg.add_theme_color(dpg.mvThemeCol_Border, COLORS["border"])
    dpg.bind_item_theme("quarantine_container", container_theme)
