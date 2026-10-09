import dearpygui.dearpygui as dpg
from ui.theme import COLORS
import threading
import sys
import os
import json
import socket
import tempfile
import webbrowser
from urllib.parse import urlencode
from urllib.request import urlopen

import system.notifications.telegram as tg
from system.mobile_pairing import generate_pairing_payload, mobile_status_payload, SYSTEM_ID
import time
import traceback
from datetime import datetime
from ui.layout import register_resize
from ui.scan_layout import _get_themes, PAGE_LEFT_PAD, CHILD_PAD_X, ITEM_SPACING_X
from ui.scan_pipeline import _row_width
from ui.scan_threats import _flat_button_theme, PILL_BG_ALPHA
from ui.quarantine import _pill_theme   # same pill look as Quarantine / Exclusions
from ui.toast import init_toast, show_toast
from ui.settings_dialogs import init_settings_dialogs, open_qr_dialog, open_instruction_dialog

#settings.py
# Add parent directory to path to import Malware_System
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# try:
#     import Malware_System as ms
#     BACKEND_AVAILABLE = True
# except Exception as e:
#     print(f"Warning: Could not load Malware_System backend: {e}")
#     BACKEND_AVAILABLE = False


# ---- Mobile card text ----
MOBILE_TITLE = "Mobile Pairing"
MOBILE_HELPER = "Pair your phone to get scan alerts"
MOBILE_HINT = "Open AYAWrus Mobile and scan this code. Each code works once and expires after 5 minutes."
STATUS_NONE = "NO DEVICE PAIRED"
STATUS_ONE = "1 DEVICE CONNECTED"
STATUS_MANY = "{n} DEVICES CONNECTED"
EXPIRY_TEXT = "Expires in {time}"
EXPIRY_EXPIRED = "CODE EXPIRED"
EXPIRY_NONE = "No active code"
BTN_VIEW_QR = "View QR Code"
BTN_NEW_QR = "Generate New QR"
QR_UNAVAILABLE_TEXT = "QR unavailable"
MSG_QR_READY = "New pairing code ready"
MSG_QR_FAILED = "Couldn't create a pairing code (see terminal)"
MSG_NO_QR = "No QR yet, press Generate New QR"
MSG_COPIED = "Copied to clipboard"
MSG_COPY_FAILED = "Couldn't copy (see terminal)"
TIP_COPY = "Copy"

# ---- Mobile card layout (tune here) ----
CARD_START_W = 1240            # placeholder until ui/layout.py sets the real width
MOBILE_CARD_HEIGHT = 330       # raise if the buttons touch the bottom edge, lower if there's a gap
CARD_SIDE_PAD = 16
CARD_TOP_PAD = 6
HEADER_GAP = 16                # space between the header row and the body

# header badge (same look as the Exclusions add card)
BADGE_SIZE = 44
BADGE_ICON = 24
BADGE_ROUNDING = 12
BADGE_BG_ALPHA = 45

# status pill pinned to the header's right side
STATUS_PILL_W = 210
STATUS_PILL_H = 28
STATUS_RIGHT_MARGIN = 20
STATUS_PILL_Y = 22             # distance from the card's top edge (nudge if it doesn't line up with the title)

# QR tile (stays WHITE on purpose, phones can't scan a tinted QR)
QR_TILE_SIZE = 170
QR_IMG_SIZE = 150
QR_IMG_PAD = (QR_TILE_SIZE - QR_IMG_SIZE) // 2
QR_TILE_BG = (255, 255, 255)
QR_TILE_ROUNDING = 14
QR_PLACEHOLDER_COLOR = (120, 130, 150)
QR_PLACEHOLDER_ICON = 56
QR_TO_INFO_GAP = 28            # space between the QR column and the info column
EXPIRY_CHIP_HEIGHT = 30
EXPIRY_WARN_SECONDS = 60       # chip turns orange at or below this
EXPIRY_TICK_SECONDS = 0.5      # how often the countdown refreshes

# info column
INFO_MIN_WIDTH = 300
INFO_WIDTH_TRIM = 4            # safety so the info table never overflows
INFO_START_W = 700
INFO_TO_HINT_GAP = 16
HINT_TO_BUTTONS_GAP = 16
BTN_W = 170
BTN_H = 38
COPY_BUTTONS = True            # False = no copy icons next to Local Address / System ID
COPY_ICON_SIZE = 18
# ---- AI card text ----
AI_TITLE = "AI Assistant"
AI_HELPER = "Connect an OpenRouter-compatible AI service"
AI_LABEL_URL = "API URL"
AI_LABEL_KEY = "API Key"
AI_LABEL_MODEL = "AI Model"
AI_LABEL_CUSTOM = "Custom model name"
AI_HINT_URL = "e.g. https://openrouter.ai/api/v1/chat/completions"
AI_HINT_KEY = "Paste your API key"
AI_HINT_CUSTOM = "e.g. openai/gpt-4"
AI_SAVE_NOTE = "Saved on this PC in config.json"
BTN_INSTRUCTION = "Instruction"
BTN_SAVE = "Save Settings"
TIP_TOGGLE_KEY = "Show or hide the key"
MSG_SAVED = "Settings saved"
MSG_SAVED_WARN = "Saved, but {problem}"
MSG_SAVE_FAILED = "Couldn't save settings (see terminal)"
PROBLEM_URL_EMPTY = "no API URL entered"
PROBLEM_URL_BAD = "the API URL doesn't start with http"
PROBLEM_KEY_EMPTY = "no API key entered"
PROBLEM_CUSTOM_EMPTY = "no custom model name entered (model left as before)"
URL_PREFIXES = ("http://", "https://")

# ---- AI card layout (tune here) ----
AI_CARD_HEIGHT = 360           # raise if the buttons touch the bottom edge, lower if there's a gap
AI_COL_GAP = 24                # space between the left and right column
AI_COL_TRIM = 4                # safety so the columns never overflow the card
AI_COL_MIN_W = 260
AI_COL_START_W = 400           # placeholder until ui/layout.py sets the real width
AI_COL_NUDGE_Y = 0.5             # lowers the LEFT column so its labels line up with the right one (a spacer also adds 4px of item spacing, so 3 moves it about 7px)
AI_FIELD_GAP = 14
AI_BUTTONS_TOP_GAP = 18
AI_NOTE_NUDGE_Y = 6            # lowers the note so it lines up with the button text
AI_BOTTOM_MARGIN = 90          # space under the page so the help button never covers the card
AI_INPUT_PAD_X = 12
AI_INPUT_PAD_Y = 10            # input height = font size (18) + 2 * this = 38px
AI_COMBO_ARROW = (45, 58, 84)
AI_COMBO_ARROW_HOVER = (60, 76, 108)

# eye button (shows / hides the API key)
EYE_BTN_SIZE = 38              # same height as the inputs
EYE_ICON_SIZE = 20
EYE_PAD = (EYE_BTN_SIZE - EYE_ICON_SIZE) // 2
EYE_BG = COLORS["bg_sidebar"]
EYE_BG_HOVER = (45, 58, 84)

SERVER_PORT_DEFAULT = 5001

_T = {}
_state = {"row_w": CARD_START_W, "expires_ts": None, "expiry_shown": None,
          "ticker_started": False, "icons": None, "fonts": None}


def _themes():
    if _T:
        return _T
    with dpg.theme() as card:
        with dpg.theme_component(dpg.mvChildWindow):
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, COLORS["bg_card"])
            dpg.add_theme_color(dpg.mvThemeCol_Border, COLORS["border"])
    _T["card"] = card

    with dpg.theme() as badge:
        with dpg.theme_component(dpg.mvChildWindow):
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, (*COLORS["accent_blue"], BADGE_BG_ALPHA))
            dpg.add_theme_color(dpg.mvThemeCol_Border, (0, 0, 0, 0))
            dpg.add_theme_style(dpg.mvStyleVar_ChildBorderSize, 0)
            dpg.add_theme_style(dpg.mvStyleVar_ChildRounding, BADGE_ROUNDING)
            dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 0, 0)
    _T["badge"] = badge

    with dpg.theme() as tile:
        with dpg.theme_component(dpg.mvChildWindow):
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, QR_TILE_BG)
            dpg.add_theme_color(dpg.mvThemeCol_Border, (0, 0, 0, 0))
            dpg.add_theme_style(dpg.mvStyleVar_ChildBorderSize, 0)
            dpg.add_theme_style(dpg.mvStyleVar_ChildRounding, QR_TILE_ROUNDING)
            dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 0, 0)
    _T["tile"] = tile

    with dpg.theme() as copy_btn:
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_color(dpg.mvThemeCol_Button, (0, 0, 0, 0))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (255, 255, 255, 28))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (255, 255, 255, 45))
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 3, 3)
    _T["copy_btn"] = copy_btn

    _T["status_on"] = _pill_theme(COLORS["accent_green"], PILL_BG_ALPHA)
    _T["status_off"] = _pill_theme(COLORS["text_secondary"], PILL_BG_ALPHA)
    _T["chip_blue"] = _pill_theme(COLORS["accent_blue"], PILL_BG_ALPHA)
    _T["chip_orange"] = _pill_theme(COLORS["accent_orange"], PILL_BG_ALPHA)
    _T["chip_red"] = _pill_theme(COLORS["accent_red"], PILL_BG_ALPHA)
    _T["chip_grey"] = _pill_theme(COLORS["text_secondary"], PILL_BG_ALPHA)
    _T["qr_ph_text"] = _flat_button_theme(QR_PLACEHOLDER_COLOR)

    with dpg.theme() as ai_input:   # inputs and the combo share one look
        for comp in (dpg.mvInputText, dpg.mvCombo):
            with dpg.theme_component(comp):
                dpg.add_theme_color(dpg.mvThemeCol_FrameBg, COLORS["bg_sidebar"])
                dpg.add_theme_color(dpg.mvThemeCol_Border, COLORS["border"])
                dpg.add_theme_color(dpg.mvThemeCol_Text, COLORS["text_primary"])
                dpg.add_theme_style(dpg.mvStyleVar_FrameBorderSize, 1)
                dpg.add_theme_style(dpg.mvStyleVar_FramePadding, AI_INPUT_PAD_X, AI_INPUT_PAD_Y)
        with dpg.theme_component(dpg.mvCombo):
            dpg.add_theme_color(dpg.mvThemeCol_Button, AI_COMBO_ARROW)
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, AI_COMBO_ARROW_HOVER)
    _T["ai_input"] = ai_input

    with dpg.theme() as eye_btn:
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_color(dpg.mvThemeCol_Button, EYE_BG)
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, EYE_BG_HOVER)
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, EYE_BG_HOVER)
            dpg.add_theme_color(dpg.mvThemeCol_Border, COLORS["border"])
            dpg.add_theme_style(dpg.mvStyleVar_FrameBorderSize, 1)
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding, EYE_PAD, EYE_PAD)
    _T["eye_btn"] = eye_btn
    return _T


AVAILABLE_AI_MODELS = [
    "nvidia/nemotron-3.5-lightning:free",
    "nvidia/nemotron-70b-reward:free",
    "mistralai/mistral-7b-instruct-v0.3",
    "meta-llama/llama-3.1-8b-instruct:free",
    "meta-llama/llama-3.1-70b-instruct:free",
    "openai/chatgpt-4o-latest",
    "anthropic/claude-3.5-sonnet",
    "google/gemini-pro-1.5",
    "custom",
]


def refresh_settings():
    """Refresh settings view"""
    config = tg.load_config()
    if dpg.does_item_exist("telegram_token"):
        dpg.set_value("telegram_token", config.get("telegram_bot_token", ""))
    if dpg.does_item_exist("telegram_chat_id"):
        dpg.set_value("telegram_chat_id", config.get("telegram_chat_id", ""))
    if dpg.does_item_exist("ai_api_url"):
        dpg.set_value("ai_api_url", config.get("ai_api_url", ""))
    if dpg.does_item_exist("ai_api_key"):
        dpg.set_value("ai_api_key", config.get("ai_api_key", ""))
    saved_model = config.get("ai_model", "nvidia/nemotron-3.5-lightning:free")
    if dpg.does_item_exist("ai_model_combo"):
        if saved_model in AVAILABLE_AI_MODELS:
            dpg.set_value("ai_model_combo", saved_model)
        else:
            dpg.set_value("ai_model_combo", "custom")
    if dpg.does_item_exist("ai_model_custom"):
        if saved_model not in AVAILABLE_AI_MODELS or saved_model == "custom":
            dpg.set_value("ai_model_custom", saved_model if saved_model != "custom" else "")
    _sync_custom_box()         # set_value doesn't fire the combo's callback, so show / hide the custom box by hand
    _set_key_visible(False)    # coming back to the tab always hides the key again
    _refresh_mobile_status()   # the sidebar calls this when the tab opens


def send_report_to_telegram():
    """Send a full scan report to Telegram"""
    if dpg.does_item_exist("report_status"):
        dpg.set_value("report_status", "Sending report...")
    
    def send_in_thread():
        try:
            success = tg.send_scan_report()
            if dpg.does_item_exist("report_status"):
                if success:
                    dpg.set_value("report_status", "Report sent!")
                else:
                    dpg.set_value("report_status", "Failed to send report!")
        except Exception as e:
            if dpg.does_item_exist("report_status"):
                dpg.set_value("report_status", f"Error: {e}")
            print(f"Error: {e}")
    
    threading.Thread(target=send_in_thread, daemon=True).start()


# ---------------------------------------------------------------------------
# AI card
# ---------------------------------------------------------------------------

def _set_key_visible(visible):
    """Eye button: shows or hides the API key (and swaps the icon)."""
    _state["key_visible"] = visible
    if dpg.does_item_exist("ai_api_key"):
        dpg.configure_item("ai_api_key", password=not visible)
    tex = (_state["icons"] or {}).get("eye_off" if visible else "eye")
    if dpg.does_item_exist("ai_key_eye") and tex:
        try:
            dpg.configure_item("ai_key_eye", texture_tag=tex)
        except Exception:
            traceback.print_exc()   # if this DPG build won't swap the texture, the icon just stays the same


def _toggle_key(sender=None, app_data=None, user_data=None):
    _set_key_visible(not _state.get("key_visible", False))


def _sync_custom_box():
    """The 'Custom model name' field only shows while the combo says 'custom'."""
    if dpg.does_item_exist("ai_custom_field") and dpg.does_item_exist("ai_model_combo"):
        dpg.configure_item("ai_custom_field", show=(dpg.get_value("ai_model_combo") == "custom"))


def _on_model_change(sender=None, app_data=None, user_data=None):
    _sync_custom_box()


def save_settings(sender=None, app_data=None, user_data=None):
    """Save button. Only touches the AI keys: everything else in config.json (Telegram, Firebase...) is kept as it is.
    Problems are warnings, never blocks: the settings are still saved."""
    url = (dpg.get_value("ai_api_url") or "").strip()      # stray spaces from pasting are a classic failure
    key = (dpg.get_value("ai_api_key") or "").strip()
    combo = dpg.get_value("ai_model_combo")
    custom = (dpg.get_value("ai_model_custom") or "").strip()

    problems = []
    if not url:
        problems.append(PROBLEM_URL_EMPTY)
    elif not url.lower().startswith(URL_PREFIXES):
        problems.append(PROBLEM_URL_BAD)
    if not key:
        problems.append(PROBLEM_KEY_EMPTY)

    model = combo
    if combo == "custom":
        if custom:
            model = custom
        else:
            model = None   # same as before: an empty custom name leaves the saved model alone
            problems.append(PROBLEM_CUSTOM_EMPTY)

    try:
        config = tg.load_config()
        config["ai_api_url"] = url
        config["ai_api_key"] = key
        if model:
            config["ai_model"] = model
        tg.save_config(config)
    except Exception:
        traceback.print_exc()
        show_toast(MSG_SAVE_FAILED, "error")
        return

    dpg.set_value("ai_api_url", url)   # show the trimmed values
    dpg.set_value("ai_api_key", key)
    if combo == "custom":
        dpg.set_value("ai_model_custom", custom)

    if problems:
        extra = f" (+{len(problems) - 1} more)" if len(problems) > 1 else ""
        show_toast(MSG_SAVED_WARN.format(problem=problems[0]) + extra, "warning")
    else:
        show_toast(MSG_SAVED, "success")


def _ai_col_w(row_w):
    inner = row_w - 2 * CHILD_PAD_X - 2 * CARD_SIDE_PAD - AI_COL_GAP - AI_COL_TRIM
    return max(AI_COL_MIN_W, int(inner // 2))


def _resize_ai(row_w):
    col = _ai_col_w(row_w)
    if dpg.does_item_exist("ai_card"):
        dpg.configure_item("ai_card", width=row_w)
    for tag in ("ai_api_url", "ai_model_combo", "ai_model_custom"):
        if dpg.does_item_exist(tag):
            dpg.configure_item(tag, width=col)
    if dpg.does_item_exist("ai_api_key"):
        dpg.configure_item("ai_api_key", width=col - EYE_BTN_SIZE - ITEM_SPACING_X)


def _build_ai_card(fonts, icons):
    t = _themes()
    base = _get_themes()   # shared buttons from ui/scan_layout.py (btn_secondary, btn_start)
    key_icon = icons.get("key_round") if icons else None
    eye = icons.get("eye") if icons else None
    key_w = AI_COL_START_W - EYE_BTN_SIZE - ITEM_SPACING_X

    with dpg.child_window(width=CARD_START_W, height=AI_CARD_HEIGHT, tag="ai_card",
                          no_scrollbar=True, no_scroll_with_mouse=True):
        dpg.add_spacer(height=CARD_TOP_PAD)

        # ---- header: badge + title + helper ----
        with dpg.group(horizontal=True, indent=CARD_SIDE_PAD):
            with dpg.child_window(width=BADGE_SIZE, height=BADGE_SIZE, tag="ai_badge",
                                  no_scrollbar=True, no_scroll_with_mouse=True):
                if key_icon:
                    pad = (BADGE_SIZE - BADGE_ICON) // 2
                    dpg.add_image(key_icon, width=BADGE_ICON, height=BADGE_ICON,
                                  tint_color=COLORS["accent_blue"], pos=(pad, pad))
            with dpg.group():
                dpg.add_text(AI_TITLE, color=COLORS["text_primary"], tag="ai_title")
                dpg.add_text(AI_HELPER, color=COLORS["text_secondary"])

        dpg.add_spacer(height=HEADER_GAP)

        # ---- fields: two columns ----
        with dpg.group(horizontal=True, indent=CARD_SIDE_PAD):
            with dpg.group():   # left: URL + key
                dpg.add_spacer(height=AI_COL_NUDGE_Y)   # matches the right column, which DPG sits slightly lower
                dpg.add_text(AI_LABEL_URL, color=COLORS["text_secondary"])
                dpg.add_input_text(tag="ai_api_url", width=AI_COL_START_W, hint=AI_HINT_URL)
                dpg.add_spacer(height=AI_FIELD_GAP)
                dpg.add_text(AI_LABEL_KEY, color=COLORS["text_secondary"])
                with dpg.group(horizontal=True):
                    dpg.add_input_text(tag="ai_api_key", width=key_w, password=True, hint=AI_HINT_KEY)
                    dpg.add_image_button(eye, width=EYE_ICON_SIZE, height=EYE_ICON_SIZE, tag="ai_key_eye",
                                         callback=_toggle_key, tint_color=COLORS["text_secondary"])
                    with dpg.tooltip("ai_key_eye"):
                        dpg.add_text(TIP_TOGGLE_KEY, color=COLORS["text_secondary"])

            dpg.add_spacer(width=max(0, AI_COL_GAP - 2 * ITEM_SPACING_X))

            with dpg.group():   # right: model + custom name
                dpg.add_text(AI_LABEL_MODEL, color=COLORS["text_secondary"])
                dpg.add_combo(tag="ai_model_combo", items=AVAILABLE_AI_MODELS,
                              default_value="nvidia/nemotron-3.5-lightning:free",
                              width=AI_COL_START_W, callback=_on_model_change)
                dpg.add_spacer(height=AI_FIELD_GAP)
                with dpg.group(tag="ai_custom_field", show=False):
                    dpg.add_text(AI_LABEL_CUSTOM, color=COLORS["text_secondary"])
                    dpg.add_input_text(tag="ai_model_custom", width=AI_COL_START_W, hint=AI_HINT_CUSTOM)

        dpg.add_spacer(height=AI_BUTTONS_TOP_GAP)

        # ---- buttons + note ----
        with dpg.group(horizontal=True, indent=CARD_SIDE_PAD):
            dpg.add_button(label=BTN_INSTRUCTION, tag="ai_instruction_btn", width=BTN_W, height=BTN_H,
                           callback=show_instruction_modal)
            dpg.add_button(label=BTN_SAVE, tag="ai_save_btn", width=BTN_W, height=BTN_H,
                           callback=save_settings)
            with dpg.group():
                dpg.add_spacer(height=AI_NOTE_NUDGE_Y)
                dpg.add_text(AI_SAVE_NOTE, color=COLORS["text_secondary"])

    dpg.bind_item_theme("ai_card", t["card"])
    dpg.bind_item_theme("ai_badge", t["badge"])
    for tag in ("ai_api_url", "ai_api_key", "ai_model_combo", "ai_model_custom"):
        dpg.bind_item_theme(tag, t["ai_input"])
    dpg.bind_item_theme("ai_key_eye", t["eye_btn"])
    dpg.bind_item_theme("ai_instruction_btn", base["btn_secondary"])
    dpg.bind_item_theme("ai_save_btn", base["btn_start"])
    if fonts and fonts.get("subheading") is not None:
        dpg.bind_item_font("ai_title", fonts["subheading"])


def get_active_local_address():
    candidates = []
    try:
        addrs = socket.getaddrinfo(socket.gethostname(), None, type=socket.SOCK_DGRAM)
        for item in addrs:
            ip = item[4][0]
            if ip and ip != "127.0.0.1":
                candidates.append(ip)
    except Exception:
        pass
    try:
        for intf in socket.if_nameindex():
            name = intf[1]
            if not name or name.startswith("lo"):
                continue
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                    s.connect(("8.8.8.8", 80))
                    ip = s.getsockname()[0]
                    if ip and ip != "127.0.0.1":
                        candidates.append(ip)
            except Exception:
                pass
    except Exception:
        pass
    seen = set()
    uniq = []
    for ip in candidates:
        if ip not in seen:
            seen.add(ip)
            uniq.append(ip)
    for ip in uniq:
        if ip.startswith(("192.168.", "10.", "172.")):
            return ip
    return uniq[0] if uniq else "127.0.0.1"


def _generate_qr_file_and_payload():
    import qrcode
    host = get_active_local_address()
    port = int(os.environ.get("SERVER_PORT", "5001"))
    api_url = f"http://127.0.0.1:{port}/api/mobile/qr?{urlencode({'host': host, 'port': port})}"
    with urlopen(api_url, timeout=3) as response:
        api_payload = json.loads(response.read().decode("utf-8"))
    payload = json.loads(api_payload["qr_payload"])
    payload["apk_url"] = f"http://{host}:{port}/mobile/download"
    setup_url = f"http://{host}:{port}/mobile/setup"
    qr_value = f"{setup_url}?{urlencode({'pairing_token': payload['pairing_token'], 'port': payload['port'], 'system_id': payload['system_id']})}"
    qr_file = os.path.join(tempfile.gettempdir(), f"ayawrus_mobile_pair_{os.getpid()}.png")
    qr = qrcode.QRCode(version=2, box_size=6, border=2)
    qr.add_data(qr_value)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGBA")
    img.save(qr_file)
    return qr_file, payload


# ---------------------------------------------------------------------------
# Mobile card: status, expiry countdown, QR
# ---------------------------------------------------------------------------

def _server_port():
    try:
        return int(os.environ.get("SERVER_PORT", str(SERVER_PORT_DEFAULT)))   # same variable the API server and the QR use
    except ValueError:
        return SERVER_PORT_DEFAULT


def _refresh_mobile_status():
    """Status pill: how many phones are paired right now. Only reads, changes nothing."""
    if not dpg.does_item_exist("mobile_status_pill"):
        return
    n = 0
    try:
        n = int(mobile_status_payload().get("connected_devices", 0))
    except Exception:
        traceback.print_exc()
    if n <= 0:
        label, theme = STATUS_NONE, _themes()["status_off"]
    else:
        label = STATUS_ONE if n == 1 else STATUS_MANY.format(n=n)
        theme = _themes()["status_on"]
    dpg.set_item_label("mobile_status_pill", label)
    dpg.bind_item_theme("mobile_status_pill", theme)


def _expiry_view():
    """(text, color kind) for the chip, from the saved expiry time."""
    ts = _state["expires_ts"]
    if ts is None:
        return EXPIRY_NONE, "grey"
    remaining = ts - time.time()
    if remaining <= 0:
        return EXPIRY_EXPIRED, "red"
    mins, secs = divmod(int(remaining), 60)
    kind = "orange" if remaining <= EXPIRY_WARN_SECONDS else "blue"
    return EXPIRY_TEXT.format(time=f"{mins:02d}:{secs:02d}"), kind


def _apply_expiry():
    view = _expiry_view()
    if view == _state["expiry_shown"]:
        return   # nothing changed, don't touch the widget
    _state["expiry_shown"] = view
    text, kind = view
    dpg.set_item_label("mobile_expiry_chip", text)
    dpg.bind_item_theme("mobile_expiry_chip", _themes()[f"chip_{kind}"])


def _expiry_loop():
    while True:
        time.sleep(EXPIRY_TICK_SECONDS)
        try:
            with dpg.mutex():
                if dpg.does_item_exist("mobile_expiry_chip"):
                    _apply_expiry()
        except Exception:
            traceback.print_exc()


def _start_expiry_ticker():
    if _state["ticker_started"]:
        return
    _state["ticker_started"] = True
    threading.Thread(target=_expiry_loop, daemon=True).start()


def _set_qr_placeholder(show):
    for tag in ("mobile_qr_ph_icon", "mobile_qr_ph_text"):
        if dpg.does_item_exist(tag):
            dpg.configure_item(tag, show=show)


def regenerate_mobile_qr(notify=False):
    """Makes a new pairing code and shows it. notify=True (the button) also shows a toast."""
    try:
        qr_file, payload = _generate_qr_file_and_payload()   # unchanged backend-facing code

        for tag in ("mobile_qr_modal", "mobile_qr_image", "mobile_qr_texture"):
            if dpg.does_item_exist(tag):
                dpg.delete_item(tag)

        width, height, channels, data = dpg.load_image(qr_file)
        if not dpg.does_item_exist("mobile_qr_texture_registry"):
            dpg.add_texture_registry(tag="mobile_qr_texture_registry")
        dpg.add_static_texture(width, height, data, parent="mobile_qr_texture_registry", tag="mobile_qr_texture")
        dpg.add_image("mobile_qr_texture", parent="mobile_qr_tile", tag="mobile_qr_image",
                      width=QR_IMG_SIZE, height=QR_IMG_SIZE, pos=(QR_IMG_PAD, QR_IMG_PAD))
        _set_qr_placeholder(False)

        if dpg.does_item_exist("mobile_address_value"):
            dpg.set_value("mobile_address_value", f"{payload['host']}:{payload['port']}")
        try:
            _state["expires_ts"] = float(payload.get("expires_at_ts") or
                                         datetime.fromisoformat(payload["expires_at"]).timestamp())
        except Exception:
            traceback.print_exc()
            _state["expires_ts"] = None
        _state["expiry_shown"] = None
        _apply_expiry()
        _refresh_mobile_status()
        if notify:
            show_toast(MSG_QR_READY, "success")
        return payload
    except Exception:
        traceback.print_exc()
        for tag in ("mobile_qr_modal", "mobile_qr_image", "mobile_qr_texture"):
            if dpg.does_item_exist(tag):
                dpg.delete_item(tag)
        _set_qr_placeholder(True)
        _state["expires_ts"] = None
        _state["expiry_shown"] = None
        if dpg.does_item_exist("mobile_expiry_chip"):
            _apply_expiry()
        if notify:
            show_toast(MSG_QR_FAILED, "error")
        return None


def _on_generate_click(sender=None, app_data=None, user_data=None):
    regenerate_mobile_qr(notify=True)


def _copy_value(sender, app_data, user_data):
    try:
        dpg.set_clipboard_text(dpg.get_value(user_data))
        show_toast(MSG_COPIED, "success")
    except Exception:
        traceback.print_exc()
        show_toast(MSG_COPY_FAILED, "error")


def show_qr_modal(sender=None, app_data=None, user_data=None):
    """View QR Code button. The dialog itself lives in ui/settings_dialogs.py."""
    if not dpg.does_item_exist("mobile_qr_texture"):
        show_toast(MSG_NO_QR, "warning")
        return
    open_qr_dialog()


def _info_cell(label, value, tag, copy=False):
    """One 'LABEL / value (+ copy icon)' stack, drawn inside the current table cell."""
    icons, fonts = _state["icons"], _state["fonts"] or {}
    with dpg.group():
        dpg.add_text(label, color=COLORS["text_secondary"])
        with dpg.group(horizontal=True):
            dpg.add_text(value, tag=tag, color=COLORS["text_primary"])
            if fonts.get("mono_small") is not None:
                dpg.bind_item_font(tag, fonts["mono_small"])
            icon = icons.get("copy") if icons else None
            if copy and COPY_BUTTONS and icon:
                btn = dpg.add_image_button(icon, width=COPY_ICON_SIZE, height=COPY_ICON_SIZE,
                                           callback=_copy_value, user_data=tag,
                                           tint_color=COLORS["text_secondary"])
                dpg.bind_item_theme(btn, _themes()["copy_btn"])
                with dpg.tooltip(btn):
                    dpg.add_text(TIP_COPY, color=COLORS["text_secondary"])


def _build_mobile_card(fonts, icons):
    t = _themes()
    base = _get_themes()   # shared buttons from ui/scan_layout.py (btn_secondary, btn_start)
    phone = icons.get("smartphone") if icons else None
    qr_icon = icons.get("qr_code") if icons else None

    with dpg.child_window(width=CARD_START_W, height=MOBILE_CARD_HEIGHT, tag="mobile_card",
                          no_scrollbar=True, no_scroll_with_mouse=True):
        dpg.add_spacer(height=CARD_TOP_PAD)

        # ---- header: badge + title + helper ----
        with dpg.group(horizontal=True, indent=CARD_SIDE_PAD):
            with dpg.child_window(width=BADGE_SIZE, height=BADGE_SIZE, tag="mobile_badge",
                                  no_scrollbar=True, no_scroll_with_mouse=True):
                if phone:
                    pad = (BADGE_SIZE - BADGE_ICON) // 2
                    dpg.add_image(phone, width=BADGE_ICON, height=BADGE_ICON,
                                  tint_color=COLORS["accent_blue"], pos=(pad, pad))
            with dpg.group():
                dpg.add_text(MOBILE_TITLE, color=COLORS["text_primary"], tag="mobile_title")
                dpg.add_text(MOBILE_HELPER, color=COLORS["text_secondary"])

        dpg.add_spacer(height=HEADER_GAP)

        # ---- body: QR column on the left, info column on the right ----
        with dpg.group(horizontal=True, indent=CARD_SIDE_PAD):
            with dpg.group():
                with dpg.child_window(width=QR_TILE_SIZE, height=QR_TILE_SIZE, tag="mobile_qr_tile",
                                      no_scrollbar=True, no_scroll_with_mouse=True):
                    if qr_icon:
                        dpg.add_image(qr_icon, width=QR_PLACEHOLDER_ICON, height=QR_PLACEHOLDER_ICON,
                                      tint_color=QR_PLACEHOLDER_COLOR, tag="mobile_qr_ph_icon",
                                      pos=((QR_TILE_SIZE - QR_PLACEHOLDER_ICON) // 2, 38))
                    dpg.add_button(label=QR_UNAVAILABLE_TEXT, width=QR_TILE_SIZE, height=24,
                                   tag="mobile_qr_ph_text", pos=(0, 108))
                dpg.add_button(label=EXPIRY_NONE, tag="mobile_expiry_chip", width=QR_TILE_SIZE,
                               height=EXPIRY_CHIP_HEIGHT)

            dpg.add_spacer(width=max(0, QR_TO_INFO_GAP - 2 * ITEM_SPACING_X))

            with dpg.group():
                with dpg.table(header_row=False, tag="mobile_info_table", width=INFO_START_W,
                               row_background=False, borders_innerH=False, borders_outerH=False,
                               borders_innerV=False, borders_outerV=False):
                    for _ in range(3):
                        dpg.add_table_column(width_stretch=True, init_width_or_weight=1.0)
                    with dpg.table_row():
                        _info_cell("System Name", socket.gethostname(), "mobile_name_value")
                        _info_cell("Local Address", f"{get_active_local_address()}:{_server_port()}",
                                   "mobile_address_value", copy=True)
                        _info_cell("System ID", SYSTEM_ID, "mobile_id_value", copy=True)

                dpg.add_spacer(height=INFO_TO_HINT_GAP)
                dpg.add_text(MOBILE_HINT, color=COLORS["text_secondary"], wrap=INFO_START_W,
                             tag="mobile_hint_text")
                dpg.add_spacer(height=HINT_TO_BUTTONS_GAP)
                with dpg.group(horizontal=True):
                    dpg.add_button(label=BTN_VIEW_QR, tag="mobile_view_btn", width=BTN_W, height=BTN_H,
                                   callback=show_qr_modal)
                    dpg.add_button(label=BTN_NEW_QR, tag="mobile_new_btn", width=BTN_W, height=BTN_H,
                                   callback=_on_generate_click)

        # pinned by hand, so it goes LAST (a pos= item moves the cursor)
        dpg.add_button(label=STATUS_NONE, tag="mobile_status_pill", width=STATUS_PILL_W,
                       height=STATUS_PILL_H, pos=(CARD_START_W - STATUS_PILL_W - STATUS_RIGHT_MARGIN,
                                                  STATUS_PILL_Y))

    dpg.bind_item_theme("mobile_card", t["card"])
    dpg.bind_item_theme("mobile_badge", t["badge"])
    dpg.bind_item_theme("mobile_qr_tile", t["tile"])
    dpg.bind_item_theme("mobile_qr_ph_text", t["qr_ph_text"])
    dpg.bind_item_theme("mobile_expiry_chip", t["chip_grey"])
    dpg.bind_item_theme("mobile_status_pill", t["status_off"])
    dpg.bind_item_theme("mobile_view_btn", base["btn_secondary"])
    dpg.bind_item_theme("mobile_new_btn", base["btn_start"])
    if fonts and fonts.get("subheading") is not None:
        dpg.bind_item_font("mobile_title", fonts["subheading"])


def _resize_settings(content_w, content_h):
    """Called by ui/layout.py whenever the window size changes."""
    row_w = _row_width(content_w)   # same edges as every other tab
    _state["row_w"] = row_w
    info_w = max(INFO_MIN_WIDTH, row_w - 2 * CHILD_PAD_X - 2 * CARD_SIDE_PAD - QR_TILE_SIZE
                 - QR_TO_INFO_GAP - INFO_WIDTH_TRIM)
    if dpg.does_item_exist("mobile_card"):
        dpg.configure_item("mobile_card", width=row_w)
    if dpg.does_item_exist("mobile_status_pill"):
        dpg.configure_item("mobile_status_pill",
                           pos=(row_w - STATUS_PILL_W - STATUS_RIGHT_MARGIN, STATUS_PILL_Y))
    if dpg.does_item_exist("mobile_info_table"):
        dpg.configure_item("mobile_info_table", width=info_w)
    if dpg.does_item_exist("mobile_hint_text"):
        dpg.configure_item("mobile_hint_text", wrap=info_w)
    _resize_ai(row_w)


def show_instruction_modal(sender=None, app_data=None, user_data=None):
    """Instruction button. The dialog itself lives in ui/settings_dialogs.py."""
    open_instruction_dialog()


def build_settings(parent, fonts, icons):
    _state["icons"] = icons
    _state["fonts"] = fonts
    init_toast()   # safe to call again: Quarantine and Exclusions call it too
    init_settings_dialogs(fonts, icons)   # the QR + Instruction pop-ups live in ui/settings_dialogs.py
    dpg.add_spacer(height=20, parent=parent)

    with dpg.group(horizontal=True, parent=parent):
        dpg.add_spacer(width=24)
        with dpg.group():
            dpg.add_text("Settings", tag="settings_page_title")
            dpg.bind_item_font("settings_page_title", fonts["heading"])
            dpg.add_text("Configure AI API settings and mobile pairing", color=COLORS["text_secondary"])
            dpg.add_spacer(height=15)

            _build_mobile_card(fonts, icons)

            dpg.add_spacer(height=20)

            _build_ai_card(fonts, icons)
            dpg.add_spacer(height=AI_BOTTOM_MARGIN)


    register_resize("settings", _resize_settings)
    _start_expiry_ticker()
    regenerate_mobile_qr(notify=False)   # first QR at launch, same as before
    refresh_settings()
