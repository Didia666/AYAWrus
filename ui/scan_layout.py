import threading
import time
import dearpygui.dearpygui as dpg
from ui.theme import COLORS
from ui.layout import register_resize

# scan_layout.py

# ---- Scan page layout constants (tune here) ----
PAGE_LEFT_PAD = 24             # same as the dashboard's left spacer
PAGE_RIGHT_MARGIN = 16         # breathing room on the right (raise it if a horizontal scrollbar appears)
ITEM_SPACING_X = 8             # DPG's default horizontal item spacing
CHILD_PAD_X = 8                # DPG's default child window padding

# ---- Scan type cards ----
CARD_GAP = 20                  # visual gap between cards (same as the dashboard)
SCAN_KEYS = ("quick", "full", "custom")
SCAN_CARD_MIN_WIDTH = 240
SCAN_CARD_HEIGHT = 124         # raise if the subtitle touches the bottom edge, lower if there's a gap
SCAN_CARD_TOP_SPACER = 6       # space above the icon
SCAN_CARD_ICON_SIZE = 28
SCAN_CARD_LABEL_HEIGHT = 26
SCAN_CARD_SUB_HEIGHT = 24
SCAN_CARD_TEXT_TRIM = 2        # label/subtitle width = card width - padding - this

# ---- Ready panel ----
READY_PANEL_HEIGHT = 370       # tall enough for icon + heading + buttons + custom row + progress block
READY_TOP_SPACER = 6
READY_ICON_SIZE = 44
READY_ICON_GAP = 2
READY_HEADING_GAP = 6
HEADING_WATCH_SECONDS = 0.25   # how often the heading is re-checked for a text change
HEADING_FALLBACK_CHAR_WIDTH = 14   # only used if DPG can't measure the heading text

BUTTON_WIDTH = 180
BUTTON_HEIGHT = 38
BUTTON_GAP = 24                # visible gap between Start and Cancel
ROW_GAP = 8

# progress block (status text + bar + elapsed + threats)
PROGRESS_WIDTH_RATIO = 0.80    # share of the panel width
PROGRESS_MIN_WIDTH = 360
PROGRESS_MAX_WIDTH = 900
PROGRESS_BLOCK_HEIGHT = 140    # raise if "Threats found" gets cut off, lower if there's a gap
PROGRESS_ITEM_SPACING_Y = 2    # tightens the vertical gaps inside the block

# custom scan row (Select Path + path box)
CUSTOM_SELECT_WIDTH = 120
CUSTOM_PATH_WIDTH = 420
CUSTOM_PATH_MIN_WIDTH = 200
CUSTOM_SIDE_MARGIN = 40
CUSTOM_ROW_HEIGHT = BUTTON_HEIGHT
CUSTOM_INPUT_PAD_Y = 10        # input height = font size (18) + 2 * this, so 10 matches the 38px buttons

# button colors: (normal, hover, pressed, text)
START_COLORS = (COLORS["accent_blue"], (76, 150, 246), (46, 120, 236), COLORS["text_primary"])
CANCEL_COLORS = ((150, 45, 55), (190, 55, 65), (120, 35, 45), COLORS["text_primary"])
SECONDARY_COLORS = ((45, 58, 84), (60, 76, 108), (38, 49, 72), COLORS["text_primary"])
DISABLED_BG = (38, 46, 66)
DISABLED_TEXT = (100, 116, 139)

_THEMES = {}
_state = {"panel_w": 900, "heading_text": None, "heading_font": None, "watcher_started": False}


# ---------------------------------------------------------------------------
# Themes
# ---------------------------------------------------------------------------

def _text_button_theme(color):
    """Invisible button that only shows centered text (it never reacts to hover/click)."""
    with dpg.theme() as theme:
        with dpg.theme_component(dpg.mvButton):
            dpg.add_theme_color(dpg.mvThemeCol_Button, (0, 0, 0, 0))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (0, 0, 0, 0))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (0, 0, 0, 0))
            dpg.add_theme_color(dpg.mvThemeCol_Text, color)
            dpg.add_theme_color(dpg.mvThemeCol_Border, (0, 0, 0, 0))
            dpg.add_theme_style(dpg.mvStyleVar_FrameBorderSize, 0)
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 0, 0)
    return theme


def _card_theme(bg, border):
    with dpg.theme() as theme:
        with dpg.theme_component(dpg.mvChildWindow):
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, bg)
            dpg.add_theme_color(dpg.mvThemeCol_Border, border)
    return theme


def _button_theme(colors):
    """Normal look + a dimmed look for when the button is disabled."""
    normal, hover, active, text = colors
    with dpg.theme() as theme:
        with dpg.theme_component(dpg.mvButton):
            dpg.add_theme_color(dpg.mvThemeCol_Button, normal)
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, hover)
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, active)
            dpg.add_theme_color(dpg.mvThemeCol_Text, text)
        with dpg.theme_component(dpg.mvButton, enabled_state=False):
            dpg.add_theme_color(dpg.mvThemeCol_Button, DISABLED_BG)
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, DISABLED_BG)
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, DISABLED_BG)
            dpg.add_theme_color(dpg.mvThemeCol_Text, DISABLED_TEXT)
    return theme


def _progress_box_theme():
    """Transparent, borderless, zero-padding box so the progress block blends into the panel."""
    with dpg.theme() as theme:
        with dpg.theme_component(dpg.mvChildWindow):
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, (0, 0, 0, 0))
            dpg.add_theme_style(dpg.mvStyleVar_ChildBorderSize, 0)
            dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 0, 0)
            dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, ITEM_SPACING_X, PROGRESS_ITEM_SPACING_Y)
    return theme


def _path_input_theme():
    with dpg.theme() as theme:
        with dpg.theme_component(dpg.mvInputText):
            dpg.add_theme_color(dpg.mvThemeCol_FrameBg, COLORS["bg_sidebar"])
            dpg.add_theme_color(dpg.mvThemeCol_Border, COLORS["border"])
            dpg.add_theme_color(dpg.mvThemeCol_Text, COLORS["text_secondary"])
            dpg.add_theme_style(dpg.mvStyleVar_FrameBorderSize, 1)
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 12, CUSTOM_INPUT_PAD_Y)
    return theme


def _get_themes():
    """Built once, the first time something needs them."""
    if _THEMES:
        return _THEMES
    _THEMES["card_on"] = _card_theme(COLORS["bg_card"], COLORS["accent_blue"])
    _THEMES["card_off"] = _card_theme(COLORS["bg_sidebar"], COLORS["border"])
    _THEMES["label_on"] = _text_button_theme(COLORS["text_primary"])
    _THEMES["label_off"] = _text_button_theme(COLORS["text_secondary"])
    _THEMES["sub"] = _text_button_theme(COLORS["text_secondary"])
    _THEMES["btn_start"] = _button_theme(START_COLORS)
    _THEMES["btn_cancel"] = _button_theme(CANCEL_COLORS)
    _THEMES["btn_secondary"] = _button_theme(SECONDARY_COLORS)
    _THEMES["progress_box"] = _progress_box_theme()
    _THEMES["path_input"] = _path_input_theme()
    return _THEMES


# ---------------------------------------------------------------------------
# Scan type cards
# ---------------------------------------------------------------------------

def build_scan_card(key, icon_texture, label, subtitle, is_active):
    """One scan-type card. Sizes are placeholders; _resize_scan sets the real ones."""
    t = _get_themes()
    with dpg.child_window(width=400, height=SCAN_CARD_HEIGHT, tag=f"scan_{key}_card",
                          no_scrollbar=True, no_scroll_with_mouse=True):
        dpg.add_spacer(height=SCAN_CARD_TOP_SPACER)
        with dpg.group(horizontal=True):
            dpg.add_spacer(width=100, tag=f"scan_{key}_icon_pad")
            dpg.add_image(icon_texture, width=SCAN_CARD_ICON_SIZE, height=SCAN_CARD_ICON_SIZE,
                          tint_color=COLORS["accent_blue"] if is_active else COLORS["text_secondary"],
                          tag=f"scan_{key}_icon")
        dpg.add_button(label=label, width=300, height=SCAN_CARD_LABEL_HEIGHT, tag=f"scan_{key}_label")
        dpg.add_button(label=subtitle, width=300, height=SCAN_CARD_SUB_HEIGHT, tag=f"scan_{key}_sub")

    dpg.bind_item_theme(f"scan_{key}_card", t["card_on"] if is_active else t["card_off"])
    dpg.bind_item_theme(f"scan_{key}_label", t["label_on"] if is_active else t["label_off"])
    dpg.bind_item_theme(f"scan_{key}_sub", t["sub"])


def apply_card_states(active_key):
    """Highlights the selected card (border, icon tint, label color)."""
    t = _get_themes()
    for key in SCAN_KEYS:
        is_active = key == active_key
        if not dpg.does_item_exist(f"scan_{key}_card"):
            continue
        dpg.bind_item_theme(f"scan_{key}_card", t["card_on"] if is_active else t["card_off"])
        dpg.bind_item_theme(f"scan_{key}_label", t["label_on"] if is_active else t["label_off"])
        dpg.configure_item(f"scan_{key}_icon",
                           tint_color=COLORS["accent_blue"] if is_active else COLORS["text_secondary"])


# ---------------------------------------------------------------------------
# Ready panel
# ---------------------------------------------------------------------------

def _center_indent(outer_w, inner_w):
    """Indent that centers an item of inner_w inside a child window of outer_w."""
    return max(0, int((outer_w - inner_w) // 2) - CHILD_PAD_X)


def _custom_path_width():
    room = _state["panel_w"] - CUSTOM_SELECT_WIDTH - ITEM_SPACING_X - 2 * CHILD_PAD_X - CUSTOM_SIDE_MARGIN
    return max(CUSTOM_PATH_MIN_WIDTH, min(CUSTOM_PATH_WIDTH, room))


def _custom_row_width():
    return CUSTOM_SELECT_WIDTH + ITEM_SPACING_X + _custom_path_width()


def build_ready_panel(icons, fonts, start_cb, cancel_cb):
    """The big 'Ready to Scan' panel. Call it where the old scan_empty_state block was."""
    t = _get_themes()
    _state["heading_font"] = fonts.get("heading") if fonts else None

    with dpg.child_window(width=900, height=READY_PANEL_HEIGHT, tag="scan_empty_state",
                          no_scrollbar=True, no_scroll_with_mouse=True):
        dpg.add_spacer(height=READY_TOP_SPACER)
        dpg.add_image(icons["search"], width=READY_ICON_SIZE, height=READY_ICON_SIZE,
                      tint_color=COLORS["accent_blue"], tag="scan_ready_icon")
        dpg.add_spacer(height=READY_ICON_GAP)

        heading = dpg.add_text("Ready to Scan", color=COLORS["text_primary"], tag="scan_ready_heading")
        if _state["heading_font"] is not None:
            dpg.bind_item_font(heading, _state["heading_font"])
        dpg.add_spacer(height=READY_HEADING_GAP)

        with dpg.group(horizontal=True, tag="scan_button_group"):
            dpg.add_button(label="Start Quick Scan", width=BUTTON_WIDTH, height=BUTTON_HEIGHT,
                           tag="start_scan_btn", callback=start_cb)
            dpg.add_spacer(width=max(0, BUTTON_GAP - 2 * ITEM_SPACING_X))
            dpg.add_button(label="Cancel Scan", width=BUTTON_WIDTH, height=BUTTON_HEIGHT,
                           tag="cancel_scan_btn", callback=cancel_cb, enabled=False)

        with dpg.group(tag="scan_custom_row"):   # filled by rebuild_custom_row()
            pass

        # the scan logic rebuilds this box's contents when a scan starts
        with dpg.child_window(width=700, height=PROGRESS_BLOCK_HEIGHT, border=False,
                              no_scrollbar=True, no_scroll_with_mouse=True,
                              tag="scan_progress_container"):
            pass

    dpg.bind_item_theme("start_scan_btn", t["btn_start"])
    dpg.bind_item_theme("cancel_scan_btn", t["btn_cancel"])
    dpg.bind_item_theme("scan_progress_container", t["progress_box"])


def rebuild_custom_row(is_custom, current_path, on_select):
    """Select Path + read-only path box (only for Custom Scan). Space is always reserved."""
    t = _get_themes()
    if dpg.does_item_exist("custom_controls_group"):
        dpg.delete_item("custom_controls_group")
    if not dpg.does_item_exist("scan_custom_row"):
        return

    with dpg.group(parent="scan_custom_row", tag="custom_controls_group"):
        if is_custom:
            with dpg.group(horizontal=True, tag="custom_row_inner",
                           indent=_center_indent(_state["panel_w"], _custom_row_width())):
                dpg.add_button(label="Select Path", tag="select_path_btn", width=CUSTOM_SELECT_WIDTH,
                               height=BUTTON_HEIGHT, callback=on_select)
                dpg.add_input_text(tag="custom_path_display", default_value=current_path or "",
                                   hint="No path selected", readonly=True, width=_custom_path_width())
            dpg.bind_item_theme("select_path_btn", t["btn_secondary"])
            dpg.bind_item_theme("custom_path_display", t["path_input"])
        else:
            dpg.add_spacer(height=CUSTOM_ROW_HEIGHT)


def reset_ready_state():
    """Back to the idle look: 'Ready to Scan' heading and an empty progress block."""
    if dpg.does_item_exist("scan_ready_heading"):
        dpg.set_value("scan_ready_heading", "Ready to Scan")
    if dpg.does_item_exist("scan_progress_container"):
        dpg.delete_item("scan_progress_container", children_only=True)


# ---- heading re-centering (the scan logic changes the heading text, so we watch it) ----

def _center_heading(text=None):
    if not dpg.does_item_exist("scan_ready_heading"):
        return
    if text is None:
        text = dpg.get_value("scan_ready_heading") or ""
    _state["heading_text"] = text
    font = _state["heading_font"]
    try:
        size = dpg.get_text_size(text, font=font) if font is not None else dpg.get_text_size(text)
    except Exception:
        size = None
    text_w = size[0] if size else len(text) * HEADING_FALLBACK_CHAR_WIDTH
    dpg.configure_item("scan_ready_heading", indent=_center_indent(_state["panel_w"], text_w))


def _heading_watcher():
    while True:
        time.sleep(HEADING_WATCH_SECONDS)
        try:
            with dpg.mutex():
                if not dpg.does_item_exist("scan_ready_heading"):
                    continue
                text = dpg.get_value("scan_ready_heading")
                if text != _state["heading_text"]:
                    _center_heading(text)
        except Exception:
            pass


def _start_heading_watcher():
    if _state["watcher_started"]:
        return
    _state["watcher_started"] = True
    threading.Thread(target=_heading_watcher, daemon=True).start()


# ---------------------------------------------------------------------------
# Resize
# ---------------------------------------------------------------------------

def _resize_ready_panel(row_w):
    if dpg.does_item_exist("scan_empty_state"):
        dpg.configure_item("scan_empty_state", width=row_w, height=READY_PANEL_HEIGHT)
    if dpg.does_item_exist("scan_ready_icon"):
        dpg.configure_item("scan_ready_icon", indent=_center_indent(row_w, READY_ICON_SIZE))

    prog_w = max(PROGRESS_MIN_WIDTH, min(PROGRESS_MAX_WIDTH, int(row_w * PROGRESS_WIDTH_RATIO)))
    prog_w = min(prog_w, row_w - 2 * CHILD_PAD_X)
    if dpg.does_item_exist("scan_progress_container"):
        dpg.configure_item("scan_progress_container", width=prog_w, height=PROGRESS_BLOCK_HEIGHT,
                           indent=_center_indent(row_w, prog_w))

    if dpg.does_item_exist("scan_button_group"):
        buttons_w = 2 * BUTTON_WIDTH + BUTTON_GAP
        dpg.configure_item("scan_button_group", indent=_center_indent(row_w, buttons_w))

    if dpg.does_item_exist("custom_row_inner"):
        dpg.configure_item("custom_row_inner", indent=_center_indent(row_w, _custom_row_width()))
        if dpg.does_item_exist("custom_path_display"):
            dpg.configure_item("custom_path_display", width=_custom_path_width())

    _center_heading()


def _resize_scan(content_w, content_h):
    """Called by ui/layout.py whenever the window size changes."""
    usable_w = content_w - PAGE_LEFT_PAD - ITEM_SPACING_X - PAGE_RIGHT_MARGIN
    gap = CARD_GAP + 2 * ITEM_SPACING_X   # a spacer in a horizontal group gets spacing on both sides
    count = len(SCAN_KEYS)
    card_w = max(SCAN_CARD_MIN_WIDTH, int((usable_w - (count - 1) * gap) / count))
    text_w = card_w - 2 * CHILD_PAD_X - SCAN_CARD_TEXT_TRIM
    icon_pad = max(0, (card_w - SCAN_CARD_ICON_SIZE) // 2 - CHILD_PAD_X - ITEM_SPACING_X)

    for key in SCAN_KEYS:
        if not dpg.does_item_exist(f"scan_{key}_card"):
            continue
        dpg.configure_item(f"scan_{key}_card", width=card_w, height=SCAN_CARD_HEIGHT)
        dpg.configure_item(f"scan_{key}_icon_pad", width=icon_pad)
        dpg.configure_item(f"scan_{key}_label", width=text_w)
        dpg.configure_item(f"scan_{key}_sub", width=text_w)

    # everything below the cards uses the exact same row width, so the edges line up
    row_w = count * card_w + (count - 1) * gap
    _state["panel_w"] = row_w
    _resize_ready_panel(row_w)


def register_scan_layout():
    """Call once from build_scan (before init_layout runs)."""
    register_resize("scan", _resize_scan)
    _start_heading_watcher()