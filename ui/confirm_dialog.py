"""
confirm_dialog.py - ONE reusable "Are you sure?" popup for the whole app.

How to use it from any tab:
    from ui.confirm_dialog import init_confirm, ask_confirm
    init_confirm(fonts)        # once, in the tab's build function
    ask_confirm("Delete file?", "This can't be undone.", on_confirm=my_callback,
                user_data=whatever, confirm_label="Delete", danger=True)

on_confirm is called like a normal DPG callback: on_confirm(sender, app_data, user_data),
so an existing callback can be plugged in without changing it.

Used by: ui/quarantine.py (Delete button), ui/exclusions.py (Remove button).      <- add new users to this list
"""
import traceback
import dearpygui.dearpygui as dpg
from ui.theme import COLORS
from ui.layout import register_resize
from ui.scan_layout import _get_themes

# confirm_dialog.py

# ---- Size (tune here) ----
CONFIRM_W = 440                # dialog width
CONFIRM_MIN_H = 170            # the height is measured from the text, but never smaller than this
CONFIRM_MARGIN = 24            # never closer than this to the window edges
CONFIRM_PAD = 22               # padding inside the dialog
CONFIRM_ROUNDING = 14
CONFIRM_H_EXTRA = 6            # safety margin added to the measured height (raise if the buttons touch the bottom)

# ---- Spacing ----
CONFIRM_TITLE_GAP = 8          # space under the title
CONFIRM_MSG_GAP = 22           # space between the message and the buttons
CONFIRM_BTN_W = 130
CONFIRM_BTN_H = 38
CONFIRM_BTN_GAP = 12           # space between Cancel and the confirm button

# ---- Colors ----
CONFIRM_MSG_COLOR = COLORS["text_secondary"]
CONFIRM_BORDER_NORMAL = (*COLORS["accent_blue"], 110)
CONFIRM_BORDER_DANGER = (*COLORS["accent_red"], 140)

# ---- Only used if DPG can't measure text ----
CONFIRM_FALLBACK_TITLE_H = 26
CONFIRM_FALLBACK_LINE_H = 22
CONFIRM_FALLBACK_CHAR_W = 8

WIN = "confirm_dialog_window"
CANCEL_BTN = "confirm_cancel_btn"
OK_BTN = "confirm_ok_btn"

_T = {}
_s = {"ready": False, "open": False, "fonts": None, "cb": None, "user_data": None, "w": CONFIRM_W, "h": CONFIRM_MIN_H}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dialog_theme(border):
    c = COLORS
    with dpg.theme() as th:
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_color(dpg.mvThemeCol_WindowBg, c["bg_card"])
            dpg.add_theme_color(dpg.mvThemeCol_Border, border)
            dpg.add_theme_color(dpg.mvThemeCol_Text, c["text_primary"])
            dpg.add_theme_style(dpg.mvStyleVar_WindowRounding, CONFIRM_ROUNDING)
            dpg.add_theme_style(dpg.mvStyleVar_WindowBorderSize, 1)
            dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, CONFIRM_PAD, CONFIRM_PAD)
            dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, CONFIRM_BTN_GAP, 0)   # x = gap between buttons, y = 0 so our spacers are exact
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 8)
    return th


def _measure_height(title, message, wrap_w, font):
    """Dialog height from the real text sizes (measured at click time, so the font is ready)."""
    title_h = CONFIRM_FALLBACK_TITLE_H
    try:
        size = dpg.get_text_size(title, font=font) if font is not None else dpg.get_text_size(title)
        if size:
            title_h = size[1]
    except Exception:
        print("[confirm] could not measure the title, using the fallback height")
    msg_h = (int(len(message) * CONFIRM_FALLBACK_CHAR_W / max(1, wrap_w)) + 1) * CONFIRM_FALLBACK_LINE_H
    try:
        size = dpg.get_text_size(message, wrap_width=wrap_w)
        if size:
            msg_h = size[1]
    except Exception:
        print("[confirm] could not measure the message, using the fallback height")
    h = 2 * CONFIRM_PAD + title_h + CONFIRM_TITLE_GAP + msg_h + CONFIRM_MSG_GAP + CONFIRM_BTN_H + CONFIRM_H_EXTRA
    return max(CONFIRM_MIN_H, int(h))


def _center_pos(w, h):
    vw = dpg.get_viewport_client_width()
    vh = dpg.get_viewport_client_height()
    return max(CONFIRM_MARGIN, (vw - w) // 2), max(CONFIRM_MARGIN, (vh - h) // 2)


# ---------------------------------------------------------------------------
# Open / close
# ---------------------------------------------------------------------------

def _close():
    if dpg.does_item_exist(WIN):
        dpg.configure_item(WIN, show=False)
        dpg.delete_item(WIN)
    _s["open"] = False


def _on_cancel(sender=None, app_data=None, user_data=None):
    _close()


def _on_ok(sender=None, app_data=None, user_data=None):
    cb, ud = _s["cb"], _s["user_data"]
    _s["cb"] = None
    _close()                      # close first, so the dialog is gone before any heavy work starts
    if cb is None:
        return
    try:
        cb(sender, app_data, ud)
    except Exception:
        traceback.print_exc()


def _on_escape(sender=None, app_data=None):
    if _s["open"]:
        _close()


def _on_resize(content_w, content_h):
    if _s["open"] and dpg.does_item_exist(WIN):
        x, y = _center_pos(_s["w"], _s["h"])
        dpg.configure_item(WIN, pos=[x, y])


def _ensure_ready():
    if _s["ready"]:
        return
    with dpg.handler_registry():
        dpg.add_key_press_handler(dpg.mvKey_Escape, callback=_on_escape)
    register_resize("confirm_dialog", _on_resize)
    _s["ready"] = True


def init_confirm(fonts=None):
    """Call once from a tab's build function. fonts is optional (used for the title)."""
    if fonts:
        _s["fonts"] = fonts
    _ensure_ready()


def ask_confirm(title, message, on_confirm, user_data=None, confirm_label="Confirm",
                cancel_label="Cancel", danger=False):
    """Shows the popup. If anything fails here, NOTHING is run (the safe default)."""
    _ensure_ready()
    _close()
    try:
        t = _get_themes()
        if not _T:
            _T["normal"] = _dialog_theme(CONFIRM_BORDER_NORMAL)
            _T["danger"] = _dialog_theme(CONFIRM_BORDER_DANGER)

        vw = dpg.get_viewport_client_width()
        w = min(CONFIRM_W, vw - 2 * CONFIRM_MARGIN)
        inner_w = w - 2 * CONFIRM_PAD
        font = (_s["fonts"] or {}).get("subheading")
        h = _measure_height(title, message, inner_w, font)
        x, y = _center_pos(w, h)
        _s["w"], _s["h"] = w, h
        _s["cb"], _s["user_data"] = on_confirm, user_data

        buttons_w = 2 * CONFIRM_BTN_W + CONFIRM_BTN_GAP
        with dpg.window(tag=WIN, modal=True, show=True, no_title_bar=True, no_resize=True,
                        no_move=True, no_collapse=True, no_scrollbar=True, no_scroll_with_mouse=True,
                        width=w, height=h, pos=[x, y], min_size=[8, 8]):
            title_item = dpg.add_text(title, color=COLORS["text_primary"])
            if font is not None:
                dpg.bind_item_font(title_item, font)
            dpg.add_spacer(height=CONFIRM_TITLE_GAP)
            dpg.add_text(message, wrap=inner_w, color=CONFIRM_MSG_COLOR)
            dpg.add_spacer(height=CONFIRM_MSG_GAP)
            with dpg.group(horizontal=True, indent=max(0, inner_w - buttons_w)):   # buttons sit on the right
                dpg.add_button(label=cancel_label, width=CONFIRM_BTN_W, height=CONFIRM_BTN_H,
                               tag=CANCEL_BTN, callback=_on_cancel)
                dpg.add_button(label=confirm_label, width=CONFIRM_BTN_W, height=CONFIRM_BTN_H,
                               tag=OK_BTN, callback=_on_ok)

        dpg.bind_item_theme(WIN, _T["danger"] if danger else _T["normal"])
        dpg.bind_item_theme(CANCEL_BTN, t["btn_secondary"])
        dpg.bind_item_theme(OK_BTN, t["btn_cancel"] if danger else t["btn_start"])
        _s["open"] = True
    except Exception:
        traceback.print_exc()
        _close()