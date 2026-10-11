import dearpygui.dearpygui as dpg
from pathlib import Path
import sys

#fonts.py

def _font_path(filename):
    if getattr(sys, "frozen", False):
        resource_root = Path(sys._MEIPASS)
    else:
        resource_root = Path(__file__).resolve().parent.parent
    return str(resource_root / "assets" / "fonts" / filename)


def load_fonts():
    with dpg.font_registry():
        with dpg.font(_font_path("Inter_18pt-Regular.ttf"), 16) as font_body:
            pass
        with dpg.font(_font_path("Inter_18pt-Bold.ttf"), 20) as font_heading:
            pass
        with dpg.font(_font_path("JetBrainsMono-Bold.ttf"), 32) as font_number_large:
            pass
        with dpg.font(_font_path("JetBrainsMono-Regular.ttf"), 14) as font_mono_small:
            pass

    return {
        "body": font_body,
        "subheading": font_subheading,
        "heading": font_heading,
        "number_large": font_number_large,
        "mono_small": font_mono_small,
        "table": font_table,
    }