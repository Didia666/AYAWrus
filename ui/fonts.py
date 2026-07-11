import dearpygui.dearpygui as dpg

#fonts.py

def load_fonts():
    with dpg.font_registry():
        with dpg.font("assets/fonts/Inter_18pt-Regular.ttf", 16) as font_body:
            pass
        with dpg.font("assets/fonts/Inter_18pt-Bold.ttf", 20) as font_heading:
            pass
        with dpg.font("assets/fonts/JetBrainsMono-Bold.ttf", 32) as font_number_large:
            pass
        with dpg.font("assets/fonts/JetBrainsMono-Regular.ttf", 14) as font_mono_small:
            pass

    return {
        "body": font_body,
        "heading": font_heading,
        "number_large": font_number_large,
        "mono_small": font_mono_small,
    }