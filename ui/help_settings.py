import dearpygui.dearpygui as dpg
from ui.theme import COLORS
from ui.layout import register_resize
from ui import help_widgets as hw
from ui.help_explain import _term_table, _text_w
from ui.help_scan_results import _put_text, _put_centered
from ui.scan_layout import SECONDARY_COLORS, START_COLORS
from ui import settings as st
from ui import settings_dialogs as sd

try:
    from system.system_updates import SYSTEM_VERSION, INSTALLER_ASSET
except Exception:
    SYSTEM_VERSION = None
    INSTALLER_ASSET = "the installer"

# help_settings.py
# Help manual topic: Settings. Wording shown in the app (card titles, buttons, statuses, toast messages and the
# whole Instruction window) is read from ui/settings.py and ui/settings_dialogs.py, so it can't drift.

# ---- Switches (flip these when the matching work is done) ----
# True = the help bubble (CyberLearn) also works offline, with ready-made questions and no AI key.
# False = the manual says the bubble needs the AI Assistant settings to answer at all.
CYBERLEARN_HAS_OFFLINE_MODE = True

# ---- Shared sizes ----
DEFAULT_WIDTH = 540
DRAW_MIN_WIDTH = 480
DRAW_MAX_WIDTH = 720
SIDE_CHROME = 64                   # pane padding + scrollbar + breathing room, subtracted from the pane width
FRAME_DELAY = 3                    # frames to wait after a resize so help_manual sizes the pane first
DIAG_PAD = 8
ROUNDING = 8
CALLOUT_RADIUS_RATIO = 0.021
MIN_CALLOUT_RADIUS = 9
PILL_BG_ALPHA = 40
PILL_BORDER_ALPHA = 160
SUBHEADING_GAP = 14
TEXT_TOP_OFFSET = 4                # lines table text up with the middle of a chip
STATE_COLUMN = 230                 # first column of the chip tables (wide enough for "2 DEVICES CONNECTED")
TERM_FONT_KEY = "mono_small"

# ---- Overview diagram of the Settings tab (all values made up) ----
DIAG_TAG = "help_settings_diagram"
DIAG_TITLE_H = 30
DIAG_TITLE_SIZE = 16
DIAG_TEXT_SIZE = 12
DIAG_SMALL_SIZE = 10
DIAG_CARD_GAP = 12
DIAG_CARD_PAD = 12
DIAG_BADGE = 28
DIAG_BADGE_ICON = 16
DIAG_BADGE_ROUNDING = 8
DIAG_BADGE_ALPHA = 45
DIAG_BODY_TOP = 52                 # where each card's content starts, below its header
DIAG_BOTTOM_PAD = 10
DIAG_MOBILE_H = 164
DIAG_UPDATE_H = 90
DIAG_AI_H = 182
DIAG_INTRO_H = 108
DIAG_BTN_H = 24
DIAG_BTN_PAD = 26
DIAG_BTN_GAP = 8
DIAG_BTN_TEXT_SIZE = 11
DIAG_PILL_H = 20
DIAG_PILL_PAD = 24
DIAG_CHIP_H = 18
DIAG_CHIP_EXTRA = 14
DIAG_QR_SIZE = 76
DIAG_QR_INSET = 4
DIAG_QR_TO_INFO = 22
DIAG_HINT_TRIM = 20
DIAG_LABEL_H = 14
DIAG_INPUT_H = 24
DIAG_FIELD_GAP = 10
DIAG_BUTTONS_GAP = 12
DIAG_COL_GAP = 16
DIAG_EYE_ICON = 14
DIAG_COMBO_ARROW = (45, 58, 84)
DIAG_INTRO_BTN_MAX = 120
DIAG_URL_HINT = "e.g. https://openrouter.ai/..."
DIAG_INFO = (("System Name", "MY-PC"), ("Local Address", "192.168.0.10:5001"), ("System ID", "AYA-XXXXXXXX"))
QR_GRID = 9
QR_PATTERN = [                     # 9 x 9, "#" = dark cell. The three corners are drawn as finder squares instead
    "...#.#...",
    "...#..#..",
    "...#.##..",
    "#.#.#.#.#",
    ".#.#..#..",
    "#..##.#.#",
    "...#.#...",
    "...#..##.",
    "...##.#..",
]
QR_DARK = (20, 20, 30)
QR_FINDER = 3

# ---- Pairing flow strip ----
FLOW_TAG = "help_settings_flow"
FLOW_H = 96
FLOW_GAP = 22
FLOW_ICON = 26
FLOW_ICON_TOP = 14
FLOW_LABEL_TOP = 56
FLOW_LABEL_H = 20
FLOW_LABEL_SIZE = 12
FLOW_BADGE_SIZE = 11
FLOW_STEPS = [                     # (icon from icons.py, short label)
    ("qr_code", "Show code"),
    ("scan_search", "Scan it"),
    ("smartphone", "Install"),
    ("qr_code", "Scan in app"),
    ("shield_check", "Paired"),
]

# ---- Dialog replicas ----
QR_REPLICA_TILE = 190
QR_REPLICA_INSET = 12
HEADER_BADGE = 40
HEADER_ICON = 24
HEADER_BADGE_ROUNDING = 12
STEP_BADGE = 30
STEP_GAP = 14
LINES_GAP = 4
CODE_BOX_PADDING = (12, 8)
INTRO_REPLICA_BTN_W = 160
UPDATE_BUTTON_W = st.BTN_W
AI_BUTTON_W = st.BTN_W

# ---- Messages that settings.py builds inline (copied from check_system_update in ui/settings.py; update here if they change) ----
UPDATE_MESSAGES = [
    ("Checking for system updates...", "accent_blue",
     "The check is running. The button is greyed out until it finishes."),
    ("AYAWrus is up to date", "accent_green", "You already have the newest version."),
    ("System update 1.2.3 is available", "accent_blue",
     "A newer version exists, and its download page opens in your browser. The number is an example."),
    ("Couldn't open the system update page", "accent_red",
     "A newer version exists, but your browser couldn't be opened."),
    ("Couldn't check GitHub releases: ...", "accent_red",
     "AYAWrus couldn't reach GitHub, for example because the computer is offline. The text after the colon says why."),
    ("System update 1.2.3 is missing AYAWrus-Setup.exe.", "accent_red",
     "A newer version was published, but its installer file isn't attached yet, so there is nothing to download. "
     "Try again later."),
    ("System update check failed: ...", "accent_red",
     "Something unexpected went wrong. The text after the colon says what."),
]
WARNING_MEANINGS = [               # (problem text from ui/settings.py, meaning)
    (st.PROBLEM_URL_EMPTY, "The API URL box is empty."),
    (st.PROBLEM_URL_BAD, "The API URL doesn't start with http:// or https://."),
    (st.PROBLEM_KEY_EMPTY, "The API Key box is empty."),
    (st.PROBLEM_CUSTOM_EMPTY, "You picked custom but left the name empty, so the model you had before is kept."),
]
INTRO_MEANINGS = {
    "always": "The intro plays every time AYAWrus opens.",
    "once_per_boot": "The intro plays only the first time AYAWrus opens after your PC starts.",
    "never": "AYAWrus opens without the intro.",
}


def _text_size_w(text, size):
    return _text_w(text, size)


def _pill(dl, x0, y0, x1, y1, color, text, size):
    dpg.draw_rectangle((x0, y0), (x1, y1), color=(*color[:3], PILL_BORDER_ALPHA), fill=(*color[:3], PILL_BG_ALPHA),
                       rounding=(y1 - y0) / 2, parent=dl)
    _put_centered(dl, text, x0, x1, y0, y1, size, color[:3])


def _button(dl, x, y, text, bg, fg, width=None):
    w = width or (_text_size_w(text, DIAG_BTN_TEXT_SIZE) + DIAG_BTN_PAD)
    dpg.draw_rectangle((x, y), (x + w, y + DIAG_BTN_H), color=(0, 0, 0, 0), fill=bg, rounding=4, parent=dl)
    _put_centered(dl, text, x, x + w, y, y + DIAG_BTN_H, DIAG_BTN_TEXT_SIZE, fg)
    return x + w


def _subheading(text, fonts):
    dpg.add_spacer(height=SUBHEADING_GAP)
    t = dpg.add_text(text, color=COLORS["text_primary"])
    font = fonts.get("subheading")
    if font is not None:
        dpg.bind_item_font(t, font)
    dpg.add_spacer(height=4)


def _chip_table(rows, fonts):
    """rows = (chip text, color name, meaning)."""
    with dpg.table(header_row=False, borders_innerH=False, borders_outerH=False,
                   borders_innerV=False, borders_outerV=False):
        dpg.add_table_column(width_fixed=True, init_width_or_weight=STATE_COLUMN)
        dpg.add_table_column(width_stretch=True, init_width_or_weight=1.0)
        for chip_text, color_name, meaning in rows:
            with dpg.table_row():
                with dpg.group():
                    hw.chip(chip_text, color_name, fonts)
                    dpg.add_spacer(height=4)
                with dpg.group():
                    dpg.add_spacer(height=TEXT_TOP_OFFSET)
                    dpg.add_text(meaning, wrap=0, color=hw.HELP_BODY_COLOR)
                    dpg.add_spacer(height=4)
    hw.gap()


# ---------- fake QR code ----------

def _draw_qr(dl, x, y, size):
    clear = (0, 0, 0, 0)
    cell = size / (QR_GRID + 2)        # one empty cell of margin all around
    ox, oy = x + cell, y + cell
    for row in range(QR_GRID):
        for col in range(QR_GRID):
            in_finder = ((row < QR_FINDER and col < QR_FINDER)
                         or (row < QR_FINDER and col >= QR_GRID - QR_FINDER)
                         or (row >= QR_GRID - QR_FINDER and col < QR_FINDER))
            if in_finder or QR_PATTERN[row][col] != "#":
                continue
            dpg.draw_rectangle((ox + col * cell, oy + row * cell), (ox + (col + 1) * cell, oy + (row + 1) * cell),
                               color=clear, fill=QR_DARK, parent=dl)
    for frow, fcol in ((0, 0), (0, QR_GRID - QR_FINDER), (QR_GRID - QR_FINDER, 0)):
        fx, fy = ox + fcol * cell, oy + frow * cell
        dpg.draw_rectangle((fx, fy), (fx + QR_FINDER * cell, fy + QR_FINDER * cell), color=clear, fill=QR_DARK, parent=dl)
        dpg.draw_rectangle((fx + cell * 0.7, fy + cell * 0.7), (fx + cell * 2.3, fy + cell * 2.3), color=clear,
                           fill=(255, 255, 255), parent=dl)
        dpg.draw_rectangle((fx + cell * 1.1, fy + cell * 1.1), (fx + cell * 1.9, fy + cell * 1.9), color=clear,
                           fill=QR_DARK, parent=dl)


# ---------- overview diagram (redrawn to fit the pane whenever the window resizes) ----------

def _diag_height():
    return int(DIAG_TITLE_H + DIAG_MOBILE_H + DIAG_UPDATE_H + DIAG_AI_H + DIAG_INTRO_H
               + 3 * DIAG_CARD_GAP + DIAG_BOTTOM_PAD)


def _frame(dl, x0, y0, x1, height):
    dpg.draw_rectangle((x0, y0), (x1, y0 + height), color=COLORS["border"], fill=COLORS["bg_card"],
                       rounding=ROUNDING, parent=dl)


def _card_header(dl, x0, y0, icon_key, title, helper):
    blue = COLORS["accent_blue"]
    bx0, by0 = x0 + DIAG_CARD_PAD, y0 + DIAG_CARD_PAD
    dpg.draw_rectangle((bx0, by0), (bx0 + DIAG_BADGE, by0 + DIAG_BADGE), color=(0, 0, 0, 0),
                       fill=(*blue, DIAG_BADGE_ALPHA), rounding=DIAG_BADGE_ROUNDING, parent=dl)
    tex = f"tex_{icon_key}"
    if dpg.does_item_exist(tex):
        off = (DIAG_BADGE - DIAG_BADGE_ICON) / 2
        dpg.draw_image(tex, (bx0 + off, by0 + off), (bx0 + off + DIAG_BADGE_ICON, by0 + off + DIAG_BADGE_ICON),
                       color=blue, parent=dl)
    tx = bx0 + DIAG_BADGE + 8
    _put_text(dl, title, tx, by0, by0 + DIAG_BADGE / 2, DIAG_TEXT_SIZE + 1, COLORS["text_primary"])
    _put_text(dl, helper, tx, by0 + DIAG_BADGE / 2, by0 + DIAG_BADGE, DIAG_SMALL_SIZE, COLORS["text_secondary"])


def _draw_mobile(dl, x0, y0, x1):
    clear = (0, 0, 0, 0)
    _frame(dl, x0, y0, x1, DIAG_MOBILE_H)
    _card_header(dl, x0, y0, "smartphone", st.MOBILE_TITLE, st.MOBILE_HELPER)

    pill_w = _text_size_w(st.STATUS_NONE, DIAG_SMALL_SIZE) + DIAG_PILL_PAD
    pill_x1 = x1 - DIAG_CARD_PAD
    pill_x0 = pill_x1 - pill_w
    pill_y0 = y0 + DIAG_CARD_PAD
    _pill(dl, pill_x0, pill_y0, pill_x1, pill_y0 + DIAG_PILL_H, COLORS["text_secondary"], st.STATUS_NONE,
          DIAG_SMALL_SIZE)

    tx0, ty0 = x0 + DIAG_CARD_PAD, y0 + DIAG_BODY_TOP
    dpg.draw_rectangle((tx0, ty0), (tx0 + DIAG_QR_SIZE, ty0 + DIAG_QR_SIZE), color=clear, fill=(255, 255, 255),
                       rounding=10, parent=dl)
    _draw_qr(dl, tx0 + DIAG_QR_INSET, ty0 + DIAG_QR_INSET, DIAG_QR_SIZE - 2 * DIAG_QR_INSET)
    chip_y0 = ty0 + DIAG_QR_SIZE + 6
    _pill(dl, tx0, chip_y0, tx0 + DIAG_QR_SIZE + DIAG_CHIP_EXTRA, chip_y0 + DIAG_CHIP_H, COLORS["accent_blue"],
          st.EXPIRY_TEXT.format(time="03:05"), DIAG_SMALL_SIZE - 1)

    ix = tx0 + DIAG_QR_SIZE + DIAG_QR_TO_INFO
    col_w = (x1 - DIAG_CARD_PAD - ix) / 3
    for i, (label, value) in enumerate(DIAG_INFO):
        cx = ix + i * col_w
        _put_text(dl, label, cx, ty0, ty0 + 12, DIAG_SMALL_SIZE, COLORS["text_secondary"])
        _put_text(dl, value, cx, ty0 + 14, ty0 + 26, DIAG_SMALL_SIZE, COLORS["text_primary"])
    dpg.draw_rectangle((ix, ty0 + 40), (x1 - DIAG_CARD_PAD - DIAG_HINT_TRIM, ty0 + 44), color=clear,
                       fill=(*COLORS["text_secondary"], 110), rounding=2, parent=dl)
    by = ty0 + 56
    nx = _button(dl, ix, by, st.BTN_VIEW_QR, SECONDARY_COLORS[0], SECONDARY_COLORS[3])
    _button(dl, nx + DIAG_BTN_GAP, by, st.BTN_NEW_QR, START_COLORS[0], START_COLORS[3])
    return pill_x0, pill_y0 + DIAG_PILL_H / 2


def _draw_update(dl, x0, y0, x1):
    _frame(dl, x0, y0, x1, DIAG_UPDATE_H)
    _card_header(dl, x0, y0, "refresh", st.UPDATE_TITLE, st.UPDATE_HELPER)
    _button(dl, x0 + DIAG_CARD_PAD, y0 + DIAG_BODY_TOP, st.BTN_UPDATE, START_COLORS[0], START_COLORS[3])


def _draw_ai(dl, x0, y0, x1):
    border = COLORS["border"]
    secondary = COLORS["text_secondary"]
    primary = COLORS["text_primary"]
    _frame(dl, x0, y0, x1, DIAG_AI_H)
    _card_header(dl, x0, y0, "key_round", st.AI_TITLE, st.AI_HELPER)
    inner0, inner1 = x0 + DIAG_CARD_PAD, x1 - DIAG_CARD_PAD
    col_w = (inner1 - inner0 - DIAG_COL_GAP) / 2
    right0 = inner0 + col_w + DIAG_COL_GAP
    top1 = y0 + DIAG_BODY_TOP - 2
    top2 = top1 + DIAG_LABEL_H + DIAG_INPUT_H + DIAG_FIELD_GAP

    def field(x, top, width, label, text, text_color):
        box_y0 = top + DIAG_LABEL_H
        _put_text(dl, label, x, top, top + DIAG_LABEL_H, DIAG_SMALL_SIZE, secondary)
        dpg.draw_rectangle((x, box_y0), (x + width, box_y0 + DIAG_INPUT_H), color=border, fill=COLORS["bg_sidebar"],
                           rounding=4, parent=dl)
        _put_text(dl, text, x + 8, box_y0, box_y0 + DIAG_INPUT_H, DIAG_SMALL_SIZE, text_color)
        return box_y0

    field(inner0, top1, col_w, st.AI_LABEL_URL, DIAG_URL_HINT, secondary)
    key_y0 = field(inner0, top2, col_w - DIAG_INPUT_H - 6, st.AI_LABEL_KEY, st.AI_HINT_KEY, secondary)
    eye_x0 = inner0 + col_w - DIAG_INPUT_H
    dpg.draw_rectangle((eye_x0, key_y0), (eye_x0 + DIAG_INPUT_H, key_y0 + DIAG_INPUT_H), color=border,
                       fill=COLORS["bg_sidebar"], rounding=4, parent=dl)
    if dpg.does_item_exist("tex_eye"):
        off = (DIAG_INPUT_H - DIAG_EYE_ICON) / 2
        dpg.draw_image("tex_eye", (eye_x0 + off, key_y0 + off), (eye_x0 + off + DIAG_EYE_ICON, key_y0 + off + DIAG_EYE_ICON),
                       color=secondary, parent=dl)
    combo_y0 = field(right0, top1, col_w, st.AI_LABEL_MODEL, st.AVAILABLE_AI_MODELS[0], primary)
    arrow_x0 = right0 + col_w - DIAG_INPUT_H
    dpg.draw_rectangle((arrow_x0, combo_y0), (right0 + col_w, combo_y0 + DIAG_INPUT_H), color=border,
                       fill=DIAG_COMBO_ARROW, rounding=4, parent=dl)
    ax, ay = arrow_x0 + DIAG_INPUT_H / 2, combo_y0 + DIAG_INPUT_H / 2
    dpg.draw_triangle((ax - 4, ay - 2), (ax + 4, ay - 2), (ax, ay + 3), color=primary, fill=primary, parent=dl)

    btn_y = top2 + DIAG_LABEL_H + DIAG_INPUT_H + DIAG_BUTTONS_GAP
    ix = _button(dl, inner0, btn_y, st.BTN_INSTRUCTION, SECONDARY_COLORS[0], SECONDARY_COLORS[3])
    sx = _button(dl, ix + DIAG_BTN_GAP, btn_y, st.BTN_SAVE, START_COLORS[0], START_COLORS[3])
    _put_text(dl, st.AI_SAVE_NOTE, sx + DIAG_BTN_GAP + 4, btn_y, btn_y + DIAG_BTN_H, DIAG_SMALL_SIZE, secondary)


def _draw_intro(dl, x0, y0, x1):
    _frame(dl, x0, y0, x1, DIAG_INTRO_H)
    _card_header(dl, x0, y0, "play", st.INTRO_TITLE, st.INTRO_HELPER)
    inner0, inner1 = x0 + DIAG_CARD_PAD, x1 - DIAG_CARD_PAD
    count = len(st.INTRO_MODES)
    bw = min(DIAG_INTRO_BTN_MAX, (inner1 - inner0 - (count - 1) * DIAG_BTN_GAP) / count)
    by = y0 + DIAG_BODY_TOP
    for i, (_mode, label) in enumerate(st.INTRO_MODES):
        colors = START_COLORS if i == 0 else SECONDARY_COLORS
        _button(dl, inner0 + i * (bw + DIAG_BTN_GAP), by, label, colors[0], colors[3], width=bw)
    _put_text(dl, st.INTRO_NOTE, inner0, by + DIAG_BTN_H + 6, by + DIAG_BTN_H + 20, DIAG_SMALL_SIZE,
              COLORS["text_primary"])


def _draw_diagram(w):
    dl = DIAG_TAG
    dpg.delete_item(dl, children_only=True)
    r = max(MIN_CALLOUT_RADIUS, int(w * CALLOUT_RADIUS_RATIO))
    x0, x1 = DIAG_PAD, w - DIAG_PAD
    dpg.draw_rectangle((0, 0), (w - 1, _diag_height() - 1), color=COLORS["border"], fill=COLORS["bg_main"],
                       rounding=ROUNDING, parent=dl)
    _put_text(dl, "Settings", x0, 0, DIAG_TITLE_H, DIAG_TITLE_SIZE, COLORS["text_primary"])

    y = DIAG_TITLE_H
    pill_x0, pill_mid = _draw_mobile(dl, x0, y, x1)
    y += DIAG_MOBILE_H + DIAG_CARD_GAP
    update_y = y
    _draw_update(dl, x0, y, x1)
    y += DIAG_UPDATE_H + DIAG_CARD_GAP
    ai_y = y
    _draw_ai(dl, x0, y, x1)
    y += DIAG_AI_H + DIAG_CARD_GAP
    intro_y = y
    _draw_intro(dl, x0, y, x1)

    # numbered callouts last, so they sit on top
    hw.draw_callout(pill_x0 - r - 8, pill_mid, 1, radius=r, parent=dl)
    for number, top in ((2, update_y), (3, ai_y), (4, intro_y)):
        hw.draw_callout(x1 - r - 10, top + r + 8, number, radius=r, parent=dl)


def _build_diagram():
    with dpg.drawlist(width=DEFAULT_WIDTH, height=_diag_height(), tag=DIAG_TAG):
        pass
    _draw_diagram(DEFAULT_WIDTH)
    hw.gap()


# ---------- pairing flow strip ----------

def _chevron(dl, x, y):
    color = COLORS["text_secondary"]
    dpg.draw_line((x - 3, y - 5), (x + 2, y), color=color, thickness=2, parent=dl)
    dpg.draw_line((x + 2, y), (x - 3, y + 5), color=color, thickness=2, parent=dl)


def _draw_flow(w):
    dl = FLOW_TAG
    dpg.delete_item(dl, children_only=True)
    count = len(FLOW_STEPS)
    tile_w = (w - (count - 1) * FLOW_GAP) / count
    for i, (icon_name, label) in enumerate(FLOW_STEPS):
        last = i == count - 1
        x0 = i * (tile_w + FLOW_GAP)
        x1 = x0 + tile_w
        dpg.draw_rectangle((x0, 0), (x1, FLOW_H - 1), color=COLORS["accent_green"] if last else COLORS["border"],
                           fill=COLORS["bg_card"] if last else COLORS["bg_sidebar"], rounding=ROUNDING, parent=dl)
        tex = f"tex_{icon_name}"
        if dpg.does_item_exist(tex):
            cx = (x0 + x1) / 2
            dpg.draw_image(tex, (cx - FLOW_ICON / 2, FLOW_ICON_TOP), (cx + FLOW_ICON / 2, FLOW_ICON_TOP + FLOW_ICON),
                           color=COLORS["accent_green"] if last else COLORS["accent_blue"], parent=dl)
        _put_centered(dl, label, x0, x1, FLOW_LABEL_TOP, FLOW_LABEL_TOP + FLOW_LABEL_H, FLOW_LABEL_SIZE,
                      COLORS["text_primary"])
        dpg.draw_text((x1 - 14, 4), str(i + 1), color=COLORS["text_secondary"], size=FLOW_BADGE_SIZE, parent=dl)
        if not last:
            _chevron(dl, x1 + FLOW_GAP / 2, FLOW_H / 2)


def _build_flow():
    with dpg.drawlist(width=DEFAULT_WIDTH, height=FLOW_H, tag=FLOW_TAG):
        pass
    _draw_flow(DEFAULT_WIDTH)
    hw.gap()


# ---------- resize ----------

def _fit_all():
    if not dpg.does_item_exist(hw.HELP_CONTENT_PANE_TAG):
        return
    pane_w = dpg.get_item_width(hw.HELP_CONTENT_PANE_TAG)
    w = int(max(DRAW_MIN_WIDTH, min(DRAW_MAX_WIDTH, pane_w - SIDE_CHROME)))
    if dpg.does_item_exist(DIAG_TAG):
        dpg.configure_item(DIAG_TAG, width=w, height=_diag_height())
        _draw_diagram(w)
    if dpg.does_item_exist(FLOW_TAG):
        dpg.configure_item(FLOW_TAG, width=w, height=FLOW_H)
        _draw_flow(w)


def _on_layout_resize(content_w, content_h):
    # help_manual sizes the pane in its own resize handler, which may run AFTER this one,
    # so wait a few frames and then read the pane's final width.
    dpg.set_frame_callback(dpg.get_frame_count() + FRAME_DELAY, lambda *args: _fit_all())


# ---------- dialog replicas (pictures of ui/settings_dialogs.py) ----------

def _dialog_header(icon_key, title, helper, fonts):
    blue = COLORS["accent_blue"]
    with dpg.group(horizontal=True):
        with dpg.drawlist(width=HEADER_BADGE, height=HEADER_BADGE):
            dpg.draw_rectangle((0, 0), (HEADER_BADGE - 1, HEADER_BADGE - 1), color=(0, 0, 0, 0), fill=(*blue, 45),
                               rounding=HEADER_BADGE_ROUNDING)
            tex = f"tex_{icon_key}"
            if dpg.does_item_exist(tex):
                off = (HEADER_BADGE - HEADER_ICON) / 2
                dpg.draw_image(tex, (off, off), (off + HEADER_ICON, off + HEADER_ICON), color=blue)
        with dpg.group():
            t = dpg.add_text(title, color=COLORS["text_primary"])
            font = fonts.get("subheading")
            if font is not None:
                dpg.bind_item_font(t, font)
            dpg.add_text(helper, color=COLORS["text_secondary"])


def _qr_dialog_replica(fonts):
    inner_w = sd.QR_DLG_W - 2 * sd.DLG_PAD
    with dpg.child_window(width=sd.QR_DLG_W, auto_resize_y=True, border=True) as box:
        _dialog_header("qr_code", sd.QR_TITLE, sd.QR_HELPER, fonts)
        dpg.add_spacer(height=sd.HEADER_GAP)
        with dpg.group(indent=max(0, (inner_w - QR_REPLICA_TILE) // 2)):
            with dpg.drawlist(width=QR_REPLICA_TILE, height=QR_REPLICA_TILE) as tile:
                dpg.draw_rectangle((0, 0), (QR_REPLICA_TILE, QR_REPLICA_TILE), color=(0, 0, 0, 0),
                                   fill=(255, 255, 255), rounding=sd.QR_TILE_ROUNDING)
                _draw_qr(tile, QR_REPLICA_INSET, QR_REPLICA_INSET, QR_REPLICA_TILE - 2 * QR_REPLICA_INSET)
        dpg.add_spacer(height=sd.QR_TILE_GAP)
        dpg.add_text(sd.QR_HINT, wrap=inner_w, color=COLORS["text_secondary"])
        dpg.add_spacer(height=sd.QR_BTN_GAP)
        hw.fake_button(sd.BTN_CLOSE, SECONDARY_COLORS[0], SECONDARY_COLORS[3], width=inner_w)
    dpg.bind_item_theme(box, hw.child_card_theme(COLORS["bg_card"], sd.DLG_BORDER, (sd.DLG_PAD, sd.DLG_PAD)))
    hw.gap()


def _lines(lines):
    for line in lines:
        dpg.add_text(line, wrap=0, color=COLORS["text_secondary"])


def _code_box(value, fonts):
    with dpg.child_window(width=-1, auto_resize_y=True, border=True) as box:
        t = dpg.add_text(value, wrap=0, color=COLORS["text_primary"])
        font = fonts.get(TERM_FONT_KEY)
        if font is not None:
            dpg.bind_item_font(t, font)
    dpg.bind_item_theme(box, hw.child_card_theme(COLORS["bg_sidebar"], COLORS["border"], CODE_BOX_PADDING))


def _step_replica(number, title, fonts, build_content):
    blue = COLORS["accent_blue"]
    with dpg.group(horizontal=True):
        with dpg.drawlist(width=STEP_BADGE, height=STEP_BADGE):
            dpg.draw_circle((STEP_BADGE / 2, STEP_BADGE / 2), STEP_BADGE / 2 - 1, color=(*blue, 110), fill=(*blue, 60))
            label = str(number)
            tw, th = hw._measure(label)
            dpg.draw_text(((STEP_BADGE - tw) / 2, (STEP_BADGE - th) / 2), label, color=blue,
                          size=hw.HELP_FAKE_TEXT_SIZE)
        with dpg.group():
            t = dpg.add_text(title, color=COLORS["text_primary"])
            font = fonts.get("subheading")
            if font is not None:
                dpg.bind_item_font(t, font)
            build_content()
    dpg.add_spacer(height=STEP_GAP)


def _instruction_replica(fonts):
    def step2():
        dpg.add_text(sd.STEP2_URL_LABEL, wrap=0, color=COLORS["text_secondary"])
        _code_box(sd.DEFAULT_API_URL, fonts)
        _lines(sd.STEP2_LINES)

    def step3():
        _lines(sd.STEP3_LINES)
        dpg.add_text(sd.STEP3_MODEL_LABEL, wrap=0, color=COLORS["text_secondary"])
        _code_box(sd.RECOMMENDED_MODEL, fonts)
        _lines((sd.STEP3_FREE, sd.STEP3_PAID))

    with dpg.child_window(width=-1, auto_resize_y=True, border=True) as box:
        _dialog_header("key_round", sd.INSTR_TITLE, sd.INSTR_HELPER, fonts)
        dpg.add_spacer(height=sd.HEADER_GAP)
        _step_replica(1, sd.STEP1_TITLE, fonts, lambda: _lines(sd.STEP1_LINES))
        _step_replica(2, sd.STEP2_TITLE, fonts, step2)
        _step_replica(3, sd.STEP3_TITLE, fonts, step3)
        tips = dpg.add_text(sd.TIPS_TITLE, color=COLORS["text_primary"])
        if fonts.get("subheading") is not None:
            dpg.bind_item_font(tips, fonts["subheading"])
        _lines(sd.TIPS_LINES)
        dpg.add_spacer(height=STEP_GAP)
        with dpg.group(horizontal=True):
            hw.fake_button(sd.BTN_VISIT, SECONDARY_COLORS[0], SECONDARY_COLORS[3])
            hw.fake_button(sd.BTN_CLOSE, START_COLORS[0], START_COLORS[3], width=sd.CLOSE_W)
    dpg.bind_item_theme(box, hw.child_card_theme(COLORS["bg_card"], sd.DLG_BORDER, (sd.DLG_PAD, sd.DLG_PAD)))
    hw.gap()


# ---------- sections ----------

def _build_mobile(fonts, icons):
    hw.paragraph("Pairing links your phone to this PC, so the phone can show alerts when a scan finds a threat. "
                 "Your phone and PC need to be on the same network, for example the same Wi-Fi, because the code "
                 "points to your PC's local address.")

    _subheading("Pair a phone", fonts)
    hw.paragraph("The first time, you install the AYAWrus Mobile app and then link it. After that, only the last "
                 "steps matter.")
    _build_flow()
    hw.numbered_row(1, "Show the code", "A code is made when AYAWrus starts. If the countdown says "
                                         f"{st.EXPIRY_EXPIRED}, press {st.BTN_NEW_QR}.")
    hw.numbered_row(2, "Scan it with any QR scanner", "Your phone's camera or any scanner app works. It opens a page "
                                                      "from this PC with the AYAWrus Mobile installer, an APK file. "
                                                      "You only need this step the first time.")
    hw.numbered_row(3, "Install the app", "Download and install it. Your phone may ask permission to install apps from "
                                          "outside the app store.")
    hw.numbered_row(4, "Open AYAWrus Mobile", "Tap Scan QR Code inside the app.")
    hw.numbered_row(5, "Scan the code on your PC screen", "Use the same code. Do it before the countdown ends. If it "
                                                          f"runs out, press {st.BTN_NEW_QR} and scan the new one.")
    hw.numbered_row(6, "Check the status", f"Reopen the Settings tab and the pill at the top right turns green, for "
                                           f"example {st.STATUS_ONE}.")

    _subheading("Reading the card", fonts)
    hw.paragraph("The pill at the top right shows how many phones are connected to this PC right now:")
    _chip_table([
        (st.STATUS_NONE, "text_secondary", "No phone is connected right now."),
        (st.STATUS_ONE, "accent_green", "One phone is connected."),
        (st.STATUS_MANY.format(n=2), "accent_green", "More than one phone is connected. The number tells you how many."),
    ], fonts)
    hw.paragraph("The chip under the QR code is a countdown. Each code works once and lasts 5 minutes:")
    _chip_table([
        (st.EXPIRY_TEXT.format(time="03:05"), "accent_blue", "The code is valid. The time left counts down."),
        (st.EXPIRY_TEXT.format(time="00:45"), "accent_orange",
         f"Under {st.EXPIRY_WARN_SECONDS} seconds left. Finish pairing, or make a new code."),
        (st.EXPIRY_EXPIRED, "accent_red", f"The code ran out. Press {st.BTN_NEW_QR}."),
        (st.EXPIRY_NONE, "text_secondary",
         f"There is no code right now, for example because one couldn't be made. Press {st.BTN_NEW_QR}."),
    ], fonts)
    hw.paragraph("Next to the QR code you also see details about this PC:")
    _term_table([
        ("System Name", "text_primary", "This PC's name."),
        ("Local Address", "text_primary", "The address your phone uses to reach AYAWrus on this PC, with the port "
                                          "number. It says 'Network unavailable' when the PC isn't connected to a "
                                          "network. The copy icon next to it copies the address."),
        ("System ID", "text_primary", "A code that identifies AYAWrus on this PC. It is generated each time AYAWrus starts, so it changes after a restart. The copy icon next to it copies it."),
        ("QR code", "text_primary", f"The white square holds the pairing code. It says '{st.QR_UNAVAILABLE_TEXT}' if "
                                    "a code couldn't be made."),
    ])

    _subheading("The two buttons", fonts)
    _term_table([
        (st.BTN_VIEW_QR, "text_primary", "Shows the code larger in a pop-up window, which is easier to scan. If there "
                                         "is no code yet, you get a message asking you to make one. Press Esc or "
                                         "Close to dismiss it."),
        (st.BTN_NEW_QR, "text_primary", "Makes a fresh code and restarts the 5-minute countdown."),
    ])
    hw.paragraph("This is the View QR Code window (the code in the picture is only a drawing):")
    _qr_dialog_replica(fonts)

    _subheading("Messages you may see", fonts)
    _term_table([
        (st.MSG_QR_READY, "accent_green", "A new code is ready."),
        (st.MSG_NO_QR, "accent_orange", "You pressed View QR Code before a code existed."),
        (st.MSG_QR_FAILED, "accent_red", "A code couldn't be made. The terminal window has the technical reason."),
        (st.MSG_COPIED, "accent_green", "The address or ID was copied."),
        (st.MSG_COPY_FAILED, "accent_red", "Copying didn't work. The terminal window has the technical reason."),
    ])


def _build_update(fonts, icons):
    hw.paragraph("System Update checks whether a newer version of AYAWrus has been published. It needs an internet "
                 "connection.")
    if SYSTEM_VERSION:
        hw.paragraph("This copy of AYAWrus is version " + ".".join(map(str, SYSTEM_VERSION)) + ". New versions are "
                     f"published on GitHub with an installer file called {INSTALLER_ASSET}.")
    hw.fake_button(st.BTN_UPDATE, START_COLORS[0], START_COLORS[3], width=UPDATE_BUTTON_W)
    hw.gap()
    hw.paragraph("If a newer version exists, AYAWrus opens its download page in your browser, and you download and "
                 "install it yourself. Nothing is installed automatically. A message tells you what happened:")
    _term_table(UPDATE_MESSAGES)


def _models_list():
    with dpg.collapsing_header(label=f"Models in the list ({len(st.AVAILABLE_AI_MODELS)})", default_open=False):
        for model in st.AVAILABLE_AI_MODELS:
            dpg.add_text(model, color=COLORS["text_secondary"])
    hw.gap()


def _build_ai(fonts, icons):
    intro = ("The AI Assistant settings let AYAWrus's help bubble (CyberLearn) use an online AI service.")
    if CYBERLEARN_HAS_OFFLINE_MODE:
        intro += (" Without them the bubble still works offline: you pick from its ready-made questions, such as "
                  "'What is a trojan?', and it shows the stored answer. With them, it can also answer questions you "
                  "type yourself, which needs an internet connection.")
    else:
        intro += " The bubble needs them to answer."
    hw.paragraph(intro)

    _subheading("The fields", fonts)
    _term_table([
        (st.AI_LABEL_URL, "text_primary", f"The address of the AI service. For OpenRouter it is {sd.DEFAULT_API_URL}. "
                                          "It should start with http:// or https://."),
        (st.AI_LABEL_KEY, "text_primary", "Your private key from the service. It is hidden as dots. The eye button next "
                                          "to it shows or hides it, and it is hidden again whenever you come back to "
                                          "the tab."),
        (st.AI_LABEL_MODEL, "text_primary", "Which AI model answers. Pick one from the list."),
        (st.AI_LABEL_CUSTOM, "text_primary", "Appears only when you pick 'custom' at the bottom of the list. Type any "
                                             f"model name your service offers, such as {st.AI_HINT_CUSTOM.replace('e.g. ', '')}."),
    ])
    hw.paragraph("Open the list below to see the models you can pick from. Models that end in :free cost nothing but "
                 "can be slow or busy.")
    _models_list()

    _subheading("Save Settings", fonts)
    with dpg.group(horizontal=True):
        hw.fake_button(st.BTN_INSTRUCTION, SECONDARY_COLORS[0], SECONDARY_COLORS[3], width=AI_BUTTON_W)
        hw.fake_button(st.BTN_SAVE, START_COLORS[0], START_COLORS[3], width=AI_BUTTON_W)
        dpg.add_text(st.AI_SAVE_NOTE, color=COLORS["text_secondary"])
    hw.gap()
    hw.paragraph("Spaces around what you paste are removed automatically. AYAWrus saves your settings even when "
                 "something looks incomplete, and then tells you:")
    _term_table([
        (st.MSG_SAVED, "accent_green", "Everything was saved with no problems."),
        (st.MSG_SAVED_WARN.format(problem=st.PROBLEM_KEY_EMPTY), "accent_orange",
         "It was saved, but something looks incomplete. If there are several problems, the first is shown, plus "
         "'(+N more)'."),
        (st.MSG_SAVE_FAILED, "accent_red", "It couldn't be saved. The terminal window has the technical reason."),
    ])
    hw.paragraph("These are the problems it can point out:")
    _term_table([(st.MSG_SAVED_WARN.format(problem=problem), "accent_orange", meaning)
                 for problem, meaning in WARNING_MEANINGS])

    _subheading("The Instruction window", fonts)
    hw.paragraph(f"Press {st.BTN_INSTRUCTION} to open a short guide to setting this up. Here is what it shows:")
    _instruction_replica(fonts)


def _build_intro(fonts, icons):
    hw.paragraph("The intro is the short animation that plays when AYAWrus opens. Choose how often you want to see it. "
                 "The selected choice is blue.")
    with dpg.group(horizontal=True):
        for i, (_mode, label) in enumerate(st.INTRO_MODES):
            colors = START_COLORS if i == 0 else SECONDARY_COLORS
            hw.fake_button(label, colors[0], colors[3], width=INTRO_REPLICA_BTN_W)
    hw.gap()
    _term_table([(label, "text_primary", INTRO_MEANINGS.get(mode, "")) for mode, label in st.INTRO_MODES])
    hw.paragraph(f"{st.INTRO_NOTE}. Pressing a button saves your choice right away and shows a message:")
    _term_table([
        (st.MSG_INTRO_SET.format(label=st.INTRO_MODES[-1][1]), "accent_green", "Your choice was saved."),
        (st.MSG_INTRO_FAILED, "accent_red", "It couldn't be saved. The terminal window has the technical reason."),
    ])


# ---------- the topic ----------

def build_topic(fonts, icons):
    hw.page_heading("Settings", "Pair a phone, check for updates, connect the AI Assistant and choose the intro.", fonts)
    hw.paragraph("Settings is made of four cards. Each one is independent: you can use any of them without touching "
                 "the others.")

    hw.section_heading("What you're looking at", fonts)
    hw.paragraph("Here is the tab in simplified form (made-up values). The numbers match the list underneath.")
    _build_diagram()
    hw.numbered_row(1, st.MOBILE_TITLE, f"{st.MOBILE_HELPER}.")
    hw.numbered_row(2, st.UPDATE_TITLE, "Checks whether a newer version of AYAWrus has been published.")
    hw.numbered_row(3, st.AI_TITLE, "Connects an online AI service to the help bubble.")
    hw.numbered_row(4, st.INTRO_TITLE, f"{st.INTRO_HELPER}.")

    hw.section_heading(st.MOBILE_TITLE, fonts)
    _build_mobile(fonts, icons)

    hw.section_heading(st.UPDATE_TITLE, fonts)
    _build_update(fonts, icons)

    hw.section_heading(st.AI_TITLE, fonts)
    _build_ai(fonts, icons)

    hw.section_heading(st.INTRO_TITLE, fonts)
    _build_intro(fonts, icons)

    hw.section_heading("Good to know", fonts)
    hw.tip_box("note", "Save before you leave",
               "Opening the Settings tab reloads what was saved, so AI Assistant fields you typed but didn't save "
               "are cleared. The other cards take effect as soon as you press their buttons.", icons)
    hw.tip_box("note", "Your API key is stored as plain text",
               "The key is saved in config.json on this PC. Keep it private, and don't share that file.", icons)
    hw.tip_box("note", "Treat the pairing code like a password",
               "Anyone who scans an active code can pair with your PC. Don't share a picture of it. Each code "
               "works once and stops working after 5 minutes.", icons)
    hw.tip_box("note", "Connections don't last forever",
               "Pairing details are kept in memory only, so they are gone when AYAWrus closes. A phone's connection "
               "also lasts 30 minutes unless its app renews it. If the pill says NO DEVICE PAIRED when you expected a "
               "phone, pair it again.", icons)
    hw.tip_box("tip", "The status pill isn't live",
               "The pairing status updates when you open the Settings tab or make a new code. After pairing a phone, "
               "reopen the tab to see it turn green.", icons)

    register_resize("help_settings", _on_layout_resize)