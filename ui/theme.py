import dearpygui.dearpygui as dpg

#theme.py

# Centralized color palette — change here, updates everywhere
COLORS = {
    "bg_main": (15, 21, 35),          # back to original navy
    "bg_card": (30, 40, 62),           # noticeably lighter than main — "lifted" feel
    "bg_sidebar": (10, 15, 26),        # darker than main, but not pitch black
    "accent_blue": (56, 130, 246),
    "accent_orange": (245, 158, 11),
    "accent_red": (239, 68, 68),
    "accent_green": (16, 185, 129),
    "text_primary": (255, 255, 255),
    "text_secondary": (148, 163, 184),
    "border": (55, 68, 95),            # visible but not glaring border for card definition
}

def apply_global_theme():
    with dpg.theme() as global_theme:
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_color(dpg.mvThemeCol_WindowBg, COLORS["bg_main"])
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, COLORS["bg_card"])
            dpg.add_theme_color(dpg.mvThemeCol_Text, COLORS["text_primary"])
            dpg.add_theme_color(dpg.mvThemeCol_Border, COLORS["border"])
            dpg.add_theme_style(dpg.mvStyleVar_WindowRounding, 0)
            dpg.add_theme_style(dpg.mvStyleVar_ChildRounding, 8)
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 6)

    dpg.bind_theme(global_theme)