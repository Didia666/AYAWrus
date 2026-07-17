import dearpygui.dearpygui as dpg
from ui.theme import COLORS
import threading
import time

#sidebar.py

CURRENT_PAGE = "dashboard"

NAV_ITEMS = [
    {"key": "dashboard", "label": "Dashboard", "icon": "layout_dashboard"},
    {"key": "scan", "label": "Scan", "icon": "scan_search"},
    {"key": "quarantine", "label": "Quarantine", "icon": "shield_cog"},
    {"key": "history", "label": "History", "icon": "history"},
    {"key": "exclusions", "label": "Exclusions", "icon": "sliders_horizontal"},
    {"key": "settings", "label": "Settings", "icon": "sliders_horizontal"},
]

def pulse_dot(tag):
    def _pulse():
        while True:
            for alpha in list(range(80, 256, 15)) + list(range(255, 79, -15)):
                try:
                    dpg.configure_item(tag, fill=(*COLORS["accent_green"], alpha), color=(*COLORS["accent_green"], alpha))
                    time.sleep(0.05)
                except:
                    return
    threading.Thread(target=_pulse, daemon=True).start()

def _nav_theme(is_active):
    with dpg.theme() as theme:
        with dpg.theme_component(dpg.mvChildWindow):
            bg = COLORS["bg_card"] if is_active else COLORS["bg_sidebar"]
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, bg)
    return theme

def _switch_page(sender, app_data, user_data):
    global CURRENT_PAGE
    CURRENT_PAGE = user_data

    for item in NAV_ITEMS:
        key = item["key"]
        is_active = key == CURRENT_PAGE
        tag = f"nav_{key}"
        dpg.configure_item(f"{tag}_indicator_rect", show=is_active)
        dpg.configure_item(f"{tag}_icon", tint_color=COLORS["accent_blue"] if is_active else COLORS["text_secondary"])
        dpg.configure_item(f"{tag}_text", color=COLORS["text_primary"] if is_active else COLORS["text_secondary"])
        dpg.bind_item_theme(f"{tag}_bg", _nav_theme(is_active))

    # Only Dashboard and Scan pages exist so far — others just highlight with no content yet
    if dpg.does_item_exist("page_dashboard"):
        dpg.configure_item("page_dashboard", show=(CURRENT_PAGE == "dashboard"))
    if dpg.does_item_exist("page_scan"):
        dpg.configure_item("page_scan", show=(CURRENT_PAGE == "scan"))
    if dpg.does_item_exist("page_quarantine"):
        dpg.configure_item("page_quarantine", show=(CURRENT_PAGE == "quarantine"))
        # Refresh quarantine table when switching to quarantine tab!
        if CURRENT_PAGE == "quarantine":
            from ui.quarantine import _rebuild_quarantine_table
            _rebuild_quarantine_table()
    if dpg.does_item_exist("page_history"):
        dpg.configure_item("page_history", show=(CURRENT_PAGE == "history"))
        # Refresh history table when switching to history tab!
        if CURRENT_PAGE == "history":
            from ui.history import _rebuild_history
            _rebuild_history()
    if dpg.does_item_exist("page_exclusions"):
        dpg.configure_item("page_exclusions", show=(CURRENT_PAGE == "exclusions"))
    if dpg.does_item_exist("page_settings"):
        dpg.configure_item("page_settings", show=(CURRENT_PAGE == "settings"))
        # Refresh settings when switching to settings tab!
        if CURRENT_PAGE == "settings":
            from ui.settings import refresh_settings
            refresh_settings()

def nav_item(key, label, icon_texture):
    is_active = key == CURRENT_PAGE
    tag = f"nav_{key}"
    with dpg.group(horizontal=True):
        with dpg.drawlist(width=3, height=36, tag=f"{tag}_indicator"):
            dpg.draw_rectangle((0, 0), (3, 36), fill=COLORS["accent_blue"], color=COLORS["accent_blue"],
                                show=is_active, tag=f"{tag}_indicator_rect")

        with dpg.child_window(width=190, height=36, tag=f"{tag}_bg", no_scrollbar=True):
            with dpg.group(horizontal=True):
                dpg.add_spacer(width=8)
                dpg.add_image(icon_texture, width=18, height=18,
                              tint_color=COLORS["accent_blue"] if is_active else COLORS["text_secondary"],
                              tag=f"{tag}_icon")
                dpg.add_spacer(width=8)
                dpg.add_text(label, color=COLORS["text_primary"] if is_active else COLORS["text_secondary"],
                             tag=f"{tag}_text")

    dpg.bind_item_theme(f"{tag}_bg", _nav_theme(is_active))

def _handle_click(sender, app_data):
    for item in NAV_ITEMS:
        tag = f"nav_{item['key']}_bg"
        if dpg.is_item_hovered(tag):
            _switch_page(sender, app_data, item["key"])
            return
        
def build_sidebar(icons):
    with dpg.child_window(width=220, border=False, tag="sidebar"):
        with dpg.handler_registry():
            dpg.add_mouse_click_handler(callback=_handle_click)
        dpg.add_spacer(height=15)
        logo_texture = icons.get("logo") if icons is not None else None
        if logo_texture:
            dpg.add_image(logo_texture, width=200, height=70, tint_color=COLORS["accent_blue"])
        else:
            dpg.add_text("AYAWrus", color=COLORS["text_primary"])
            dpg.add_text("MALWARE DEFENSE", color=COLORS["text_secondary"])
        dpg.add_spacer(height=20)
        dpg.add_separator()
        dpg.add_spacer(height=15)

        for i, item in enumerate(NAV_ITEMS):
            nav_item(item["key"], item["label"], icons[item["icon"]])
            if i < len(NAV_ITEMS) - 1:
                dpg.add_spacer(height=4)

        dpg.add_spacer(height=380)
        dpg.add_separator()
        dpg.add_spacer(height=10)

        with dpg.group(horizontal=True):
            dpg.add_spacer(width=8)
            with dpg.drawlist(width=10, height=10, tag="status_dot"):
                dpg.draw_circle((5, 5), 4, fill=COLORS["accent_green"], color=COLORS["accent_green"], tag="status_dot_shape")
            dpg.add_spacer(width=6)
            dpg.add_text("System Protected", color=COLORS["accent_green"])

        pulse_dot("status_dot_shape")