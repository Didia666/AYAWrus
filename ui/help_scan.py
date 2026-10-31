import dearpygui.dearpygui as dpg
from ui.theme import COLORS
from ui.layout import register_resize
from ui import help_widgets as hw
from ui.scan import SCAN_TYPES
from ui.scan_layout import START_COLORS, CANCEL_COLORS, SECONDARY_COLORS, DISABLED_BG, DISABLED_TEXT

try:
    import system.config as cfg
    SUSPICIOUS_AT = cfg.MALWARE_SUSPICIOUS_THRESHOLD
    MALICIOUS_AT = cfg.MALWARE_MALICIOUS_THRESHOLD
except Exception:
    SUSPICIOUS_AT = 0.50           # fallbacks, same as system/config.py
    MALICIOUS_AT = 0.90

# help_scan.py
# Help manual topic: Scan.

# ---- Scan topic constants (tune here) ----
MAX_FILE_MB = 500                  # mirrors the size limit in system/scanner/file_scan.py. Update here if that changes

SCAN_CARD_WIDTH = 250
SCAN_CARD_HEIGHT = 96
SCAN_CARD_PADDING = (12, 10)
SCAN_CARD_ICON_SIZE = 26
SCAN_CARD_ACTIVE_KEY = "quick"     # which card is drawn as "selected" in the examples

BUTTON_WIDTH = 150
SELECT_PATH_WIDTH = 120
PATH_BOX_WIDTH = 260
PATH_HINT = "No path selected"

STATE_PADDING = (14, 12)
STATE_HEADING_FONT_KEY = "subheading"
STATE_START_LABEL = "Start Quick Scan"
STATE_EXAMPLE_FILE = "example.exe"

DECISION_INDENT = 34               # outcome rows sit under the question text
DECISION_CHIP_COLUMN = 140
OUTCOME_TEXT_TOP_OFFSET = 4        # lines the text up with the middle of the chip

STRIP_TAG = "help_scan_strip"
STRIP_DEFAULT_WIDTH = 540
STRIP_MIN_WIDTH = 380
STRIP_MAX_WIDTH = 720
STRIP_HEIGHT = 64
STRIP_GAP = 8
STRIP_ROUNDING = 6
STRIP_ICON_SIZE = 24
STRIP_ICON_DROP = 4                # nudges the icon down a little, below the step number
STRIP_BADGE_DX = 14                # step number distance from the tile's right edge
STRIP_BADGE_DY = 3
STRIP_BADGE_SIZE = 13
STRIP_SIDE_CHROME = 64             # pane padding + scrollbar + breathing room, subtracted from the pane width
STRIP_FRAME_DELAY = 3              # frames to wait after a resize so help_manual sizes the pane first

_SCAN_BY_KEY = {s["key"]: s for s in SCAN_TYPES}

SCOPE_TEXT = {
    "quick": "Checks the places malware most often lands: your Downloads and Desktop folders, your Temp folder "
             "and the Windows Temp folder. Usually the fastest option.",
    "full": "Checks everything on the system drive (usually C:), except protected folders such as Windows, "
            "Program Files, Program Files (x86), the Recycle Bin and System Volume Information. "
            "Other drives, like D:, are not included.",
    "custom": "Checks one folder that you choose, including everything inside its subfolders.",
}

# (icon from icons.py, title, plain-language line). Titles match the Detection Pipeline in the Scan tab.
PIPELINE_STEPS = [
    ("search", "File Selected",
     "AYAWrus opens the file and checks where it is and its basic details."),
    ("monitor_cog", "File Type Verification",
     "It checks the file's real internal signature to confirm it is a Windows program, "
     "so a renamed file can't hide."),
    ("chart_area", "PE Analysis",
     "It reads the program's internal structure: its sections, the Windows functions it uses and its data patterns."),
    ("chart_bar", "Feature Extraction",
     "It turns that structure into a list of measurements the AI can compare."),
    ("shield_cog", "Random Forest AI",
     "A trained AI model compares those measurements with what it learned from many safe and malicious programs."),
    ("shield_check", "Prediction",
     "The model gives its estimate of how likely the file is to be malicious."),
    ("octagon_alert", "Quarantine",
     "Files judged MALICIOUS are moved into quarantine automatically. "
     "SUSPICIOUS files stay where they are until you decide."),
]


def _percent(value):
    return int(round(value * 100))


# ---------- scan type cards ----------

def _scan_card_replica(icon_name, label, subtitle, active, icons):
    border = COLORS["accent_blue"] if active else COLORS["border"]
    bg = COLORS["bg_card"] if active else COLORS["bg_sidebar"]
    with dpg.child_window(width=SCAN_CARD_WIDTH, height=SCAN_CARD_HEIGHT,
                          no_scrollbar=True, no_scroll_with_mouse=True) as card:
        icon = icons.get(icon_name)
        if icon:
            dpg.add_image(icon, width=SCAN_CARD_ICON_SIZE, height=SCAN_CARD_ICON_SIZE,
                          tint_color=COLORS["accent_blue"] if active else COLORS["text_secondary"])
        dpg.add_text(label, color=COLORS["text_primary"] if active else COLORS["text_secondary"])
        dpg.add_text(subtitle, color=COLORS["text_secondary"])
    dpg.bind_item_theme(card, hw.child_card_theme(bg, border, SCAN_CARD_PADDING))


def _scan_type_block(key, icons):
    scan = _SCAN_BY_KEY[key]
    with dpg.group(horizontal=True):
        _scan_card_replica(scan["icon"], scan["label"], scan["subtitle"], key == SCAN_CARD_ACTIVE_KEY, icons)
        with dpg.group():
            dpg.add_text(scan["label"], color=COLORS["text_primary"])
            dpg.add_text(SCOPE_TEXT[key], wrap=0, color=hw.HELP_BODY_COLOR)
    hw.gap()


def _build_custom_row():
    with dpg.group(horizontal=True):
        hw.fake_button("Select Path", SECONDARY_COLORS[0], SECONDARY_COLORS[3], width=SELECT_PATH_WIDTH)
        hw.fake_input(PATH_HINT, PATH_BOX_WIDTH)
    hw.gap()


# ---------- the Ready panel in each state ----------

def _button_spec(label, kind):
    if kind == "start":
        return (label, START_COLORS[0], START_COLORS[3])
    if kind == "cancel":
        return (label, CANCEL_COLORS[0], CANCEL_COLORS[3])
    return (label, DISABLED_BG, DISABLED_TEXT)


def _state_panel(chip_text, chip_color, heading, buttons, status, progress, extras, fonts):
    hw.chip(chip_text, chip_color, fonts)
    with dpg.child_window(width=-1, auto_resize_y=True, border=True) as panel:
        title = dpg.add_text(heading, color=COLORS["text_primary"])
        font = fonts.get(STATE_HEADING_FONT_KEY)
        if font is not None:
            dpg.bind_item_font(title, font)
        with dpg.group(horizontal=True):
            for label, bg, fg in buttons:
                hw.fake_button(label, bg, fg, width=BUTTON_WIDTH)
        if status:
            dpg.add_text(status, wrap=0, color=COLORS["text_secondary"])
        if progress is not None:
            dpg.add_progress_bar(default_value=progress, width=-1)
        for line in extras:
            dpg.add_text(line, color=COLORS["text_secondary"])
    dpg.bind_item_theme(panel, hw.child_card_theme(hw.HELP_INSET_BG, COLORS["border"], STATE_PADDING))
    hw.gap()


def _build_states(fonts):
    idle = [_button_spec(STATE_START_LABEL, "start"), _button_spec("Cancel Scan", "off")]
    running = [_button_spec("Scanning...", "off"), _button_spec("Cancel Scan", "cancel")]
    _state_panel("READY", "accent_blue", "Ready to Scan", idle, None, None, [], fonts)
    _state_panel("SCANNING", "accent_blue", "Scanning...", running,
                 f"Scanning: {STATE_EXAMPLE_FILE} (1,240/5,800 files)", 0.21,
                 ["Elapsed: 12.4s", "Threats found: 2"], fonts)
    _state_panel("COMPLETE", "accent_green", "Scan Complete!", idle,
                 "Scanned 5,800 files in 41.3s. 2 threats found.", 1.0, [], fonts)
    _state_panel("CANCELLED", "accent_orange", "Scan Cancelled", idle,
                 "Scan cancelled. Processed 2,100 files in 15.2s. 3 threats found.", 0.36, [], fonts)
    _state_panel("FAILED", "accent_red", "Scan Failed", idle,
                 "The reason for the failure appears here.", None, [], fonts)


# ---------- "what gets checked" decision flow ----------

def _outcome_table(outcomes, fonts):
    with dpg.group(indent=DECISION_INDENT):
        with dpg.table(header_row=False, borders_innerH=False, borders_outerH=False,
                       borders_innerV=False, borders_outerV=False):
            dpg.add_table_column(width_fixed=True, init_width_or_weight=DECISION_CHIP_COLUMN)
            dpg.add_table_column(width_stretch=True, init_width_or_weight=1.0)
            for chip_text, color_name, meaning in outcomes:
                with dpg.table_row():
                    with dpg.group():
                        hw.chip(chip_text, color_name, fonts)
                        dpg.add_spacer(height=4)
                    with dpg.group():
                        dpg.add_spacer(height=OUTCOME_TEXT_TOP_OFFSET)
                        dpg.add_text(meaning, wrap=0, color=hw.HELP_BODY_COLOR)
                        dpg.add_spacer(height=4)


def _decision_step(number, question, detail, outcomes, fonts):
    hw.numbered_row(number, question, detail)
    _outcome_table(outcomes, fonts)
    hw.gap()


def _build_decisions(fonts):
    sus, mal = _percent(SUSPICIOUS_AT), _percent(MALICIOUS_AT)
    _decision_step(
        1, "Is the file on your Exclusions list?",
        "Excluded files and folders are never scanned.",
        [("SKIPPED", "text_secondary", "Yes: AYAWrus moves on without looking at it.")], fonts)
    _decision_step(
        2, "Is it a Windows program?",
        "AYAWrus checks the file's real internal signature, not its name or extension, so renaming a file doesn't "
        "change the answer. Program files and libraries, such as .exe and .dll files, count.",
        [("SKIPPED", "text_secondary",
          "No: documents, pictures, videos, scripts and other non-program files are skipped. "
          "They are still counted in 'Scanned N files'.")], fonts)
    _decision_step(
        3, "Is it a reasonable size?",
        f"Very large files are not analyzed.",
        [("SKIPPED", "text_secondary", f"Files over {MAX_FILE_MB} MB are skipped.")], fonts)
    _decision_step(
        4, "Is it a known malware file?",
        "AYAWrus compares the file's fingerprint (SHA-256) against a list of known malware.",
        [("MALICIOUS", "accent_red",
          "Yes: flagged right away and moved to quarantine. There is no percentage, so Confidence shows a dash.")],
        fonts)
    _decision_step(
        5, "What does the AI estimate?",
        "If nothing matched, the AI model estimates how likely the file is to be malware.",
        [("CLEAN", "accent_green", f"Under {sus}%: nothing found. Clean files aren't saved to History."),
         ("SUSPICIOUS", "accent_orange",
          f"{sus}% up to just under {mal}%: the file stays where it is and is listed under Detected Threats "
          "so you can decide."),
         ("MALICIOUS", "accent_red", f"{mal}% or higher: moved to quarantine automatically.")], fonts)


# ---------- detection pipeline strip (redrawn to fit the pane whenever the window resizes) ----------

def _draw_strip(w):
    dl = STRIP_TAG
    dpg.delete_item(dl, children_only=True)
    count = len(PIPELINE_STEPS)
    tile_w = (w - (count - 1) * STRIP_GAP) / count
    for i, (icon_name, _title, _line) in enumerate(PIPELINE_STEPS):
        active = i == 0
        x0 = i * (tile_w + STRIP_GAP)
        x1 = x0 + tile_w
        dpg.draw_rectangle((x0, 0), (x1, STRIP_HEIGHT - 1),
                           color=COLORS["accent_blue"] if active else COLORS["border"],
                           fill=COLORS["bg_card"] if active else COLORS["bg_sidebar"],
                           rounding=STRIP_ROUNDING, parent=dl)
        tex = f"tex_{icon_name}"
        if dpg.does_item_exist(tex):
            cx = (x0 + x1) / 2
            top = (STRIP_HEIGHT - STRIP_ICON_SIZE) / 2 + STRIP_ICON_DROP
            dpg.draw_image(tex, (cx - STRIP_ICON_SIZE / 2, top), (cx + STRIP_ICON_SIZE / 2, top + STRIP_ICON_SIZE),
                           color=COLORS["accent_blue"] if active else COLORS["text_secondary"], parent=dl)
        dpg.draw_text((x1 - STRIP_BADGE_DX, STRIP_BADGE_DY), str(i + 1), color=COLORS["text_secondary"],
                      size=STRIP_BADGE_SIZE, parent=dl)


def _fit_strip():
    if not dpg.does_item_exist(STRIP_TAG) or not dpg.does_item_exist(hw.HELP_CONTENT_PANE_TAG):
        return
    pane_w = dpg.get_item_width(hw.HELP_CONTENT_PANE_TAG)
    w = int(max(STRIP_MIN_WIDTH, min(STRIP_MAX_WIDTH, pane_w - STRIP_SIDE_CHROME)))
    dpg.configure_item(STRIP_TAG, width=w, height=STRIP_HEIGHT)
    _draw_strip(w)


def _on_layout_resize(content_w, content_h):
    # help_manual sizes the pane in its own resize handler, which may run AFTER this one,
    # so wait a few frames and then read the pane's final width.
    dpg.set_frame_callback(dpg.get_frame_count() + STRIP_FRAME_DELAY, lambda *args: _fit_strip())


def _build_strip():
    with dpg.drawlist(width=STRIP_DEFAULT_WIDTH, height=STRIP_HEIGHT, tag=STRIP_TAG):
        pass
    _draw_strip(STRIP_DEFAULT_WIDTH)
    dpg.add_spacer(height=hw.HELP_PARAGRAPH_GAP)


# ---------- the topic ----------

def build_topic(fonts, icons):
    hw.page_heading("Scan", "Check your PC for malicious files.", fonts)
    hw.paragraph("The Scan tab is where you ask AYAWrus to look for malware. Pick a scan type, press Start and "
                 "watch the progress. Anything suspicious is listed below the scan panel when it finishes.")

    hw.section_heading("Pick a scan type", fonts)
    hw.paragraph("Three cards sit at the top of the Scan tab. Click one to select it. The selected card gets a "
                 "blue border, and the Start button takes its name.")
    for key in ("quick", "full", "custom"):
        _scan_type_block(key, icons)
    hw.paragraph("With Custom Scan selected, a Select Path button and a path box appear under the Start button.")
    _build_custom_row()
    hw.paragraph("Select Path opens a folder picker, and the folder you choose shows in the box. The box is "
                 "read-only, so you pick folders with the button instead of typing. If you press Start Custom Scan "
                 "before choosing a folder, the picker opens for you.")

    hw.section_heading("Run a scan", fonts)
    hw.numbered_row(1, "Press Start", "The button is named after your scan type, such as Start Quick Scan.")
    hw.numbered_row(2, "Wait for the count", "AYAWrus first counts the files to check (Discovering files...), "
                                              "then scans them. Big folders can take a moment before the bar moves.")
    hw.numbered_row(3, "Watch the progress", "The status line names the file being checked and how many are done. "
                                              "You also see the time elapsed and a running count of threats found.")
    hw.numbered_row(4, "Read the result", "The heading changes to Scan Complete!, Scan Cancelled or Scan Failed, "
                                           "and a summary line appears.")
    hw.paragraph("Here is the panel at each stage. The numbers are made up.")
    _build_states(fonts)

    hw.section_heading("What gets checked", fonts)
    hw.paragraph("For every file in the scan, AYAWrus asks a few questions in order. The first answer that "
                 "settles the file ends the check.")
    _build_decisions(fonts)

    hw.section_heading("The Detection Pipeline", fonts)
    hw.paragraph("At the bottom of the Scan tab is the Detection Pipeline. It is a guide, not a live tracker: "
                 "nothing lights up while a scan runs. Click a step to read what it does. The selected step grows "
                 "wider and its description appears underneath.")
    _build_strip()
    for number, (_icon, title, line) in enumerate(PIPELINE_STEPS, 1):
        hw.numbered_row(number, title, line)

    hw.section_heading("Good to know", fonts)
    hw.tip_box("tip", "Cancel is safe",
               "Cancel finishes the file AYAWrus is working on, then stops. Anything already found stays in the "
               "results.", icons)
    hw.tip_box("note", "Full Scan covers one drive",
               "Full Scan checks the system drive, usually C:. Files on other drives, such as D:, are not included. "
               "Use Custom Scan to check a folder on another drive.", icons)
    hw.tip_box("tip", "Your PC stays usable",
               "AYAWrus limits how many files it checks at once based on your processor and free memory, so your "
               "other programs keep running. A Full Scan can still take a while.", icons)
    hw.tip_box("note", "What 'Scanned N files' means",
               "It counts every file AYAWrus looked at, including skipped ones. The number that matters is "
               "Threats found.", icons)

    register_resize("help_scan", _on_layout_resize)