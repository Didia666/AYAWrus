"""
CyberLearn Assistant - DearPyGui Version
Bottom-RIGHT FLOATING BUTTON + chat window
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
_CHAT_WINDOW = "cyberlearn_chat_window"
_MESSAGES_CONTAINER = "cyberlearn_messages"
_STATUS_TEXT = "cyberlearn_status"
_SEARCH_INPUT = "cyberlearn_search"
_SUGGESTION_PREFIX = "cyberlearn_sug_"
_FLOATING_BUTTON = "cyberlearn_floating_btn"
_AI_STATUS_TEXT = "cyberlearn_ai_status"
_NEW_CHAT_BTN = "cyberlearn_new_chat"
work_lock = threading.Lock()
_work_in_progress = False
_messages = []
_THINKING_PREFIX = "[🧠 Thinking...]"


def _add_message(role, text, append_only=False):
    """Add message to chat. If append_only=True, add without refreshing thinking msg removal."""
    timestamp = datetime.now().strftime("%H:%M")
    
    if role == "user":
        prefix = "You"
    elif role == "system":
        prefix = "ℹ️"
    elif role == "thinking":
        prefix = "🧠 Thinking"
    else:  # assistant
        prefix = "🤖 Assistant"
    
    formatted = f"[{timestamp}] {prefix}: {text}"
    _messages.append(formatted)
    
    # Keep only last 30 messages
    while len(_messages) > 30:
        _messages.pop(0)
    
    _refresh_chat_display()


def _remove_thinking_message():
    """Remove the thinking placeholder message if present."""
    global _messages
    _messages = [m for m in _messages if _THINKING_PREFIX not in m and "🧠 Thinking" not in m]
    _refresh_chat_display()


def _refresh_chat_display():
    """Refresh chat display with current messages."""
    try:
        if dpg.does_item_exist(_MESSAGES_CONTAINER):
            full_text = "\n\n".join(_messages)
            dpg.set_value(_MESSAGES_CONTAINER, full_text)
    except Exception:
        pass


def _update_ai_status_display():
    """Update the AI status badge in the UI."""
    if not dpg.does_item_exist(_AI_STATUS_TEXT):
        return
    global _AI_ENABLED
    if _AI_ENABLED:
        model = getattr(_AI_CLIENT, 'model', 'default') if _AI_CLIENT else 'default'
        dpg.set_value(_AI_STATUS_TEXT, f"  🤖 AI Online  •  Model: {model}  ")
    else:
        dpg.set_value(_AI_STATUS_TEXT, "  📚 Local Mode (no API key)  ")


def _set_status(text):
    """Safely set status text."""
    if dpg.does_item_exist(_STATUS_TEXT):
        dpg.set_value(_STATUS_TEXT, text)


def _fallback_kb_search(query: str, show_error: bool = False, error_msg: str = None):
    """Fallback to local knowledge base when AI unavailable."""
    if show_error and error_msg:
        _add_message("system", f"⚠️ {error_msg}\nFalling back to local knowledge base...")
    
    if _KB is None:
        _add_message("system", "Local knowledge base not loaded. Please check your KB file path.")
        return
    
    results = _KB.search(query, limit=1)
    if results:
        topic = results[0]
        _add_message("assistant", topic["answer"])
        related = _KB.get_related_topics(topic["id"], limit=3)
        if related:
            related_text = "📌 Related topics:\n"
            for rel in related:
                related_text += f"• {rel['question']}\n"
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
                        related_text = "📌 Related topics:\n"
                        for rel in results[1:4]:
                            related_text += f"• {rel['question']}\n"
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
    
    _add_message("system", "🔄 New conversation started!\n\nWhat would you like to learn about?")
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


def _toggle_cyberlearn():
    """Open CyberLearn chat window."""
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
        dpg.show_item(_CHAT_WINDOW)
        dpg.focus_item(_CHAT_WINDOW)
        _update_ai_status_display()
        return
    
    # Create chat window
    with dpg.window(label="🎓 CyberLearn Assistant (AI Powered)", tag=_CHAT_WINDOW, width=620, height=750,
                    pos=(780, 90)):
        
        # Theme
        with dpg.theme() as chat_theme:
            with dpg.theme_component(dpg.mvAll):
                dpg.add_theme_color(dpg.mvThemeCol_WindowBg, COLORS["bg_card"])
                dpg.add_theme_color(dpg.mvThemeCol_Text, COLORS["text_primary"])
                dpg.add_theme_color(dpg.mvThemeCol_Border, COLORS["border"])
                dpg.add_theme_color(dpg.mvThemeCol_Button, COLORS["accent_blue"])
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (76, 150, 246))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (46, 120, 236))
                dpg.add_theme_style(dpg.mvStyleVar_WindowRounding, 8)
                dpg.add_theme_style(dpg.mvStyleVar_ChildRounding, 6)
                dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 6)
        
        dpg.bind_item_theme(_CHAT_WINDOW, chat_theme)
        
        # Header
        with dpg.group(horizontal=True):
            dpg.add_text("🎓 CyberLearn Assistant", color=COLORS["accent_blue"])
            dpg.add_spacer(width=-1)
            # AI status badge
            with dpg.theme() as badge_theme:
                with dpg.theme_component(dpg.mvAll):
                    if _AI_ENABLED:
                        dpg.add_theme_color(dpg.mvThemeCol_Button, (40, 167, 69, 50))
                        dpg.add_theme_color(dpg.mvThemeCol_Text, (40, 167, 69))
                    else:
                        dpg.add_theme_color(dpg.mvThemeCol_Button, (255, 193, 7, 50))
                        dpg.add_theme_color(dpg.mvThemeCol_Text, (255, 193, 7))
            badge = dpg.add_text(tag=_AI_STATUS_TEXT, wrap=0)
            dpg.bind_item_theme(badge, badge_theme)
            _update_ai_status_display()
        
        dpg.add_text("AI-powered cybersecurity educator • Ask anything!", color=COLORS["text_secondary"])
        dpg.add_spacer(height=10)
        
        # Search / Ask area
        dpg.add_text("Ask:", color=COLORS["text_secondary"])
        dpg.add_spacer(height=5)
        with dpg.group(horizontal=True):
            dpg.add_input_text(
                tag=_SEARCH_INPUT,
                default_value="",
                width=-120,
                hint="e.g. 'What is a Trojan?' • 'How to prevent phishing?'",
                callback=_on_search_click,
                on_enter=True
            )
            dpg.add_button(label="Send", width=80, height=32, callback=_on_search_click)
            dpg.add_button(label="New Chat", tag=_NEW_CHAT_BTN, width=90, height=32, callback=_on_new_chat_click)
            # Style New Chat button slightly differently
            with dpg.theme() as nc_theme:
                with dpg.theme_component(dpg.mvButton):
                    dpg.add_theme_color(dpg.mvThemeCol_Button, (108, 117, 125))
                    dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (130, 139, 147))
                    dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (90, 98, 104))
            dpg.bind_item_theme(_NEW_CHAT_BTN, nc_theme)
        
        dpg.add_spacer(height=10)
        
        # Chat history
        dpg.add_text("Chat:", color=COLORS["text_secondary"])
        dpg.add_spacer(height=5)
        with dpg.child_window(width=-1, height=330, border=True, tag="cyberlearn_chat_child"):
            dpg.add_spacer(height=10)
            with dpg.group(horizontal=True):
                dpg.add_spacer(width=10)
                dpg.add_text("", tag=_MESSAGES_CONTAINER, wrap=560, color=COLORS["text_primary"])
        
        dpg.add_spacer(height=10)
        
        # Popular / Suggested topics
        dpg.add_text("� Suggested Questions:", color=COLORS["text_secondary"])
        dpg.add_spacer(height=5)
        with dpg.child_window(width=-1, height=130, border=True):
            questions = _KB.get_all_questions() if _KB and _KB.all_topics else [
                "What is a Trojan and how does it differ from a virus?",
                "What is ransomware and how does it work?",
                "What is a computer worm?",
                "What is phishing and how to prevent it?",
                "What is malware entropy analysis?",
                "How do machine learning malware detectors work?"
            ]
            for i, question in enumerate(questions[:6]):
                btn_label = (question[:55] + "...") if len(question) > 55 else question
                btn_tag = f"{_SUGGESTION_PREFIX}{i}"
                dpg.add_button(
                    label=btn_label,
                    width=-1,
                    height=32,
                    tag=btn_tag,
                    callback=_on_suggestion_click,
                    user_data=question
                )
                dpg.add_spacer(height=4)
        
        dpg.add_spacer(height=10)
        
        # Footer status
        with dpg.group(horizontal=True):
            kb_count = len(_KB.all_topics) if _KB and _KB.all_topics else 0
            dpg.add_text("Ready", tag=_STATUS_TEXT, color=COLORS["text_secondary"])
            dpg.add_spacer(width=-1)
            dpg.add_text(f"KB Topics: {kb_count}", color=COLORS["text_secondary"])
        
        # Initial welcome message (only once)
        if not _messages:
            welcome_extra = ""
            if not _AI_ENABLED:
                welcome_extra = (
                    "\n\n⚠️ No API key configured yet. Go to Settings > AI API Settings "
                    "to add your OpenRouter key. Using local knowledge base mode."
                )
            _add_message("system",
                "👋 Welcome to CyberLearn Assistant!\n\n"
                "I'm an AI-powered cybersecurity educator. I can explain concepts, "
                "describe malware types, teach detection techniques, and more.\n\n"
                "Tips:\n"
                "• Type any question and press Enter or click Send\n"
                "• Click suggested questions below to get started\n"
                "• Ask follow-up questions - I remember our conversation!\n"
                "• Click 'New Chat' to start fresh\n\n"
                "What would you like to learn about?" + welcome_extra
            )


def create_floating_button():
    """Create a FLOATING button in BOTTOM-RIGHT CORNER!"""
    if dpg.does_item_exist(_FLOATING_BUTTON):
        return
    
    with dpg.window(label="", tag=_FLOATING_BUTTON, 
                  no_title_bar=True, no_resize=True, no_scrollbar=True,
                  no_move=False, no_background=True,
                  width=80, height=80,
                  pos=(1480, 820)):
        
        # Theme for button
        with dpg.theme() as btn_theme:
            with dpg.theme_component(dpg.mvAll):
                dpg.add_theme_color(dpg.mvThemeCol_Button, COLORS["accent_blue"])
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (76, 150, 246))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (46, 120, 236))
                dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 50)
        
        dpg.add_spacer(height=10)
        with dpg.group(horizontal=True):
            dpg.add_spacer(width=10)
            btn = dpg.add_button(
                label="🎓",
                width=60,
                height=60,
                callback=_toggle_cyberlearn
            )
            dpg.bind_item_theme(btn, btn_theme)


def init_cyberlearn_for_dpg():
    """Initialize CyberLearn! Must be called after main_content exists!"""
    global _KB, _AI_CLIENT, _AI_ENABLED
    
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
