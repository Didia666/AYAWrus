"""
CyberLearn Assistant - DearPyGui Version
Bottom-RIGHT floating help button + docked chat panel
Powered by OpenRouter AI API with local knowledge base fallback.
"""

import json
import os
import sys
import threading
from datetime import datetime
from typing import List, Dict, Optional
import dearpygui.dearpygui as dpg
from ui.theme import COLORS
from ui.layout import register_resize

#cyberlearn_assistant_dpg.py

# ---- Floating help button constants (tune here) ----
FLOAT_BTN_SIZE = 60            # the round button
FLOAT_WINDOW_SIZE = 84         # the invisible window holding it (button + DPG's window padding)
FLOAT_MARGIN_RIGHT = 32        # gap from the right edge of the window
FLOAT_MARGIN_BOTTOM = 32       # gap from the bottom edge of the window
FLOAT_ICON_TEXTURE = "tex_help_chat"   # registered by ui/icons.py

# ---- Chat panel constants (tune here) ----
CHAT_LOCKED = True             # True = docked (no drag, re-docks on resize). False = draggable (stays where you drop it)
CHAT_WIDTH_RATIO = 0.40        # share of the window width
CHAT_MIN_WIDTH = 480
CHAT_MAX_WIDTH = 700
CHAT_MAX_HEIGHT = 820
CHAT_MIN_HEIGHT = 520
CHAT_MARGIN_RIGHT = 24         # gap from the right edge of the window
CHAT_MARGIN_BOTTOM = 24        # gap from the bottom edge of the window
CHAT_MARGIN_TOP = 24           # minimum gap from the top edge of the window

CHAT_ITEM_SPACING = 8          # horizontal spacing between items (used in width math)
CHAT_WINDOW_PAD_X = 16
CHAT_WINDOW_PAD_Y = 14
CHAT_CHILD_PAD_X = 12
CHAT_CHILD_PAD_Y = 10
CHAT_FRAME_PAD_X = 12          # inner padding of buttons / input
CHAT_FRAME_PAD_Y = 9
CHAT_ROUNDING = 14             # panel corners
CHAT_BOX_ROUNDING = 10         # chat box / suggestion box corners
CHAT_CONTROL_ROUNDING = 8      # buttons / input corners

CHAT_HEADER_ICON_SIZE = 26
CHAT_HEADER_BTN_HEIGHT = 30
CHAT_PILL_WIDTH = 116          # the AI ONLINE / LOCAL MODE pill
CHAT_PILL_ROUNDING = 15
CHAT_PILL_BG_ALPHA = 40
CHAT_PILL_BORDER_ALPHA = 160
CHAT_CLOSE_WIDTH = 30          # the X button
CHAT_HEADER_RIGHT_COLUMN = CHAT_PILL_WIDTH + CHAT_ITEM_SPACING + CHAT_CLOSE_WIDTH + 16

CHAT_BUTTON_HEIGHT = 36        # Send / New Chat
CHAT_SEND_WIDTH = 84
CHAT_NEWCHAT_WIDTH = 104
CHAT_INPUT_RESERVE = CHAT_SEND_WIDTH + CHAT_NEWCHAT_WIDTH + 2 * CHAT_ITEM_SPACING   # room kept for the two buttons

CHAT_SUGGEST_HEIGHT = 150      # height of the suggestions box
CHAT_SUGGEST_BUTTON_HEIGHT = 34
CHAT_SUGGEST_MAX_CHARS = 56
CHAT_SUGGEST_COUNT = 6
CHAT_RESERVE_EXTRA = 86        # labels + footer + spacing below the chat box. Raise if the footer gets cut off, lower if there's a gap
CHAT_RESERVE_BELOW = CHAT_SUGGEST_HEIGHT + CHAT_RESERVE_EXTRA

CHAT_MESSAGE_SPACING = 10      # gap between messages
CHAT_MAX_MESSAGES = 30         # how many messages are kept on screen

# role -> (label, color name from theme.py COLORS)
CHAT_ROLE_STYLES = {
    "user":      ("YOU",       "accent_blue"),
    "assistant": ("ASSISTANT", "accent_green"),
    "system":    ("SYSTEM",    "text_secondary"),
    "thinking":  ("ASSISTANT", "text_secondary"),
}

# Extra colors used only by the chat panel
CHAT_COLOR_BORDER_GLOW = (56, 130, 246, 90)     # soft blue outline around the panel
CHAT_COLOR_HINT = (100, 116, 139)               # placeholder text in the input
CHAT_COLOR_BTN_HOVER = (76, 150, 246)
CHAT_COLOR_BTN_ACTIVE = (46, 120, 236)
CHAT_COLOR_SECONDARY_BTN = (45, 58, 84)
CHAT_COLOR_SECONDARY_BTN_HOVER = (60, 76, 108)
CHAT_COLOR_SECONDARY_BTN_ACTIVE = (38, 49, 72)
CHAT_COLOR_CHIP = (30, 40, 62)
CHAT_COLOR_CHIP_HOVER = (44, 58, 88)
CHAT_COLOR_SCROLL_HOVER = (80, 96, 128)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from system.ai import OpenRouterClient, load_ai_config


class KnowledgeBase:
    """Load and manage the cybersecurity knowledge base."""
    
    def __init__(self, kb_path=None):
        self.kb_path = kb_path
        self.data = {}
        self.all_topics = []
        self.categories = {}
        if kb_path:
            self._load()
    
    def _load(self):
        """Load knowledge base from JSON file."""
        try:
            with open(self.kb_path, "r", encoding="utf-8") as f:
                self.data = json.load(f)
                self.categories = self.data.get("categories", {})
                self._index_topics()
        except Exception as e:
            print(f"Error loading knowledge base: {e}")
    
    def _index_topics(self):
        """Index all topics for faster search."""
        self.all_topics = []
        for category_key, category_data in self.categories.items():
            category_name = category_data.get("name", category_key)
            category_icon = category_data.get("icon", "")
            for topic in category_data.get("topics", []):
                topic["_category_key"] = category_key
                topic["_category_name"] = category_name
                topic["_category_icon"] = category_icon
                self.all_topics.append(topic)
    
    def search(self, query: str, limit: int = 5) -> List[Dict]:
        """Search topics by keyword matching."""
        query_lower = query.lower()
        results = []
        
        # Question match first
        for topic in self.all_topics:
            if query_lower in topic.get("question", "").lower():
                results.append((topic, 100))
        
        # Keyword match
        for topic in self.all_topics:
            keywords = topic.get("keywords", [])
            for keyword in keywords:
                if query_lower in keyword.lower():
                    results.append((topic, 80))
                    break
        
        # Content match
        for topic in self.all_topics:
            if query_lower in topic.get("answer", "").lower():
                results.append((topic, 60))
        
        # Remove duplicates
        seen_ids = set()
        unique_results = []
        for topic, score in sorted(results, key=lambda x: -x[1]):
            if topic["id"] not in seen_ids:
                unique_results.append(topic)
                seen_ids.add(topic["id"])
        
        return unique_results[:limit]
    
    def get_topic_by_id(self, topic_id: str) -> Dict:
        """Get topic by ID."""
        for topic in self.all_topics:
            if topic["id"] == topic_id:
                return topic
        return None
    
    def get_related_topics(self, topic_id: str, limit: int = 3) -> List[Dict]:
        """Get related topics."""
        topic = self.get_topic_by_id(topic_id)
        if not topic:
            return []
        
        related_ids = topic.get("related", [])
        related_topics = []
        for rel_id in related_ids:
            rel_topic = self.get_topic_by_id(rel_id)
            if rel_topic:
                related_topics.append(rel_topic)
        
        return related_topics[:limit]
    
    def get_all_questions(self) -> List[str]:
        """Get all questions."""
        return [t["question"] for t in self.all_topics]


# Global state
_KB = None
_AI_CLIENT: Optional[OpenRouterClient] = None
_AI_ENABLED = False
_FONTS = {}
_THEMES = {}
_CHAT_WINDOW = "cyberlearn_chat_window"
_CHAT_CHILD = "cyberlearn_chat_child"
_MESSAGES_CONTAINER = "cyberlearn_messages"
_STATUS_TEXT = "cyberlearn_status"
_SUBTITLE_TEXT = "cyberlearn_subtitle"
_SEARCH_INPUT = "cyberlearn_search"
_SUGGESTION_PREFIX = "cyberlearn_sug_"
_FLOATING_BUTTON = "cyberlearn_floating_btn"
_AI_STATUS_TEXT = "cyberlearn_ai_status"
_NEW_CHAT_BTN = "cyberlearn_new_chat"
_CLOSE_BTN = "cyberlearn_close_btn"
work_lock = threading.Lock()
_work_in_progress = False
_messages = []   # list of (role, timestamp, text)
_THINKING_PREFIX = "Thinking..."

# Characters the UI font can actually draw: Basic Latin / Latin-1, and general punctuation (bullets, quotes, dashes)
_TEXT_REPLACEMENTS = {"\u2192": "->", "\u2190": "<-", "\u2713": "", "\u200d": "", "\u200b": ""}


def _clean_text(text):
    """Display-only: drops emoji and other glyphs the font can't draw (they'd show up as '?')."""
    if not text:
        return ""
    out = []
    for ch in str(text):
        if ch in _TEXT_REPLACEMENTS:
            out.append(_TEXT_REPLACEMENTS[ch])
            continue
        code = ord(ch)
        if ch in "\n\t" or code <= 0xFF or 0x2000 <= code <= 0x206F:
            out.append(ch)
    return "".join(out).strip()


def _bind_font(item, key):
    font = _FONTS.get(key) if _FONTS else None
    if font is not None:
        dpg.bind_item_font(item, font)


# ---------------------------------------------------------------------------
# Themes (built once, before the chat window is created)
# ---------------------------------------------------------------------------

def _build_pill_theme(color):
    bg = (*color, CHAT_PILL_BG_ALPHA)
    border = (*color, CHAT_PILL_BORDER_ALPHA)
    with dpg.theme() as theme:
        with dpg.theme_component(dpg.mvButton):
            # same color for normal / hover / pressed, so the pill never reacts like a real button
            dpg.add_theme_color(dpg.mvThemeCol_Button, bg)
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, bg)
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, bg)
            dpg.add_theme_color(dpg.mvThemeCol_Text, color)
            dpg.add_theme_color(dpg.mvThemeCol_Border, border)
            dpg.add_theme_style(dpg.mvStyleVar_FrameBorderSize, 1)
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, CHAT_PILL_ROUNDING)
    return theme


def _build_themes():
    if _THEMES:
        return
    c = COLORS

    # Whole panel
    with dpg.theme() as window_theme:
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_color(dpg.mvThemeCol_WindowBg, c["bg_card"])
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, c["bg_main"])
            dpg.add_theme_color(dpg.mvThemeCol_Text, c["text_primary"])
            dpg.add_theme_color(dpg.mvThemeCol_TextDisabled, CHAT_COLOR_HINT)
            dpg.add_theme_color(dpg.mvThemeCol_Border, CHAT_COLOR_BORDER_GLOW)
            dpg.add_theme_color(dpg.mvThemeCol_FrameBg, c["bg_sidebar"])
            dpg.add_theme_color(dpg.mvThemeCol_FrameBgHovered, c["bg_main"])
            dpg.add_theme_color(dpg.mvThemeCol_FrameBgActive, c["bg_main"])
            dpg.add_theme_color(dpg.mvThemeCol_Button, c["accent_blue"])
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, CHAT_COLOR_BTN_HOVER)
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, CHAT_COLOR_BTN_ACTIVE)
            dpg.add_theme_color(dpg.mvThemeCol_Separator, c["border"])
            # slim scrollbars that match the design
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarBg, (0, 0, 0, 0))
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarGrab, c["border"])
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarGrabHovered, CHAT_COLOR_SCROLL_HOVER)
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarGrabActive, c["accent_blue"])
            dpg.add_theme_style(dpg.mvStyleVar_WindowRounding, CHAT_ROUNDING)
            dpg.add_theme_style(dpg.mvStyleVar_ChildRounding, CHAT_BOX_ROUNDING)
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, CHAT_CONTROL_ROUNDING)
            dpg.add_theme_style(dpg.mvStyleVar_WindowBorderSize, 1)
            dpg.add_theme_style(dpg.mvStyleVar_ChildBorderSize, 1)
            dpg.add_theme_style(dpg.mvStyleVar_FrameBorderSize, 0)
            dpg.add_theme_style(dpg.mvStyleVar_ScrollbarSize, 8)
            dpg.add_theme_style(dpg.mvStyleVar_ScrollbarRounding, 8)
            dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, CHAT_WINDOW_PAD_X, CHAT_WINDOW_PAD_Y)
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding, CHAT_FRAME_PAD_X, CHAT_FRAME_PAD_Y)
            dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, CHAT_ITEM_SPACING, 6)
        with dpg.theme_component(dpg.mvChildWindow):
            dpg.add_theme_color(dpg.mvThemeCol_Border, c["border"])
            dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, CHAT_CHILD_PAD_X, CHAT_CHILD_PAD_Y)
    _THEMES["window"] = window_theme

    # Input box: thin outline
    with dpg.theme() as input_theme:
        with dpg.theme_component(dpg.mvInputText):
            dpg.add_theme_color(dpg.mvThemeCol_Border, c["border"])
            dpg.add_theme_style(dpg.mvStyleVar_FrameBorderSize, 1)
    _THEMES["input"] = input_theme

    # New Chat: calmer than the blue Send button
    with dpg.theme() as secondary_theme:
        with dpg.theme_component(dpg.mvButton):
            dpg.add_theme_color(dpg.mvThemeCol_Button, CHAT_COLOR_SECONDARY_BTN)
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, CHAT_COLOR_SECONDARY_BTN_HOVER)
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, CHAT_COLOR_SECONDARY_BTN_ACTIVE)
    _THEMES["secondary"] = secondary_theme

    # Suggestion chips: left-aligned, outlined
    with dpg.theme() as chip_theme:
        with dpg.theme_component(dpg.mvButton):
            dpg.add_theme_color(dpg.mvThemeCol_Button, CHAT_COLOR_CHIP)
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, CHAT_COLOR_CHIP_HOVER)
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, c["accent_blue"])
            dpg.add_theme_color(dpg.mvThemeCol_Border, c["border"])
            dpg.add_theme_style(dpg.mvStyleVar_FrameBorderSize, 1)
            dpg.add_theme_style(dpg.mvStyleVar_ButtonTextAlign, 0.0, 0.5)
    _THEMES["chip"] = chip_theme

    # X button: red tint so it's easy to spot
    with dpg.theme() as close_theme:
        with dpg.theme_component(dpg.mvButton):
            dpg.add_theme_color(dpg.mvThemeCol_Button, (*c["accent_red"], 45))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (*c["accent_red"], 210))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (*c["accent_red"], 255))
            dpg.add_theme_color(dpg.mvThemeCol_Text, c["text_primary"])
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 0, 0)
    _THEMES["close"] = close_theme

    _THEMES["pill_online"] = _build_pill_theme(c["accent_green"])
    _THEMES["pill_local"] = _build_pill_theme(c["accent_orange"])


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------

def _render_message(role, timestamp, text):
    label, color_name = CHAT_ROLE_STYLES.get(role, CHAT_ROLE_STYLES["system"])
    body_color = COLORS["text_primary"] if role in ("user", "assistant") else COLORS["text_secondary"]

    with dpg.group(horizontal=True, parent=_MESSAGES_CONTAINER):
        role_label = dpg.add_text(label, color=COLORS[color_name])
        _bind_font(role_label, "mono_small")
        dpg.add_text(timestamp, color=COLORS["text_secondary"])
    dpg.add_text(text, wrap=0, color=body_color, parent=_MESSAGES_CONTAINER)
    dpg.add_spacer(height=CHAT_MESSAGE_SPACING, parent=_MESSAGES_CONTAINER)


def _add_message(role, text, append_only=False):
    """Add a message to the chat (display only: emoji are stripped)."""
    timestamp = datetime.now().strftime("%H:%M")
    _messages.append((role, timestamp, _clean_text(text)))

    # Keep only the last N messages
    while len(_messages) > CHAT_MAX_MESSAGES:
        _messages.pop(0)

    _refresh_chat_display()


def _remove_thinking_message():
    """Remove the thinking placeholder message if present."""
    global _messages
    _messages = [m for m in _messages if m[0] != "thinking"]
    _refresh_chat_display()


def _refresh_chat_display():
    """Rebuild the message list from the current messages."""
    try:
        if dpg.does_item_exist(_MESSAGES_CONTAINER):
            dpg.delete_item(_MESSAGES_CONTAINER, children_only=True)
            for role, timestamp, text in _messages:
                _render_message(role, timestamp, text)
    except Exception:
        pass


def _update_ai_status_display():
    """Update the status pill and the subtitle line."""
    if dpg.does_item_exist(_AI_STATUS_TEXT):
        if _AI_ENABLED:
            dpg.set_item_label(_AI_STATUS_TEXT, "AI ONLINE")
            dpg.bind_item_theme(_AI_STATUS_TEXT, _THEMES["pill_online"])
        else:
            dpg.set_item_label(_AI_STATUS_TEXT, "LOCAL MODE")
            dpg.bind_item_theme(_AI_STATUS_TEXT, _THEMES["pill_local"])

    if dpg.does_item_exist(_SUBTITLE_TEXT):
        if _AI_ENABLED:
            model = getattr(_AI_CLIENT, 'model', 'default') if _AI_CLIENT else 'default'
            subtitle = f"Model: {model}  \u2022  Ask anything about cybersecurity!"
        else:
            subtitle = "No API key found. Answering from the local knowledge base."
        dpg.set_value(_SUBTITLE_TEXT, _clean_text(subtitle))


def _set_status(text):
    """Safely set status text."""
    if dpg.does_item_exist(_STATUS_TEXT):
        dpg.set_value(_STATUS_TEXT, _clean_text(text))


def _fallback_kb_search(query: str, show_error: bool = False, error_msg: str = None):
    """Fallback to local knowledge base when AI unavailable."""
    if show_error and error_msg:
        _add_message("system", f"AI unavailable: {error_msg}\nFalling back to local knowledge base...")
    
    if _KB is None:
        _add_message("system", "Local knowledge base not loaded. Please check your KB file path.")
        return
    
    results = _KB.search(query, limit=1)
    if results:
        topic = results[0]
        _add_message("assistant", topic["answer"])
        related = _KB.get_related_topics(topic["id"], limit=3)
        if related:
            related_text = "Related topics:\n"
            for rel in related:
                related_text += f"\u2022 {rel['question']}\n"
            _add_message("system", related_text)
        _set_status("Ready (local KB)")
    else:
        _add_message("system", "Sorry, no topics found. Try different keywords!")
        _set_status("No results")


def _on_ai_response_callback(success: bool, content: Optional[str], error: Optional[str], original_query: str):
    """Called from background thread when AI request completes. Must marshal to DPG thread via queue/single-shot."""
    def _apply_update():
        global _work_in_progress
        try:
            _remove_thinking_message()
            if success and content:
                _add_message("assistant", content)
                if _KB is not None:
                    results = _KB.search(original_query, limit=3)
                    if results and len(results) > 1:
                        related_text = "Related topics:\n"
                        for rel in results[1:4]:
                            related_text += f"\u2022 {rel['question']}\n"
                        _add_message("system", related_text)
                _set_status("AI response received")
            else:
                _fallback_kb_search(original_query, show_error=True, error_msg=error or "AI request failed")
        except Exception as e:
            _add_message("system", f"Unexpected error: {e}")
            _set_status(f"Error: {e}")
        finally:
            with work_lock:
                _work_in_progress = False
    
    # DPG is not thread-safe for widget mutation; run on main thread via dpg's queue
    try:
        dpg.run_callbacks(lambda: _apply_update())
    except Exception:
        # Fallback: apply directly if run_callbacks unavailable in older DPG
        _apply_update()


def _on_search_click():
    """Handle search/ask button click - AI first, then KB fallback."""
    global _work_in_progress, _AI_ENABLED
    
    with work_lock:
        if _work_in_progress:
            _set_status("Still processing... please wait")
            return
        _work_in_progress = True
    
    try:
        query = dpg.get_value(_SEARCH_INPUT).strip()
        if not query:
            _set_status("Please enter a question")
            with work_lock:
                _work_in_progress = False
            return
        
        _add_message("user", query)
        dpg.set_value(_SEARCH_INPUT, "")
        
        if _AI_ENABLED and _AI_CLIENT is not None:
            _set_status("Contacting AI...")
            _add_message("thinking", _THINKING_PREFIX)
            captured_query = query
            _AI_CLIENT.chat_async(
                query,
                callback=lambda s, c, e: _on_ai_response_callback(s, c, e, captured_query)
            )
            # Don't clear work_in_progress here - callback does it
        else:
            _set_status("Searching local KB...")
            _fallback_kb_search(query)
            with work_lock:
                _work_in_progress = False
        
    except Exception as e:
        _set_status(f"Error: {e}")
        with work_lock:
            _work_in_progress = False


def _on_suggestion_click(sender, app_data, user_data):
    """Handle suggestion button click - AI first, then KB fallback."""
    global _work_in_progress, _AI_ENABLED
    
    with work_lock:
        if _work_in_progress:
            _set_status("Still processing... please wait")
            return
        _work_in_progress = True
    
    try:
        question = user_data
        _add_message("user", question)
        
        if _AI_ENABLED and _AI_CLIENT is not None:
            _set_status("Generating AI answer...")
            _add_message("thinking", _THINKING_PREFIX)
            captured_question = question
            _AI_CLIENT.chat_async(
                question,
                callback=lambda s, c, e: _on_ai_response_callback(s, c, e, captured_question)
            )
        else:
            _set_status("Retrieving from KB...")
            _fallback_kb_search(question)
            with work_lock:
                _work_in_progress = False
        
    except Exception as e:
        _set_status(f"Error: {e}")
        with work_lock:
            _work_in_progress = False


def _on_new_chat_click():
    """Clear chat and reset AI conversation history."""
    global _messages, _work_in_progress
    with work_lock:
        if _work_in_progress:
            _set_status("Wait for current request to finish")
            return
    
    _messages.clear()
    if _AI_CLIENT is not None:
        _AI_CLIENT.reset()
    
    _add_message("system", "New conversation started!\n\nWhat would you like to learn about?")
    _set_status("Ready")


def _find_kb_path():
    """Locate cyberlearn_knowledge_base.json reliably using absolute paths."""
    ui_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(ui_dir)
    
    candidates = [
        os.path.join(project_root, "cyberlearn_knowledge_base.json"),
        os.path.join(ui_dir, "cyberlearn_knowledge_base.json"),
        os.path.abspath("cyberlearn_knowledge_base.json"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


def _ensure_ai_initialized():
    """Initialize OpenRouter client and AI status."""
    global _AI_CLIENT, _AI_ENABLED
    if _AI_CLIENT is None:
        try:
            _AI_CLIENT = OpenRouterClient()
            _AI_ENABLED = _AI_CLIENT.is_configured()
        except Exception as e:
            print(f"[CyberLearn] Failed to init AI client: {e}")
            _AI_CLIENT = None
            _AI_ENABLED = False
    return _AI_CLIENT


# ---------------------------------------------------------------------------
# Chat panel: layout, open / close, build
# ---------------------------------------------------------------------------

def _layout_chat_window(force_pos=False):
    """Sizes the panel from the viewport and docks it bottom-right."""
    if not dpg.does_item_exist(_CHAT_WINDOW):
        return
    vw = dpg.get_viewport_client_width()
    vh = dpg.get_viewport_client_height()

    w = max(CHAT_MIN_WIDTH, min(CHAT_MAX_WIDTH, int(vw * CHAT_WIDTH_RATIO)))
    h = max(CHAT_MIN_HEIGHT, min(CHAT_MAX_HEIGHT, vh - CHAT_MARGIN_TOP - CHAT_MARGIN_BOTTOM))
    dpg.configure_item(_CHAT_WINDOW, width=w, height=h)

    # When unlocked (draggable) we only re-dock on open, so a resize doesn't yank it back
    if CHAT_LOCKED or force_pos:
        dpg.configure_item(_CHAT_WINDOW, pos=(vw - w - CHAT_MARGIN_RIGHT, vh - h - CHAT_MARGIN_BOTTOM))


def _on_chat_resize(content_w=None, content_h=None):
    _layout_chat_window()


def _close_cyberlearn():
    """Hide the chat and bring the help button back."""
    if dpg.does_item_exist(_CHAT_WINDOW):
        dpg.configure_item(_CHAT_WINDOW, show=False)
    if dpg.does_item_exist(_FLOATING_BUTTON):
        dpg.configure_item(_FLOATING_BUTTON, show=True)


def _build_chat_window():
    _build_themes()

    with dpg.window(tag=_CHAT_WINDOW, no_title_bar=True, no_resize=True, no_collapse=True,
                    no_scrollbar=True, no_move=CHAT_LOCKED,
                    width=CHAT_MIN_WIDTH, height=CHAT_MIN_HEIGHT, pos=(0, 0)):
        dpg.bind_item_theme(_CHAT_WINDOW, _THEMES["window"])

        # ---- Header: icon + title on the left, status pill + X on the right ----
        with dpg.table(header_row=False):
            dpg.add_table_column(width_stretch=True, init_width_or_weight=1.0)
            dpg.add_table_column(width_fixed=True, init_width_or_weight=CHAT_HEADER_RIGHT_COLUMN)
            with dpg.table_row():
                with dpg.group():
                    dpg.add_spacer(height=2)
                    with dpg.group(horizontal=True):
                        if dpg.does_item_exist(FLOAT_ICON_TEXTURE):
                            dpg.add_image(FLOAT_ICON_TEXTURE, width=CHAT_HEADER_ICON_SIZE,
                                          height=CHAT_HEADER_ICON_SIZE, tint_color=COLORS["accent_blue"])
                        title = dpg.add_text("CyberLearn Assistant", color=COLORS["text_primary"])
                        _bind_font(title, "subheading")
                with dpg.group(horizontal=True):
                    pill = dpg.add_button(label="", tag=_AI_STATUS_TEXT,
                                          width=CHAT_PILL_WIDTH, height=CHAT_HEADER_BTN_HEIGHT)
                    _bind_font(pill, "mono_small")
                    close_btn = dpg.add_button(label="X", tag=_CLOSE_BTN, width=CHAT_CLOSE_WIDTH,
                                               height=CHAT_HEADER_BTN_HEIGHT, callback=_close_cyberlearn)
                    _bind_font(close_btn, "subheading")
                    dpg.bind_item_theme(close_btn, _THEMES["close"])

        dpg.add_text("", tag=_SUBTITLE_TEXT, wrap=0, color=COLORS["text_secondary"])
        dpg.add_separator()

        # ---- Ask row: input + Send + New Chat, all on one line ----
        with dpg.group(horizontal=True):
            dpg.add_input_text(
                tag=_SEARCH_INPUT,
                default_value="",
                width=-CHAT_INPUT_RESERVE,
                hint="Ask anything, e.g. 'What is a Trojan?'",
                callback=_on_search_click,
                on_enter=True
            )
            dpg.add_button(label="Send", width=CHAT_SEND_WIDTH, height=CHAT_BUTTON_HEIGHT,
                           callback=_on_search_click)
            dpg.add_button(label="New Chat", tag=_NEW_CHAT_BTN, width=CHAT_NEWCHAT_WIDTH,
                           height=CHAT_BUTTON_HEIGHT, callback=_on_new_chat_click)
        dpg.bind_item_theme(_SEARCH_INPUT, _THEMES["input"])
        dpg.bind_item_theme(_NEW_CHAT_BTN, _THEMES["secondary"])

        # ---- Conversation (this box stretches with the window) ----
        convo_label = dpg.add_text("CONVERSATION", color=COLORS["text_secondary"])
        _bind_font(convo_label, "mono_small")
        with dpg.child_window(tag=_CHAT_CHILD, width=-1, height=-CHAT_RESERVE_BELOW, border=True):
            with dpg.group(tag=_MESSAGES_CONTAINER):
                pass

        # ---- Suggested questions ----
        sug_label = dpg.add_text("SUGGESTED QUESTIONS", color=COLORS["text_secondary"])
        _bind_font(sug_label, "mono_small")
        with dpg.child_window(width=-1, height=CHAT_SUGGEST_HEIGHT, border=True):
            questions = _KB.get_all_questions() if _KB and _KB.all_topics else [
                "What is a Trojan and how does it differ from a virus?",
                "What is ransomware and how does it work?",
                "What is a computer worm?",
                "What is phishing and how to prevent it?",
                "What is malware entropy analysis?",
                "How do machine learning malware detectors work?"
            ]
            for i, question in enumerate(questions[:CHAT_SUGGEST_COUNT]):
                label = _clean_text(question)
                if len(label) > CHAT_SUGGEST_MAX_CHARS:
                    label = label[:CHAT_SUGGEST_MAX_CHARS - 3] + "..."
                btn_tag = f"{_SUGGESTION_PREFIX}{i}"
                dpg.add_button(
                    label=label,
                    width=-1,
                    height=CHAT_SUGGEST_BUTTON_HEIGHT,
                    tag=btn_tag,
                    callback=_on_suggestion_click,
                    user_data=question
                )
                dpg.bind_item_theme(btn_tag, _THEMES["chip"])

        # ---- Footer status ----
        with dpg.group(horizontal=True):
            kb_count = len(_KB.all_topics) if _KB and _KB.all_topics else 0
            dpg.add_text("Ready", tag=_STATUS_TEXT, color=COLORS["text_secondary"])
            dpg.add_spacer(width=12)
            dpg.add_text(f"KB Topics: {kb_count}", color=COLORS["text_secondary"])

    _update_ai_status_display()

    # Initial welcome message (only once)
    if not _messages:
        welcome_extra = ""
        if not _AI_ENABLED:
            welcome_extra = (
                "\n\nNo API key configured yet. Go to Settings > AI API Settings "
                "to add your OpenRouter key. Using local knowledge base mode."
            )
        _add_message("system",
            "Welcome to CyberLearn Assistant!\n\n"
            "I'm an AI-powered cybersecurity educator. I can explain concepts, "
            "describe malware types, teach detection techniques, and more.\n\n"
            "Tips:\n"
            "\u2022 Type any question and press Enter or click Send\n"
            "\u2022 Click suggested questions below to get started\n"
            "\u2022 Ask follow-up questions - I remember our conversation!\n"
            "\u2022 Click 'New Chat' to start fresh\n\n"
            "What would you like to learn about?" + welcome_extra
        )
    else:
        _refresh_chat_display()


def _toggle_cyberlearn():
    """Open CyberLearn chat window (the help button hides while it's open)."""
    global _KB, _AI_CLIENT, _AI_ENABLED
    
    # Ensure KB and AI are ready
    if _KB is None:
        kb_path = _find_kb_path()
        if kb_path:
            print(f"[CyberLearn] Loading KB from: {kb_path}")
            _KB = KnowledgeBase(kb_path)
            print(f"[CyberLearn] Loaded {len(_KB.all_topics)} topics")
        else:
            print("[CyberLearn] WARNING: KB file not found, AI will be used exclusively")
            _KB = KnowledgeBase()
    
    _ensure_ai_initialized()
    
    if dpg.does_item_exist(_CHAT_WINDOW):
        dpg.configure_item(_CHAT_WINDOW, show=True)
        _layout_chat_window(force_pos=True)
        dpg.focus_item(_CHAT_WINDOW)
        _update_ai_status_display()
    else:
        _build_chat_window()
        _layout_chat_window(force_pos=True)

    if dpg.does_item_exist(_FLOATING_BUTTON):
        dpg.configure_item(_FLOATING_BUTTON, show=False)


def _reposition_floating_button(content_w=None, content_h=None):
    """Keeps the button a fixed distance from the bottom-right corner on every resize."""
    if not dpg.does_item_exist(_FLOATING_BUTTON):
        return
    vw = dpg.get_viewport_client_width()
    vh = dpg.get_viewport_client_height()
    dpg.configure_item(
        _FLOATING_BUTTON,
        pos=(vw - FLOAT_WINDOW_SIZE - FLOAT_MARGIN_RIGHT, vh - FLOAT_WINDOW_SIZE - FLOAT_MARGIN_BOTTOM),
    )


def create_floating_button():
    """Create a FLOATING button that follows the bottom-right corner."""
    if dpg.does_item_exist(_FLOATING_BUTTON):
        return

    with dpg.window(label="", tag=_FLOATING_BUTTON,
                    no_title_bar=True, no_resize=True, no_scrollbar=True,
                    no_move=False, no_background=True,
                    width=FLOAT_WINDOW_SIZE, height=FLOAT_WINDOW_SIZE,
                    pos=(1480, 820)):

        with dpg.theme() as btn_theme:
            with dpg.theme_component(dpg.mvAll):
                dpg.add_theme_color(dpg.mvThemeCol_Button, COLORS["accent_blue"])
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (76, 150, 246))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (46, 120, 236))
                dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 50)

        if dpg.does_item_exist(FLOAT_ICON_TEXTURE):
            btn = dpg.add_image_button(
                FLOAT_ICON_TEXTURE,
                width=FLOAT_BTN_SIZE - 20,
                height=FLOAT_BTN_SIZE - 20,
                frame_padding=10,
                background_color=COLORS["accent_blue"],
                tint_color=(255, 255, 255, 255),
                callback=_toggle_cyberlearn,
            )
        else:
            # Fallback if the icon texture is missing: plain "?" button
            btn = dpg.add_button(label="?", width=FLOAT_BTN_SIZE, height=FLOAT_BTN_SIZE,
                                 callback=_toggle_cyberlearn)
        dpg.bind_item_theme(btn, btn_theme)

    register_resize("help_button", _reposition_floating_button)
    register_resize("cyberlearn_chat", _on_chat_resize)


def init_cyberlearn_for_dpg(fonts=None):
    """Initialize CyberLearn! Must be called after main_content exists! Pass the fonts dict for bold titles."""
    global _KB, _AI_CLIENT, _AI_ENABLED, _FONTS
    _FONTS = fonts or {}
    
    # Initialize KB early with fixed path resolution
    if _KB is None:
        kb_path = _find_kb_path()
        if kb_path:
            print(f"[CyberLearn] Found knowledge base at: {kb_path}")
            _KB = KnowledgeBase(kb_path)
            print(f"[CyberLearn] Loaded {len(_KB.all_topics)} topics")
        else:
            print("[CyberLearn] WARNING: Could not find cyberlearn_knowledge_base.json in any path!")
            print("[CyberLearn] Searched:")
            ui_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(ui_dir)
            for p in [
                os.path.join(project_root, "cyberlearn_knowledge_base.json"),
                os.path.join(ui_dir, "cyberlearn_knowledge_base.json"),
                os.path.abspath("cyberlearn_knowledge_base.json"),
            ]:
                print(f"  - {p} (exists: {os.path.exists(p)})")
            _KB = KnowledgeBase()
    
    # Pre-initialize AI client
    _ensure_ai_initialized()
    print(f"[CyberLearn] AI enabled: {_AI_ENABLED}")
    if _AI_CLIENT:
        print(f"[CyberLearn] AI model: {_AI_CLIENT.model}")
    
    create_floating_button()


if __name__ == "__main__":
    dpg.create_context()
    dpg.create_viewport(title="CyberLearn Test", width=1600, height=950)
    dpg.setup_dearpygui()
    
    with dpg.window(tag="primary_window", no_scrollbar=True):
        with dpg.group(horizontal=True, tag="main_content"):
            dpg.add_child_window(width=-1, height=-1, border=False, tag="test_content")
            dpg.add_text("Test app content!")
    
    init_cyberlearn_for_dpg()
    
    dpg.show_viewport()
    dpg.set_primary_window("primary_window", True)
    dpg.start_dearpygui()
    dpg.destroy_context()