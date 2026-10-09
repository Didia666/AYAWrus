import dearpygui.dearpygui as dpg

#fonts.py

# ---- Font sizes (change here, updates everywhere) ----
FONT_BODY_SIZE = 18          # was 16 - default text everywhere
FONT_SUBHEADING_SIZE = 20    # NEW - card titles (Threat Index, Recent Activity)
FONT_HEADING_SIZE = 26       # was 20 - page titles (System Overview)
FONT_NUMBER_LARGE_SIZE = 44  # was 32 - big stat numbers
FONT_MONO_SMALL_SIZE = 16    # was 14
FONT_TABLE_SIZE = 20         # NEW - table rows (bound per table; the Quarantine table uses it)

FONT_DIR = "assets/fonts"


def load_fonts():
    with dpg.font_registry():
        with dpg.font(f"{FONT_DIR}/Inter_18pt-Regular.ttf", FONT_BODY_SIZE) as font_body:
            pass
        with dpg.font(f"{FONT_DIR}/Inter_18pt-Bold.ttf", FONT_SUBHEADING_SIZE) as font_subheading:
            pass
        with dpg.font(f"{FONT_DIR}/Inter_18pt-Bold.ttf", FONT_HEADING_SIZE) as font_heading:
            pass
        with dpg.font(f"{FONT_DIR}/JetBrainsMono-Bold.ttf", FONT_NUMBER_LARGE_SIZE) as font_number_large:
            pass
        with dpg.font(f"{FONT_DIR}/JetBrainsMono-Regular.ttf", FONT_MONO_SMALL_SIZE) as font_mono_small:
            pass
        with dpg.font(f"{FONT_DIR}/Inter_18pt-Regular.ttf", FONT_TABLE_SIZE) as font_table:
            pass

    return {
        "body": font_body,
        "subheading": font_subheading,
        "heading": font_heading,
        "number_large": font_number_large,
        "mono_small": font_mono_small,
        "table": font_table,
    }