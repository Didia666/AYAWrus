import dearpygui.dearpygui as dpg
from ui.theme import COLORS
from ui.layout import register_resize
from ui.activity_feed import ACTIVITY_STATUS_STYLES, ACTIVITY_DEFAULT_STYLE, _add_badge
from ui import help_widgets as hw

# help_dashboard.py
# Help manual topic: Dashboard.

# ---- Dashboard topic constants (tune here) ----
DIAGRAM_TAG = "help_dash_diagram"
DIAGRAM_DEFAULT_WIDTH = 520
DIAGRAM_MIN_WIDTH = 380
DIAGRAM_MAX_WIDTH = 640
DIAGRAM_ASPECT = 0.52              # diagram height = width * this
DIAGRAM_SIDE_CHROME = 64           # pane padding + scrollbar + breathing room, subtracted from the pane width
DIAGRAM_FRAME_DELAY = 3            # frames to wait after a resize so help_manual sizes the pane first
DIAGRAM_NAV_ROWS = 7               # fake sidebar buttons (6 tabs + Help)
DIAGRAM_CALLOUT_RADIUS_RATIO = 0.024
DIAGRAM_MIN_CALLOUT_RADIUS = 9
DIAGRAM_CHART_VALUES = [0.02, 0.02, 0.92, 0.04, 0.02, 0.04, 0.78]
DIAGRAM_FEED_ROWS = 5

CHART_DEMO_TAG = "help_dash_chart_demo"
CHART_DEMO_WIDTH = 460
CHART_DEMO_HEIGHT = 180
CHART_DEMO_PAD = (40, 26, 18, 30)  # left, top, right, bottom
CHART_DEMO_VALUES = [0, 0, 9, 3, 0, 0, 6]
CHART_DEMO_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
CHART_DEMO_Y_TOP = 10
CHART_DEMO_CALLOUT_RADIUS = 10

# These mirror the card color rules in ui/dashboard.py (counts, not percentages). Update here if those change.
HIGH_RISK_ORANGE_AT = 30
HIGH_RISK_RED_AT = 70

BADGE_LEGEND_COLUMN_WIDTH = 136
BADGE_LEGEND_TEXT_TOP_OFFSET = 5   # lines the one-line text up with the middle of the badge

# result key (from activity_feed.py) -> what it means. New statuses added there show up automatically.
BADGE_MEANINGS = {
    "MALICIOUS": "The scan flagged this file as malware. Counts toward the Threat Index chart.",
    "SUSPICIOUS": "The scan found something unusual but isn't certain. Counts toward the chart. Worth a closer look.",
    "CLEAN": "The file was checked and nothing was found. Clean files usually aren't saved to history, so you'll rarely see this one.",
    "QUARANTINED": "The file was moved into isolation. You'll find it in the Quarantine tab.",
    "RESTORED": "A quarantined file was restored.",
    "DELETED": "A quarantined file was deleted.",
    "INFO": "Anything else, such as a file AYAWrus couldn't analyze. The example rows on a brand-new install use this badge too.",
}
BADGE_DEFAULT_MEANING = "Other activity."


# ---------- parts diagram (redrawn to fit the pane whenever the window resizes) ----------

def _draw_diagram(w, h):
    dl = DIAGRAM_TAG
    dpg.delete_item(dl, children_only=True)
    clear = (0, 0, 0, 0)
    border = COLORS["border"]
    r = max(DIAGRAM_MIN_CALLOUT_RADIUS, int(w * DIAGRAM_CALLOUT_RADIUS_RATIO))

    # app window
    dpg.draw_rectangle((0, 0), (w - 1, h - 1), color=border, fill=COLORS["bg_main"], rounding=6, parent=dl)

    # sidebar: logo + fake nav buttons, first one active
    sb_w = w * 0.17
    dpg.draw_rectangle((1, 1), (sb_w, h - 2), color=clear, fill=COLORS["bg_sidebar"], rounding=6, parent=dl)
    dpg.draw_rectangle((sb_w * 0.12, h * 0.05), (sb_w * 0.88, h * 0.13), color=clear,
                       fill=(*COLORS["accent_blue"], 90), rounding=3, parent=dl)
    row_h = h * 0.07
    for i in range(DIAGRAM_NAV_ROWS):
        y0 = h * 0.20 + i * h * 0.095
        active = i == 0
        dpg.draw_rectangle((sb_w * 0.12, y0), (sb_w * 0.88, y0 + row_h), color=border,
                           fill=COLORS["bg_card"] if active else COLORS["bg_sidebar"], rounding=3, parent=dl)
        if active:
            dpg.draw_rectangle((1, y0), (3, y0 + row_h), color=COLORS["accent_blue"],
                               fill=COLORS["accent_blue"], parent=dl)

    # page title + subtitle placeholders
    left = sb_w + w * 0.03
    right = w * 0.97
    cw = right - left
    gap = w * 0.02
    dpg.draw_rectangle((left, h * 0.06), (left + w * 0.22, h * 0.09), color=clear,
                       fill=(*COLORS["text_primary"], 200), rounding=2, parent=dl)
    dpg.draw_rectangle((left, h * 0.115), (left + w * 0.40, h * 0.135), color=clear,
                       fill=(*COLORS["text_secondary"], 110), rounding=2, parent=dl)

    # three stat cards
    cards_y0, cards_y1 = h * 0.17, h * 0.39
    ch = cards_y1 - cards_y0
    card_w = (cw - 2 * gap) / 3
    for i, name in enumerate(("accent_green", "accent_red", "accent_blue")):
        x0 = left + i * (card_w + gap)
        ac = COLORS[name]
        dpg.draw_rectangle((x0, cards_y0), (x0 + card_w, cards_y1), color=border,
                           fill=COLORS["bg_card"], rounding=4, parent=dl)
        ix = x0 + card_w * 0.08
        dpg.draw_rectangle((ix, cards_y0 + ch * 0.15), (ix + w * 0.02, cards_y0 + ch * 0.15 + w * 0.02),
                           color=clear, fill=(*ac, 200), rounding=2, parent=dl)
        dpg.draw_rectangle((ix, cards_y0 + ch * 0.50), (ix + card_w * 0.22, cards_y0 + ch * 0.74),
                           color=clear, fill=(*ac, 230), rounding=2, parent=dl)

    # chart + feed
    area_y0, area_y1 = h * 0.45, h * 0.95
    ah = area_y1 - area_y0
    chart_x1 = left + cw * 0.60 - gap / 2
    feed_x0 = chart_x1 + gap
    pad = w * 0.02

    dpg.draw_rectangle((left, area_y0), (chart_x1, area_y1), color=border, fill=COLORS["bg_card"],
                       rounding=4, parent=dl)
    dpg.draw_rectangle((left + pad, area_y0 + ah * 0.07), (left + pad + w * 0.16, area_y0 + ah * 0.14),
                       color=clear, fill=(*COLORS["text_primary"], 200), rounding=2, parent=dl)
    plot_x0, plot_x1 = left + pad, chart_x1 - pad
    plot_y0, plot_y1 = area_y0 + ah * 0.26, area_y1 - ah * 0.12
    for k in range(3):
        y = plot_y0 + k * (plot_y1 - plot_y0) / 2
        dpg.draw_line((plot_x0, y), (plot_x1, y), color=(*border, 160), thickness=1, parent=dl)
    n = len(DIAGRAM_CHART_VALUES)
    points = [(plot_x0 + i * (plot_x1 - plot_x0) / (n - 1), plot_y1 - v * (plot_y1 - plot_y0))
              for i, v in enumerate(DIAGRAM_CHART_VALUES)]
    dpg.draw_polyline(points, color=COLORS["accent_blue"], thickness=2, parent=dl)

    dpg.draw_rectangle((feed_x0, area_y0), (right, area_y1), color=border, fill=COLORS["bg_card"],
                       rounding=4, parent=dl)
    dpg.draw_rectangle((feed_x0 + pad, area_y0 + ah * 0.07), (feed_x0 + pad + w * 0.14, area_y0 + ah * 0.14),
                       color=clear, fill=(*COLORS["text_primary"], 200), rounding=2, parent=dl)
    orange = COLORS["accent_orange"]
    for i in range(DIAGRAM_FEED_ROWS):
        ry = area_y0 + ah * 0.27 + i * (ah * 0.68 / DIAGRAM_FEED_ROWS)
        dpg.draw_circle((feed_x0 + pad + 4, ry), 4, color=orange, fill=(*orange, 200), parent=dl)
        dpg.draw_rectangle((feed_x0 + pad + 14, ry - 3), (feed_x0 + (right - feed_x0) * 0.52, ry + 3),
                           color=clear, fill=(*COLORS["text_secondary"], 140), rounding=2, parent=dl)
        dpg.draw_rectangle((right - pad - w * 0.07, ry - 6), (right - pad, ry + 6), color=(*orange, 160),
                           fill=(*orange, 40), rounding=6, parent=dl)

    # numbered callouts last, so they sit on top
    hw.draw_callout(sb_w * 0.5, h * 0.92, 1, radius=r, parent=dl)
    hw.draw_callout(left + r + 4, cards_y0, 2, radius=r, parent=dl)
    hw.draw_callout(left + r + 4, area_y0, 3, radius=r, parent=dl)
    hw.draw_callout(feed_x0 + r + 4, area_y0, 4, radius=r, parent=dl)


def _fit_diagram():
    if not dpg.does_item_exist(DIAGRAM_TAG) or not dpg.does_item_exist(hw.HELP_CONTENT_PANE_TAG):
        return
    pane_w = dpg.get_item_width(hw.HELP_CONTENT_PANE_TAG)
    w = int(max(DIAGRAM_MIN_WIDTH, min(DIAGRAM_MAX_WIDTH, pane_w - DIAGRAM_SIDE_CHROME)))
    h = int(w * DIAGRAM_ASPECT)
    dpg.configure_item(DIAGRAM_TAG, width=w, height=h)
    _draw_diagram(w, h)


def _on_layout_resize(content_w, content_h):
    # help_manual sizes the pane in its own resize handler, which may run AFTER this one,
    # so wait a few frames and then read the pane's final width.
    dpg.set_frame_callback(dpg.get_frame_count() + DIAGRAM_FRAME_DELAY, lambda *args: _fit_diagram())


def _build_diagram():
    w = DIAGRAM_DEFAULT_WIDTH
    h = int(w * DIAGRAM_ASPECT)
    with dpg.drawlist(width=w, height=h, tag=DIAGRAM_TAG):
        pass
    _draw_diagram(w, h)
    dpg.add_spacer(height=hw.HELP_PARAGRAPH_GAP)


# ---------- small example chart ----------

def _build_chart_demo():
    w, h = CHART_DEMO_WIDTH, CHART_DEMO_HEIGHT
    pl, pt, pr, pb = CHART_DEMO_PAD
    plot_w, plot_h = w - pl - pr, h - pt - pb
    last = len(CHART_DEMO_VALUES) - 1

    def px(i):
        return pl + i * plot_w / last

    def py(v):
        return pt + plot_h - (v / CHART_DEMO_Y_TOP) * plot_h

    with dpg.drawlist(width=w, height=h, tag=CHART_DEMO_TAG):
        dpg.draw_rectangle((0, 0), (w - 1, h - 1), color=COLORS["border"], fill=hw.HELP_INSET_BG, rounding=6)
        for v in (0, CHART_DEMO_Y_TOP / 2, CHART_DEMO_Y_TOP):
            y = py(v)
            dpg.draw_line((pl, y), (w - pr, y), color=(*COLORS["border"], 150), thickness=1)
            dpg.draw_text((10, y - 8), str(int(v)), color=COLORS["text_secondary"], size=14)
        points = [(px(i), py(v)) for i, v in enumerate(CHART_DEMO_VALUES)]
        dpg.draw_polyline(points, color=COLORS["accent_blue"], thickness=2)
        for i, (x, y) in enumerate(points):
            dpg.draw_circle((x, y), 4, color=COLORS["accent_blue"], fill=COLORS["accent_blue"])
            dpg.draw_text((x - 12, h - pb + 8), CHART_DEMO_DAYS[i], color=COLORS["text_secondary"], size=14)
        hw.draw_callout(px(2), py(max(CHART_DEMO_VALUES)) - 18, 1, radius=CHART_DEMO_CALLOUT_RADIUS)
        hw.draw_callout((px(0) + px(1)) / 2, py(0) - 18, 2, radius=CHART_DEMO_CALLOUT_RADIUS)
    hw.gap()


# ---------- badge legend ----------

def _build_badge_legend(fonts):
    entries = list(ACTIVITY_STATUS_STYLES.items()) + [("INFO", ACTIVITY_DEFAULT_STYLE)]
    with dpg.table(header_row=False, borders_innerH=False, borders_outerH=False,
                   borders_innerV=False, borders_outerV=False):
        dpg.add_table_column(width_fixed=True, init_width_or_weight=BADGE_LEGEND_COLUMN_WIDTH)
        dpg.add_table_column(width_stretch=True, init_width_or_weight=1.0)
        for key, (_icon, badge_text, color_name) in entries:
            with dpg.table_row():
                with dpg.group():
                    _add_badge(badge_text, color_name, fonts)
                    dpg.add_spacer(height=4)
                with dpg.group():
                    dpg.add_spacer(height=BADGE_LEGEND_TEXT_TOP_OFFSET)
                    dpg.add_text(BADGE_MEANINGS.get(key, BADGE_DEFAULT_MEANING), wrap=0, color=hw.HELP_BODY_COLOR)
                    dpg.add_spacer(height=4)
    hw.gap()


# ---------- the three cards ----------

def _card_block(icon_name, label, value, caption, color_name, explanation, chips, fonts, icons):
    with dpg.group(horizontal=True):
        hw.mini_stat_card(icon_name, label, value, caption, color_name, fonts, icons)
        with dpg.group():
            dpg.add_text(explanation, wrap=0, color=hw.HELP_BODY_COLOR)
    hw.gap()
    hw.chip_row("Number color:", chips, fonts)
    hw.gap()


def _build_cards(fonts, icons):
    hw.paragraph("The numbers on these example cards are made up. Yours will be different.")
    _card_block(
        "shield_check", "High-Risk Items", 3,
        "Quarantined files with estimates of 70% or higher", "accent_green",
        "How many files in Quarantine have an estimated risk of 70% or higher. These are the ones to look at first.",
        [(f"0-{HIGH_RISK_ORANGE_AT - 1}", "accent_green"),
         (f"{HIGH_RISK_ORANGE_AT}-{HIGH_RISK_RED_AT - 1}", "accent_orange"),
         (f"{HIGH_RISK_RED_AT}+", "accent_red")],
        fonts, icons)
    _card_block(
        "octagon_alert", "Quarantined Files", 8,
        "Files currently held in isolation", "accent_red",
        "How many files are being held in isolation right now. Open the Quarantine tab to restore or delete them.",
        [("0", "accent_green"), ("1 or more", "accent_red")],
        fonts, icons)
    _card_block(
        "chart_bar", "Recorded Scans", 492,
        "Results saved in scan history", "accent_blue",
        "How many results are saved in your history. Each flagged file counts as one, and so do quarantine, "
        "restore and delete events, so this is not the number of scans you've run. "
        "Files that scanned clean aren't saved. The History tab groups the results by scan.",
        [("Always blue", "accent_blue")],
        fonts, icons)


# ---------- the topic ----------

def build_topic(fonts, icons):
    hw.page_heading("Dashboard", "Your at-a-glance summary of what AYAWrus has found.", fonts)
    hw.paragraph("The Dashboard is the first screen you see when AYAWrus opens. It's a read-only summary: "
                 "there is nothing to configure here, and the only things to click are the tabs in the sidebar.")

    hw.section_heading("What you're looking at", fonts)
    hw.paragraph("Here is the screen in simplified form. The numbers match the list underneath.")
    _build_diagram()
    hw.numbered_row(1, "Sidebar", "Switches between tabs. The highlighted tab is the screen you're on.")
    hw.numbered_row(2, "Summary cards", "Three counters: High-Risk Items, Quarantined Files and Recorded Scans.")
    hw.numbered_row(3, "Threat Index chart", "How many files were flagged on each of the last 7 days.")
    hw.numbered_row(4, "Recent Activity", "A running list of the latest scan results and quarantine actions.")

    hw.section_heading("The three cards", fonts)
    _build_cards(fonts, icons)

    hw.section_heading("Reading the Threat Index chart", fonts)
    hw.paragraph("The chart shows how many files were flagged on each day. A file counts as flagged when its "
                 "result is DANGER or WARN (the badges are explained below). It always covers the last 7 days, "
                 "laid out from Monday to Sunday. The values in this example are made up.")
    _build_chart_demo()
    hw.numbered_row(1, "Each dot is one day", "The higher the dot, the more files were flagged on that day.")
    hw.numbered_row(2, "Resting on zero is good news", "A flat stretch along the bottom means nothing was flagged that day.")
    hw.paragraph("The chart counts files, not severity: a tall peak means many files were flagged, not that any "
                 "single one is worse. A file that's scanned twice is counted twice.")

    hw.section_heading("Recent Activity badges", fonts)
    hw.paragraph("Every row in Recent Activity has a colored badge on the right. Here is what each one means. "
                 "The newest items are at the top.")
    _build_badge_legend(fonts)

    hw.section_heading("Good to know", fonts)
    hw.tip_box("tip", "The numbers count up",
               "When the Dashboard loads, the numbers count up from zero. That's just an animation, nothing is wrong.",
               icons)
    hw.tip_box("note", "When does it update?",
"The three cards refresh when the app opens, when a scan finishes, and after you quarantine, restore or delete a file. "
               "The chart shows the last 7 days as they were when the app opened. Recent Activity updates when a scan finishes and after you quarantine files from the Scan tab.",
               icons)
    hw.tip_box("note", "Brand-new install?",
               "Before your first scan, Recent Activity shows a few example rows marked INFO. They're placeholders, "
               "not real scan results.",
               icons)
    hw.tip_box("tip", "Need a hand?",
               "The round help bubble in the bottom-right corner opens CyberLearn, the built-in assistant. "
               "Ask it anything in your own words.",
               icons)

    register_resize("help_dashboard", _on_layout_resize)