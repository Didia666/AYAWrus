import dearpygui.dearpygui as dpg
from contextlib import contextmanager
from ui.theme import COLORS
from ui.layout import register_resize
from ui import help_widgets as hw
from ui.help_scan import SUSPICIOUS_AT, MALICIOUS_AT
from ui.scan_layout import START_COLORS
from ui.scan_explain import TABS
from ui.scan_targets import (STATE_MESSAGES, RISK_COL_W, ROW_BUTTON_H, CHIP_HEIGHT, HEADER_FONT,
                             NOTE_ICON_SIZE, _themes as _targets_themes)

# help_explain.py
# Help manual topic: Explain a Threat (the popup opened by the Explain button in Detected Threats).

# ---- Switches (flip these when the matching work is done) ----
# True once the backend calls set_likely_targets_data() (see the big comment at the top of ui/scan_targets.py).
# False = the Likely Targets section shows a short "Coming soon" note.
LIKELY_TARGETS_BACKEND_READY = False
# True while some detections come without a background explanation (so Explain tabs can be empty).
# Set False once the backend schedules explanations for every detection.
SHOW_EXPLANATION_AVAILABILITY_NOTE = True

# ---- Mirrors of backend numbers (update here if system/utils/utility.py changes) ----
CATEGORY_HIGH_AT = 0.70            # categorize_threat(): HIGH starts here (SEVERE = the MALICIOUS cut-off)
CATEGORY_MEDIUM_AT = 0.40

# ---- Shared sizes ----
SIDE_CHROME = 64                   # pane padding + scrollbar + breathing room, subtracted from the pane width
FRAME_DELAY = 3                    # frames to wait after a resize so help_manual sizes the pane first
DRAW_MIN_WIDTH = 400
DRAW_MAX_WIDTH = 720
TAB_TITLE_GAP = 18
TAB_TITLE_ICON_SIZE = 22
TERM_COLUMN_WIDTH = 190
CARD_PADDING = (12, 10)

# ---- Popup parts diagram ----
POPUP_TAG = "help_explain_popup"
POPUP_DEFAULT_WIDTH = 540
POPUP_ASPECT = 0.62                # drawing height = width * this
POPUP_X_RATIO = 0.03               # popup position and size, as shares of the drawing
POPUP_Y_RATIO = 0.05
POPUP_W_RATIO = 0.72
POPUP_H_RATIO = 0.90
POPUP_ROUNDING = 10
POPUP_BORDER_ALPHA = 110
POPUP_CALLOUT_RADIUS_RATIO = 0.024
POPUP_MIN_CALLOUT_RADIUS = 9
POPUP_TAB_H_RATIO = 0.075          # tab sizes, as shares of the drawing height / width
POPUP_TAB_GAP_RATIO = 0.014
POPUP_TAB_TOP_RATIO = 0.20         # first tab's distance below the popup's top edge (share of the popup height)
POPUP_TAB_OUT_ACTIVE_RATIO = 0.18  # how far the selected tab sticks out
POPUP_TAB_OUT_INACTIVE_RATIO = 0.06
POPUP_TAB_OVERLAP = 2              # tabs cover the popup's edge by this much
POPUP_TAB_ROUNDING = 5
POPUP_TAB_ICON_RATIO = 0.55        # icon size as a share of the tab height
POPUP_TAB_ICON_PAD = 6
POPUP_TAB_TEXT_RATIO = 0.021       # label size as a share of the drawing width
POPUP_TAB_MIN_TEXT = 9

# ---- Overview replica ----
OVERVIEW_CHIP_HEIGHT = 84
OVERVIEW_CHIP_PADDING = (12, 8)
OVERVIEW_EXAMPLE_PATH = "D:\\Downloads\\example.exe"   # made up
OVERVIEW_EXAMPLE_CATEGORY = "MEDIUM"
OVERVIEW_EXAMPLE_CONFIDENCE = "71.2%"                  # made up

# ---- Scan Steps replica (wording copied from a real Explain window) ----
STEP_BADGE = 30
STEP_EXAMPLES = [
    ("Checking the file type", "Checking whether this is a Windows program file."),
    ("Looking at how the file is put together", "Checking the file's main parts and layout."),
    ("Checking how jumbled the file data is", "A high randomness score can happen with compressed or hidden data."),
]

# ---- PE Analysis replica (values are made up) ----
METRIC_COLUMNS = 2
METRIC_HEIGHT = 70
METRIC_PADDING = (12, 8)
METRICS = [                         # (caption, value, meaning). Meanings are the same text the real cards show
    ("File Size", "1.20 MB", "How much storage space this file takes."),
    ("File Entropy", "6.412 / 8.0", "How random or scrambled the file's data appears. Compressed or hidden data "
                                    "tends to score high."),
    ("Architecture", "x64", "The type of computer processor this program is designed for."),
    ("PE Sections", "6", "The internal parts that make up this Windows program."),
    ("Imported DLL Count", "14", "The number of unique Windows libraries the file references."),
    ("Imported Function Count", "212", "The number of functions requested from those libraries."),
]
EXAMPLE_DLLS = ["kernel32.dll", "user32.dll", "advapi32.dll"]

# ---- SHAP bar chart (made up) ----
SHAP_TAG = "help_explain_shap"
SHAP_DEFAULT_WIDTH = 540
SHAP_HEADER_H = 30
SHAP_ROW_H = 28
SHAP_BOTTOM_PAD = 8
SHAP_PAD = 10
SHAP_LABEL_RATIO = 0.30
SHAP_BAR_H = 14
SHAP_BAR_SCALE = 0.78              # the longest bar fills this share of the half-width
SHAP_BAR_ALPHA = 215
SHAP_TEXT_SIZE = 12
SHAP_NOTE_SIZE = 11
SHAP_ROUNDING = 6
SHAP_EXAMPLE = [                   # (group of characteristics, change in percentage points). Made up
    ("Program Sections", 6.1),
    ("Text and Hidden Clues", -2.4),
    ("File Data Patterns", 1.3),
    ("Program Information", -0.6),
]

# ---- Placeholder lines (Actions / Learn Why replicas) ----
PLACEHOLDER_W = 360
PLACEHOLDER_LINE_H = 8
PLACEHOLDER_LINE_GAP = 8
PLACEHOLDER_ALPHA = 90
ICON_BULLET = 18
ACTION_PLACEHOLDERS = [(0.90, 0.55), (0.75,)]      # one tuple per card = line widths as shares of PLACEHOLDER_W
LEARN_PLACEHOLDERS = [(0.95, 0.80, 0.50), (0.90, 0.65)]

# ---- Likely Targets replica (only used when LIKELY_TARGETS_BACKEND_READY is True; all made up) ----
TARGET_CHIPS = [("documents", 92, True), ("images", 71, True), ("archives", 12, False)]   # (name, %, flagged)
TARGET_CATEGORY = "documents"
TARGET_CATEGORY_COUNT = 98
TARGET_FOLDER = "C:\\Users\\Example\\Documents"
TARGET_FILES = [("high", "report_final.docx"), ("medium", "budget.xlsx"), ("low", "notes.txt")]
TARGET_LAST_SCANNED = "Last scanned 06:53"
TARGET_STATS = "52,340 files scanned  |  87 skipped (no permission)  |  142 at risk"
RESCAN_W = 100
RESCAN_H = 30


def _percent(value):
    return int(round(value * 100))


def _text_w(text, size):
    """Rough pixel width of text drawn at a smaller size than the default font."""
    return hw._measure(text)[0] * size / hw.HELP_FAKE_TEXT_SIZE


_TAB_BY_KEY = {key: (icon, label) for key, icon, label in TABS}


# ---------- small building blocks ----------

@contextmanager
def _card():
    with dpg.child_window(width=-1, auto_resize_y=True, border=True) as box:
        yield box
    dpg.bind_item_theme(box, hw.child_card_theme(hw.HELP_INSET_BG, COLORS["border"], CARD_PADDING))


def _caption(text, fonts):
    t = dpg.add_text(text.upper(), color=COLORS["text_secondary"])
    font = fonts.get("mono_small")
    if font is not None:
        dpg.bind_item_font(t, font)


def _tab_title(key, fonts, icons):
    icon_name, label = _TAB_BY_KEY[key]
    dpg.add_spacer(height=TAB_TITLE_GAP)
    with dpg.group(horizontal=True):
        icon = icons.get(icon_name)
        if icon:
            dpg.add_image(icon, width=TAB_TITLE_ICON_SIZE, height=TAB_TITLE_ICON_SIZE,
                          tint_color=COLORS["accent_blue"])
        title = dpg.add_text(label, color=COLORS["text_primary"])
        font = fonts.get("subheading")
        if font is not None:
            dpg.bind_item_font(title, font)
    dpg.add_spacer(height=4)


def _term_table(rows):
    """rows = (term, color name, meaning)."""
    with dpg.table(header_row=False, borders_innerH=False, borders_outerH=False,
                   borders_innerV=False, borders_outerV=False):
        dpg.add_table_column(width_fixed=True, init_width_or_weight=TERM_COLUMN_WIDTH)
        dpg.add_table_column(width_stretch=True, init_width_or_weight=1.0)
        for term, color_name, meaning in rows:
            with dpg.table_row():
                with dpg.group():
                    dpg.add_text(term, wrap=0, color=COLORS[color_name])
                    dpg.add_spacer(height=4)
                with dpg.group():
                    dpg.add_text(meaning, wrap=0, color=hw.HELP_BODY_COLOR)
                    dpg.add_spacer(height=4)
    hw.gap()


def _placeholder_lines(widths):
    height = len(widths) * (PLACEHOLDER_LINE_H + PLACEHOLDER_LINE_GAP) - PLACEHOLDER_LINE_GAP
    with dpg.drawlist(width=PLACEHOLDER_W, height=height):
        for i, share in enumerate(widths):
            y = i * (PLACEHOLDER_LINE_H + PLACEHOLDER_LINE_GAP)
            dpg.draw_rectangle((0, y), (PLACEHOLDER_W * share, y + PLACEHOLDER_LINE_H), color=(0, 0, 0, 0),
                               fill=(*COLORS["text_secondary"], PLACEHOLDER_ALPHA), rounding=3)


# ---------- popup parts diagram (redrawn to fit the pane whenever the window resizes) ----------

def _draw_popup(w):
    dl = POPUP_TAG
    dpg.delete_item(dl, children_only=True)
    h = int(w * POPUP_ASPECT)
    r = max(POPUP_MIN_CALLOUT_RADIUS, int(w * POPUP_CALLOUT_RADIUS_RATIO))
    clear = (0, 0, 0, 0)
    border = COLORS["border"]

    dpg.draw_rectangle((0, 0), (w - 1, h - 1), color=border, fill=COLORS["bg_main"], rounding=6, parent=dl)

    px0, py0 = w * POPUP_X_RATIO, h * POPUP_Y_RATIO
    pw, ph = w * POPUP_W_RATIO, h * POPUP_H_RATIO
    px1, py1 = px0 + pw, py0 + ph
    dpg.draw_rectangle((px0, py0), (px1, py1), color=(*COLORS["accent_blue"], POPUP_BORDER_ALPHA),
                       fill=COLORS["bg_card"], rounding=POPUP_ROUNDING, parent=dl)

    # title + subtitle placeholders
    left = px0 + pw * 0.05
    right = px1 - pw * 0.05
    dpg.draw_rectangle((left, py0 + ph * 0.07), (left + pw * 0.26, py0 + ph * 0.12), color=clear,
                       fill=(*COLORS["text_primary"], 210), rounding=2, parent=dl)
    dpg.draw_rectangle((left, py0 + ph * 0.15), (left + pw * 0.22, py0 + ph * 0.18), color=clear,
                       fill=(*COLORS["text_secondary"], 120), rounding=2, parent=dl)

    # close button
    size = ph * 0.085
    cx1 = px1 - pw * 0.04
    cx0 = cx1 - size
    cy0 = py0 + ph * 0.05
    dpg.draw_rectangle((cx0, cy0), (cx1, cy0 + size), color=clear, fill=(*COLORS["accent_red"], 110),
                       rounding=4, parent=dl)

    # page content: three chips and two cards (a simplified Overview)
    gap = pw * 0.03
    chip_w = (right - left - 2 * gap) / 3
    top = py0 + ph * 0.26
    for i in range(3):
        x0 = left + i * (chip_w + gap)
        value_color = COLORS["accent_orange"] if i == 0 else COLORS["text_primary"]
        dpg.draw_rectangle((x0, top), (x0 + chip_w, top + ph * 0.17), color=border, fill=COLORS["bg_main"],
                           rounding=4, parent=dl)
        dpg.draw_rectangle((x0 + chip_w * 0.10, top + ph * 0.04), (x0 + chip_w * 0.45, top + ph * 0.06),
                           color=clear, fill=(*COLORS["text_secondary"], 110), rounding=2, parent=dl)
        dpg.draw_rectangle((x0 + chip_w * 0.10, top + ph * 0.09), (x0 + chip_w * 0.60, top + ph * 0.13),
                           color=clear, fill=(*value_color, 200), rounding=2, parent=dl)
    for a, b in ((0.46, 0.62), (0.67, 0.85)):
        dpg.draw_rectangle((left, py0 + ph * a), (right, py0 + ph * b), color=border, fill=COLORS["bg_main"],
                           rounding=4, parent=dl)
        dpg.draw_rectangle((left + pw * 0.03, py0 + ph * (a + 0.04)), (left + pw * 0.23, py0 + ph * (a + 0.06)),
                           color=clear, fill=(*COLORS["accent_blue"], 170), rounding=2, parent=dl)
        dpg.draw_rectangle((left + pw * 0.03, py0 + ph * (a + 0.09)), (left + pw * 0.60, py0 + ph * (a + 0.11)),
                           color=clear, fill=(*COLORS["text_secondary"], 110), rounding=2, parent=dl)

    # the tab strip on the right edge: first tab selected (wider, with its label)
    tab_h = h * POPUP_TAB_H_RATIO
    tab_gap = h * POPUP_TAB_GAP_RATIO
    out_active = w * POPUP_TAB_OUT_ACTIVE_RATIO
    out_inactive = w * POPUP_TAB_OUT_INACTIVE_RATIO
    first_y = py0 + ph * POPUP_TAB_TOP_RATIO
    icon_size = tab_h * POPUP_TAB_ICON_RATIO
    text_size = max(POPUP_TAB_MIN_TEXT, w * POPUP_TAB_TEXT_RATIO)
    for i, (_key, icon_name, label) in enumerate(TABS):
        active = i == 0
        x0 = px1 - POPUP_TAB_OVERLAP
        x1 = px1 + (out_active if active else out_inactive)
        y0 = first_y + i * (tab_h + tab_gap)
        dpg.draw_rectangle((x0, y0), (x1, y0 + tab_h), color=clear if active else border,
                           fill=COLORS["bg_card"] if active else COLORS["bg_sidebar"],
                           rounding=POPUP_TAB_ROUNDING, parent=dl)
        tex = f"tex_{icon_name}"
        ix = x0 + POPUP_TAB_OVERLAP + POPUP_TAB_ICON_PAD
        iy = y0 + (tab_h - icon_size) / 2
        if dpg.does_item_exist(tex):
            dpg.draw_image(tex, (ix, iy), (ix + icon_size, iy + icon_size),
                           color=COLORS["accent_blue"] if active else COLORS["text_secondary"], parent=dl)
        if active:
            dpg.draw_text((ix + icon_size + 6, y0 + (tab_h - text_size) / 2), label,
                          color=COLORS["text_primary"], size=text_size, parent=dl)

    # numbered callouts last, so they sit on top
    hw.draw_callout(left + pw * 0.26 + r + 8, py0 + ph * 0.095, 1, radius=r, parent=dl)
    hw.draw_callout(cx0 - r - 6, cy0 + size / 2, 2, radius=r, parent=dl)
    hw.draw_callout(right - r - 6, py0 + ph * 0.565, 3, radius=r, parent=dl)
    hw.draw_callout(px1 + out_inactive + r + 6, first_y + 3.5 * (tab_h + tab_gap), 4, radius=r, parent=dl)


def _build_popup_diagram():
    w = POPUP_DEFAULT_WIDTH
    with dpg.drawlist(width=w, height=int(w * POPUP_ASPECT), tag=POPUP_TAG):
        pass
    _draw_popup(w)
    dpg.add_spacer(height=hw.HELP_PARAGRAPH_GAP)


# ---------- SHAP bar chart ----------

def _shap_height():
    return SHAP_HEADER_H + len(SHAP_EXAMPLE) * SHAP_ROW_H + SHAP_BOTTOM_PAD


def _draw_shap(w):
    dl = SHAP_TAG
    dpg.delete_item(dl, children_only=True)
    h = _shap_height()
    dpg.draw_rectangle((0, 0), (w - 1, h - 1), color=COLORS["border"], fill=hw.HELP_INSET_BG,
                       rounding=SHAP_ROUNDING, parent=dl)

    x0 = w * SHAP_LABEL_RATIO
    x1 = w - SHAP_PAD
    cx = (x0 + x1) / 2
    half = (x1 - x0) / 2
    biggest = max(abs(value) for _name, value in SHAP_EXAMPLE) or 1.0

    dpg.draw_text((x0, 6), "Toward safe", color=COLORS["accent_green"], size=SHAP_NOTE_SIZE, parent=dl)
    right_label = "Toward malware"
    dpg.draw_text((x1 - _text_w(right_label, SHAP_NOTE_SIZE), 6), right_label, color=COLORS["accent_red"],
                  size=SHAP_NOTE_SIZE, parent=dl)
    dpg.draw_line((cx, SHAP_HEADER_H - 4), (cx, h - SHAP_BOTTOM_PAD), color=COLORS["text_secondary"],
                  thickness=1, parent=dl)

    for i, (name, value) in enumerate(SHAP_EXAMPLE):
        mid = SHAP_HEADER_H + i * SHAP_ROW_H + SHAP_ROW_H / 2
        dpg.draw_text((SHAP_PAD, mid - SHAP_TEXT_SIZE / 2), name, color=COLORS["text_primary"],
                      size=SHAP_TEXT_SIZE, parent=dl)
        length = abs(value) / biggest * half * SHAP_BAR_SCALE
        color = COLORS["accent_red"] if value > 0 else COLORS["accent_green"]
        text = f"{value:+.1f}"
        if value > 0:
            bar = ((cx, mid - SHAP_BAR_H / 2), (cx + length, mid + SHAP_BAR_H / 2))
            text_x = cx + length + 4
        else:
            bar = ((cx - length, mid - SHAP_BAR_H / 2), (cx, mid + SHAP_BAR_H / 2))
            text_x = cx - length - 4 - _text_w(text, SHAP_TEXT_SIZE)
        dpg.draw_rectangle(bar[0], bar[1], color=(0, 0, 0, 0), fill=(*color, SHAP_BAR_ALPHA), parent=dl)
        dpg.draw_text((text_x, mid - SHAP_TEXT_SIZE / 2), text, color=COLORS["text_secondary"],
                      size=SHAP_TEXT_SIZE, parent=dl)


def _build_shap_chart():
    with dpg.drawlist(width=SHAP_DEFAULT_WIDTH, height=_shap_height(), tag=SHAP_TAG):
        pass
    _draw_shap(SHAP_DEFAULT_WIDTH)
    hw.gap()


# ---------- resize ----------

def _fit_all():
    if not dpg.does_item_exist(hw.HELP_CONTENT_PANE_TAG):
        return
    pane_w = dpg.get_item_width(hw.HELP_CONTENT_PANE_TAG)
    w = int(max(DRAW_MIN_WIDTH, min(DRAW_MAX_WIDTH, pane_w - SIDE_CHROME)))
    if dpg.does_item_exist(POPUP_TAG):
        dpg.configure_item(POPUP_TAG, width=w, height=int(w * POPUP_ASPECT))
        _draw_popup(w)
    if dpg.does_item_exist(SHAP_TAG):
        dpg.configure_item(SHAP_TAG, width=w, height=_shap_height())
        _draw_shap(w)


def _on_layout_resize(content_w, content_h):
    # help_manual sizes the pane in its own resize handler, which may run AFTER this one,
    # so wait a few frames and then read the pane's final width.
    dpg.set_frame_callback(dpg.get_frame_count() + FRAME_DELAY, lambda *args: _fit_all())


# ---------- the seven tabs ----------

def _build_overview(fonts, icons):
    _tab_title("overview", fonts, icons)
    hw.paragraph("The summary: the verdict at a glance, where the file is and a short reason it was flagged. "
                 "The values below are made up.")
    chips = [("Prediction", "Suspicious", COLORS["accent_orange"]),
             ("Confidence", OVERVIEW_EXAMPLE_CONFIDENCE, COLORS["text_primary"]),
             ("Risk level", "Medium", COLORS["accent_orange"])]
    with dpg.table(header_row=False, policy=dpg.mvTable_SizingStretchSame):
        for _ in chips:
            dpg.add_table_column()
        with dpg.table_row():
            for caption, value, color in chips:
                with dpg.child_window(width=-1, height=OVERVIEW_CHIP_HEIGHT, border=True,
                                      no_scrollbar=True, no_scroll_with_mouse=True) as chip:
                    _caption(caption, fonts)
                    v = dpg.add_text(value, color=color)
                    dpg.bind_item_font(v, fonts["heading"])
                dpg.bind_item_theme(chip, hw.child_card_theme(hw.HELP_INSET_BG, COLORS["border"],
                                                              OVERVIEW_CHIP_PADDING))
    with _card():
        _caption("Location", fonts)
        dpg.add_text(OVERVIEW_EXAMPLE_PATH, color=COLORS["text_primary"])
        _caption("Category", fonts)
        dpg.add_text(OVERVIEW_EXAMPLE_CATEGORY, color=COLORS["text_primary"])
    with _card():
        dpg.add_text("Why was this file flagged?", color=COLORS["accent_blue"])
        dpg.add_text("A short reason, in plain language, appears here.", wrap=0, color=COLORS["text_secondary"])
    hw.gap()
    sus, mal, high, med = (_percent(SUSPICIOUS_AT), _percent(MALICIOUS_AT),
                           _percent(CATEGORY_HIGH_AT), _percent(CATEGORY_MEDIUM_AT))
    _term_table([
        ("Prediction", "text_primary", "AYAWrus's call on the file, such as Suspicious or Malicious."),
        ("Confidence", "text_primary", "How likely the AI thinks the file is malware. A prediction, not proof."),
        ("Risk level", "text_primary", "A rough rating from the detailed explanation: Low, Medium, High or Severe. "
                                      "It shows a dash when no explanation is available."),
        ("Category", "text_primary", "A label based on the estimate. Flagged files start at "
                                    f"{sus}%, so these are the three you will see:"),
        ("SEVERE", "accent_red", f"{mal}% or higher"),
        ("HIGH", "accent_orange", f"{high}% up to just under {mal}%"),
        ("MEDIUM", "accent_blue", f"{med}% up to just under {high}%"),
    ])


def _step_card(number, title, text):
    with _card():
        with dpg.group(horizontal=True):
            with dpg.drawlist(width=STEP_BADGE, height=STEP_BADGE):
                dpg.draw_rectangle((0, 0), (STEP_BADGE - 1, STEP_BADGE - 1), color=(*COLORS["accent_blue"], 160),
                                   fill=(*COLORS["accent_blue"], 40), rounding=9)
                label = str(number)
                tw, th = hw._measure(label)
                dpg.draw_text(((STEP_BADGE - tw) / 2, (STEP_BADGE - th) / 2), label, color=COLORS["accent_blue"],
                              size=hw.HELP_FAKE_TEXT_SIZE)
            with dpg.group():
                dpg.add_text(title, color=COLORS["text_primary"])
                dpg.add_text(text, wrap=0, color=COLORS["text_secondary"])


def _build_steps(fonts, icons):
    _tab_title("steps", fonts, icons)
    hw.paragraph("A plain-language story of the checks AYAWrus ran on this particular file, in order. It is the "
                 "personal version of the Detection Pipeline on the Scan tab. The first three of seven steps are "
                 "shown here.")
    for number, (title, text) in enumerate(STEP_EXAMPLES, 1):
        _step_card(number, title, text)
    hw.gap()


def _build_pe(fonts, icons):
    _tab_title("suspicious", fonts, icons)
    hw.paragraph("The file's technical profile. PE (Portable Executable) is the format Windows programs use. "
                 "The values below are made up.")
    for start in range(0, len(METRICS), METRIC_COLUMNS):
        with dpg.group(horizontal=True):
            for caption, value, _meaning in METRICS[start:start + METRIC_COLUMNS]:
                with dpg.child_window(width=-1 if METRIC_COLUMNS == 1 else 0, height=METRIC_HEIGHT, border=True,
                                      no_scrollbar=True, no_scroll_with_mouse=True) as card:
                    _caption(caption, fonts)
                    dpg.add_text(value, color=COLORS["text_primary"])
                dpg.bind_item_theme(card, hw.child_card_theme(hw.HELP_INSET_BG, COLORS["border"], METRIC_PADDING))
    hw.gap()
    _term_table([(caption, "text_primary", meaning) for caption, _value, meaning in METRICS])
    hw.paragraph("Click the arrow below to open the list of Windows libraries the file uses (example names).")
    with dpg.collapsing_header(label=f"Imported DLLs ({len(EXAMPLE_DLLS)})", default_open=False):
        for name in EXAMPLE_DLLS:
            dpg.add_text(name, color=COLORS["text_secondary"])
    hw.gap()
    with _card():
        dpg.add_text("Example: compressed data", color=COLORS["accent_orange"])
        dpg.add_text("Sometimes a Characteristics Worth Reviewing section lists details like this one. They deserve "
                     "a closer look but do not necessarily mean the file is malicious.", wrap=0,
                     color=COLORS["text_secondary"])
    hw.paragraph("If the file is not a Windows program, the tab says the PE structure is unavailable. "
                 "Anything AYAWrus couldn't read shows N/A.")


def _build_shap(fonts, icons):
    _tab_title("shap", fonts, icons)
    hw.paragraph("SHAP shows which clues the AI used to make its call. Some clues push the estimate toward malware, "
                 "others push it toward safe.")
    with _card():
        dpg.add_text("What is SHAP?", color=COLORS["accent_blue"])
        dpg.add_text("SHAP helps explain why AYAWrus made its prediction. Think of it as showing which clues the AI "
                     "used when deciding whether a file may be dangerous.", wrap=0, color=COLORS["text_secondary"])
    with _card():
        dpg.add_text("Generate a Model Explanation", color=COLORS["text_primary"])
        dpg.add_text("Pressing the button analyzes the file in the background and works out which characteristics "
                     "contributed most. This can take a while, and the file is never executed.", wrap=0,
                     color=COLORS["text_secondary"])
        dpg.add_spacer(height=8)
        hw.fake_button("Generate Explanation", START_COLORS[0], START_COLORS[3])
    dpg.add_text("Ready to generate an explanation.", color=COLORS["text_secondary"])
    hw.gap()
    hw.paragraph("When it finishes, the status line says \"Explanation generated successfully.\" and you see the "
                 "model's malware score and a card for each group of file characteristics. Each card shows whether "
                 "that group raised or lowered the malware estimate, the change in percentage points, and its share "
                 "of the total influence. Here is the idea as a chart (made-up numbers, and your real results appear "
                 "as cards instead of bars): a red bar pushed the estimate up, a green bar pulled it down, and the "
                 "number is the change in percentage points.")
    _build_shap_chart()
    hw.paragraph("A collapsed Advanced Explanation Details section holds the technical numbers for anyone who wants "
                 "them. SHAP explains the model's reasoning. It is not proof that a file is malicious, or that it is safe.")


def _build_actions(fonts, icons):
    _tab_title("actions", fonts, icons)
    hw.paragraph("Suggested next steps for this file, written in plain language. They are recommendations only: "
                 "nothing happens automatically.")
    for widths in ACTION_PLACEHOLDERS:
        with _card():
            with dpg.group(horizontal=True):
                icon = icons.get("circle_check")
                if icon:
                    dpg.add_image(icon, width=ICON_BULLET, height=ICON_BULLET, tint_color=COLORS["accent_green"])
                _placeholder_lines(widths)
    dpg.add_text("The wording is written for each file, so sample text isn't shown here.", wrap=0,
                 color=COLORS["text_secondary"])
    hw.gap()


def _build_learn(fonts, icons):
    _tab_title("learn", fonts, icons)
    hw.paragraph("Short lessons that explain the ideas behind this detection, so you understand what the file did "
                 "and why it matters. Each lesson is its own card.")
    for widths in LEARN_PLACEHOLDERS:
        with _card():
            dpg.add_text("Lesson title", color=COLORS["accent_green"])
            _placeholder_lines(widths)
    dpg.add_text("The lessons depend on the detection, so sample text isn't shown here.", wrap=0,
                 color=COLORS["text_secondary"])
    hw.gap()


def _build_targets(fonts, icons):
    _tab_title("targets", fonts, icons)
    hw.paragraph("This tab estimates which kinds of personal files a suspicious program could go after, such as "
                 "documents or pictures, based on what it is built to do. These are predictions, not confirmed damage.")
    if not LIKELY_TARGETS_BACKEND_READY:
        hw.tip_box("note", "Coming soon",
                   "Likely Targets is still being built. If the tab says 'Waiting for analysis...', that is "
                   "expected for now.", icons)
        return

    T = _targets_themes()
    hw.paragraph("The chips at the top show each kind of file with a percentage. Red chips are the kinds this file "
                 "looks most likely to go after. Below, open a kind to see the folders and files at risk, "
                 "highest risk first, and click a file to read why it was flagged. The examples are made up.")
    with dpg.group(horizontal=True):
        tri = icons.get("triangle_alert")
        if tri:
            dpg.add_image(tri, width=NOTE_ICON_SIZE, height=NOTE_ICON_SIZE, tint_color=COLORS["accent_orange"])
        note = dpg.add_text("Predictions, not confirmed damage", color=COLORS["text_secondary"])
        if fonts.get("mono_small") is not None:
            dpg.bind_item_font(note, fonts["mono_small"])
    dpg.add_spacer(height=4)
    with dpg.group(horizontal=True):
        for name, percent, flagged in TARGET_CHIPS:
            chip = dpg.add_button(label=f"{name} {percent}%", height=CHIP_HEIGHT)
            dpg.bind_item_theme(chip, T["chip_flagged" if flagged else "chip_quiet"])
    dpg.add_spacer(height=4)
    with dpg.collapsing_header(label=f"{TARGET_CATEGORY} ({TARGET_CATEGORY_COUNT} files)",
                               default_open=True) as header:
        dpg.add_text(TARGET_FOLDER, wrap=0, color=COLORS["text_secondary"])
        with dpg.table(header_row=False, policy=dpg.mvTable_SizingStretchProp):
            dpg.add_table_column(width_fixed=True, init_width_or_weight=RISK_COL_W)
            dpg.add_table_column()
            for risk, name in TARGET_FILES:
                with dpg.table_row():
                    pill = dpg.add_button(label=risk, width=-1, height=ROW_BUTTON_H)
                    dpg.bind_item_theme(pill, T["risk_" + risk])
                    dpg.add_text(name, color=COLORS["text_primary"])
    dpg.bind_item_theme(header, T["header_flagged"])
    if fonts.get(HEADER_FONT) is not None:
        dpg.bind_item_font(header, fonts[HEADER_FONT])
    dpg.add_spacer(height=6)
    with dpg.table(header_row=False, policy=dpg.mvTable_SizingStretchProp):
        dpg.add_table_column()
        dpg.add_table_column(width_fixed=True, init_width_or_weight=RESCAN_W + 8)
        with dpg.table_row():
            with dpg.group():
                dpg.add_text(TARGET_LAST_SCANNED, color=COLORS["text_primary"])
                dpg.add_text(TARGET_STATS, wrap=0, color=COLORS["text_secondary"])
            hw.fake_button("Rescan", (*COLORS["accent_blue"], 40), COLORS["accent_blue"], width=RESCAN_W,
                           height=RESCAN_H)
    hw.gap()
    hw.paragraph("Rescan runs the analysis again. The tab can also show these messages:")
    _term_table([
        ("Checking this PC...", "text_secondary", "A spinner shows while the analysis runs. The chips appear first."),
        (STATE_MESSAGES["partial"], "accent_orange", "The analysis stopped at its limit, so the list may be incomplete."),
        (STATE_MESSAGES["cancelled"], "accent_orange", "The analysis was cancelled. You see what was found so far."),
        (STATE_MESSAGES["error"], "accent_red", "Something went wrong, so only saved results are shown."),
        (STATE_MESSAGES["unsupported"], "text_secondary", "Detailed analysis only works for .exe and .dll files for now."),
    ])


# ---------- the topic ----------

def build_topic(fonts, icons):
    hw.page_heading("Explain a Threat", "A closer look at why AYAWrus flagged a file.", fonts)
    hw.paragraph("Press Explain on any row of Detected Threats to open a window with the details behind that "
                 "verdict. Think of it as the file's report card: what AYAWrus checked, what it found and what "
                 "to do next. AYAWrus only reads the file. It never runs it.")

    hw.section_heading("Opening and closing", fonts)
    hw.paragraph("The window slides up and the rest of the app dims behind it. Here it is in simplified form.")
    _build_popup_diagram()
    hw.numbered_row(1, "Title", "The file's name, with its category underneath.")
    hw.numbered_row(2, "Close", "Press X, press Esc, or click the dimmed area outside the window.")
    hw.numbered_row(3, "Page", "The content of the selected tab. It scrolls when there is a lot to show.")
    hw.numbered_row(4, "Tabs", "Click an icon on the right edge to switch tabs. The selected tab widens to show its "
                               "name, and you can hover over the others to see theirs.")

    hw.section_heading("The seven tabs", fonts)
    hw.paragraph("Each tab answers a different question about the file. The examples use made-up values.")
    _build_overview(fonts, icons)
    _build_steps(fonts, icons)
    _build_pe(fonts, icons)
    _build_shap(fonts, icons)
    _build_actions(fonts, icons)
    _build_learn(fonts, icons)
    _build_targets(fonts, icons)

    hw.section_heading("Good to know", fonts)
    if SHOW_EXPLANATION_AVAILABILITY_NOTE:
        hw.tip_box("note", "Not every detection has a full explanation",
                   "Some detections come without the detailed explanation. If a tab says an explanation isn't "
                   "available, the details weren't generated for that file.", icons)
    hw.tip_box("note", "SHAP needs the file",
               "Generate Explanation reads the file again, so it can't work if the file has been moved or deleted, "
               "for example a MALICIOUS file that was already quarantined. It can take a while, and only one runs "
               "at a time.", icons)
    hw.tip_box("tip", "Switching tabs",
               "Every tab opens at the top of its page. Closing the window and pressing Explain on another file "
               "starts fresh.", icons)

    register_resize("help_explain", _on_layout_resize)