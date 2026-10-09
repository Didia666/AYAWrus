import traceback
import webbrowser
import dearpygui.dearpygui as dpg
from ui.theme import COLORS
from ui.layout import register_resize
from ui.scan_layout import _get_themes
from ui.toast import show_toast
from ui.scrollbar_theme import (SCROLL_SIZE, SCROLL_ROUNDING, SCROLL_TRACK,
                                SCROLL_GRAB, SCROLL_GRAB_HOVER, SCROLL_GRAB_ACTIVE)

# settings_dialogs.py
# The two pop-ups of the Settings tab: the QR viewer and the AI setup instructions.
# They are separate from settings.py so that file doesn't balloon, and they only read what settings.py already made
# (the "mobile_qr_texture" texture). Same look as ui/confirm_dialog.py.

# ---- Shared look (tune here) ----
DLG_ROUNDING = 14
DLG_PAD = 22                   # padding inside the dialog
DLG_MARGIN = 24                # never closer than this to the window edges
DLG_BORDER = (*COLORS["accent_blue"], 110)
DLG_ITEM_X = 10                # horizontal gap between items
DLG_ITEM_Y = 6                 # vertical gap between items
BADGE_SIZE = 44                # header badge (same as the Settings cards)
BADGE_ICON = 24
BADGE_ROUNDING = 12
BADGE_BG_ALPHA = 45
BTN_H = 38
HEADER_GAP = 14                # space under the header

# ---- QR dialog ----
QR_DLG_W = 420
QR_DLG_H = 560                 # raise if the Close button touches the bottom, lower if there's a gap
QR_TILE = 270                  # white tile
QR_IMG = 240                   # keep smaller than the tile
QR_PAD = (QR_TILE - QR_IMG) // 2
QR_TILE_ROUNDING = 14
QR_TILE_GAP = 14               # space under the tile
QR_BTN_GAP = 12                # space above the Close button
QR_TITLE = "Scan to pair"
QR_HELPER = "Use AYAWrus Mobile on your phone"
QR_HINT = "Each code works once and expires after 5 minutes. Make a new one from the Settings page if it ran out."

# ---- Instruction dialog ----
INSTR_W = 640
INSTR_H = 620
INSTR_TITLE = "Set up the AI Assistant"
INSTR_HELPER = "Three steps, about two minutes"
FOOTER_H = BTN_H
FOOTER_GAP = 14                # space between the scrolling body and the buttons
VISIT_W = 190
CLOSE_W = 130
SCROLL_RESERVE = SCROLL_SIZE + 6   # width kept free for the scrollbar when the body overflows
STEP_BADGE = 30                # numbered circle
STEP_GAP_Y = 14                # space between steps
CODE_H = 38                    # code box height (same as the inputs)
COPY_ICON = 20
COPY_PAD = (CODE_H - COPY_ICON) // 2
CODE_PAD_X = 12
CODE_PAD_Y = 9                 # lowers or raises the text inside the code box

OPENROUTER_URL = "https://openrouter.ai"
DEFAULT_API_URL = "https://openrouter.ai/api/v1/chat/completions"
RECOMMENDED_MODEL = "nvidia/nemotron-3.5-lightning:free"
BTN_VISIT = "Visit OpenRouter.ai"
BTN_CLOSE = "Close"
TIP_COPY = "Copy"
MSG_COPIED = "Copied to clipboard"
MSG_COPY_FAILED = "Couldn't copy (see terminal)"
MSG_BROWSER_FAILED = "Couldn't open the browser (see terminal)"

STEP1_TITLE = "Get an API key"
STEP1_LINES = (
    "Go to openrouter.ai and sign in, or create an account.",
    "Open Settings > API Keys, press Create Key and copy the key.",
)
STEP2_TITLE = "Fill in the fields"
STEP2_URL_LABEL = "API URL (the default for OpenRouter):"
STEP2_LINES = (
    "Paste your key into the API Key field. The eye button lets you check what you pasted.",
)
STEP3_TITLE = "Pick a model"
STEP3_LINES = (
    "Choose one from the AI Model list, or pick custom and type any model name.",
)
STEP3_MODEL_LABEL = "Recommended (free):"
STEP3_FREE = "Also free: meta-llama/llama-3.1-8b-instruct:free"
STEP3_PAID = "Paid: openai/chatgpt-4o-latest, anthropic/claude-3.5-sonnet"
TIPS_TITLE = "Good to know"
TIPS_LINES = (
    "- Keep your API key private and never share it.",
    "- Free models have rate limits, so they can be slow or refuse requests when busy.",
    "- The key is saved as plain text in config.json on this PC, so don't share that file either.",
)

WIN_QR = "mobile_qr_modal"     # same tag settings.py already deletes before it makes a new QR
WIN_INSTR = "ai_api_instruction_modal"

_T = {}
_s = {"ready": False, "open": None, "w": 0, "h": 0, "icons": None, "fonts": None}


# ---------------------------------------------------------------------------
# Themes (built once)
# ---------------------------------------------------------------------------

def _themes():
    if _T:
        return _T
    c = COLORS

    with dpg.theme() as dialog:
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_color(dpg.mvThemeCol_WindowBg, c["bg_card"])
            dpg.add_theme_color(dpg.mvThemeCol_Border, DLG_BORDER)
            dpg.add_theme_color(dpg.mvThemeCol_Text, c["text_primary"])
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarBg, SCROLL_TRACK)
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarGrab, SCROLL_GRAB)
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarGrabHovered, SCROLL_GRAB_HOVER)
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarGrabActive, SCROLL_GRAB_ACTIVE)
            dpg.add_theme_style(dpg.mvStyleVar_WindowRounding, DLG_ROUNDING)
            dpg.add_theme_style(dpg.mvStyleVar_WindowBorderSize, 1)
            dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, DLG_PAD, DLG_PAD)
            dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, DLG_ITEM_X, DLG_ITEM_Y)
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 8)
            dpg.add_theme_style(dpg.mvStyleVar_ScrollbarSize, SCROLL_SIZE)
            dpg.add_theme_style(dpg.mvStyleVar_ScrollbarRounding, SCROLL_ROUNDING)
    _T["dialog"] = dialog

    with dpg.theme() as badge:
        with dpg.theme_component(dpg.mvChildWindow):
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, (*c["accent_blue"], BADGE_BG_ALPHA))
            dpg.add_theme_color(dpg.mvThemeCol_Border, (0, 0, 0, 0))
            dpg.add_theme_style(dpg.mvStyleVar_ChildBorderSize, 0)
            dpg.add_theme_style(dpg.mvStyleVar_ChildRounding, BADGE_ROUNDING)
            dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 0, 0)
    _T["badge"] = badge

    with dpg.theme() as tile:
        with dpg.theme_component(dpg.mvChildWindow):
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, (255, 255, 255))
            dpg.add_theme_color(dpg.mvThemeCol_Border, (0, 0, 0, 0))
            dpg.add_theme_style(dpg.mvStyleVar_ChildBorderSize, 0)
            dpg.add_theme_style(dpg.mvStyleVar_ChildRounding, QR_TILE_ROUNDING)
            dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 0, 0)
    _T["tile"] = tile

    with dpg.theme() as body:   # the scrolling area of the Instruction dialog: see-through, no border, no padding
        with dpg.theme_component(dpg.mvChildWindow):
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, (0, 0, 0, 0))
            dpg.add_theme_color(dpg.mvThemeCol_Border, (0, 0, 0, 0))
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarBg, SCROLL_TRACK)
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarGrab, SCROLL_GRAB)
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarGrabHovered, SCROLL_GRAB_HOVER)
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarGrabActive, SCROLL_GRAB_ACTIVE)
            dpg.add_theme_style(dpg.mvStyleVar_ChildBorderSize, 0)
            dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 0, 0)
            dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, DLG_ITEM_X, DLG_ITEM_Y)
            dpg.add_theme_style(dpg.mvStyleVar_ScrollbarSize, SCROLL_SIZE)
            dpg.add_theme_style(dpg.mvStyleVar_ScrollbarRounding, SCROLL_ROUNDING)
    _T["body"] = body

    with dpg.theme() as code:   # the little box that shows a URL or a model name
        with dpg.theme_component(dpg.mvChildWindow):
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, c["bg_sidebar"])
            dpg.add_theme_color(dpg.mvThemeCol_Border, c["border"])
            dpg.add_theme_style(dpg.mvStyleVar_ChildBorderSize, 1)
            dpg.add_theme_style(dpg.mvStyleVar_ChildRounding, 8)
            dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, CODE_PAD_X, CODE_PAD_Y)
    _T["code"] = code

    with dpg.theme() as copy_btn:
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_color(dpg.mvThemeCol_Button, c["bg_sidebar"])
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (45, 58, 84))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (45, 58, 84))
            dpg.add_theme_color(dpg.mvThemeCol_Border, c["border"])
            dpg.add_theme_style(dpg.mvStyleVar_FrameBorderSize, 1)
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 8)
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding, COPY_PAD, COPY_PAD)
    _T["copy_btn"] = copy_btn

    with dpg.theme() as step:   # numbered circle
        with dpg.theme_component(dpg.mvButton):
            dpg.add_theme_color(dpg.mvThemeCol_Button, (*c["accent_blue"], 60))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (*c["accent_blue"], 60))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (*c["accent_blue"], 60))
            dpg.add_theme_color(dpg.mvThemeCol_Text, c["accent_blue"])
            dpg.add_theme_color(dpg.mvThemeCol_Border, (*c["accent_blue"], 110))
            dpg.add_theme_style(dpg.mvStyleVar_FrameBorderSize, 1)
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, STEP_BADGE // 2)
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 0, 0)
    _T["step"] = step
    return _T


# ---------------------------------------------------------------------------
# Open / close
# ---------------------------------------------------------------------------

def _center_pos(w, h):
    vw = dpg.get_viewport_client_width()
    vh = dpg.get_viewport_client_height()
    return max(DLG_MARGIN, (vw - w) // 2), max(DLG_MARGIN, (vh - h) // 2)


def _close(sender=None, app_data=None, user_data=None):
    tag = _s["open"]
    _s["open"] = None
    if tag and dpg.does_item_exist(tag):
        dpg.configure_item(tag, show=False)
        dpg.delete_item(tag)


def _on_escape(sender=None, app_data=None):
    if _s["open"]:
        _close()


def _on_resize(content_w, content_h):
    tag = _s["open"]
    if tag and dpg.does_item_exist(tag):
        x, y = _center_pos(_s["w"], _s["h"])
        dpg.configure_item(tag, pos=[x, y])


def _open_window(tag, want_w, want_h, build_body):
    """Makes the dialog and fills it with build_body(w, h). If anything fails, nothing is left half open."""
    _close()
    try:
        t = _themes()
        vw = dpg.get_viewport_client_width()
        vh = dpg.get_viewport_client_height()
        w = min(want_w, vw - 2 * DLG_MARGIN)
        h = min(want_h, vh - 2 * DLG_MARGIN)
        x, y = _center_pos(w, h)
        with dpg.window(tag=tag, modal=True, show=True, no_title_bar=True, no_resize=True, no_move=True,
                        no_collapse=True, no_scrollbar=True, no_scroll_with_mouse=True,
                        width=w, height=h, pos=[x, y], min_size=[8, 8]):
            build_body(w, h)
        dpg.bind_item_theme(tag, t["dialog"])
        _s["open"], _s["w"], _s["h"] = tag, w, h
    except Exception:
        traceback.print_exc()
        if dpg.does_item_exist(tag):
            dpg.delete_item(tag)
        _s["open"] = None


# ---------------------------------------------------------------------------
# Pieces
# ---------------------------------------------------------------------------

def _header(title, helper, icon_key):
    t = _themes()
    icons, fonts = _s["icons"], _s["fonts"] or {}
    icon = icons.get(icon_key) if icons else None
    with dpg.group(horizontal=True):
        with dpg.child_window(width=BADGE_SIZE, height=BADGE_SIZE, no_scrollbar=True,
                              no_scroll_with_mouse=True) as badge:
            if icon:
                pad = (BADGE_SIZE - BADGE_ICON) // 2
                dpg.add_image(icon, width=BADGE_ICON, height=BADGE_ICON,
                              tint_color=COLORS["accent_blue"], pos=(pad, pad))
        dpg.bind_item_theme(badge, t["badge"])
        with dpg.group():
            title_item = dpg.add_text(title, color=COLORS["text_primary"])
            if fonts.get("subheading") is not None:
                dpg.bind_item_font(title_item, fonts["subheading"])
            dpg.add_text(helper, color=COLORS["text_secondary"])


def _copy(sender, app_data, user_data):
    try:
        dpg.set_clipboard_text(user_data)
        show_toast(MSG_COPIED, "success")
    except Exception:
        traceback.print_exc()
        show_toast(MSG_COPY_FAILED, "error")


def _code_row(value, width):
    """A dark box with the value in the mono font + a copy icon. width = the whole row."""
    t = _themes()
    icons, fonts = _s["icons"], _s["fonts"] or {}
    icon = icons.get("copy") if icons else None
    box_w = width - (CODE_H + DLG_ITEM_X) if icon else width
    with dpg.group(horizontal=True):
        with dpg.child_window(width=box_w, height=CODE_H, no_scrollbar=True, no_scroll_with_mouse=True) as box:
            text = dpg.add_text(value, color=COLORS["text_primary"])
            if fonts.get("mono_small") is not None:
                dpg.bind_item_font(text, fonts["mono_small"])
        dpg.bind_item_theme(box, t["code"])
        if icon:
            btn = dpg.add_image_button(icon, width=COPY_ICON, height=COPY_ICON, callback=_copy,
                                       user_data=value, tint_color=COLORS["text_secondary"])
            dpg.bind_item_theme(btn, t["copy_btn"])
            with dpg.tooltip(btn):
                dpg.add_text(TIP_COPY, color=COLORS["text_secondary"])


def _step(num, title, text_w, build_content):
    """Numbered circle on the left, title + content on the right."""
    t = _themes()
    fonts = _s["fonts"] or {}
    with dpg.group(horizontal=True):
        badge = dpg.add_button(label=str(num), width=STEP_BADGE, height=STEP_BADGE)
        dpg.bind_item_theme(badge, t["step"])
        with dpg.group():
            title_item = dpg.add_text(title, color=COLORS["text_primary"])
            if fonts.get("subheading") is not None:
                dpg.bind_item_font(title_item, fonts["subheading"])
            build_content(text_w)
    dpg.add_spacer(height=STEP_GAP_Y)


def _muted(lines, wrap):
    for line in lines:
        dpg.add_text(line, wrap=wrap, color=COLORS["text_secondary"])


# ---------------------------------------------------------------------------
# QR dialog
# ---------------------------------------------------------------------------

def _build_qr(w, h):
    t = _themes()
    base = _get_themes()
    inner_w = w - 2 * DLG_PAD
    _header(QR_TITLE, QR_HELPER, "qr_code")
    dpg.add_spacer(height=HEADER_GAP)
    with dpg.child_window(width=QR_TILE, height=QR_TILE, indent=max(0, (inner_w - QR_TILE) // 2),
                          no_scrollbar=True, no_scroll_with_mouse=True) as tile:
        dpg.add_image("mobile_qr_texture", width=QR_IMG, height=QR_IMG, pos=(QR_PAD, QR_PAD))
    dpg.bind_item_theme(tile, t["tile"])
    dpg.add_spacer(height=QR_TILE_GAP)
    dpg.add_text(QR_HINT, wrap=inner_w, color=COLORS["text_secondary"])
    dpg.add_spacer(height=QR_BTN_GAP)
    close = dpg.add_button(label=BTN_CLOSE, width=-1, height=BTN_H, callback=_close)
    dpg.bind_item_theme(close, base["btn_secondary"])


def open_qr_dialog():
    """View QR Code button. settings.py checks the texture exists before calling this."""
    _open_window(WIN_QR, QR_DLG_W, QR_DLG_H, _build_qr)


# ---------------------------------------------------------------------------
# Instruction dialog
# ---------------------------------------------------------------------------

def _open_site(sender=None, app_data=None, user_data=None):
    try:
        webbrowser.open(OPENROUTER_URL)
    except Exception:
        traceback.print_exc()
        show_toast(MSG_BROWSER_FAILED, "error")


def _build_instruction(w, h):
    base = _get_themes()
    t = _themes()
    inner_w = w - 2 * DLG_PAD
    text_w = inner_w - SCROLL_RESERVE - STEP_BADGE - DLG_ITEM_X   # width of the column right of the numbers

    _header(INSTR_TITLE, INSTR_HELPER, "key_round")
    dpg.add_spacer(height=HEADER_GAP)

    # negative height = "fill the rest minus this much" (my understanding of DPG, if the buttons get cut, see the knobs)
    with dpg.child_window(width=-1, height=-(FOOTER_H + FOOTER_GAP), tag="ai_instruction_body") as body:
        def step1(tw):
            _muted(STEP1_LINES, tw)

        def step2(tw):
            dpg.add_text(STEP2_URL_LABEL, wrap=tw, color=COLORS["text_secondary"])
            _code_row(DEFAULT_API_URL, tw)
            _muted(STEP2_LINES, tw)

        def step3(tw):
            _muted(STEP3_LINES, tw)
            dpg.add_text(STEP3_MODEL_LABEL, wrap=tw, color=COLORS["text_secondary"])
            _code_row(RECOMMENDED_MODEL, tw)
            _muted((STEP3_FREE, STEP3_PAID), tw)

        _step(1, STEP1_TITLE, text_w, step1)
        _step(2, STEP2_TITLE, text_w, step2)
        _step(3, STEP3_TITLE, text_w, step3)

        tips_title = dpg.add_text(TIPS_TITLE, color=COLORS["text_primary"])
        if (_s["fonts"] or {}).get("subheading") is not None:
            dpg.bind_item_font(tips_title, _s["fonts"]["subheading"])
        _muted(TIPS_LINES, inner_w - SCROLL_RESERVE)
    dpg.bind_item_theme(body, t["body"])

    dpg.add_spacer(height=FOOTER_GAP)
    buttons_w = VISIT_W + CLOSE_W + DLG_ITEM_X
    with dpg.group(horizontal=True, indent=max(0, inner_w - buttons_w)):   # buttons sit on the right
        visit = dpg.add_button(label=BTN_VISIT, width=VISIT_W, height=BTN_H, callback=_open_site)
        close = dpg.add_button(label=BTN_CLOSE, width=CLOSE_W, height=BTN_H, callback=_close)
    dpg.bind_item_theme(visit, base["btn_secondary"])
    dpg.bind_item_theme(close, base["btn_start"])


def open_instruction_dialog():
    _open_window(WIN_INSTR, INSTR_W, INSTR_H, _build_instruction)


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------

def init_settings_dialogs(fonts, icons):
    """Call once from build_settings."""
    _s["fonts"] = fonts
    _s["icons"] = icons
    if _s["ready"]:
        return
    with dpg.handler_registry():
        dpg.add_key_press_handler(dpg.mvKey_Escape, callback=_on_escape)
    register_resize("settings_dialogs", _on_resize)
    _s["ready"] = True