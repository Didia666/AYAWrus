import dearpygui.dearpygui as dpg
from ui.theme import COLORS
from ui.layout import register_resize
from ui import help_widgets as hw
from ui.help_explain import _term_table, _card, _text_w
from ui.help_scan_results import _chip_table, _put_text, _put_centered
from ui.scan_layout import SECONDARY_COLORS, CANCEL_COLORS
from ui.confirm_dialog import (CONFIRM_W, CONFIRM_PAD, CONFIRM_BTN_W, CONFIRM_BTN_H, CONFIRM_BTN_GAP,
                               CONFIRM_TITLE_GAP, CONFIRM_MSG_GAP, CONFIRM_MSG_COLOR, CONFIRM_BORDER_DANGER)
from ui.quarantine import (RISK_SEVERE_MIN, RISK_HIGH_MIN, RISK_MEDIUM_MIN, RISK_MISSING_LABEL, TIP_SCORE,
                           CONFIRM_DELETE_TITLE, CONFIRM_DELETE_MESSAGE, CONFIRM_DELETE_LABEL,
                           MSG_RESTORED, MSG_DELETED, MSG_RESTORE_FAILED, MSG_DELETE_FAILED,
                           EMPTY_TITLE, EMPTY_SUBTITLE, EMPTY_ICON_SIZE)

# help_quarantine.py
# Help manual topic: Quarantine. Wording shown in the app (risk cut-offs, toasts, delete dialog, empty state)
# is imported from ui/quarantine.py, so it can't drift. The Restore dialog text below is copied from
# _ask_restore() in that file, so update it here if that text changes.

# ---- Quarantine topic constants (tune here) ----
SIDE_CHROME = 64                   # pane padding + scrollbar + breathing room, subtracted from the pane width
FRAME_DELAY = 3                    # frames to wait after a resize so help_manual sizes the pane first
DRAW_MIN_WIDTH = 400
DRAW_MAX_WIDTH = 720
EXAMPLE_NAME = "example.exe"       # made-up file name used in the examples

# ---- Parts diagram of the Quarantine tab ----
DIAG_TAG = "help_quarantine_diagram"
DIAG_DEFAULT_WIDTH = 540
DIAG_PAD = 8
DIAG_TITLE_H = 36                  # the title row (title + counter pill)
DIAG_TITLE_SIZE = 16
DIAG_CHIP_H = 22
DIAG_CHIP_GAP = 10
DIAG_CHIP_PAD_X = 10
DIAG_CALLOUT_GAP = 10              # space around the numbered circles above the header
DIAG_CALLOUT_RADIUS_RATIO = 0.021
DIAG_MIN_CALLOUT_RADIUS = 9
DIAG_HEADER_H = 26
DIAG_ROW_H = 32
DIAG_BOTTOM_PAD = 10
DIAG_ROUNDING = 6
DIAG_TEXT_SIZE = 12
DIAG_BUTTON_TEXT_SIZE = 10
DIAG_PILL_TEXT_SIZE = 10
DIAG_CELL_PAD = 4
DIAG_LOCK_SIZE = 16
DIAG_HEADER_BG = (40, 52, 78)      # same as HEADER_BG in ui/scan_threats.py
DIAG_ROW_ALT_BG = (255, 255, 255, 10)
DIAG_PILL_BG_ALPHA = 40
DIAG_PILL_BORDER_ALPHA = 160
DIAG_BUTTON_GAP = 4
DIAG_COUNT_TEXT = "3 items"
DIAG_COLUMNS = [                   # (header label, share of the width). Must add up to 1.0
    ("", 0.06), ("Threat Name", 0.18), ("Original Location", 0.21),
    ("Date Detected", 0.21), ("Risk", 0.14), ("Actions", 0.20),
]
# (file name, location, date, risk label, pill color, copy missing?). All made up.
DIAG_ROWS = [
    ("setup.exe", "D:\\Downloads\\...", "10-18 09:42", "MEDIUM", "accent_orange", False),
    ("patch.dll", "D:\\Games\\...", "10-18 08:42", "HIGH", "accent_red", False),
    ("tool.exe", "C:\\Temp\\...", "10-17 20:57", "SEVERE", "accent_red", True),
]

# ---- Dialog replicas ----
RESTORE_DIALOG_TITLE = "Restore Quarantined File"
RESTORE_DIALOG_MESSAGE = (
    "Are you sure you want to restore '{name}'?\n\n"
    "AYAWrus detected this file as potentially malicious.\n"
    "Restoring it may expose your device to threats.\n\n"
    "Choosing Restore & Trust also excludes this file from future scans.\n"
    "Only continue if you have independently verified that it is safe."
)
RESTORE_CONFIRM_LABEL = "Restore & Trust (Exclude)"
DIALOG_BUTTON_PAD = 24             # extra width around a long confirm label, so it is never clipped

# ---- Empty state replica (a drawing, so it can be centered at any width) ----
EMPTY_TAG = "help_quarantine_empty"
EMPTY_DRAW_H = 140
EMPTY_PAD_Y = 16
EMPTY_GAP = 8
EMPTY_TITLE_H = 26
EMPTY_SUB_H = 22
EMPTY_TITLE_SIZE = 18
EMPTY_SUB_SIZE = 14
EMPTY_ROUNDING = 6


def _percent(value):
    return int(round(value * 100))


# ---------- parts diagram (redrawn to fit the pane whenever the window resizes) ----------

def _diag_metrics(w):
    r = max(DIAG_MIN_CALLOUT_RADIUS, int(w * DIAG_CALLOUT_RADIUS_RATIO))
    top = DIAG_TITLE_H + 2 * r + DIAG_CALLOUT_GAP
    h = top + DIAG_HEADER_H + len(DIAG_ROWS) * DIAG_ROW_H + DIAG_BOTTOM_PAD
    return r, top, int(h)


def _column_edges(w):
    inner = w - 2 * DIAG_PAD
    edges = [DIAG_PAD]
    for _label, share in DIAG_COLUMNS:
        edges.append(edges[-1] + inner * share)
    return edges


def _draw_diagram(w):
    dl = DIAG_TAG
    dpg.delete_item(dl, children_only=True)
    r, top, h = _diag_metrics(w)
    edges = _column_edges(w)
    clear = (0, 0, 0, 0)
    border = COLORS["border"]
    blue = COLORS["accent_blue"]

    dpg.draw_rectangle((0, 0), (w - 1, h - 1), color=border, fill=COLORS["bg_card"],
                       rounding=DIAG_ROUNDING, parent=dl)

    # title + counter pill
    dpg.draw_text((DIAG_PAD, (DIAG_TITLE_H - DIAG_TITLE_SIZE) / 2), "Quarantine", color=COLORS["text_primary"],
                  size=DIAG_TITLE_SIZE, parent=dl)
    chip_x0 = DIAG_PAD + _text_w("Quarantine", DIAG_TITLE_SIZE) + DIAG_CHIP_GAP
    chip_x1 = chip_x0 + _text_w(DIAG_COUNT_TEXT, DIAG_TEXT_SIZE) + 2 * DIAG_CHIP_PAD_X
    chip_y0 = (DIAG_TITLE_H - DIAG_CHIP_H) / 2
    chip_y1 = chip_y0 + DIAG_CHIP_H
    dpg.draw_rectangle((chip_x0, chip_y0), (chip_x1, chip_y1), color=(*blue, DIAG_PILL_BORDER_ALPHA),
                       fill=(*blue, DIAG_PILL_BG_ALPHA), rounding=DIAG_CHIP_H / 2, parent=dl)
    _put_centered(dl, DIAG_COUNT_TEXT, chip_x0, chip_x1, chip_y0, chip_y1, DIAG_TEXT_SIZE, blue)

    # header
    dpg.draw_rectangle((DIAG_PAD, top), (w - DIAG_PAD, top + DIAG_HEADER_H), color=clear,
                       fill=DIAG_HEADER_BG, parent=dl)
    for i, (label, _share) in enumerate(DIAG_COLUMNS):
        if label:
            _put_text(dl, label, edges[i] + DIAG_CELL_PAD, top, top + DIAG_HEADER_H, DIAG_TEXT_SIZE,
                      COLORS["text_secondary"])

    # rows
    for n, (name, location, date, risk, color_name, missing) in enumerate(DIAG_ROWS):
        y0 = top + DIAG_HEADER_H + n * DIAG_ROW_H
        y1 = y0 + DIAG_ROW_H
        mid = (y0 + y1) / 2
        color = COLORS[color_name]
        if n % 2 == 1:
            dpg.draw_rectangle((DIAG_PAD, y0), (w - DIAG_PAD, y1), color=clear, fill=DIAG_ROW_ALT_BG, parent=dl)
        if dpg.does_item_exist("tex_lock"):
            lx = (edges[0] + edges[1]) / 2 - DIAG_LOCK_SIZE / 2
            dpg.draw_image("tex_lock", (lx, mid - DIAG_LOCK_SIZE / 2), (lx + DIAG_LOCK_SIZE, mid + DIAG_LOCK_SIZE / 2),
                           color=COLORS["accent_orange"] if missing else COLORS["accent_red"], parent=dl)
        _put_text(dl, name, edges[1] + DIAG_CELL_PAD, y0, y1, DIAG_TEXT_SIZE, COLORS["text_primary"])
        _put_text(dl, location, edges[2] + DIAG_CELL_PAD, y0, y1, DIAG_TEXT_SIZE, COLORS["text_secondary"])
        _put_text(dl, date, edges[3] + DIAG_CELL_PAD, y0, y1, DIAG_TEXT_SIZE, COLORS["text_secondary"])
        px0, px1 = edges[4] + DIAG_CELL_PAD, edges[5] - DIAG_CELL_PAD
        dpg.draw_rectangle((px0, y0 + 7), (px1, y1 - 7), color=(*color, DIAG_PILL_BORDER_ALPHA),
                           fill=(*color, DIAG_PILL_BG_ALPHA), rounding=8, parent=dl)
        _put_centered(dl, risk, px0, px1, y0, y1, DIAG_PILL_TEXT_SIZE, color)
        ax0, ax1 = edges[5] + DIAG_CELL_PAD, edges[6] - DIAG_CELL_PAD
        bw = (ax1 - ax0 - DIAG_BUTTON_GAP) / 2
        dpg.draw_rectangle((ax0, y0 + 6), (ax0 + bw, y1 - 6), color=clear, fill=SECONDARY_COLORS[0],
                           rounding=4, parent=dl)
        _put_centered(dl, "Restore", ax0, ax0 + bw, y0, y1, DIAG_BUTTON_TEXT_SIZE, COLORS["text_primary"])
        dpg.draw_rectangle((ax0 + bw + DIAG_BUTTON_GAP, y0 + 6), (ax1, y1 - 6), color=clear,
                           fill=CANCEL_COLORS[0], rounding=4, parent=dl)
        _put_centered(dl, "Delete", ax0 + bw + DIAG_BUTTON_GAP, ax1, y0, y1, DIAG_BUTTON_TEXT_SIZE,
                      COLORS["text_primary"])

    # numbered callouts last, so they sit on top
    cy = DIAG_TITLE_H + DIAG_CALLOUT_GAP / 2 + r
    for i in range(len(DIAG_COLUMNS)):
        hw.draw_callout((edges[i] + edges[i + 1]) / 2, cy, i + 1, radius=r, parent=dl)
    hw.draw_callout(chip_x1 + r + 8, DIAG_TITLE_H / 2, len(DIAG_COLUMNS) + 1, radius=r, parent=dl)


def _build_diagram():
    w = DIAG_DEFAULT_WIDTH
    _r, _top, h = _diag_metrics(w)
    with dpg.drawlist(width=w, height=h, tag=DIAG_TAG):
        pass
    _draw_diagram(w)
    hw.gap()


# ---------- empty state replica ----------

def _draw_empty(w):
    dl = EMPTY_TAG
    dpg.delete_item(dl, children_only=True)
    dpg.draw_rectangle((0, 0), (w - 1, EMPTY_DRAW_H - 1), color=COLORS["border"], fill=hw.HELP_INSET_BG,
                       rounding=EMPTY_ROUNDING, parent=dl)
    y = EMPTY_PAD_Y
    if dpg.does_item_exist("tex_shield_check"):
        dpg.draw_image("tex_shield_check", ((w - EMPTY_ICON_SIZE) / 2, y), ((w + EMPTY_ICON_SIZE) / 2, y + EMPTY_ICON_SIZE),
                       color=COLORS["accent_green"], parent=dl)
    y += EMPTY_ICON_SIZE + EMPTY_GAP
    _put_centered(dl, EMPTY_TITLE, 0, w, y, y + EMPTY_TITLE_H, EMPTY_TITLE_SIZE, COLORS["text_primary"])
    y += EMPTY_TITLE_H
    _put_centered(dl, EMPTY_SUBTITLE, 0, w, y, y + EMPTY_SUB_H, EMPTY_SUB_SIZE, COLORS["text_secondary"])


def _build_empty():
    with dpg.drawlist(width=DIAG_DEFAULT_WIDTH, height=EMPTY_DRAW_H, tag=EMPTY_TAG):
        pass
    _draw_empty(DIAG_DEFAULT_WIDTH)
    hw.gap()


# ---------- resize ----------

def _fit_all():
    if not dpg.does_item_exist(hw.HELP_CONTENT_PANE_TAG):
        return
    pane_w = dpg.get_item_width(hw.HELP_CONTENT_PANE_TAG)
    w = int(max(DRAW_MIN_WIDTH, min(DRAW_MAX_WIDTH, pane_w - SIDE_CHROME)))
    if dpg.does_item_exist(DIAG_TAG):
        _r, _top, h = _diag_metrics(w)
        dpg.configure_item(DIAG_TAG, width=w, height=h)
        _draw_diagram(w)
    if dpg.does_item_exist(EMPTY_TAG):
        dpg.configure_item(EMPTY_TAG, width=w, height=EMPTY_DRAW_H)
        _draw_empty(w)


def _on_layout_resize(content_w, content_h):
    # help_manual sizes the pane in its own resize handler, which may run AFTER this one,
    # so wait a few frames and then read the pane's final width.
    dpg.set_frame_callback(dpg.get_frame_count() + FRAME_DELAY, lambda *args: _fit_all())


# ---------- dialog replica ----------

def _dialog_replica(title, message, confirm_label, fonts):
    """A picture of the app's confirm dialog (ui/confirm_dialog.py): title, message, then Cancel and a red confirm button on the right."""
    inner_w = CONFIRM_W - 2 * CONFIRM_PAD
    confirm_w = max(CONFIRM_BTN_W, int(hw._measure(confirm_label)[0] + DIALOG_BUTTON_PAD))
    buttons_w = CONFIRM_BTN_W + CONFIRM_BTN_GAP + confirm_w
    with dpg.child_window(width=CONFIRM_W, auto_resize_y=True, border=True) as box:
        t = dpg.add_text(title, color=COLORS["text_primary"])
        font = fonts.get("subheading")
        if font is not None:
            dpg.bind_item_font(t, font)
        dpg.add_spacer(height=CONFIRM_TITLE_GAP)
        dpg.add_text(message, wrap=inner_w, color=CONFIRM_MSG_COLOR)
        dpg.add_spacer(height=CONFIRM_MSG_GAP)
        with dpg.group(horizontal=True, indent=max(0, inner_w - buttons_w)):
            hw.fake_button("Cancel", SECONDARY_COLORS[0], SECONDARY_COLORS[3], width=CONFIRM_BTN_W,
                           height=CONFIRM_BTN_H)
            hw.fake_button(confirm_label, CANCEL_COLORS[0], CANCEL_COLORS[3], width=confirm_w,
                           height=CONFIRM_BTN_H)
    dpg.bind_item_theme(box, hw.child_card_theme(COLORS["bg_card"], CONFIRM_BORDER_DANGER,
                                                 (CONFIRM_PAD, CONFIRM_PAD)))
    hw.gap()


# ---------- the topic ----------

def build_topic(fonts, icons):
    sev, high, med = _percent(RISK_SEVERE_MIN), _percent(RISK_HIGH_MIN), _percent(RISK_MEDIUM_MIN)

    hw.page_heading("Quarantine", "A locked box for files AYAWrus flagged.", fonts)
    hw.paragraph("Quarantine holds files AYAWrus considers harmful, so they can't run or touch the rest of your PC. "
                 "Nothing here is deleted until you choose to delete it, and you can bring a file back if you are "
                 "sure it is safe.")

    hw.section_heading("How files get here", fonts)
    hw.paragraph("Files judged MALICIOUS are moved here automatically during a scan. Suspicious files arrive when you "
                 "tick them in Detected Threats and press Quarantine Selected.")
    hw.paragraph("AYAWrus copies the file into its own quarantine folder under a scrambled name, checks that the copy "
                 "is identical, locks it read-only and only then removes the original.")

    hw.section_heading("What you're looking at", fonts)
    hw.paragraph("Here is the tab in simplified form. The rows are made up, and the third one shows what a missing "
                 "file looks like. The numbers match the list underneath.")
    _build_diagram()
    hw.numbered_row(1, "Lock", "A red lock means the file is safely held. An orange lock means AYAWrus couldn't find "
                               "the quarantined copy when the list loaded. Hover over the name for details.")
    hw.numbered_row(2, "Threat Name", "The file's original name. Hover over it to see more.")
    hw.numbered_row(3, "Original Location", "Where the file was before it was quarantined. Long paths are shortened "
                                            "with ... and the full path shows when you hover. On narrow windows this "
                                            "column is hidden and the path moves into the name's tooltip.")
    hw.numbered_row(4, "Date Detected", "When the file was flagged and quarantined.")
    hw.numbered_row(5, "Risk", "How worrying the file looks (explained below).")
    hw.numbered_row(6, "Actions", "Restore brings the file back. Delete removes it for good. Hover over each button "
                                  "to see what it does.")
    hw.numbered_row(7, "Counter", "The pill next to the title shows how many items are in quarantine.")

    hw.section_heading("Risk levels", fonts)
    _chip_table([
        ("SEVERE", "accent_red", f"{sev}% or higher."),
        ("HIGH", "accent_red", f"{high}% up to just under {sev}%."),
        ("MEDIUM", "accent_orange", f"{med}% up to just under {high}%."),
        ("LOW", "accent_green", f"Below {med}%."),
        (RISK_MISSING_LABEL, "text_secondary",
         "No score was recorded for this file, so AYAWrus can't rate it. This is common for known-malware matches. "
         "Missing evidence is never shown as HIGH."),
    ], fonts)
    hw.paragraph("The percentage is the AI's estimate that the file is malware. Hover over a pill to see it, for "
                 f"example '{TIP_SCORE.format(score=0.712)}'. The Dashboard's High-Risk Items card counts the HIGH and "
                 "SEVERE items shown here.")

    hw.section_heading("Restore a file", fonts)
    hw.paragraph("Restore puts a file back where it came from. Because AYAWrus flagged it, you are asked to confirm "
                 "first. This is what the warning says (the name is an example):")
    _dialog_replica(RESTORE_DIALOG_TITLE, RESTORE_DIALOG_MESSAGE.format(name=EXAMPLE_NAME), RESTORE_CONFIRM_LABEL,
                    fonts)
    hw.numbered_row(1, "Press Restore", "Use the Restore button on the file's row.")
    hw.numbered_row(2, "Confirm", f"Read the warning, then choose {RESTORE_CONFIRM_LABEL}. You can back out instead.")
    hw.numbered_row(3, "AYAWrus checks the file",
                    "Before copying it back, AYAWrus verifies that the quarantined copy hasn't changed (its SHA-256 "
                    "fingerprint). It refuses to overwrite a file that is already in the original spot, and it can't "
                    "restore into a folder that no longer exists.")
    hw.numbered_row(4, "Done", "The file is back in its original folder, the row leaves the list, and the Dashboard "
                               "and History update.")
    hw.tip_box("note", "Restore means trust",
               "Restore & Trust adds the file to your Exclusions, so future scans skip it. Only restore files you "
               "have independently checked. A restored file comes back read-only. You can manage the exclusions list "
               "in the Exclusions tab.", icons)

    hw.section_heading("Delete a file", fonts)
    hw.paragraph("Delete removes the quarantined copy for good. There is no undo, so you are asked first (the name is "
                 "an example):")
    _dialog_replica(CONFIRM_DELETE_TITLE, CONFIRM_DELETE_MESSAGE.format(name=EXAMPLE_NAME), CONFIRM_DELETE_LABEL,
                    fonts)
    hw.paragraph("AYAWrus checks that the quarantined copy is intact before it deletes it. Afterwards the row "
                 "disappears, and the Dashboard and History update.")

    hw.section_heading("Messages you may see", fonts)
    hw.paragraph("After Restore or Delete, a short message tells you how it went.")
    _term_table([
        (MSG_RESTORED.format(name=EXAMPLE_NAME), "accent_green", "The file is back in its original folder."),
        (MSG_DELETED.format(name=EXAMPLE_NAME), "accent_green", "The quarantined copy was permanently removed."),
        (f"{EXAMPLE_NAME}: RESTORE BLOCKED: Destination already exists", "accent_blue",
         "AYAWrus refused for safety. The text after the name says why: a file is already in the original spot, the "
         "original folder is missing, or the quarantined copy no longer matches its fingerprint."),
        (MSG_RESTORE_FAILED.format(name=EXAMPLE_NAME), "accent_red",
         "The restore didn't work. The terminal window has the technical reason."),
        (MSG_DELETE_FAILED.format(name=EXAMPLE_NAME), "accent_red",
         "The delete didn't work, for example because the quarantined copy is missing or has changed."),
    ])

    hw.section_heading("When it's empty", fonts)
    _build_empty()
    hw.paragraph("Until something is quarantined, this message fills the tab.")

    hw.section_heading("Good to know", fonts)
    hw.tip_box("tip", "Hover for details",
               "Hovering over a name, location, risk pill or button shows more information, including the exact "
               "confidence score.", icons)
    hw.tip_box("tip", "Always up to date",
               "The list refreshes every time you open the tab and after every Restore or Delete.", icons)
    hw.tip_box("tip", "Nothing here can run",
               "Quarantined files are stored under scrambled names in a locked folder, so nothing in this list can "
               "open or run by accident.", icons)

    register_resize("help_quarantine", _on_layout_resize)