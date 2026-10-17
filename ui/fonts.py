import dearpygui.dearpygui as dpg
from pathlib import Path
import sys

# fonts.py

# ---- Font sizes (change here, updates everywhere) ----
FONT_BODY_SIZE = 18            # default text everywhere
FONT_SUBHEADING_SIZE = 20      # card titles (Threat Index, Recent Activity)
FONT_HEADING_SIZE = 26         # page titles (System Overview)
FONT_NUMBER_LARGE_SIZE = 44    # big stat numbers
FONT_MONO_SMALL_SIZE = 16      # small mono text
FONT_TABLE_SIZE = 20           # table rows (bound per table), pipeline text, toasts


def _font_path(filename):
    """Finds a font file both when running from source and when packaged with PyInstaller."""
    if getattr(sys, "frozen", False):
        resource_root = Path(sys._MEIPASS)
    else:
        resource_root = Path(__file__).resolve().parent.parent
    return str(resource_root / "assets" / "fonts" / filename)


def load_fonts():
    with dpg.font_registry():
        with dpg.font(_font_path("Inter_18pt-Regular.ttf"), FONT_BODY_SIZE) as font_body:
            pass
        with dpg.font(_font_path("Inter_18pt-Bold.ttf"), FONT_SUBHEADING_SIZE) as font_subheading:
            pass
        with dpg.font(_font_path("Inter_18pt-Bold.ttf"), FONT_HEADING_SIZE) as font_heading:
            pass
        with dpg.font(_font_path("JetBrainsMono-Bold.ttf"), FONT_NUMBER_LARGE_SIZE) as font_number_large:
            pass
        with dpg.font(_font_path("JetBrainsMono-Regular.ttf"), FONT_MONO_SMALL_SIZE) as font_mono_small:
            pass
        with dpg.font(_font_path("Inter_18pt-Regular.ttf"), FONT_TABLE_SIZE) as font_table:
            pass

    return {
        "body": font_body,
        "subheading": font_subheading,
        "heading": font_heading,
        "number_large": font_number_large,
        "mono_small": font_mono_small,
        "table": font_table,
    }