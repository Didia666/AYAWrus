import dearpygui.dearpygui as dpg
from ui.theme import COLORS
from ui.layout import register_resize
from ui import help_widgets as hw
from ui.help_scan import SUSPICIOUS_AT, MALICIOUS_AT
from ui.help_explain import _term_table, _text_w
from ui.help_scan_results import _put_text, _put_centered
from ui.scan_layout import SECONDARY_COLORS
from ui.table_style import TABLE_PILL_HEIGHT, TABLE_CELL_MUTED_COLOR
from ui import history as hist

# help_history.py
# Help manual topic: History. Wording shown in the app (state tooltips, empty-state texts, strip labels, chip labels,
# result colors and icons) is read from ui/history.py, so it can't drift.

# ---- Switches (flip these when the matching work is done) ----
# True while system/history/batches.py counts QUARANTINED (and similar) results under "Clean", and one flagged file can
# be saved twice (flagged, then quarantined). Set False once the backend is fixed.
COUNTS_INCLUDE_QUARANTINE_ACTIONS = True
# True once ui/scan.py saves cancelled scans as CANCELLED (the one-line flush_log_buffer fix). False = CANCELLED is left out.
CANCELLED_STATUS_IS_RECORDED = True

# ---- Mirrors of app numbers ----
HISTORY_LIST_LIMIT = 50            # _rebuild_history(limit=50) in ui/history.py

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
STAT_CHIP_COLUMN = 190
STATE_BADGE_COLUMN = 64
STATE_BADGE_BOX = 44
STATE_BADGE_ICON = 22
DOT_R = 5
DOT_COLUMN = 210
DOT_BOX_H = 24
RESULT_ICON_SIZE = 20
RESULT_ICON_COLUMN = 36
RESULT_PILL_COLUMN = 150

# ---- Scan card diagram ----
CARD_TAG = "help_history_card"
CARD_DIAG_H = 132
CARD_BORDER_ALPHA = 110
CARD_BADGE = 46
CARD_BADGE_ICON = 24
CARD_BADGE_LEFT = 18
CARD_TEXT_GAP = 16
CARD_ROW1 = 34                     # row centers, measured from the card's top edge
CARD_ROW2 = 62
CARD_ROW3 = 92
CARD_TITLE_SIZE = 16
CARD_TEXT_SIZE = 14
CARD_PILL_TEXT_SIZE = 12
CARD_CHIP_H = 24
CARD_CHIP_PAD_X = 10
CARD_RIGHT_W = 150
CARD_RIGHT_MARGIN = 20
CARD_PILL_W = 118
CARD_PILL_H = 26
CARD_DATE_Y = 50
CARD_PILL_Y = 78
EXAMPLE_SCAN_TYPE = "custom"
EXAMPLE_INFO = "12 results  \u00b7  1m 36s"   # made up
EXAMPLE_PATH = "D:\\Games\\Example Game"
EXAMPLE_CHIP = "Suspicious: 12"
EXAMPLE_DATE = "2026-10-29 07:44:52"
EXAMPLE_STATUS = "COMPLETED"

# ---- Detail view diagram ----
DETAIL_TAG = "help_history_detail"
DETAIL_BACK_W = 170
DETAIL_BACK_H = 26
DETAIL_BACK_GAP = 10
DETAIL_BACK_TEXT = "\u2190 Back to all batches"
DETAIL_CARD_H = 132
DETAIL_BADGE = 40
DETAIL_BADGE_ICON = 22
DETAIL_PILL_W = 96
DETAIL_PILL_H = 22
DETAIL_CHIP_H = 22
DETAIL_STRIP_PAD = 18
DETAIL_HEADING_GAP = 10
DETAIL_HEADING_H = 22
DETAIL_HEADING_SIZE = 16
DETAIL_CALLOUT_GAP = 8
DETAIL_HEADER_H = 26
DETAIL_ROW_H = 30
DETAIL_BOTTOM_PAD = 10
DETAIL_TEXT_SIZE = 12
DETAIL_SMALL_SIZE = 10
DETAIL_HEADER_BG = (40, 52, 78)    # same as HEADER_BG in ui/scan_threats.py
DETAIL_ROW_ALT_BG = (255, 255, 255, 10)
DETAIL_ICON_DRAW = 16
DETAIL_COLUMNS = [                 # (header label, share of the width). Must add up to 1.0
    ("", 0.07), ("Explain", 0.11), ("File Name", 0.17), ("Location", 0.20),
    ("Result", 0.17), ("Confidence", 0.14), ("Behavior", 0.14),
]
DETAIL_EXAMPLE_VALUES = ("2026-10-29 07:44:52", "2026-10-29 07:46:29", "1m 36s", "BA1B2C3D4E5F6789")   # made up
DETAIL_HEADING_TEXT = "Saved results (12)"
# (file name, location, result, confidence, behavior). All made up.
DETAIL_ROWS = [
    ("setup.exe", "D:\\Downloads\\...", "SUSPICIOUS", "63.8%", "0%"),
    ("tool.exe", "C:\\Temp\\...", "MALICIOUS", "96.4%", "85%"),
]

# ---- Empty state replicas ----
EMPTY_LIST_TAG = "help_history_empty_list"
EMPTY_DETAIL_TAG = "help_history_empty_detail"
EMPTY_H = 140
EMPTY_PAD_Y = 16
EMPTY_GAP = 8
EMPTY_TITLE_H = 26
EMPTY_SUB_H = 22
EMPTY_TITLE_SIZE = 18
EMPTY_SUB_SIZE = 14

# ---- Legends ----
STATE_ORDER = ("threats", "failed", "running", "empty", "clean")
RESULT_ORDER = ("MALICIOUS", "SUSPICIOUS", "QUARANTINED", "ERROR")
CHIP_COLOR_BY_THEME = {"chip_red": "accent_red", "chip_orange": "accent_orange",
                       "chip_green": "accent_green", "chip_grey": "text_secondary"}
EXAMPLE_COUNTS = {"total_files": 11, "malicious_count": 3, "suspicious_count": 5, "clean_count": 2,
                  "error_count": 1}   # only used to get the chip labels from ui/history.py


def _percent(value):
    return int(round(value * 100))


def _radius(w):
    return max(MIN_CALLOUT_RADIUS, int(w * CALLOUT_RADIUS_RATIO))


def _muted(color):
    return tuple(max(0, min(255, c // 5)) for c in color[:3])


def _pill(dl, x0, y0, x1, y1, color, text, size):
    dpg.draw_rectangle((x0, y0), (x1, y1), color=(*color[:3], PILL_BORDER_ALPHA), fill=(*color[:3], PILL_BG_ALPHA),
                       rounding=(y1 - y0) / 2, parent=dl)
    _put_centered(dl, text, x0, x1, y0, y1, size, color[:3])


def _icon(dl, keys, x0, y0, size, color):
    for key in keys:
        tex = f"tex_{key}"
        if dpg.does_item_exist(tex):
            dpg.draw_image(tex, (x0, y0), (x0 + size, y0 + size), color=color[:3], parent=dl)
            return


def _badge_box(dl, x0, y0, size, icon_size, keys, color):
    dpg.draw_rectangle((x0, y0), (x0 + size, y0 + size), color=COLORS["border"], fill=(*_muted(color), 255),
                       rounding=ROUNDING, parent=dl)
    offset = (size - icon_size) / 2
    _icon(dl, keys, x0 + offset, y0 + offset, icon_size, color)


def _subheading(text, fonts):
    dpg.add_spacer(height=SUBHEADING_GAP)
    t = dpg.add_text(text, color=COLORS["text_primary"])
    font = fonts.get("subheading")
    if font is not None:
        dpg.bind_item_font(t, font)
    dpg.add_spacer(height=4)


# ---------- scan card diagram (redrawn to fit the pane whenever the window resizes) ----------

def _draw_card(w):
    dl = CARD_TAG
    dpg.delete_item(dl, children_only=True)
    r = _radius(w)
    x0, x1 = DIAG_PAD, w - DIAG_PAD
    y0, y1 = DIAG_PAD, CARD_DIAG_H - DIAG_PAD
    muted = TABLE_CELL_MUTED_COLOR

    dpg.draw_rectangle((x0, y0), (x1, y1), color=(*COLORS["accent_red"], CARD_BORDER_ALPHA),
                       fill=COLORS["bg_card"], rounding=ROUNDING, parent=dl)

    keys, state_color, _tip = hist.STATE_STYLE["threats"]
    bx0 = x0 + CARD_BADGE_LEFT
    by0 = y0 + (y1 - y0 - CARD_BADGE) / 2
    _badge_box(dl, bx0, by0, CARD_BADGE, CARD_BADGE_ICON, keys, state_color)

    tx = bx0 + CARD_BADGE + CARD_TEXT_GAP
    r1, r2, r3 = y0 + CARD_ROW1, y0 + CARD_ROW2, y0 + CARD_ROW3
    dot = hist._scan_type_color(EXAMPLE_SCAN_TYPE)[:3]
    dpg.draw_circle((tx + DOT_R, r1), DOT_R, color=dot, fill=dot, parent=dl)
    title = hist._scan_type_label(EXAMPLE_SCAN_TYPE)
    title_x = tx + 2 * DOT_R + 6
    title_w = _text_w(title, CARD_TITLE_SIZE)
    _put_text(dl, title, title_x, r1 - 10, r1 + 10, CARD_TITLE_SIZE, COLORS["text_primary"])
    info_x = title_x + title_w + 8
    info_w = _text_w(EXAMPLE_INFO, CARD_TEXT_SIZE)
    _put_text(dl, EXAMPLE_INFO, info_x, r1 - 10, r1 + 10, CARD_TEXT_SIZE, muted)
    path_w = _text_w(EXAMPLE_PATH, CARD_TEXT_SIZE)
    _put_text(dl, EXAMPLE_PATH, tx, r2 - 10, r2 + 10, CARD_TEXT_SIZE, muted)
    chip_w = _text_w(EXAMPLE_CHIP, CARD_TEXT_SIZE) + 2 * CARD_CHIP_PAD_X
    _pill(dl, tx, r3 - CARD_CHIP_H / 2, tx + chip_w, r3 + CARD_CHIP_H / 2, COLORS["accent_orange"],
          EXAMPLE_CHIP, CARD_TEXT_SIZE)

    rx1 = x1 - CARD_RIGHT_MARGIN
    rx0 = rx1 - CARD_RIGHT_W
    date_y, pill_y = y0 + CARD_DATE_Y, y0 + CARD_PILL_Y
    _put_centered(dl, EXAMPLE_DATE, rx0, rx1, date_y - 10, date_y + 10, CARD_TEXT_SIZE, muted)
    px0 = rx0 + (CARD_RIGHT_W - CARD_PILL_W) / 2
    _pill(dl, px0, pill_y - CARD_PILL_H / 2, px0 + CARD_PILL_W, pill_y + CARD_PILL_H / 2,
          COLORS["text_secondary"], EXAMPLE_STATUS, CARD_PILL_TEXT_SIZE)

    # numbered callouts last, so they sit on top
    hw.draw_callout(bx0 + CARD_BADGE, by0, 1, radius=r, parent=dl)
    hw.draw_callout(title_x + title_w / 2, y0 + r, 2, radius=r, parent=dl)
    hw.draw_callout(info_x + info_w / 2, y0 + r, 3, radius=r, parent=dl)
    hw.draw_callout(tx + path_w + r + 10, r2, 4, radius=r, parent=dl)
    hw.draw_callout(tx + chip_w + r + 10, r3, 5, radius=r, parent=dl)
    hw.draw_callout(rx0 - r - 6, date_y, 6, radius=r, parent=dl)
    hw.draw_callout(px0 - r - 6, pill_y, 7, radius=r, parent=dl)


def _build_card_diagram():
    with dpg.drawlist(width=DEFAULT_WIDTH, height=CARD_DIAG_H, tag=CARD_TAG):
        pass
    _draw_card(DEFAULT_WIDTH)
    hw.gap()


# ---------- detail view diagram ----------

def _detail_layout(w):
    r = _radius(w)
    back_y0 = DIAG_PAD
    card_y0 = back_y0 + DETAIL_BACK_H + DETAIL_BACK_GAP
    card_y1 = card_y0 + DETAIL_CARD_H
    heading_y = card_y1 + DETAIL_HEADING_GAP + DETAIL_HEADING_H / 2
    header_y0 = card_y1 + DETAIL_HEADING_GAP + DETAIL_HEADING_H + 2 * r + DETAIL_CALLOUT_GAP
    header_y1 = header_y0 + DETAIL_HEADER_H
    h = header_y1 + len(DETAIL_ROWS) * DETAIL_ROW_H + DETAIL_BOTTOM_PAD
    return r, back_y0, card_y0, card_y1, heading_y, header_y0, header_y1, int(h)


def _column_edges(w):
    inner = w - 2 * DIAG_PAD
    edges = [DIAG_PAD]
    for _label, share in DETAIL_COLUMNS:
        edges.append(edges[-1] + inner * share)
    return edges


def _draw_detail(w):
    dl = DETAIL_TAG
    dpg.delete_item(dl, children_only=True)
    r, back_y0, cy0, cy1, heading_y, hy0, hy1, h = _detail_layout(w)
    clear = (0, 0, 0, 0)
    border = COLORS["border"]
    muted = TABLE_CELL_MUTED_COLOR
    x0, x1 = DIAG_PAD, w - DIAG_PAD

    dpg.draw_rectangle((0, 0), (w - 1, h - 1), color=border, fill=COLORS["bg_main"], rounding=ROUNDING, parent=dl)

    # back button
    back_mid = back_y0 + DETAIL_BACK_H / 2
    dpg.draw_rectangle((x0, back_y0), (x0 + DETAIL_BACK_W, back_y0 + DETAIL_BACK_H), color=clear,
                       fill=SECONDARY_COLORS[0], rounding=4, parent=dl)
    _put_centered(dl, DETAIL_BACK_TEXT, x0, x0 + DETAIL_BACK_W, back_y0, back_y0 + DETAIL_BACK_H,
                  DETAIL_TEXT_SIZE, COLORS["text_primary"])

    # summary card
    dpg.draw_rectangle((x0, cy0), (x1, cy1), color=(*COLORS["accent_red"], CARD_BORDER_ALPHA),
                       fill=COLORS["bg_card"], rounding=ROUNDING, parent=dl)
    keys, state_color, _tip = hist.STATE_STYLE["threats"]
    bx0 = x0 + CARD_BADGE_LEFT
    _badge_box(dl, bx0, cy0 + 16, DETAIL_BADGE, DETAIL_BADGE_ICON, keys, state_color)
    tx = bx0 + DETAIL_BADGE + CARD_TEXT_GAP
    r1, r2, r3 = cy0 + 24, cy0 + 50, cy0 + 76
    dot = hist._scan_type_color(EXAMPLE_SCAN_TYPE)[:3]
    dpg.draw_circle((tx + DOT_R, r1), DOT_R, color=dot, fill=dot, parent=dl)
    title = hist._scan_type_label(EXAMPLE_SCAN_TYPE)
    title_x = tx + 2 * DOT_R + 6
    title_w = _text_w(title, CARD_TITLE_SIZE)
    _put_text(dl, title, title_x, r1 - 10, r1 + 10, CARD_TITLE_SIZE, COLORS["text_primary"])
    pill_x0 = title_x + title_w + 10
    _pill(dl, pill_x0, r1 - DETAIL_PILL_H / 2, pill_x0 + DETAIL_PILL_W, r1 + DETAIL_PILL_H / 2,
          COLORS["text_secondary"], EXAMPLE_STATUS, DETAIL_SMALL_SIZE + 1)
    _put_text(dl, EXAMPLE_PATH, tx, r2 - 10, r2 + 10, CARD_TEXT_SIZE, muted)
    chip_w = _text_w(EXAMPLE_CHIP, DETAIL_TEXT_SIZE + 1) + 2 * CARD_CHIP_PAD_X
    _pill(dl, tx, r3 - DETAIL_CHIP_H / 2, tx + chip_w, r3 + DETAIL_CHIP_H / 2, COLORS["accent_orange"],
          EXAMPLE_CHIP, DETAIL_TEXT_SIZE + 1)

    # the four-cell details strip
    divider_y = cy0 + 94
    dpg.draw_line((x0 + 10, divider_y), (x1 - 10, divider_y), color=border, thickness=1, parent=dl)
    sx0, sx1 = x0 + DETAIL_STRIP_PAD, x1 - DETAIL_STRIP_PAD
    weights = hist.STRIP_WEIGHTS
    unit = (sx1 - sx0) / sum(weights)
    cursor = sx0
    labels_y, values_y = cy0 + 106, cy0 + 122
    for i, weight in enumerate(weights):
        label = hist.STRIP_LABELS[i]
        label = label.upper() if hist.STRIP_LABELS_UPPERCASE else label
        _put_text(dl, label, cursor, labels_y - 6, labels_y + 6, DETAIL_SMALL_SIZE, COLORS["text_secondary"])
        _put_text(dl, DETAIL_EXAMPLE_VALUES[i], cursor, values_y - 7, values_y + 7, DETAIL_TEXT_SIZE,
                  COLORS["text_primary"])
        cursor += unit * weight

    # heading
    heading_w = _text_w(DETAIL_HEADING_TEXT, DETAIL_HEADING_SIZE)
    _put_text(dl, DETAIL_HEADING_TEXT, x0 + 4, heading_y - 11, heading_y + 11, DETAIL_HEADING_SIZE,
              COLORS["text_primary"])

    # table: header, then rows
    edges = _column_edges(w)
    dpg.draw_rectangle((x0, hy0), (x1, hy1), color=clear, fill=DETAIL_HEADER_BG, parent=dl)
    for i, (label, _share) in enumerate(DETAIL_COLUMNS):
        if label:
            _put_text(dl, label, edges[i] + 4, hy0, hy1, DETAIL_TEXT_SIZE, COLORS["text_secondary"])
    for n, (name, location, result, confidence, behavior) in enumerate(DETAIL_ROWS):
        ry0 = hy1 + n * DETAIL_ROW_H
        ry1 = ry0 + DETAIL_ROW_H
        mid = (ry0 + ry1) / 2
        color, icon_keys = hist.RESULT_STYLE.get(result, hist.RESULT_DEFAULT)
        if n % 2 == 1:
            dpg.draw_rectangle((x0, ry0), (x1, ry1), color=clear, fill=DETAIL_ROW_ALT_BG, parent=dl)
        _icon(dl, icon_keys, (edges[0] + edges[1]) / 2 - DETAIL_ICON_DRAW / 2, mid - DETAIL_ICON_DRAW / 2,
              DETAIL_ICON_DRAW, color)
        dpg.draw_rectangle((edges[1] + 3, ry0 + 5), (edges[2] - 3, ry1 - 5), color=clear,
                           fill=SECONDARY_COLORS[0], rounding=4, parent=dl)
        _put_centered(dl, "Explain", edges[1] + 3, edges[2] - 3, ry0, ry1, DETAIL_SMALL_SIZE, COLORS["text_primary"])
        _put_text(dl, name, edges[2] + 4, ry0, ry1, DETAIL_TEXT_SIZE, COLORS["text_primary"])
        _put_text(dl, location, edges[3] + 4, ry0, ry1, DETAIL_TEXT_SIZE, COLORS["text_secondary"])
        _pill(dl, edges[4] + 4, ry0 + 6, edges[5] - 6, ry1 - 6, color, result, DETAIL_SMALL_SIZE)
        conf_color = COLORS["accent_red"] if result == "MALICIOUS" else COLORS["accent_orange"]
        _put_text(dl, confidence, edges[5] + 4, ry0, ry1, DETAIL_TEXT_SIZE, conf_color)
        _put_text(dl, behavior, edges[6] + 4, ry0, ry1, DETAIL_TEXT_SIZE, COLORS["accent_orange"])

    # numbered callouts last, so they sit on top
    hw.draw_callout(x0 + DETAIL_BACK_W + r + 8, back_mid, 1, radius=r, parent=dl)
    hw.draw_callout(pill_x0 + DETAIL_PILL_W + r + 8, r1, 2, radius=r, parent=dl)
    hw.draw_callout(sx1 - r - 4, (labels_y + values_y) / 2, 3, radius=r, parent=dl)
    hw.draw_callout(x0 + 4 + heading_w + r + 10, heading_y, 4, radius=r, parent=dl)
    gutter_y = hy0 - r - 4
    for number, column in ((5, 1), (6, 4), (7, 5), (8, 6)):
        hw.draw_callout((edges[column] + edges[column + 1]) / 2, gutter_y, number, radius=r, parent=dl)


def _build_detail_diagram():
    h = _detail_layout(DEFAULT_WIDTH)[-1]
    with dpg.drawlist(width=DEFAULT_WIDTH, height=h, tag=DETAIL_TAG):
        pass
    _draw_detail(DEFAULT_WIDTH)
    hw.gap()


# ---------- empty state replicas ----------

def _draw_empty(tag, w, icon_keys, title, subtitle):
    dl = tag
    dpg.delete_item(dl, children_only=True)
    dpg.draw_rectangle((0, 0), (w - 1, EMPTY_H - 1), color=COLORS["border"], fill=hw.HELP_INSET_BG,
                       rounding=ROUNDING, parent=dl)
    size = hist.EMPTY_ICON_SIZE
    y = EMPTY_PAD_Y
    _icon(dl, icon_keys, (w - size) / 2, y, size, COLORS["text_secondary"])
    y += size + EMPTY_GAP
    _put_centered(dl, title, 0, w, y, y + EMPTY_TITLE_H, EMPTY_TITLE_SIZE, COLORS["text_primary"])
    y += EMPTY_TITLE_H
    _put_centered(dl, subtitle, 0, w, y, y + EMPTY_SUB_H, EMPTY_SUB_SIZE, COLORS["text_secondary"])


def _empty_specs():
    return [(EMPTY_LIST_TAG, ("history",), hist.EMPTY_TITLE, hist.EMPTY_SUBTITLE),
            (EMPTY_DETAIL_TAG, ("file_x", "folder_search"), hist.DETAIL_EMPTY_TITLE, hist.DETAIL_EMPTY_SUBTITLE)]


def _build_empty_states():
    for tag, keys, title, subtitle in _empty_specs():
        with dpg.drawlist(width=DEFAULT_WIDTH, height=EMPTY_H, tag=tag):
            pass
        _draw_empty(tag, DEFAULT_WIDTH, keys, title, subtitle)
        dpg.add_spacer(height=hw.HELP_PARAGRAPH_GAP)


# ---------- resize ----------

def _fit_all():
    if not dpg.does_item_exist(hw.HELP_CONTENT_PANE_TAG):
        return
    pane_w = dpg.get_item_width(hw.HELP_CONTENT_PANE_TAG)
    w = int(max(DRAW_MIN_WIDTH, min(DRAW_MAX_WIDTH, pane_w - SIDE_CHROME)))
    if dpg.does_item_exist(CARD_TAG):
        dpg.configure_item(CARD_TAG, width=w, height=CARD_DIAG_H)
        _draw_card(w)
    if dpg.does_item_exist(DETAIL_TAG):
        dpg.configure_item(DETAIL_TAG, width=w, height=_detail_layout(w)[-1])
        _draw_detail(w)
    for tag, keys, title, subtitle in _empty_specs():
        if dpg.does_item_exist(tag):
            dpg.configure_item(tag, width=w, height=EMPTY_H)
            _draw_empty(tag, w, keys, title, subtitle)


def _on_layout_resize(content_w, content_h):
    # help_manual sizes the pane in its own resize handler, which may run AFTER this one,
    # so wait a few frames and then read the pane's final width.
    dpg.set_frame_callback(dpg.get_frame_count() + FRAME_DELAY, lambda *args: _fit_all())


# ---------- legends ----------

def _legend_table(first_width, rows_builder):
    with dpg.table(header_row=False, borders_innerH=False, borders_outerH=False,
                   borders_innerV=False, borders_outerV=False):
        dpg.add_table_column(width_fixed=True, init_width_or_weight=first_width)
        dpg.add_table_column(width_stretch=True, init_width_or_weight=1.0)
        rows_builder()
    hw.gap()


def _state_rows():
    meanings = {
        "threats": "At least one threat was saved for this scan. The card also gets a red border.",
        "failed": "The scan failed or was cancelled. The card gets a red border too.",
        "running": "The scan is still going. Reopen the tab after it finishes to see the final numbers.",
        "empty": "No results were saved for this scan. A scan that finishes without flagging anything looks like "
                 "this, because clean files aren't saved. It doesn't mean nothing was checked.",
        "clean": "Some results were saved, but none of them were threats.",
    }
    for state in STATE_ORDER:
        keys, color, tip = hist.STATE_STYLE[state]
        with dpg.table_row():
            with dpg.group():
                with dpg.drawlist(width=STATE_BADGE_BOX, height=STATE_BADGE_BOX):
                    dpg.draw_rectangle((0, 0), (STATE_BADGE_BOX - 1, STATE_BADGE_BOX - 1), color=COLORS["border"],
                                       fill=(*_muted(color), 255), rounding=ROUNDING)
                    for key in keys:
                        tex = f"tex_{key}"
                        if dpg.does_item_exist(tex):
                            off = (STATE_BADGE_BOX - STATE_BADGE_ICON) / 2
                            dpg.draw_image(tex, (off, off), (off + STATE_BADGE_ICON, off + STATE_BADGE_ICON),
                                           color=color[:3])
                            break
                dpg.add_spacer(height=6)
            with dpg.group():
                dpg.add_text(tip, wrap=0, color=COLORS["text_primary"])
                dpg.add_text(meanings[state], wrap=0, color=hw.HELP_BODY_COLOR)
                dpg.add_spacer(height=6)


def _scan_type_rows():
    rows = [("quick", "From the Quick Scan card."),
            ("full", "From the Full Scan card."),
            ("custom", "From the Custom Scan card, for the folder you picked.")]
    for key, meaning in rows:
        color = hist._scan_type_color(key)[:3]
        with dpg.table_row():
            with dpg.group(horizontal=True):
                with dpg.drawlist(width=2 * DOT_R + 2, height=DOT_BOX_H):
                    dpg.draw_circle((DOT_R + 1, DOT_BOX_H / 2), DOT_R, color=color, fill=color)
                dpg.add_text(hist._scan_type_label(key), color=COLORS["text_primary"])
            with dpg.group():
                dpg.add_text(meaning, wrap=0, color=hw.HELP_BODY_COLOR)
                dpg.add_spacer(height=4)


def _stat_chip_rows(fonts):
    sus, mal = _percent(SUSPICIOUS_AT), _percent(MALICIOUS_AT)
    meanings = {
        "chip_red": f"Results the AI judged MALICIOUS ({mal}% or higher), or that matched a known-malware fingerprint.",
        "chip_orange": f"Results the AI judged SUSPICIOUS ({sus}% up to just under {mal}%).",
        "chip_green": "Results that weren't flagged as threats. Clean files usually aren't saved, so this is "
                      "normally small." + (" It can also include quarantine actions that AYAWrus saved during the "
                                           "scan." if COUNTS_INCLUDE_QUARANTINE_ACTIONS else ""),
        "chip_grey": "Files AYAWrus couldn't analyze.",
    }
    for label, theme_key in hist._chips_for(EXAMPLE_COUNTS):
        with dpg.table_row():
            with dpg.group():
                hw.chip(label, CHIP_COLOR_BY_THEME[theme_key], fonts)
                dpg.add_spacer(height=4)
            with dpg.group():
                dpg.add_spacer(height=TEXT_TOP_OFFSET)
                dpg.add_text(meanings[theme_key], wrap=0, color=hw.HELP_BODY_COLOR)
                dpg.add_spacer(height=4)
    empty_label, empty_theme = hist._chips_for({"total_files": 0})[0]
    with dpg.table_row():
        with dpg.group():
            hw.chip(empty_label, CHIP_COLOR_BY_THEME[empty_theme], fonts)
            dpg.add_spacer(height=4)
        with dpg.group():
            dpg.add_spacer(height=TEXT_TOP_OFFSET)
            dpg.add_text("No results were saved for this scan (see the grey icon above).", wrap=0,
                         color=hw.HELP_BODY_COLOR)
            dpg.add_spacer(height=4)


def _status_rows(fonts):
    rows = [("COMPLETED", "text_secondary", "The scan finished."),
            ("RUNNING", "accent_blue", "The scan is still going."),
            ("FAILED", "accent_red", "The scan hit an error and stopped.")]
    if CANCELLED_STATUS_IS_RECORDED:
        rows.append(("CANCELLED", "accent_red", "You pressed Cancel Scan before it finished. Results found before "
                                                 "that are kept."))
    for text, color_name, meaning in rows:
        with dpg.table_row():
            with dpg.group():
                hw.chip(text, color_name, fonts)
                dpg.add_spacer(height=4)
            with dpg.group():
                dpg.add_spacer(height=TEXT_TOP_OFFSET)
                dpg.add_text(meaning, wrap=0, color=hw.HELP_BODY_COLOR)
                dpg.add_spacer(height=4)


def _result_rows(icons):
    sus, mal = _percent(SUSPICIOUS_AT), _percent(MALICIOUS_AT)
    meanings = {
        "MALICIOUS": f"The AI estimated {mal}% or higher, or the file matched a known-malware fingerprint.",
        "SUSPICIOUS": f"The AI estimated {sus}% up to just under {mal}%.",
        "QUARANTINED": "The file was moved into quarantine. A MALICIOUS file gets this entry right after its "
                       "MALICIOUS one.",
        "ERROR": "AYAWrus couldn't analyze the file.",
    }
    own = hist._themes()
    for result in RESULT_ORDER:
        color, keys = hist.RESULT_STYLE.get(result, hist.RESULT_DEFAULT)
        tex = hist._first_icon(icons, keys)
        with dpg.table_row():
            with dpg.group():
                if tex:
                    dpg.add_image(tex, width=RESULT_ICON_SIZE, height=RESULT_ICON_SIZE, tint_color=color)
            with dpg.group():
                pill = dpg.add_button(label=result, width=-1, height=TABLE_PILL_HEIGHT)
                dpg.bind_item_theme(pill, own.get(f"result_{result}", own["result_OTHER"]))
                dpg.add_spacer(height=4)
            with dpg.group():
                dpg.add_spacer(height=TEXT_TOP_OFFSET)
                dpg.add_text(meanings[result], wrap=0, color=hw.HELP_BODY_COLOR)
                dpg.add_spacer(height=4)


def _result_table(icons):
    with dpg.table(header_row=False, borders_innerH=False, borders_outerH=False,
                   borders_innerV=False, borders_outerV=False):
        dpg.add_table_column(width_fixed=True, init_width_or_weight=RESULT_ICON_COLUMN)
        dpg.add_table_column(width_fixed=True, init_width_or_weight=RESULT_PILL_COLUMN)
        dpg.add_table_column(width_stretch=True, init_width_or_weight=1.0)
        _result_rows(icons)
    hw.gap()


# ---------- the topic ----------

def build_topic(fonts, icons):
    hw.page_heading("History", "A record of the scans you've run.", fonts)
    hw.paragraph("History keeps a summary of each scan so you can look back at what was found. Each scan is a "
                 "'batch'. The tab has two views: a list of your scans, and a closer look inside one scan.")

    # ---------------- part 1: the list ----------------
    hw.section_heading("The list of scans", fonts)
    hw.paragraph(f"The list shows your {HISTORY_LIST_LIMIT} most recent scans, newest first, with the number of "
                 "scans shown next to the title. Here is one card in simplified form (made-up values). The numbers "
                 "match the list underneath.")
    _build_card_diagram()
    hw.numbered_row(1, "Status icon", "Shows at a glance how the scan went (explained below). Hover over it for a "
                                      "short description.")
    hw.numbered_row(2, "Scan type", "The colored dot and name tell you which kind of scan it was.")
    hw.numbered_row(3, "Summary", "How many results were saved for the scan, and how long it took.")
    hw.numbered_row(4, "Folder", "What was scanned. Long paths are shortened with ... and the full path shows when "
                                 "you hover.")
    hw.numbered_row(5, "Stat chips", "A count for each kind of result that was saved.")
    hw.numbered_row(6, "Date", "When the scan started.")
    hw.numbered_row(7, "Status", "Whether the scan finished, is still running or stopped early.")
    hw.paragraph("Click anywhere on a card to open that scan. The card lights up when you hover over it.")

    _subheading("Card icons and borders", fonts)
    _legend_table(STATE_BADGE_COLUMN, _state_rows)
    _subheading("Scan types", fonts)
    _legend_table(DOT_COLUMN, _scan_type_rows)
    _subheading("Stat chips", fonts)
    _legend_table(STAT_CHIP_COLUMN, lambda: _stat_chip_rows(fonts))
    _subheading("Status", fonts)
    _legend_table(STAT_CHIP_COLUMN, lambda: _status_rows(fonts))

    # ---------------- part 2: inside a scan ----------------
    hw.section_heading("Inside a scan", fonts)
    hw.paragraph("Opening a scan shows its summary and every result that was saved for it. Press the Back button "
                 "to return to the list.")
    _build_detail_diagram()
    hw.numbered_row(1, "Back", "Returns to the list of scans.")
    hw.numbered_row(2, "Summary", "The same card as in the list, with the status pill beside the scan type.")
    hw.numbered_row(3, "Details", "When the scan started and finished, how long it took and its batch ID (a unique "
                                  "code for the scan).")
    hw.numbered_row(4, "Saved results", "Every result saved for this scan. If there are more than "
                                        f"{hist.DETAIL_MAX_FILES}, the first {hist.DETAIL_MAX_FILES} are shown.")
    hw.numbered_row(5, "Explain", "Opens the Explain window for that file.")
    hw.numbered_row(6, "Result", "What AYAWrus concluded about the file (explained below).")
    hw.numbered_row(7, "Confidence", "How likely the AI thought the file was malware.")
    hw.numbered_row(8, "Behavior", "A guess at what kind of threat the file might be.")

    _subheading("Results", fonts)
    hw.paragraph("Each result has its own icon and colored pill.")
    _result_table(icons)
    hw.paragraph("Restoring and deleting quarantined files are recorded in Recent Activity on the Dashboard.")

    _subheading("Confidence and Behavior", fonts)
    _term_table([
        ("Confidence", "text_primary", "The AI's estimate that the file is malware. Red for MALICIOUS, orange for "
                                       "SUSPICIOUS, and a dash when there is no estimate."),
        ("Behavior %", "text_primary", "How sure the separate behavior model is about its best guess. 0% means no "
                                       "kind of threat stood out."),
        ("Type", "text_primary", "That best guess, such as Ransomware, Spyware or Worm. A dash means none."),
    ])
    hw.paragraph("On narrow windows the Location column is hidden (hover over the file name to see the path) and "
                 "Behavior % and Type merge into one column like '85% | Ransomware'. Hover over it to see both parts.")

    _subheading("Explain from History", fonts)
    hw.paragraph("Explain here opens the same window as on the Scan tab, but it only has what was saved with the "
                 "result: the verdict, the confidence and the file's location. The detailed tabs may be empty. SHAP "
                 "can still be generated if the file is still where it was.")

    # ---------------- empty states ----------------
    hw.section_heading("When there's nothing to show", fonts)
    hw.paragraph("Before your first scan, the list looks like this:")
    _build_empty_states()
    hw.paragraph("The second picture is what you see when you open a scan that has no saved results.")

    hw.section_heading("Good to know", fonts)
    count_text = ("The numbers count results AYAWrus saved, not every file it looked at. Files that scanned clean "
                  "aren't saved, so a scan can look small, or even empty, when thousands of files were checked.")
    if COUNTS_INCLUDE_QUARANTINE_ACTIONS:
        count_text += (" Quarantine actions during a scan are saved as results too, so one flagged file can add "
                       "two to the total.")
    hw.tip_box("note", "Counts are saved results", count_text, icons)
    hw.tip_box("tip", "Only the latest scans are listed",
               f"The list shows your {HISTORY_LIST_LIMIT} most recent scans. Older ones stay saved but aren't shown.",
               icons)
    hw.tip_box("tip", "Always starts at the list",
               "Opening the History tab always shows the list, refreshed. A scan that is still running appears as "
               "RUNNING, so reopen the tab when it finishes.", icons)
    hw.tip_box("tip", "Hover for saved notes",
               "Hovering over a file name in the results shows any notes that were saved with it.", icons)

    register_resize("help_history", _on_layout_resize)