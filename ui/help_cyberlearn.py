import dearpygui.dearpygui as dpg
from ui.theme import COLORS
from ui.layout import register_resize
from ui import help_widgets as hw
from ui.help_explain import _term_table, _card, _text_w
from ui.help_scan_results import _chip_table, _put_text, _put_centered
from ui.help_settings import CYBERLEARN_PICKS_UP_NEW_KEY_WITHOUT_RESTART
from ui.scan_layout import SECONDARY_COLORS, START_COLORS

try:
    from ui.cyberlearn_assistant_dpg import (CHAT_ROLE_STYLES, CHAT_SUGGEST_COUNT, CHAT_MAX_MESSAGES, CHAT_LOCKED,
                                             CHAT_COLOR_BORDER_GLOW)
except Exception:                  # the chat file couldn't be imported: fall back to the values it has today
    CHAT_ROLE_STYLES = {"user": ("YOU", "accent_blue"), "assistant": ("ASSISTANT", "accent_green"),
                        "system": ("SYSTEM", "text_secondary")}
    CHAT_SUGGEST_COUNT = 6
    CHAT_MAX_MESSAGES = 30
    CHAT_LOCKED = True
    CHAT_COLOR_BORDER_GLOW = (56, 130, 246, 90)

# help_cyberlearn.py
# Help manual topic: CyberLearn (the chat panel behind the round help bubble). Written from
# ui/cyberlearn_assistant_dpg.py. The mirrors below copy text that lives inline in that file.

# ---- Mirrors of text and numbers in ui/cyberlearn_assistant_dpg.py (update here if they change) ----
KB_TOPIC_COUNT = 32                # the number after "KB Topics:" in the chat footer
PANEL_TITLE = "CyberLearn Assistant"
PILL_LOCAL = "LOCAL MODE"
PILL_ONLINE = "AI ONLINE"
SUBTITLE_LOCAL = "No API key found. Answering from the local knowledge base."
INPUT_HINT = "Ask anything, e.g. 'What is a Trojan?'"
INPUT_HINT_COLOR = (100, 116, 139)
SUGGESTED_EXAMPLES = [             # the first questions of the knowledge base
    "What is a Trojan and how does it differ from a virus?",
    "What is ransomware and how does it work?",
    "What is a computer worm?",
]
EXAMPLE_TIME = "21:34"
EXAMPLE_KEYWORD = "worm"
EXAMPLE_ANSWER = "A worm is self-replicating malware that spreads across networks without user interaction ..."
EXAMPLE_RELATED = ("Related topics:\n\u2022 What is a Trojan and how does it differ from a virus?\n"
                   "\u2022 What are signs that a system is infected with malware?")
MESSAGE_GAP = 10

# ---- Shared sizes ----
DEFAULT_WIDTH = 540
DRAW_MIN_WIDTH = 480
DRAW_MAX_WIDTH = 720
SIDE_CHROME = 64                   # pane padding + scrollbar + breathing room, subtracted from the pane width
FRAME_DELAY = 3                    # frames to wait after a resize so help_manual sizes the pane first
ROUNDING = 8
CALLOUT_RADIUS_RATIO = 0.021
MIN_CALLOUT_RADIUS = 9
PILL_BG_ALPHA = 40
PILL_BORDER_ALPHA = 160
SUBHEADING_GAP = 14
BUBBLE_SIZE = 60
BUBBLE_ICON = 30
BUBBLE_ROUNDING = 14

# ---- Chat panel diagram ----
PANEL_TAG = "help_cyberlearn_panel"
PANEL_TOP = 26                     # room above the panel for the callouts that sit on its top edge
PANEL_PAD = 8
PANEL_ROUNDING = 14
PANEL_INNER_PAD = 14
P_HEADER_TOP = 12                  # vertical layout, measured from the panel's top edge
P_HEADER_H = 26
P_SUBTITLE_TOP = 46
P_SUBTITLE_H = 16
P_SEP_Y = 68
P_INPUT_TOP = 76
P_INPUT_H = 26
P_CONV_LABEL_TOP = 110
P_CONV_TOP = 124
P_CONV_H = 136
P_SUG_LABEL_TOP = 268
P_SUG_TOP = 282
P_SUG_H = 92
P_FOOTER_TOP = 382
P_FOOTER_H = 16
P_BOTTOM_PAD = 14
P_ICON = 18
P_TITLE_SIZE = 13
P_SMALL_SIZE = 10
P_PILL_SIZE = 9
P_PILL_H = 20
P_PILL_PAD = 24
P_CLOSE_SIZE = 22
P_SEND_W = 56
P_NEWCHAT_W = 72
P_BTN_GAP = 6
P_CHIP_H = 22
P_CHIP_GAP = 6
P_CHIP_FILL = (30, 40, 62)
P_BAR_H = 5
P_BAR_GAP = 9
P_MESSAGE_PAD = 10

# ---- Switches ----
# (CYBERLEARN_PICKS_UP_NEW_KEY_WITHOUT_RESTART lives in ui/help_settings.py)


def _percent_text(value):
    return str(int(value))


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


# ---------- help bubble replica ----------

def _build_bubble_replica():
    with dpg.drawlist(width=BUBBLE_SIZE, height=BUBBLE_SIZE) as dl:
        dpg.draw_rectangle((0, 0), (BUBBLE_SIZE - 1, BUBBLE_SIZE - 1), color=(0, 0, 0, 0), fill=COLORS["accent_blue"],
                           rounding=BUBBLE_ROUNDING, parent=dl)
        if dpg.does_item_exist("tex_help_chat"):
            off = (BUBBLE_SIZE - BUBBLE_ICON) / 2
            dpg.draw_image("tex_help_chat", (off, off), (off + BUBBLE_ICON, off + BUBBLE_ICON),
                           color=(255, 255, 255), parent=dl)


# ---------- chat panel diagram (redrawn to fit the pane whenever the window resizes) ----------

def _panel_body_h():
    return P_FOOTER_TOP + P_FOOTER_H + P_BOTTOM_PAD


def _panel_height():
    return int(PANEL_TOP + _panel_body_h() + PANEL_PAD)


def _draw_panel(w):
    dl = PANEL_TAG
    dpg.delete_item(dl, children_only=True)
    r = max(MIN_CALLOUT_RADIUS, int(w * CALLOUT_RADIUS_RATIO))
    clear = (0, 0, 0, 0)
    border = COLORS["border"]
    blue, green, orange, red = (COLORS["accent_blue"], COLORS["accent_green"], COLORS["accent_orange"],
                                COLORS["accent_red"])
    primary, secondary = COLORS["text_primary"], COLORS["text_secondary"]

    dpg.draw_rectangle((0, 0), (w - 1, _panel_height() - 1), color=border, fill=COLORS["bg_main"],
                       rounding=ROUNDING, parent=dl)
    x0, x1 = PANEL_PAD, w - PANEL_PAD
    y0 = PANEL_TOP
    dpg.draw_rectangle((x0, y0), (x1, y0 + _panel_body_h()), color=CHAT_COLOR_BORDER_GLOW, fill=COLORS["bg_card"],
                       rounding=PANEL_ROUNDING, parent=dl)
    ix0, ix1 = x0 + PANEL_INNER_PAD, x1 - PANEL_INNER_PAD

    # header: icon + title on the left, mode pill + X on the right
    hy0 = y0 + P_HEADER_TOP
    hy1 = hy0 + P_HEADER_H
    hmid = (hy0 + hy1) / 2
    if dpg.does_item_exist("tex_help_chat"):
        dpg.draw_image("tex_help_chat", (ix0, hmid - P_ICON / 2), (ix0 + P_ICON, hmid + P_ICON / 2), color=blue,
                       parent=dl)
    title_x = ix0 + P_ICON + 8
    _put_text(dl, PANEL_TITLE, title_x, hy0, hy1, P_TITLE_SIZE, primary)
    title_w = _text_w(PANEL_TITLE, P_TITLE_SIZE)
    close_x1 = ix1
    close_x0 = close_x1 - P_CLOSE_SIZE
    dpg.draw_rectangle((close_x0, hmid - P_CLOSE_SIZE / 2), (close_x1, hmid + P_CLOSE_SIZE / 2), color=clear,
                       fill=(*red, 70), rounding=6, parent=dl)
    _put_centered(dl, "X", close_x0, close_x1, hmid - P_CLOSE_SIZE / 2, hmid + P_CLOSE_SIZE / 2, P_SMALL_SIZE + 2,
                  primary)
    pill_x1 = close_x0 - 8
    pill_x0 = pill_x1 - (_text_w(PILL_LOCAL, P_PILL_SIZE) + P_PILL_PAD)
    _pill(dl, pill_x0, hmid - P_PILL_H / 2, pill_x1, hmid + P_PILL_H / 2, orange, PILL_LOCAL, P_PILL_SIZE)

    # subtitle + separator
    sub_y0 = y0 + P_SUBTITLE_TOP
    sub_y1 = sub_y0 + P_SUBTITLE_H
    _put_text(dl, SUBTITLE_LOCAL, ix0, sub_y0, sub_y1, P_SMALL_SIZE, secondary)
    dpg.draw_line((ix0, y0 + P_SEP_Y), (ix1, y0 + P_SEP_Y), color=border, thickness=1, parent=dl)

    # input row: question box, Send, New Chat
    in_y0 = y0 + P_INPUT_TOP
    in_y1 = in_y0 + P_INPUT_H
    new_x1 = ix1
    new_x0 = new_x1 - P_NEWCHAT_W
    send_x1 = new_x0 - P_BTN_GAP
    send_x0 = send_x1 - P_SEND_W
    box_x1 = send_x0 - P_BTN_GAP
    dpg.draw_rectangle((ix0, in_y0), (box_x1, in_y1), color=border, fill=COLORS["bg_sidebar"], rounding=6, parent=dl)
    _put_text(dl, INPUT_HINT, ix0 + 8, in_y0, in_y1, P_SMALL_SIZE, INPUT_HINT_COLOR)
    dpg.draw_rectangle((send_x0, in_y0), (send_x1, in_y1), color=clear, fill=START_COLORS[0], rounding=6, parent=dl)
    _put_centered(dl, "Send", send_x0, send_x1, in_y0, in_y1, P_SMALL_SIZE + 1, primary)
    dpg.draw_rectangle((new_x0, in_y0), (new_x1, in_y1), color=clear, fill=SECONDARY_COLORS[0], rounding=6, parent=dl)
    _put_centered(dl, "New Chat", new_x0, new_x1, in_y0, in_y1, P_SMALL_SIZE + 1, primary)

    # conversation box with three sample messages (text drawn as bars)
    _put_text(dl, "CONVERSATION", ix0, y0 + P_CONV_LABEL_TOP, y0 + P_CONV_LABEL_TOP + 12, P_PILL_SIZE, secondary)
    cy0 = y0 + P_CONV_TOP
    cy1 = cy0 + P_CONV_H
    dpg.draw_rectangle((ix0, cy0), (ix1, cy1), color=border, fill=COLORS["bg_main"], rounding=10, parent=dl)
    mx = ix0 + P_MESSAGE_PAD
    bar_w = ix1 - ix0 - 2 * P_MESSAGE_PAD

    def message(top, label, color, ratios):
        _put_text(dl, label, mx, top, top + 12, P_PILL_SIZE, color)
        _put_text(dl, EXAMPLE_TIME, mx + _text_w(label, P_PILL_SIZE) + 6, top, top + 12, P_PILL_SIZE, secondary)
        for i, ratio in enumerate(ratios):
            by = top + 18 + i * P_BAR_GAP
            dpg.draw_rectangle((mx, by), (mx + bar_w * ratio, by + P_BAR_H), color=clear, fill=(*secondary, 110),
                               rounding=2, parent=dl)
        return top + 18 + len(ratios) * P_BAR_GAP + 8

    top = cy0 + 8
    top = message(top, CHAT_ROLE_STYLES["user"][0], blue, (0.3,))
    top = message(top, CHAT_ROLE_STYLES["assistant"][0], green, (0.9, 0.8, 0.5))
    message(top, CHAT_ROLE_STYLES["system"][0], secondary, (0.6, 0.5))

    # suggested questions
    _put_text(dl, "SUGGESTED QUESTIONS", ix0, y0 + P_SUG_LABEL_TOP, y0 + P_SUG_LABEL_TOP + 12, P_PILL_SIZE, secondary)
    sy0 = y0 + P_SUG_TOP
    dpg.draw_rectangle((ix0, sy0), (ix1, sy0 + P_SUG_H), color=border, fill=COLORS["bg_main"], rounding=10, parent=dl)
    for i, question in enumerate(SUGGESTED_EXAMPLES):
        cy = sy0 + 6 + i * (P_CHIP_H + P_CHIP_GAP)
        dpg.draw_rectangle((ix0 + 6, cy), (ix1 - 14, cy + P_CHIP_H), color=border, fill=P_CHIP_FILL, rounding=6,
                           parent=dl)
        _put_text(dl, question, ix0 + 14, cy, cy + P_CHIP_H, P_SMALL_SIZE, primary)

    # footer
    fy0 = y0 + P_FOOTER_TOP
    fy1 = fy0 + P_FOOTER_H
    _put_text(dl, "Ready", ix0, fy0, fy1, P_SMALL_SIZE, secondary)
    _put_text(dl, f"KB Topics: {KB_TOPIC_COUNT}", ix0 + 52, fy0, fy1, P_SMALL_SIZE, secondary)

    # numbered callouts last, so they sit on top
    hw.draw_callout(title_x + title_w / 2, y0, 1, radius=r, parent=dl)
    hw.draw_callout((pill_x0 + pill_x1) / 2, y0, 2, radius=r, parent=dl)
    hw.draw_callout((close_x0 + close_x1) / 2, y0, 3, radius=r, parent=dl)
    hw.draw_callout(ix1 - r - 4, (sub_y0 + sub_y1) / 2, 4, radius=r, parent=dl)
    hw.draw_callout(ix0 + r + 6, in_y0, 5, radius=r, parent=dl)
    hw.draw_callout(ix1 - r - 6, cy0 + r + 6, 6, radius=r, parent=dl)
    hw.draw_callout(ix1 - r - 6, sy0 + r + 6, 7, radius=r, parent=dl)
    hw.draw_callout(ix1 - r - 4, (fy0 + fy1) / 2, 8, radius=r, parent=dl)


def _build_panel():
    with dpg.drawlist(width=DEFAULT_WIDTH, height=_panel_height(), tag=PANEL_TAG):
        pass
    _draw_panel(DEFAULT_WIDTH)
    hw.gap()


def _fit_all():
    if not dpg.does_item_exist(PANEL_TAG) or not dpg.does_item_exist(hw.HELP_CONTENT_PANE_TAG):
        return
    pane_w = dpg.get_item_width(hw.HELP_CONTENT_PANE_TAG)
    w = int(max(DRAW_MIN_WIDTH, min(DRAW_MAX_WIDTH, pane_w - SIDE_CHROME)))
    dpg.configure_item(PANEL_TAG, width=w, height=_panel_height())
    _draw_panel(w)


def _on_layout_resize(content_w, content_h):
    # help_manual sizes the pane in its own resize handler, which may run AFTER this one,
    # so wait a few frames and then read the pane's final width.
    dpg.set_frame_callback(dpg.get_frame_count() + FRAME_DELAY, lambda *args: _fit_all())


# ---------- conversation replica ----------

def _messages_replica(fonts):
    rows = [("user", EXAMPLE_KEYWORD), ("assistant", EXAMPLE_ANSWER), ("system", EXAMPLE_RELATED)]
    mono = fonts.get("mono_small")
    with _card():
        for index, (role, text) in enumerate(rows):
            label, color_name = CHAT_ROLE_STYLES.get(role, CHAT_ROLE_STYLES["system"])
            with dpg.group(horizontal=True):
                t = dpg.add_text(label, color=COLORS[color_name])
                if mono is not None:
                    dpg.bind_item_font(t, mono)
                dpg.add_text(EXAMPLE_TIME, color=COLORS["text_secondary"])
            body_color = COLORS["text_primary"] if role in ("user", "assistant") else COLORS["text_secondary"]
            dpg.add_text(text, wrap=0, color=body_color)
            if index < len(rows) - 1:
                dpg.add_spacer(height=MESSAGE_GAP)
    hw.gap()


# ---------- the topic ----------

def build_topic(fonts, icons):
    hw.page_heading("CyberLearn", "The built-in assistant for learning about cybersecurity.", fonts)
    hw.paragraph("CyberLearn is a chat assistant that explains cybersecurity: malware types such as trojans, "
                 "ransomware, worms and spyware, and how malware is detected and prevented. It sits behind the round "
                 "help bubble that floats in the bottom-right corner of every screen.")

    # ---------------- opening and closing ----------------
    hw.section_heading("Opening and closing", fonts)
    with dpg.group(horizontal=True):
        _build_bubble_replica()
        with dpg.group():
            dpg.add_text("Press the help bubble to open the chat. While the chat is open, the bubble hides. "
                         "Closing the chat brings it back.", wrap=0, color=hw.HELP_BODY_COLOR)
    hw.gap()
    if CHAT_LOCKED:
        hw.paragraph("The chat is docked to the bottom-right corner and resizes with the window. It can't be dragged. "
                     "Here is the chat in simplified form (made-up messages). The numbers match the list underneath.")
    else:
        hw.paragraph("The chat opens in the bottom-right corner. You can drag it elsewhere. Here is the chat in "
                     "simplified form (made-up messages). The numbers match the list underneath.")
    _build_panel()
    hw.numbered_row(1, "Title", PANEL_TITLE + ".")
    hw.numbered_row(2, "Mode pill", f"Shows how CyberLearn is answering: {PILL_LOCAL} (built-in answers) or "
                                    f"{PILL_ONLINE} (an online AI).")
    hw.numbered_row(3, "Close", "The X hides the chat and brings the help bubble back. Your conversation is kept.")
    hw.numbered_row(4, "Subtitle", f"Explains the mode. In {PILL_ONLINE} it names the AI model. In {PILL_LOCAL} it says "
                                   "no API key was found.")
    hw.numbered_row(5, "Question box", "Type a question or a keyword, then press Enter or Send. New Chat starts over.")
    hw.numbered_row(6, "Conversation", "Your questions and the answers, each with a time.")
    hw.numbered_row(7, "Suggested questions", "Click one to ask it straight away.")
    hw.numbered_row(8, "Footer", "A short status message, and how many answers the knowledge base holds.")

    # ---------------- the two modes ----------------
    hw.section_heading("Two modes", fonts)
    hw.paragraph("CyberLearn picks its mode by itself, depending on whether an API key is saved:")
    _chip_table([
        (PILL_LOCAL, "accent_orange",
         "Used when no API key is saved. CyberLearn looks your words up in its built-in knowledge base and shows the "
         "best matching answer, then a few related questions. It isn't a conversation: it doesn't remember earlier "
         "questions, and it can only answer topics that are in the knowledge base."),
        (PILL_ONLINE, "accent_green",
         "Used when an API key is saved. The subtitle names the AI model. Ask anything about cybersecurity in your own "
         "words and follow up on earlier answers, because it remembers the conversation. It needs an internet "
         "connection. If a request fails, CyberLearn shows why and falls back to the knowledge base."),
    ], fonts)
    if CYBERLEARN_PICKS_UP_NEW_KEY_WITHOUT_RESTART:
        key_text = "Add your key in Settings > AI Assistant, and CyberLearn notices it the next time you open the chat."
    else:
        key_text = "Add your key in Settings > AI Assistant, then restart AYAWrus so CyberLearn notices it."
    hw.paragraph(key_text + " The Settings topic walks through it.")

    # ---------------- asking ----------------
    hw.section_heading("Ask a question", fonts)
    hw.numbered_row(1, "Type or pick", "Type a question or a keyword in the box, or click a suggested question.")
    hw.numbered_row(2, "Send it", "Press Enter or the Send button. A suggested question is sent as soon as you click "
                                 "it.")
    hw.numbered_row(3, "Wait for the answer", f"In {PILL_ONLINE} a 'Thinking...' message shows while the AI works. "
                                              "Built-in answers appear straight away.")
    hw.numbered_row(4, "Read it", "The answer appears in the conversation, usually followed by a list of related "
                                  "questions. Related questions are plain text, not buttons: type one, or a keyword "
                                  "from it, to ask it. Long answers may need you to scroll the conversation box.")
    hw.paragraph(f"Here is an exchange in {PILL_LOCAL} (the answer is shortened). Typing just the keyword "
                 f"'{EXAMPLE_KEYWORD}' was enough:")
    _messages_replica(fonts)
    hw.paragraph("Each label tells you who is talking:")
    _term_table([(CHAT_ROLE_STYLES[role][0], CHAT_ROLE_STYLES[role][1], meaning) for role, meaning in (
        ("user", "Something you asked."),
        ("assistant", "An answer, from the knowledge base or the AI."),
        ("system", "A note from CyberLearn: the welcome message, related questions or an error."),
    )])

    _subheading("Suggested questions", fonts)
    hw.paragraph(f"The box under the conversation lists {CHAT_SUGGEST_COUNT} suggested questions, and you can scroll "
                 "it. Clicking one asks it right away. They are only a sample: the knowledge base holds "
                 f"{KB_TOPIC_COUNT} topics in all, and you can reach the others by typing a keyword.")

    _subheading("New Chat", fonts)
    hw.paragraph(f"New Chat clears the conversation and, in {PILL_ONLINE}, makes the AI forget it, so your next "
                 "question starts from scratch. It can't be used while a question is still being answered.")

    # ---------------- messages ----------------
    hw.section_heading("What the footer says", fonts)
    _term_table([
        ("Ready", "text_secondary", "Waiting for your question."),
        ("Contacting AI... / Generating AI answer...", "accent_blue",
         "A request is on its way to the AI service."),
        ("AI response received", "accent_green", "The AI answered."),
        ("Searching local KB... / Retrieving from KB...", "accent_blue", "Looking in the built-in knowledge base."),
        ("Ready (local KB)", "accent_green", "A knowledge base answer was shown."),
        ("No results", "accent_orange", "Nothing in the knowledge base matched. Try different keywords."),
        ("Please enter a question", "accent_orange", "You pressed Send with nothing typed."),
        ("Still processing... please wait", "accent_orange",
         "The last question hasn't finished. CyberLearn handles one at a time."),
        ("Wait for current request to finish", "accent_orange",
         "New Chat can't clear the chat while a question is still being answered."),
        (f"KB Topics: {KB_TOPIC_COUNT}", "text_primary", "How many ready-made answers the knowledge base holds."),
    ])

    hw.section_heading("When something goes wrong", fonts)
    _term_table([
        ("AI unavailable: <reason> Falling back to local knowledge base...", "accent_orange",
         "The AI request failed, for example because there is no internet connection or the key was rejected. "
         "CyberLearn shows the reason, then answers from the knowledge base instead."),
        ("Sorry, no topics found. Try different keywords!", "accent_orange",
         "Nothing in the knowledge base matched what you typed."),
        ("Local knowledge base not loaded. Please check your KB file path.", "accent_red",
         "The knowledge base file wasn't found when AYAWrus started, so built-in answers aren't available."),
        ("New conversation started!", "accent_green", "The chat was cleared."),
    ])

    # ---------------- limits ----------------
    hw.section_heading("What it can and can't do", fonts)
    _term_table([
        ("It can", "accent_green", "Explain cybersecurity ideas in plain language: malware types, how malware is "
                                   "detected and how to stay safe. In AI ONLINE mode it can also follow a conversation."),
        ("It can't", "accent_red", "Scan files, change settings or open your scan results. For help with a specific "
                                   "flagged file, use Explain in the Scan tab."),
    ])

    hw.section_heading("Good to know", fonts)
    hw.tip_box("note", "AI answers can be wrong",
               "An online AI can make mistakes, so double-check anything important. The built-in answers are fixed "
               "texts written in advance.", icons)
    hw.tip_box("note", "Keep private details out of the chat",
               f"In {PILL_ONLINE} mode, what you type is sent to the AI service you set up in Settings. Don't type "
               "passwords or other private information.", icons)
    hw.tip_box("tip", "Your chat is remembered while AYAWrus is open",
               f"Closing the chat with X doesn't erase it. Closing AYAWrus does. Only the last {CHAT_MAX_MESSAGES} "
               "messages are kept on screen.", icons)
    hw.tip_box("tip", "One question at a time",
               "CyberLearn answers one question before taking the next. Wait for the footer to say Ready.", icons)

    register_resize("help_cyberlearn", _on_layout_resize)