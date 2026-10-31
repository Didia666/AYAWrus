import dearpygui.dearpygui as dpg
from ui.theme import COLORS
from ui.layout import register_resize
from ui import help_widgets as hw
from ui.help_scan import SUSPICIOUS_AT, MALICIOUS_AT
from ui.scan_layout import START_COLORS, SECONDARY_COLORS, _get_themes
from ui.scan_threats import EMPTY_TITLE, EMPTY_SUBTITLE

# help_scan_results.py
# Help manual topic: Scan Results (the Detected Threats panel).

# ---- Scan Results topic constants (tune here) ----
# True  = ui/scan.py's Quarantine Selected clears rows that were already quarantined automatically (needs the small fix in scan.py).
# False = those rows stay in the list until the next scan, and the manual says so.
AUTO_QUARANTINED_ROWS_CLEAR = True

SIDE_CHROME = 64                   # pane padding + scrollbar + breathing room, subtracted from the pane width
FRAME_DELAY = 3                    # frames to wait after a resize so help_manual sizes the pane first
DRAW_MIN_WIDTH = 400
DRAW_MAX_WIDTH = 720

# ---- Parts diagram of the Detected Threats panel ----
DIAG_TAG = "help_results_diagram"
DIAG_DEFAULT_WIDTH = 540
DIAG_PAD = 8
DIAG_CALLOUT_GAP = 10              # space around the numbered circles above the header
DIAG_CALLOUT_RADIUS_RATIO = 0.021
DIAG_MIN_CALLOUT_RADIUS = 9
DIAG_HEADER_H = 26
DIAG_ROW_H = 30
DIAG_FOOTER_GAP = 12
DIAG_FOOTER_H = 30
DIAG_BOTTOM_PAD = 10
DIAG_ROUNDING = 6
DIAG_TEXT_SIZE = 12
DIAG_BUTTON_TEXT_SIZE = 11
DIAG_PILL_TEXT_SIZE = 10
DIAG_CELL_PAD = 4
DIAG_HEADER_BG = (40, 52, 78)      # same as HEADER_BG in ui/scan_threats.py
DIAG_ROW_ALT_BG = (255, 255, 255, 10)
DIAG_CHECK_HALF = 6
DIAG_PILL_BG_ALPHA = 40
DIAG_PILL_BORDER_ALPHA = 160
DIAG_FOOTER_SELECT_RATIO = 0.17
DIAG_FOOTER_QUARANTINE_RATIO = 0.31
DIAG_FOOTER_GAP_X = 8
DIAG_COLUMNS = [                   # (header label, share of the width). Must add up to 1.0
    ("Select", 0.08), ("Explain", 0.10), ("File Name", 0.17), ("Location", 0.22),
    ("Confidence", 0.14), ("Behavior", 0.13), ("Verdict", 0.16),
]
# (file name, location, confidence, behavior, verdict, color). All made up.
DIAG_ROWS = [
    ("setup.exe", "D:\\Downloads\\...", "63.8%", "-", "SUSPICIOUS", "accent_orange"),
    ("patch.dll", "D:\\Games\\...", "55.2%", "-", "SUSPICIOUS", "accent_orange"),
    ("tool.exe", "C:\\Temp\\...", "96.4%", "-", "MALICIOUS", "accent_red"),
]

# ---- Confidence gauge ----
GAUGE_TAG = "help_results_gauge"
GAUGE_DEFAULT_WIDTH = 540
GAUGE_HEIGHT = 96
GAUGE_PAD = 10
GAUGE_MARKER_Y = 2
GAUGE_TRI_TOP = 22
GAUGE_BAR_Y = 36
GAUGE_BAR_H = 18
GAUGE_NAME_Y = 60
GAUGE_TICK_Y = 76
GAUGE_TEXT_SIZE = 12
GAUGE_SEG_ALPHA = 210
GAUGE_EXAMPLE_NAME = "example.exe"
GAUGE_EXAMPLE_VALUE = 0.638        # made up

# ---- Tables, footer replicas, empty state ----
CHIP_COLUMN_WIDTH = 140
EXAMPLE_COLUMN_WIDTH = 190
TABLE_TEXT_TOP_OFFSET = 4          # lines the text up with the middle of the chip
FOOTER_SELECT_W = 120
FOOTER_QUARANTINE_W = 190
FOOTER_COUNTER_TOP = 6
FOOTER_PADDING = (12, 10)
EMPTY_BOX_HEIGHT = 120
EMPTY_TOP_SPACER = 22
EMPTY_TITLE_H = 30
EMPTY_SUB_H = 24
EMPTY_FONT_KEY = "subheading"


def _percent(value):
    return int(round(value * 100))


def _text_w(text, size):
    """Rough pixel width of text drawn at a smaller size than the default font."""
    return hw._measure(text)[0] * size / hw.HELP_FAKE_TEXT_SIZE


# ---------- parts diagram ----------

def _diagram_metrics(w):
    r = max(DIAG_MIN_CALLOUT_RADIUS, int(w * DIAG_CALLOUT_RADIUS_RATIO))
    top = 2 * r + DIAG_CALLOUT_GAP
    h = (top + DIAG_HEADER_H + len(DIAG_ROWS) * DIAG_ROW_H + DIAG_FOOTER_GAP
         + DIAG_FOOTER_H + DIAG_BOTTOM_PAD)
    return r, top, int(h)


def _column_edges(w):
    inner = w - 2 * DIAG_PAD
    edges = [DIAG_PAD]
    for _label, share in DIAG_COLUMNS:
        edges.append(edges[-1] + inner * share)
    return edges


def _put_text(dl, text, x, y0, y1, size, color):
    dpg.draw_text((x, (y0 + y1) / 2 - size / 2), text, color=color, size=size, parent=dl)


def _put_centered(dl, text, x0, x1, y0, y1, size, color):
    _put_text(dl, text, (x0 + x1) / 2 - _text_w(text, size) / 2, y0, y1, size, color)


def _draw_diagram(w):
    dl = DIAG_TAG
    dpg.delete_item(dl, children_only=True)
    r, top, h = _diagram_metrics(w)
    edges = _column_edges(w)
    clear = (0, 0, 0, 0)
    border = COLORS["border"]

    dpg.draw_rectangle((0, 0), (w - 1, h - 1), color=border, fill=COLORS["bg_card"],
                       rounding=DIAG_ROUNDING, parent=dl)

    # header
    dpg.draw_rectangle((DIAG_PAD, top), (w - DIAG_PAD, top + DIAG_HEADER_H), color=clear,
                       fill=DIAG_HEADER_BG, parent=dl)
    for i, (label, _share) in enumerate(DIAG_COLUMNS):
        _put_text(dl, label, edges[i] + DIAG_CELL_PAD, top, top + DIAG_HEADER_H, DIAG_TEXT_SIZE,
                  COLORS["text_secondary"])

    # rows
    for n, (name, location, confidence, behavior, verdict, color_name) in enumerate(DIAG_ROWS):
        y0 = top + DIAG_HEADER_H + n * DIAG_ROW_H
        y1 = y0 + DIAG_ROW_H
        mid = (y0 + y1) / 2
        color = COLORS[color_name]
        if n % 2 == 1:
            dpg.draw_rectangle((DIAG_PAD, y0), (w - DIAG_PAD, y1), color=clear, fill=DIAG_ROW_ALT_BG, parent=dl)
        cx = (edges[0] + edges[1]) / 2
        dpg.draw_rectangle((cx - DIAG_CHECK_HALF, mid - DIAG_CHECK_HALF), (cx + DIAG_CHECK_HALF, mid + DIAG_CHECK_HALF),
                           color=border, fill=(255, 255, 255, 15), rounding=2, parent=dl)
        dpg.draw_rectangle((edges[1] + 3, y0 + 5), (edges[2] - 3, y1 - 5), color=clear,
                           fill=SECONDARY_COLORS[0], rounding=4, parent=dl)
        _put_centered(dl, "Explain", edges[1] + 3, edges[2] - 3, y0, y1, DIAG_BUTTON_TEXT_SIZE, COLORS["text_primary"])
        _put_text(dl, name, edges[2] + DIAG_CELL_PAD, y0, y1, DIAG_TEXT_SIZE, COLORS["text_primary"])
        _put_text(dl, location, edges[3] + DIAG_CELL_PAD, y0, y1, DIAG_TEXT_SIZE, COLORS["text_secondary"])
        _put_text(dl, confidence, edges[4] + DIAG_CELL_PAD, y0, y1, DIAG_TEXT_SIZE, COLORS["accent_red"])
        _put_text(dl, behavior, edges[5] + DIAG_CELL_PAD, y0, y1, DIAG_TEXT_SIZE, COLORS["text_secondary"])
        px0, px1 = edges[6] + DIAG_CELL_PAD, edges[7] - 6
        dpg.draw_rectangle((px0, y0 + 6), (px1, y1 - 6), color=(*color, DIAG_PILL_BORDER_ALPHA),
                           fill=(*color, DIAG_PILL_BG_ALPHA), rounding=8, parent=dl)
        _put_centered(dl, verdict, px0, px1, y0, y1, DIAG_PILL_TEXT_SIZE, color)

    # footer: Select All, Quarantine Selected, counter
    inner = w - 2 * DIAG_PAD
    fy0 = top + DIAG_HEADER_H + len(DIAG_ROWS) * DIAG_ROW_H + DIAG_FOOTER_GAP
    fy1 = fy0 + DIAG_FOOTER_H
    sel_x0 = DIAG_PAD
    sel_x1 = sel_x0 + inner * DIAG_FOOTER_SELECT_RATIO
    qua_x0 = sel_x1 + DIAG_FOOTER_GAP_X
    qua_x1 = qua_x0 + inner * DIAG_FOOTER_QUARANTINE_RATIO
    dpg.draw_rectangle((sel_x0, fy0), (sel_x1, fy1), color=clear, fill=SECONDARY_COLORS[0], rounding=4, parent=dl)
    _put_centered(dl, "Select All", sel_x0, sel_x1, fy0, fy1, DIAG_BUTTON_TEXT_SIZE, COLORS["text_primary"])
    dpg.draw_rectangle((qua_x0, fy0), (qua_x1, fy1), color=clear, fill=START_COLORS[0], rounding=4, parent=dl)
    _put_centered(dl, "Quarantine Selected", qua_x0, qua_x1, fy0, fy1, DIAG_BUTTON_TEXT_SIZE, COLORS["text_primary"])
    _put_text(dl, "0 selected", qua_x1 + DIAG_FOOTER_GAP_X, fy0, fy1, DIAG_TEXT_SIZE, COLORS["text_secondary"])

    # numbered callouts last, so they sit on top
    cy = DIAG_CALLOUT_GAP / 2 + r
    for i in range(len(DIAG_COLUMNS)):
        hw.draw_callout((edges[i] + edges[i + 1]) / 2, cy, i + 1, radius=r, parent=dl)
    hw.draw_callout(w - DIAG_PAD - r - 2, (fy0 + fy1) / 2, len(DIAG_COLUMNS) + 1, radius=r, parent=dl)


def _build_diagram():
    w = DIAG_DEFAULT_WIDTH
    _r, _top, h = _diagram_metrics(w)
    with dpg.drawlist(width=w, height=h, tag=DIAG_TAG):
        pass
    _draw_diagram(w)
    hw.gap()


# ---------- confidence gauge ----------

def _place_text(dl, text, cx, y, lo, hi, color):
    tw = _text_w(text, GAUGE_TEXT_SIZE)
    x = max(lo, min(cx - tw / 2, hi - tw))
    dpg.draw_text((x, y), text, color=color, size=GAUGE_TEXT_SIZE, parent=dl)


def _draw_gauge(w):
    dl = GAUGE_TAG
    dpg.delete_item(dl, children_only=True)
    clear = (0, 0, 0, 0)
    x0, x1 = GAUGE_PAD, w - GAUGE_PAD
    span = x1 - x0
    s_x = x0 + span * SUSPICIOUS_AT
    m_x = x0 + span * MALICIOUS_AT

    dpg.draw_rectangle((0, 0), (w - 1, GAUGE_HEIGHT - 1), color=COLORS["border"], fill=hw.HELP_INSET_BG,
                       rounding=DIAG_ROUNDING, parent=dl)

    segments = [(x0, s_x, "accent_green", "CLEAN"),
                (s_x, m_x, "accent_orange", "SUSPICIOUS"),
                (m_x, x1, "accent_red", "MALICIOUS")]
    for a, b, color_name, name in segments:
        dpg.draw_rectangle((a, GAUGE_BAR_Y), (b, GAUGE_BAR_Y + GAUGE_BAR_H), color=clear,
                           fill=(*COLORS[color_name], GAUGE_SEG_ALPHA), parent=dl)
        _place_text(dl, name, (a + b) / 2, GAUGE_NAME_Y, x0, x1, COLORS[color_name])

    ticks = [(x0, "0%"), (s_x, f"{_percent(SUSPICIOUS_AT)}%"), (m_x, f"{_percent(MALICIOUS_AT)}%"), (x1, "100%")]
    for x, label in ticks:
        dpg.draw_line((x, GAUGE_BAR_Y), (x, GAUGE_BAR_Y + GAUGE_BAR_H + 4), color=COLORS["text_secondary"],
                      thickness=1, parent=dl)
        _place_text(dl, label, x, GAUGE_TICK_Y, x0, x1, COLORS["text_secondary"])

    mx = x0 + span * GAUGE_EXAMPLE_VALUE
    dpg.draw_triangle((mx - 5, GAUGE_TRI_TOP), (mx + 5, GAUGE_TRI_TOP), (mx, GAUGE_BAR_Y - 2),
                      color=COLORS["text_primary"], fill=COLORS["text_primary"], parent=dl)
    _place_text(dl, f"{GAUGE_EXAMPLE_NAME}  {GAUGE_EXAMPLE_VALUE * 100:.1f}%", mx, GAUGE_MARKER_Y, x0, x1,
                COLORS["text_primary"])


def _build_gauge():
    with dpg.drawlist(width=GAUGE_DEFAULT_WIDTH, height=GAUGE_HEIGHT, tag=GAUGE_TAG):
        pass
    _draw_gauge(GAUGE_DEFAULT_WIDTH)
    hw.gap()


# ---------- resize ----------

def _fit_all():
    if not dpg.does_item_exist(hw.HELP_CONTENT_PANE_TAG):
        return
    pane_w = dpg.get_item_width(hw.HELP_CONTENT_PANE_TAG)
    w = int(max(DRAW_MIN_WIDTH, min(DRAW_MAX_WIDTH, pane_w - SIDE_CHROME)))
    if dpg.does_item_exist(DIAG_TAG):
        _r, _top, h = _diagram_metrics(w)
        dpg.configure_item(DIAG_TAG, width=w, height=h)
        _draw_diagram(w)
    if dpg.does_item_exist(GAUGE_TAG):
        dpg.configure_item(GAUGE_TAG, width=w, height=GAUGE_HEIGHT)
        _draw_gauge(w)


def _on_layout_resize(content_w, content_h):
    # help_manual sizes the pane in its own resize handler, which may run AFTER this one,
    # so wait a few frames and then read the pane's final width.
    dpg.set_frame_callback(dpg.get_frame_count() + FRAME_DELAY, lambda *args: _fit_all())


# ---------- tables ----------

def _chip_table(rows, fonts):
    with dpg.table(header_row=False, borders_innerH=False, borders_outerH=False,
                   borders_innerV=False, borders_outerV=False):
        dpg.add_table_column(width_fixed=True, init_width_or_weight=CHIP_COLUMN_WIDTH)
        dpg.add_table_column(width_stretch=True, init_width_or_weight=1.0)
        for chip_text, color_name, meaning in rows:
            with dpg.table_row():
                with dpg.group():
                    hw.chip(chip_text, color_name, fonts)
                    dpg.add_spacer(height=4)
                with dpg.group():
                    dpg.add_spacer(height=TABLE_TEXT_TOP_OFFSET)
                    dpg.add_text(meaning, wrap=0, color=hw.HELP_BODY_COLOR)
                    dpg.add_spacer(height=4)
    hw.gap()


def _example_table(rows):
    """rows = (example cell text, color name, meaning). The example text is drawn like the real cell."""
    with dpg.table(header_row=False, borders_innerH=False, borders_outerH=False,
                   borders_innerV=False, borders_outerV=False):
        dpg.add_table_column(width_fixed=True, init_width_or_weight=EXAMPLE_COLUMN_WIDTH)
        dpg.add_table_column(width_stretch=True, init_width_or_weight=1.0)
        for example, color_name, meaning in rows:
            with dpg.table_row():
                with dpg.group():
                    dpg.add_text(example, color=COLORS[color_name])
                    dpg.add_spacer(height=4)
                with dpg.group():
                    dpg.add_text(meaning, wrap=0, color=hw.HELP_BODY_COLOR)
                    dpg.add_spacer(height=4)
    hw.gap()


# ---------- footer + empty state replicas ----------

def _footer_state(first_label, counter_text, caption):
    with dpg.child_window(width=-1, auto_resize_y=True, border=True) as box:
        with dpg.group(horizontal=True):
            hw.fake_button(first_label, SECONDARY_COLORS[0], SECONDARY_COLORS[3], width=FOOTER_SELECT_W)
            hw.fake_button("Quarantine Selected", START_COLORS[0], START_COLORS[3], width=FOOTER_QUARANTINE_W)
            with dpg.group():
                dpg.add_spacer(height=FOOTER_COUNTER_TOP)
                dpg.add_text(counter_text, color=COLORS["text_secondary"])
    dpg.bind_item_theme(box, hw.child_card_theme(hw.HELP_INSET_BG, COLORS["border"], FOOTER_PADDING))
    dpg.add_text(caption, wrap=0, color=COLORS["text_secondary"])
    hw.gap()


def _build_empty_state(fonts):
    base = _get_themes()
    with dpg.child_window(width=-1, height=EMPTY_BOX_HEIGHT, border=True,
                          no_scrollbar=True, no_scroll_with_mouse=True) as box:
        dpg.add_spacer(height=EMPTY_TOP_SPACER)
        title = dpg.add_button(label=EMPTY_TITLE, width=-1, height=EMPTY_TITLE_H)
        sub = dpg.add_button(label=EMPTY_SUBTITLE, width=-1, height=EMPTY_SUB_H)
    dpg.bind_item_theme(box, hw.child_card_theme(hw.HELP_INSET_BG, COLORS["border"], FOOTER_PADDING))
    dpg.bind_item_theme(title, base["label_on"])
    dpg.bind_item_theme(sub, base["sub"])
    font = fonts.get(EMPTY_FONT_KEY)
    if font is not None:
        dpg.bind_item_font(title, font)
    hw.gap()


# ---------- the topic ----------

def build_topic(fonts, icons):
    sus, mal = _percent(SUSPICIOUS_AT), _percent(MALICIOUS_AT)

    hw.page_heading("Scan Results", "What the Detected Threats list is telling you.", fonts)
    hw.paragraph("When a scan finishes and finds something, a Detected Threats panel appears under the scan panel. "
                 "Each row is one file AYAWrus flagged, and you decide what to do with it.")

    hw.section_heading("The results panel", fonts)
    hw.paragraph("Here is the panel in simplified form. The rows are made up. The numbers match the list underneath.")
    _build_diagram()
    hw.numbered_row(1, "Select", "Tick the files you want to quarantine.")
    hw.numbered_row(2, "Explain", "Opens a detailed explanation of why this file was flagged.")
    hw.numbered_row(3, "File Name", "The file's name. Hover over it to see the full path.")
    hw.numbered_row(4, "Location", "Where the file was found. Long paths are shortened with ... and the full path "
                                   "shows when you hover. On narrow windows this column is hidden to save room.")
    hw.numbered_row(5, "Confidence", "How likely the AI thinks the file is malware (explained below).")
    hw.numbered_row(6, "Behavior", "What kind of threat the file might be (explained below).")
    hw.numbered_row(7, "Verdict", "AYAWrus's call on the file: SUSPICIOUS or MALICIOUS.")
    hw.numbered_row(8, "Buttons", "Select All ticks every row (it turns into Clear once everything is ticked). "
                                  "Quarantine Selected moves the ticked files into quarantine. "
                                  "The counter shows how many are ticked.")

    hw.section_heading("Verdict pills", fonts)
    _chip_table([
        ("SUSPICIOUS", "accent_orange",
         f"The AI estimates {sus}% up to just under {mal}%. It isn't sure, so the file stays where it is "
         "until you decide."),
        ("MALICIOUS", "accent_red",
         f"The AI estimates {mal}% or higher, or the file matches a known malware fingerprint. These files are moved "
         "to quarantine automatically, and they are still listed here so you can review them."),
    ], fonts)

    hw.section_heading("Reading Confidence", fonts)
    hw.paragraph("Confidence is the AI's estimate of how likely the file is to be malware. The bar shows where the "
                 "cut-offs are. The marker is an example file with made-up numbers.")
    _build_gauge()
    hw.paragraph("A value like 63.8% means the AI leans toward malware but isn't sure. It does not mean 63.8% of the "
                 "file is bad. A dash means there is no estimate, which happens when a file is a known-malware match.")

    hw.section_heading("Reading Behavior", fonts)
    hw.paragraph("Behavior is a second opinion from a separate AI model. It guesses what kind of threat the file might "
                 "be, such as Ransomware, Spyware or Worm, and it is only worked out for flagged files. "
                 "The examples below are made up.")
    _example_table([
        ("-", "text_secondary",
         "No kind of threat could be identified. This is common, and it is not a sign that the file is safe or dangerous."),
        ("85% | Ransomware", "accent_orange",
         "The best guess is ransomware (a program that locks your files). 85% is how confident the behavior model is "
         "in that label."),
        ("72% | Spyware +1", "accent_orange",
         "The best guess is Spyware, and one more label was predicted too. Hover over the cell to see them all."),
    ])

    hw.section_heading("Quarantine Selected", fonts)
    hw.paragraph("Quarantine isolates a file so it can't run. AYAWrus copies it into its own quarantine folder under a "
                 "scrambled name, double-checks that the copy is identical, locks it read-only and only then removes "
                 "the original. Nothing is deleted for good: you can restore or permanently delete the file later "
                 "from the Quarantine tab.")
    _footer_state("Select All", "0 selected", "Nothing ticked yet. With nothing ticked, Quarantine Selected does nothing.")
    _footer_state("Clear", "3 selected", "Everything ticked. The first button now reads Clear.")
    hw.numbered_row(1, "Tick the files", "Use the checkboxes, or press Select All.")
    hw.numbered_row(2, "Press Quarantine Selected",
                    "AYAWrus moves each ticked file into quarantine. The button is greyed out while it works.")
    hw.numbered_row(3, "Watch the list update",
                    "Files that were quarantined leave the list, and the Dashboard numbers, Recent Activity and "
                    "History update too.")
    hw.numbered_row(4, "If a file stays",
                    "A file that couldn't be moved stays in the list, so you can try again.")
    if AUTO_QUARANTINED_ROWS_CLEAR:
        hw.tip_box("tip", "MALICIOUS rows are already quarantined",
                   "Files judged MALICIOUS are moved into quarantine during the scan, but they still appear here so "
                   "you can review them. Ticking them and pressing Quarantine Selected just clears them from the "
                   "list. They are safe in the Quarantine tab.", icons)
    else:
        hw.tip_box("tip", "MALICIOUS rows are already quarantined",
                   "Files judged MALICIOUS are moved into quarantine during the scan, but they still appear here so "
                   "you can review them. They stay in this list until your next scan. You can find them in the "
                   "Quarantine tab.", icons)

    hw.section_heading("When nothing is found", fonts)
    _build_empty_state(fonts)
    hw.paragraph("If a scan finds nothing, this message replaces the table.")

    hw.section_heading("Good to know", fonts)
    hw.tip_box("tip", "A flag is a prediction",
               "AYAWrus estimates, it doesn't know. Games, launchers and developer tools can look suspicious. "
               "Use Explain to see why a file was flagged before you decide.", icons)
    hw.tip_box("note", "Results belong to your latest scan",
               "Starting a new scan hides the list, and the next results replace it. History keeps a record of "
               "what was found.", icons)
    hw.tip_box("tip", "Hover for details",
               "Hover over a file name or location to see the full path, and over the Behavior cell to see every "
               "predicted label.", icons)

    register_resize("help_scan_results", _on_layout_resize)