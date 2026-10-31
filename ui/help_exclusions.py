import dearpygui.dearpygui as dpg
from ui.theme import COLORS
from ui.layout import register_resize
from ui import help_widgets as hw
from ui.help_explain import _term_table, _text_w
from ui.help_scan_results import _put_text, _put_centered
from ui.scan_layout import SECONDARY_COLORS, START_COLORS
from ui.confirm_dialog import (CONFIRM_W, CONFIRM_PAD, CONFIRM_BTN_W, CONFIRM_BTN_H, CONFIRM_BTN_GAP,
                               CONFIRM_TITLE_GAP, CONFIRM_MSG_GAP, CONFIRM_MSG_COLOR, CONFIRM_BORDER_NORMAL)
from ui.table_style import TABLE_PILL_HEIGHT, TABLE_CELL_MUTED_COLOR
from ui import exclusions as ex

# help_exclusions.py
# Help manual topic: Exclusions. Wording shown in the app (titles, status texts, toast messages, dialog text,
# empty state) and the path-cleanup rules are read from ui/exclusions.py, so they can't drift.

# ---- Switches (flip these when the matching work is done) ----
# True only if AYAWrus really has real-time protection (the subtitle of the Exclusions tab mentions it).
# False = the manual only talks about scans.
REAL_TIME_PROTECTION_EXISTS = False
# True once system/security/exclusions.py can skip a whole drive root such as D:\ (see the note for the backend partner).
# False = the manual tells people to exclude folders, not whole drives.
WHOLE_DRIVE_EXCLUSIONS_WORK = False

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
ICON_COLUMN = 36
PILL_COLUMN = 150
ICON_SIZE = 20
EXAMPLE_NAME = "Game Mods"         # made-up folder name used in messages and dialogs

# ---- Parts diagram of the Exclusions tab (made-up rows) ----
DIAG_TAG = "help_exclusions_diagram"
DIAG_TITLE_H = 30
DIAG_TITLE_SIZE = 16
DIAG_TEXT_SIZE = 12
DIAG_SMALL_SIZE = 10
DIAG_CARD_H = 104
DIAG_CARD_PAD = 12
DIAG_CARD_BORDER_ALPHA = 230
DIAG_CARD_GAP = 14                 # space between the add card and the list header
DIAG_CARD_GAP_X = 10               # space between the badge and the card's texts
DIAG_BADGE = 34
DIAG_BADGE_ICON = 18
DIAG_BADGE_ROUNDING = 9
DIAG_BADGE_ALPHA = 45
DIAG_ROW_BTN_H = 30
DIAG_SELECT_RATIO = 0.20           # button widths as shares of the card's inner width
DIAG_ADD_RATIO = 0.14
DIAG_BTN_GAP = 8
DIAG_LIST_HEAD_H = 30
DIAG_CHIP_H = 20
DIAG_CHIP_PAD_X = 10
DIAG_HEADER_H = 24
DIAG_ROW_H = 30
DIAG_BOTTOM_PAD = 10
DIAG_HEADER_BG = (40, 52, 78)      # same as HEADER_BG in ui/scan_threats.py
DIAG_ROW_ALT_BG = (255, 255, 255, 10)
DIAG_ICON_DRAW = 16
DIAG_COLUMNS = [                   # (header label, share of the width). Must add up to 1.0
    ("", 0.07), ("Folder", 0.24), ("Location", 0.27), ("Status", 0.22), ("Actions", 0.20),
]
DIAG_ROWS = [                      # (folder name, location, status)
    ("Game Mods", "D:\\Games", ex.STATUS_ACTIVE),
    ("Old Backups", "E:\\", ex.STATUS_MISSING),
    ("Share", "\\\\server", ex.STATUS_UNCHECKED),
]

# ---- Path cleanup examples (typed text is made up, the "saved as" column comes from the app's own cleanup) ----
CLEANUP_EXAMPLES = [
    ('"D:\\My Games\\"', "Quotes and the trailing backslash are removed."),
    ("D:/Games/Mods", "Slashes become backslashes."),
    ("d:", "A bare drive letter becomes the drive root."),
    ("  C:\\Tools\\  ", "Spaces around the path are removed."),
]
CLEANUP_TYPED_COLUMN = 170
CLEANUP_SAVED_COLUMN = 170
CLEANUP_FONT_KEY = "mono_small"

# ---- Dialog replica ----
DIALOG_BUTTON_PAD = 24             # extra width around a long confirm label, so it is never clipped

# ---- Empty state replica ----
EMPTY_TAG = "help_exclusions_empty"
EMPTY_H = 140
EMPTY_PAD_Y = 16
EMPTY_GAP = 8
EMPTY_TITLE_H = 26
EMPTY_SUB_H = 22
EMPTY_TITLE_SIZE = 18
EMPTY_SUB_SIZE = 14


def _radius(w):
    return max(MIN_CALLOUT_RADIUS, int(w * CALLOUT_RADIUS_RATIO))


def _pill(dl, x0, y0, x1, y1, color, text, size):
    dpg.draw_rectangle((x0, y0), (x1, y1), color=(*color[:3], PILL_BORDER_ALPHA), fill=(*color[:3], PILL_BG_ALPHA),
                       rounding=(y1 - y0) / 2, parent=dl)
    _put_centered(dl, text, x0, x1, y0, y1, size, color[:3])


def _subheading(text, fonts):
    dpg.add_spacer(height=SUBHEADING_GAP)
    t = dpg.add_text(text, color=COLORS["text_primary"])
    font = fonts.get("subheading")
    if font is not None:
        dpg.bind_item_font(t, font)
    dpg.add_spacer(height=4)


# ---------- parts diagram (redrawn to fit the pane whenever the window resizes) ----------

def _diag_height():
    return int(DIAG_TITLE_H + DIAG_CARD_H + DIAG_CARD_GAP + DIAG_LIST_HEAD_H + DIAG_HEADER_H
               + len(DIAG_ROWS) * DIAG_ROW_H + DIAG_BOTTOM_PAD)


def _column_edges(w):
    inner = w - 2 * DIAG_PAD
    edges = [DIAG_PAD]
    for _label, share in DIAG_COLUMNS:
        edges.append(edges[-1] + inner * share)
    return edges


def _draw_diagram(w):
    dl = DIAG_TAG
    dpg.delete_item(dl, children_only=True)
    r = _radius(w)
    h = _diag_height()
    clear = (0, 0, 0, 0)
    border = COLORS["border"]
    blue = COLORS["accent_blue"]
    x0, x1 = DIAG_PAD, w - DIAG_PAD

    dpg.draw_rectangle((0, 0), (w - 1, h - 1), color=border, fill=COLORS["bg_main"], rounding=ROUNDING, parent=dl)
    _put_text(dl, "Exclusions", x0, 0, DIAG_TITLE_H, DIAG_TITLE_SIZE, COLORS["text_primary"])

    # add card: badge, title, helper text, then the input row
    cy0 = DIAG_TITLE_H
    cy1 = cy0 + DIAG_CARD_H
    dpg.draw_rectangle((x0, cy0), (x1, cy1), color=(*blue, DIAG_CARD_BORDER_ALPHA), fill=COLORS["bg_card"],
                       rounding=ROUNDING, parent=dl)
    bx0, by0 = x0 + DIAG_CARD_PAD, cy0 + DIAG_CARD_PAD
    dpg.draw_rectangle((bx0, by0), (bx0 + DIAG_BADGE, by0 + DIAG_BADGE), color=clear, fill=(*blue, DIAG_BADGE_ALPHA),
                       rounding=DIAG_BADGE_ROUNDING, parent=dl)
    if dpg.does_item_exist("tex_folder"):
        off = (DIAG_BADGE - DIAG_BADGE_ICON) / 2
        dpg.draw_image("tex_folder", (bx0 + off, by0 + off), (bx0 + off + DIAG_BADGE_ICON, by0 + off + DIAG_BADGE_ICON),
                       color=blue, parent=dl)
    tx = bx0 + DIAG_BADGE + DIAG_CARD_GAP_X
    title_size = DIAG_TEXT_SIZE + 1
    _put_text(dl, ex.ADD_TITLE, tx, by0, by0 + DIAG_BADGE / 2, title_size, COLORS["text_primary"])
    _put_text(dl, ex.ADD_HELPER, tx, by0 + DIAG_BADGE / 2, by0 + DIAG_BADGE, DIAG_SMALL_SIZE + 1,
              COLORS["text_secondary"])
    title_w = _text_w(ex.ADD_TITLE, title_size)

    row_y0 = cy1 - DIAG_CARD_PAD - DIAG_ROW_BTN_H
    row_y1 = row_y0 + DIAG_ROW_BTN_H
    inner0, inner1 = x0 + DIAG_CARD_PAD, x1 - DIAG_CARD_PAD
    inner_w = inner1 - inner0
    sel_x1 = inner0 + inner_w * DIAG_SELECT_RATIO
    add_x0 = inner1 - inner_w * DIAG_ADD_RATIO
    in_x0, in_x1 = sel_x1 + DIAG_BTN_GAP, add_x0 - DIAG_BTN_GAP
    dpg.draw_rectangle((inner0, row_y0), (sel_x1, row_y1), color=clear, fill=SECONDARY_COLORS[0], rounding=4,
                       parent=dl)
    _put_centered(dl, "Select Folder", inner0, sel_x1, row_y0, row_y1, DIAG_TEXT_SIZE, COLORS["text_primary"])
    dpg.draw_rectangle((in_x0, row_y0), (in_x1, row_y1), color=border, fill=COLORS["bg_sidebar"], rounding=4,
                       parent=dl)
    _put_text(dl, ex.ADD_INPUT_HINT, in_x0 + 8, row_y0, row_y1, DIAG_SMALL_SIZE + 1, COLORS["text_secondary"])
    dpg.draw_rectangle((add_x0, row_y0), (inner1, row_y1), color=clear, fill=START_COLORS[0], rounding=4, parent=dl)
    _put_centered(dl, "Add", add_x0, inner1, row_y0, row_y1, DIAG_TEXT_SIZE, COLORS["text_primary"])

    # list header: title + counter chip
    ly0 = cy1 + DIAG_CARD_GAP
    ly_mid = ly0 + DIAG_LIST_HEAD_H / 2
    _put_text(dl, ex.LIST_TITLE, x0, ly0, ly0 + DIAG_LIST_HEAD_H, title_size, COLORS["text_primary"])
    chip_text = f"{len(DIAG_ROWS)} folders"
    chip_x0 = x0 + _text_w(ex.LIST_TITLE, title_size) + 10
    chip_x1 = chip_x0 + _text_w(chip_text, DIAG_TEXT_SIZE) + 2 * DIAG_CHIP_PAD_X
    _pill(dl, chip_x0, ly_mid - DIAG_CHIP_H / 2, chip_x1, ly_mid + DIAG_CHIP_H / 2, blue, chip_text, DIAG_TEXT_SIZE)

    # table: header, then rows
    edges = _column_edges(w)
    hy0 = ly0 + DIAG_LIST_HEAD_H
    hy1 = hy0 + DIAG_HEADER_H
    dpg.draw_rectangle((x0, hy0), (x1, hy1), color=clear, fill=DIAG_HEADER_BG, parent=dl)
    for i, (label, _share) in enumerate(DIAG_COLUMNS):
        if label:
            _put_text(dl, label, edges[i] + 4, hy0, hy1, DIAG_TEXT_SIZE, COLORS["text_secondary"])
    for n, (name, location, status) in enumerate(DIAG_ROWS):
        ry0 = hy1 + n * DIAG_ROW_H
        ry1 = ry0 + DIAG_ROW_H
        mid = (ry0 + ry1) / 2
        if n % 2 == 1:
            dpg.draw_rectangle((x0, ry0), (x1, ry1), color=clear, fill=DIAG_ROW_ALT_BG, parent=dl)
        if dpg.does_item_exist("tex_folder"):
            ix = (edges[0] + edges[1]) / 2 - DIAG_ICON_DRAW / 2
            dpg.draw_image("tex_folder", (ix, mid - DIAG_ICON_DRAW / 2), (ix + DIAG_ICON_DRAW, mid + DIAG_ICON_DRAW / 2),
                           color=ex.ICON_COLORS[status], parent=dl)
        _put_text(dl, name, edges[1] + 4, ry0, ry1, DIAG_TEXT_SIZE, COLORS["text_primary"])
        _put_text(dl, location, edges[2] + 4, ry0, ry1, DIAG_TEXT_SIZE, COLORS["text_secondary"])
        _pill(dl, edges[3] + 4, ry0 + 5, edges[4] - 8, ry1 - 5, ex.STATUS_STYLE[status], status, DIAG_SMALL_SIZE)
        dpg.draw_rectangle((edges[4] + 4, ry0 + 5), (edges[5] - 12, ry1 - 5), color=clear, fill=SECONDARY_COLORS[0],
                           rounding=4, parent=dl)
        _put_centered(dl, "Remove", edges[4] + 4, edges[5] - 12, ry0, ry1, DIAG_SMALL_SIZE + 1, COLORS["text_primary"])

    # numbered callouts last, so they sit on top
    hw.draw_callout(tx + title_w + r + 10, by0 + DIAG_BADGE / 4, 1, radius=r, parent=dl)
    hw.draw_callout(sel_x1 - 2, row_y0, 2, radius=r, parent=dl)
    hw.draw_callout((in_x0 + in_x1) / 2, row_y0, 3, radius=r, parent=dl)
    hw.draw_callout(inner1 - 2, row_y0, 4, radius=r, parent=dl)
    hw.draw_callout(chip_x1 + r + 6, ly_mid, 5, radius=r, parent=dl)
    hw.draw_callout(edges[2] - r - 4, (hy0 + hy1) / 2, 6, radius=r, parent=dl)
    hw.draw_callout(edges[4] - r - 4, (hy0 + hy1) / 2, 7, radius=r, parent=dl)
    hw.draw_callout(edges[5] - r - 4, (hy0 + hy1) / 2, 8, radius=r, parent=dl)


def _build_diagram():
    with dpg.drawlist(width=DEFAULT_WIDTH, height=_diag_height(), tag=DIAG_TAG):
        pass
    _draw_diagram(DEFAULT_WIDTH)
    hw.gap()


# ---------- empty state replica ----------

def _draw_empty(w):
    dl = EMPTY_TAG
    dpg.delete_item(dl, children_only=True)
    dpg.draw_rectangle((0, 0), (w - 1, EMPTY_H - 1), color=COLORS["border"], fill=hw.HELP_INSET_BG,
                       rounding=ROUNDING, parent=dl)
    size = ex.EMPTY_ICON_SIZE
    y = EMPTY_PAD_Y
    if dpg.does_item_exist("tex_folder"):
        dpg.draw_image("tex_folder", ((w - size) / 2, y), ((w + size) / 2, y + size), color=COLORS["accent_blue"],
                       parent=dl)
    y += size + EMPTY_GAP
    _put_centered(dl, ex.EMPTY_TITLE, 0, w, y, y + EMPTY_TITLE_H, EMPTY_TITLE_SIZE, COLORS["text_primary"])
    y += EMPTY_TITLE_H
    _put_centered(dl, ex.EMPTY_SUBTITLE, 0, w, y, y + EMPTY_SUB_H, EMPTY_SUB_SIZE, COLORS["text_secondary"])


def _build_empty():
    with dpg.drawlist(width=DEFAULT_WIDTH, height=EMPTY_H, tag=EMPTY_TAG):
        pass
    _draw_empty(DEFAULT_WIDTH)
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
    if dpg.does_item_exist(EMPTY_TAG):
        dpg.configure_item(EMPTY_TAG, width=w, height=EMPTY_H)
        _draw_empty(w)


def _on_layout_resize(content_w, content_h):
    # help_manual sizes the pane in its own resize handler, which may run AFTER this one,
    # so wait a few frames and then read the pane's final width.
    dpg.set_frame_callback(dpg.get_frame_count() + FRAME_DELAY, lambda *args: _fit_all())


# ---------- tables and replicas ----------

def _caption(text, fonts):
    t = dpg.add_text(text.upper(), color=COLORS["text_secondary"])
    font = fonts.get(CLEANUP_FONT_KEY)
    if font is not None:
        dpg.bind_item_font(t, font)


def _cleanup_table(fonts):
    mono = fonts.get(CLEANUP_FONT_KEY)
    with dpg.table(header_row=False, borders_innerH=False, borders_outerH=False,
                   borders_innerV=False, borders_outerV=False):
        dpg.add_table_column(width_fixed=True, init_width_or_weight=CLEANUP_TYPED_COLUMN)
        dpg.add_table_column(width_fixed=True, init_width_or_weight=CLEANUP_SAVED_COLUMN)
        dpg.add_table_column(width_stretch=True, init_width_or_weight=1.0)
        with dpg.table_row():
            _caption("You type", fonts)
            _caption("Saved as", fonts)
            _caption("What changed", fonts)
        for typed, what in CLEANUP_EXAMPLES:
            with dpg.table_row():
                with dpg.group():
                    t = dpg.add_text(typed, color=COLORS["accent_orange"])
                    if mono is not None:
                        dpg.bind_item_font(t, mono)
                    dpg.add_spacer(height=4)
                with dpg.group():
                    s = dpg.add_text(ex._clean_path(typed), color=COLORS["accent_green"])
                    if mono is not None:
                        dpg.bind_item_font(s, mono)
                    dpg.add_spacer(height=4)
                with dpg.group():
                    dpg.add_text(what, wrap=0, color=hw.HELP_BODY_COLOR)
                    dpg.add_spacer(height=4)
    hw.gap()


def _status_table(icons):
    themes = ex._themes()
    meanings = [
        (ex.STATUS_ACTIVE, f"{ex.TIP_ACTIVE}."),
        (ex.STATUS_MISSING, f"{ex.TIP_MISSING}. The exclusion stays saved, so if the folder comes back (for "
                            "example an external drive you plug in again) it is skipped again."),
        (ex.STATUS_UNCHECKED, f"{ex.TIP_UNCHECKED}."),
    ]
    with dpg.table(header_row=False, borders_innerH=False, borders_outerH=False,
                   borders_innerV=False, borders_outerV=False):
        dpg.add_table_column(width_fixed=True, init_width_or_weight=ICON_COLUMN)
        dpg.add_table_column(width_fixed=True, init_width_or_weight=PILL_COLUMN)
        dpg.add_table_column(width_stretch=True, init_width_or_weight=1.0)
        for status, meaning in meanings:
            with dpg.table_row():
                with dpg.group():
                    folder = icons.get("folder")
                    if folder:
                        dpg.add_image(folder, width=ICON_SIZE, height=ICON_SIZE, tint_color=ex.ICON_COLORS[status])
                with dpg.group():
                    pill = dpg.add_button(label=status, width=-1, height=TABLE_PILL_HEIGHT)
                    dpg.bind_item_theme(pill, themes[f"status_{status}"])
                    dpg.add_spacer(height=4)
                with dpg.group():
                    dpg.add_spacer(height=TEXT_TOP_OFFSET)
                    dpg.add_text(meaning, wrap=0, color=hw.HELP_BODY_COLOR)
                    dpg.add_spacer(height=4)
    hw.gap()


def _dialog_replica(title, message, confirm_label, fonts):
    """A picture of the app's confirm dialog (ui/confirm_dialog.py) in its normal, non-danger style:
    blue border and a blue confirm button."""
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
            hw.fake_button(confirm_label, START_COLORS[0], START_COLORS[3], width=confirm_w, height=CONFIRM_BTN_H)
    dpg.bind_item_theme(box, hw.child_card_theme(COLORS["bg_card"], CONFIRM_BORDER_NORMAL,
                                                 (CONFIRM_PAD, CONFIRM_PAD)))
    hw.gap()


def _message_rows():
    name = EXAMPLE_NAME
    rows = [
        (ex.MSG_ADDED.format(name=name), "accent_green", "The exclusion was saved."),
        (ex.MSG_DUPLICATE.format(name=name), "accent_blue", "It is already in the list, so nothing changed."),
        (ex.MSG_EMPTY, "accent_orange", "You pressed Add with nothing typed or picked."),
        (ex.MSG_ADD_FAILED.format(name=name), "accent_red",
         "It couldn't be saved. The terminal window has the technical reason."),
        (ex.MSG_REMOVED.format(name=name), "accent_green", "The exclusion was removed."),
        (ex.MSG_REMOVE_FAILED.format(name=name), "accent_red",
         "It couldn't be removed. The terminal window has the technical reason."),
    ]
    if ex.BLOCK_MISSING_PATH:
        rows.insert(3, (ex.MSG_NOT_FOUND, "accent_orange", "The path isn't on your disk, so it wasn't added."))
        rows.insert(4, (ex.MSG_NOT_FOLDER, "accent_orange", "The path points to a file, so it wasn't added."))
    return rows


# ---------- the topic ----------

def build_topic(fonts, icons):
    hw.page_heading("Exclusions", "Places AYAWrus is told to skip.", fonts)
    intro = ("Exclusions are folders, and sometimes single files, that AYAWrus leaves alone. Everything inside an "
             "excluded folder is skipped by scans. It is the first thing a scan checks, so excluded items are never "
             "opened or analyzed. Use it for software you trust that keeps getting flagged, such as a game or a "
             "project you are developing.")
    if REAL_TIME_PROTECTION_EXISTS:
        intro += " The same list applies to real-time protection."
    hw.paragraph(intro)

    hw.section_heading("What you're looking at", fonts)
    hw.paragraph("Here is the tab in simplified form (made-up rows). The numbers match the list underneath.")
    _build_diagram()
    hw.numbered_row(1, "Add card", "Where you add a new exclusion.")
    hw.numbered_row(2, "Select Folder", "Opens a folder picker. It fills in the path box, but doesn't save anything yet.")
    hw.numbered_row(3, "Path box", "Type or paste a path. Pressing Enter adds it, just like the Add button.")
    hw.numbered_row(4, "Add", "Saves the path as an exclusion.")
    hw.numbered_row(5, "Counter", "How many exclusions you have.")
    hw.numbered_row(6, "Folder and Location", "The folder's name, and the folder it sits in. If the exclusion is a whole "
                                             f"drive, the location says '{ex.LOCATION_ROOT_LABEL}'. Hover over a name to "
                                             "see the full path.")
    hw.numbered_row(7, "Status", "Whether the folder is still on your disk (explained below).")
    hw.numbered_row(8, "Remove", "Stops skipping the folder. You are asked to confirm first.")

    hw.section_heading("Add an exclusion", fonts)
    hw.numbered_row(1, "Choose a folder", "Press Select Folder and pick it, or type or paste its path into the box.")
    hw.numbered_row(2, "Press Add", "Or press Enter. AYAWrus tidies the path first (see below), then saves it.")
    hw.numbered_row(3, "Check the list", "A message confirms it, the folder appears under Current Exclusions and the "
                                         "counter goes up.")
    _subheading("How the path is tidied", fonts)
    hw.paragraph("Before saving, AYAWrus cleans up what you typed, so a path copied straight from Explorer works. "
                 "The typed examples below are made up.")
    _cleanup_table(fonts)
    hw.paragraph("Adding a folder that is already in the list is refused. Capital letters and a trailing slash don't "
                 "count as a difference.")
    if ex.BLOCK_MISSING_PATH:
        hw.paragraph("AYAWrus refuses a path that isn't on your disk.")
    else:
        hw.paragraph("AYAWrus doesn't check that the folder exists when you add it. A folder that isn't on your disk "
                     "is still saved, and shows NOT FOUND.")

    hw.section_heading("Status", fonts)
    _status_table(icons)
    hw.paragraph("The statuses are checked again every time you open the tab, and the folder icon takes the same color.")

    hw.section_heading("Remove an exclusion", fonts)
    hw.paragraph("Remove asks first (the name is an example):")
    _dialog_replica(ex.CONFIRM_REMOVE_TITLE, ex.CONFIRM_REMOVE_MESSAGE.format(name=EXAMPLE_NAME),
                    ex.CONFIRM_REMOVE_LABEL, fonts)
    hw.paragraph("After you confirm, the row disappears and AYAWrus scans that folder again from now on. It doesn't "
                 "delete anything on your disk.")

    hw.section_heading("Messages you may see", fonts)
    hw.paragraph("After Add or Remove, a short message tells you how it went.")
    _term_table(_message_rows())

    hw.section_heading("When the list is empty", fonts)
    _build_empty()
    hw.paragraph("Until you add something, this message fills the list.")

    hw.section_heading("Good to know", fonts)
    if not WHOLE_DRIVE_EXCLUSIONS_WORK:
        hw.tip_box("note", "Exclude folders, not whole drives",
                   "Adding a whole drive, such as D:\\, doesn't skip anything yet. Add the folders inside it "
                   "instead.", icons)
    hw.tip_box("note", "Only exclude what you trust",
               "AYAWrus never checks an excluded folder, so malware hiding inside it would go unnoticed. Exclude "
               "something only when you are sure it is safe.", icons)
    hw.tip_box("tip", "Restore & Trust adds files here",
               "When you restore a quarantined file with Restore & Trust, that file is added to this list. "
               "Remove it here if you want it scanned again.", icons)
    hw.tip_box("tip", "Missing folders stay saved",
               "An exclusion marked NOT FOUND stays in the list until you remove it. Remove the ones you no longer "
               "need.", icons)
    hw.tip_box("tip", "The list is remembered",
               "Your exclusions are saved, so they are still there the next time you open AYAWrus.", icons)

    register_resize("help_exclusions", _on_layout_resize)