"""
table_style.py - how EVERY table in the app looks (text size, row height, pill height, cell grey).
Change a number here and all the tables follow.

The font itself is loaded in ui/fonts.py (FONT_TABLE_SIZE, dict key "table").
Tables switch it on with apply_table_font().

Used by: ui/quarantine.py, ui/scan_threats.py (Detected Threats table).
         ui/history.py will use it for its file table.        <- add new users to this list
"""
import dearpygui.dearpygui as dpg

# table_style.py

TABLE_FONT_KEY = "table"                  # key in the fonts dict returned by ui/fonts.py
TABLE_ROW_HEIGHT = 32                     # height of the text cells and buttons inside a row
TABLE_PILL_HEIGHT = 28                    # height of the rounded result / risk pills
TABLE_CELL_MUTED_COLOR = (186, 198, 214)  # secondary cell text (paths, dates). Raise toward 255 for brighter


def apply_table_font(table_tag, fonts):
    """Binds the shared table font to a table. Rows, buttons and tooltips inside inherit it.
    If the font is missing, the table simply keeps the body font."""
    font = (fonts or {}).get(TABLE_FONT_KEY)
    if font is not None and dpg.does_item_exist(table_tag):
        dpg.bind_item_font(table_tag, font)