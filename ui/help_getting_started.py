import dearpygui.dearpygui as dpg
from ui.theme import COLORS
from ui.layout import register_resize
from ui import help_widgets as hw
from ui.help_explain import _card
from ui.help_scan import SUSPICIOUS_AT, MALICIOUS_AT
from ui.help_scan_results import _chip_table, _put_text, _put_centered
from ui.help_settings import CYBERLEARN_HAS_OFFLINE_MODE
from ui.scan_layout import _get_themes
from ui.sidebar import NAV_ITEMS

# help_getting_started.py
# Help manual topic: Getting Started (the first entry in the list). A short tour: each part points to the topic that
# explains it in full. The tab list and its icons come from ui/sidebar.py, so they can't drift.

TOPIC_KEY = "getting_started"      # must match the key in HELP_TOPICS (ui/help_manual.py)

# ---- Shared sizes ----
DEFAULT_WIDTH = 540
DRAW_MIN_WIDTH = 480
DRAW_MAX_WIDTH = 720
SIDE_CHROME = 64                   # pane padding + scrollbar + breathing room, subtracted from the pane width
FRAME_DELAY = 3                    # frames to wait after a resize so help_manual sizes the pane first
ROUNDING = 8
SUBHEADING_GAP = 14

# ---- First-scan strip ----
FLOW_TAG = "help_gs_flow"
FLOW_H = 96
FLOW_GAP = 22
FLOW_ICON = 26
FLOW_ICON_TOP = 14
FLOW_LABEL_TOP = 56
FLOW_LABEL_H = 20
FLOW_LABEL_SIZE = 12
FLOW_BADGE_SIZE = 11
FLOW_STEPS = [                     # (icon from icons.py, short label)
    ("scan_search", "Open Scan"),
    ("zap", "Pick a type"),
    ("play", "Press Start"),
    ("shield_alert", "Review"),
    ("shield_cog", "Decide"),
]

# ---- Sidebar replica (a fixed-size picture of the real sidebar) ----
SIDEBAR_W = 230
SIDEBAR_PAD = 10
SIDEBAR_LOGO_W = 150
SIDEBAR_LOGO_H = 52
SIDEBAR_LOGO_TOP = 12
SIDEBAR_SEP_GAP = 12
SIDEBAR_ITEM_H = 34
SIDEBAR_ITEM_GAP = 6
SIDEBAR_ICON = 16
SIDEBAR_ICON_X = 14
SIDEBAR_TEXT_X = 40
SIDEBAR_TEXT_SIZE = 13
SIDEBAR_INDICATOR_W = 3
SIDEBAR_BOTTOM_PAD = 12
SIDEBAR_CALLOUT_RADIUS = 11
SIDEBAR_CALLOUT_INSET = 6
SIDEBAR_CURRENT_KEY = "help"       # the tab the reader is on right now

TAB_DESCRIPTIONS = {               # nav key (from ui/sidebar.py) -> what the tab is for
    "dashboard": "A summary: three counters, a weekly chart and recent activity.",
    "scan": "Run a Quick, Full or Custom scan and review what it finds.",
    "quarantine": "Files that were isolated. Restore them or delete them.",
    "history": "A record of the scans you've run.",
    "exclusions": "Folders AYAWrus should skip.",
    "settings": "Pair a phone, check for updates, set up the AI Assistant.",
    "help": "This manual.",
}

# ---- Decision cards ----
FLAG_CARDS = [                     # (title, title color name, text)
    ("Suspicious, and you know the file", "accent_orange",
     "A game, launcher or tool you trust? Press Explain to see why it was flagged. If you are sure it is safe, leave "
     "it where it is, and add its folder to Exclusions so future scans skip it."),
    ("Suspicious, and you don't know the file", "accent_orange",
     "Tick it and press Quarantine Selected. It is isolated, not deleted, so you can restore it later if you were "
     "wrong."),
    ("Malicious", "accent_red",
     "AYAWrus has already moved it to Quarantine. Look at it in the Quarantine tab, and press Delete once you are "
     "sure you don't need it."),
]

# ---- Jump buttons ----
JUMP_BUTTON_W = 170
JUMP_BUTTON_H = 36
JUMP_PER_ROW = 3


def _percent(value):
    return int(round(value * 100))


def _subheading(text, fonts):
    dpg.add_spacer(height=SUBHEADING_GAP)
    t = dpg.add_text(text, color=COLORS["text_primary"])
    font = fonts.get("subheading")
    if font is not None:
        dpg.bind_item_font(t, font)
    dpg.add_spacer(height=4)


# ---------- first-scan strip (redrawn to fit the pane whenever the window resizes) ----------

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
        x0 = i * (tile_w + FLOW_GAP)
        x1 = x0 + tile_w
        dpg.draw_rectangle((x0, 0), (x1, FLOW_H - 1), color=COLORS["border"], fill=COLORS["bg_sidebar"],
                           rounding=ROUNDING, parent=dl)
        tex = f"tex_{icon_name}"
        if dpg.does_item_exist(tex):
            cx = (x0 + x1) / 2
            dpg.draw_image(tex, (cx - FLOW_ICON / 2, FLOW_ICON_TOP), (cx + FLOW_ICON / 2, FLOW_ICON_TOP + FLOW_ICON),
                           color=COLORS["accent_blue"], parent=dl)
        _put_centered(dl, label, x0, x1, FLOW_LABEL_TOP, FLOW_LABEL_TOP + FLOW_LABEL_H, FLOW_LABEL_SIZE,
                      COLORS["text_primary"])
        dpg.draw_text((x1 - 14, 4), str(i + 1), color=COLORS["text_secondary"], size=FLOW_BADGE_SIZE, parent=dl)
        if i < count - 1:
            _chevron(dl, x1 + FLOW_GAP / 2, FLOW_H / 2)


def _build_flow():
    with dpg.drawlist(width=DEFAULT_WIDTH, height=FLOW_H, tag=FLOW_TAG):
        pass
    _draw_flow(DEFAULT_WIDTH)
    hw.gap()


def _fit_all():
    if not dpg.does_item_exist(FLOW_TAG) or not dpg.does_item_exist(hw.HELP_CONTENT_PANE_TAG):
        return
    pane_w = dpg.get_item_width(hw.HELP_CONTENT_PANE_TAG)
    w = int(max(DRAW_MIN_WIDTH, min(DRAW_MAX_WIDTH, pane_w - SIDE_CHROME)))
    dpg.configure_item(FLOW_TAG, width=w, height=FLOW_H)
    _draw_flow(w)


def _on_layout_resize(content_w, content_h):
    # help_manual sizes the pane in its own resize handler, which may run AFTER this one,
    # so wait a few frames and then read the pane's final width.
    dpg.set_frame_callback(dpg.get_frame_count() + FRAME_DELAY, lambda *args: _fit_all())


# ---------- sidebar replica ----------

def _sidebar_height():
    return int(SIDEBAR_LOGO_TOP + SIDEBAR_LOGO_H + 2 * SIDEBAR_SEP_GAP
               + len(NAV_ITEMS) * (SIDEBAR_ITEM_H + SIDEBAR_ITEM_GAP) + SIDEBAR_BOTTOM_PAD)


def _build_sidebar_replica():
    border = COLORS["border"]
    blue = COLORS["accent_blue"]
    height = _sidebar_height()
    with dpg.drawlist(width=SIDEBAR_W, height=height) as dl:
        dpg.draw_rectangle((0, 0), (SIDEBAR_W - 1, height - 1), color=border, fill=COLORS["bg_sidebar"],
                           rounding=ROUNDING, parent=dl)
        if dpg.does_item_exist("tex_logo"):
            lx = (SIDEBAR_W - SIDEBAR_LOGO_W) / 2
            dpg.draw_image("tex_logo", (lx, SIDEBAR_LOGO_TOP), (lx + SIDEBAR_LOGO_W, SIDEBAR_LOGO_TOP + SIDEBAR_LOGO_H),
                           color=blue, parent=dl)
        sep_y = SIDEBAR_LOGO_TOP + SIDEBAR_LOGO_H + SIDEBAR_SEP_GAP
        dpg.draw_line((0, sep_y), (SIDEBAR_W, sep_y), color=border, thickness=1, parent=dl)
        y = sep_y + SIDEBAR_SEP_GAP
        x0, x1 = SIDEBAR_PAD, SIDEBAR_W - SIDEBAR_PAD
        for number, item in enumerate(NAV_ITEMS, 1):
            active = item["key"] == SIDEBAR_CURRENT_KEY
            dpg.draw_rectangle((x0, y), (x1, y + SIDEBAR_ITEM_H), color=border,
                               fill=COLORS["bg_card"] if active else COLORS["bg_sidebar"], rounding=6, parent=dl)
            if active:
                dpg.draw_rectangle((0, y), (SIDEBAR_INDICATOR_W, y + SIDEBAR_ITEM_H), color=blue, fill=blue, parent=dl)
            tex = f"tex_{item['icon']}"
            if dpg.does_item_exist(tex):
                iy = y + (SIDEBAR_ITEM_H - SIDEBAR_ICON) / 2
                dpg.draw_image(tex, (SIDEBAR_ICON_X, iy), (SIDEBAR_ICON_X + SIDEBAR_ICON, iy + SIDEBAR_ICON),
                               color=blue if active else COLORS["text_secondary"], parent=dl)
            _put_text(dl, item["label"], SIDEBAR_TEXT_X, y, y + SIDEBAR_ITEM_H, SIDEBAR_TEXT_SIZE,
                      COLORS["text_primary"] if active else COLORS["text_secondary"])
            hw.draw_callout(x1 - SIDEBAR_CALLOUT_RADIUS - SIDEBAR_CALLOUT_INSET, y + SIDEBAR_ITEM_H / 2, number,
                            radius=SIDEBAR_CALLOUT_RADIUS, parent=dl)
            y += SIDEBAR_ITEM_H + SIDEBAR_ITEM_GAP


def _build_sidebar_guide():
    with dpg.group(horizontal=True):
        _build_sidebar_replica()
        with dpg.group():
            for number, item in enumerate(NAV_ITEMS, 1):
                hw.numbered_row(number, item["label"], TAB_DESCRIPTIONS.get(item["key"], ""))
    hw.gap()


# ---------- jump buttons ----------

def _open_topic(sender, app_data, user_data):
    from ui import help_manual          # imported here, because help_manual imports this file
    help_manual._select_topic(user_data)


def _build_jump_buttons():
    from ui import help_manual
    base = _get_themes()
    topics = [t for t in help_manual.HELP_TOPICS if t["key"] != TOPIC_KEY]
    for start in range(0, len(topics), JUMP_PER_ROW):
        with dpg.group(horizontal=True):
            for topic in topics[start:start + JUMP_PER_ROW]:
                button = dpg.add_button(label=topic["label"], width=JUMP_BUTTON_W, height=JUMP_BUTTON_H,
                                        callback=_open_topic, user_data=topic["key"])
                dpg.bind_item_theme(button, base["btn_secondary"])
    hw.gap()


# ---------- decision cards ----------

def _build_flag_cards():
    for title, color_name, text in FLAG_CARDS:
        with _card():
            dpg.add_text(title, color=COLORS[color_name])
            dpg.add_text(text, wrap=0, color=hw.HELP_BODY_COLOR)
    hw.gap()


# ---------- the topic ----------

def build_topic(fonts, icons):
    sus, mal = _percent(SUSPICIOUS_AT), _percent(MALICIOUS_AT)

    hw.page_heading("Getting Started", "A quick tour of AYAWrus.", fonts)
    hw.paragraph("AYAWrus checks your PC for malicious Windows programs. It uses a trained AI model, plus a list of "
                 "known malware, to judge each program file it finds. Anything dangerous can be isolated in "
                 "Quarantine, and for every flagged file AYAWrus can show you why it was flagged. Nothing needs "
                 "setting up before your first scan.")

    hw.section_heading("Your first scan", fonts)
    _build_flow()
    hw.numbered_row(1, "Open the Scan tab", "Click Scan in the sidebar on the left.")
    hw.numbered_row(2, "Pick a scan type", "Quick Scan is a good first choice. It checks your Downloads and Desktop "
                                           "folders, your Temp folder and the Windows Temp folder. Full Scan checks "
                                           "your whole system drive, and Custom Scan checks a folder you choose.")
    hw.numbered_row(3, "Press Start", "The button is named after your scan type. A progress bar shows how it is going, "
                                      "and you can press Cancel Scan at any time.")
    hw.numbered_row(4, "Review the results", "When the scan ends, a Detected Threats list appears under the scan "
                                             "panel. If it says 'No threats detected', nothing suspicious was found.")
    hw.numbered_row(5, "Decide what to do", "For each flagged file you can look closer with Explain, isolate it with "
                                            "Quarantine Selected, or leave it alone (see below).")
    hw.paragraph("After a scan, the Dashboard's numbers and Recent Activity update, and History keeps a summary of the "
                 "scan.")

    hw.section_heading("Understanding the results", fonts)
    hw.paragraph("Each flagged file gets a verdict:")
    _chip_table([
        ("SUSPICIOUS", "accent_orange",
         f"The AI estimates {sus}% up to just under {mal}%. It isn't sure, so the file stays where it is until you "
         "decide."),
        ("MALICIOUS", "accent_red",
         f"The AI estimates {mal}% or higher, or the file matches a known malware fingerprint. It is moved to "
         "Quarantine automatically."),
    ], fonts)
    hw.tip_box("note", "A flag is a prediction",
               "AYAWrus estimates, it doesn't know. Games, launchers and developer tools can look suspicious. Use "
               "Explain to see why a file was flagged before you decide.", icons)
    _subheading("What to do with a flagged file", fonts)
    _build_flag_cards()
    hw.tip_box("tip", "Nothing is deleted by a scan",
               "A scan never deletes anything for good. MALICIOUS files are moved to Quarantine, where you can restore "
               "or delete them. Only Delete removes a file for good.", icons)

    hw.section_heading("Finding your way around", fonts)
    hw.paragraph("The sidebar on the left switches between tabs. Here it is as a picture, with the tab you are on "
                 "highlighted:")
    _build_sidebar_guide()

    hw.section_heading("Read more", fonts)
    hw.paragraph("Each topic in this manual explains one part of AYAWrus in full. Press a button to open it:")
    _build_jump_buttons()

    hw.section_heading("Getting help", fonts)
    if CYBERLEARN_HAS_OFFLINE_MODE:
        bubble = ("The round help bubble in the bottom-right corner opens CyberLearn. Pick one of its ready-made "
                  "questions for a quick answer. To type your own questions, set up the AI Assistant in Settings.")
    else:
        bubble = ("The round help bubble in the bottom-right corner opens CyberLearn. It needs the AI Assistant set "
                  "up in Settings to answer.")
    hw.tip_box("tip", "Ask CyberLearn", bubble, icons)
    hw.tip_box("tip", "Hover for details",
               "Hovering over file names, paths, colored labels and buttons shows more information.", icons)
    hw.tip_box("tip", "Optional extras",
               "When you want more, Settings lets you pair a phone to get scan alerts, set up the AI Assistant and "
               "choose when the intro animation plays.", icons)

    register_resize("help_getting_started", _on_layout_resize)