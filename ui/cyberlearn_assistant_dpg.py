"""
CyberLearn Assistant - DearPyGui Version
Bottom-RIGHT FLOATING BUTTON + chat window
"""

import json
import os
import threading
from datetime import datetime
from typing import List, Dict
import dearpygui.dearpygui as dpg
from ui.theme import COLORS


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
_CHAT_WINDOW = "cyberlearn_chat_window"
_MESSAGES_CONTAINER = "cyberlearn_messages"
_STATUS_TEXT = "cyberlearn_status"
_SEARCH_INPUT = "cyberlearn_search"
_SUGGESTION_PREFIX = "cyberlearn_sug_"
_FLOATING_BUTTON = "cyberlearn_floating_btn"
_work_lock = threading.Lock()
_work_in_progress = False
_messages = []


def _add_message(role, text):
    """Add message to chat."""
    timestamp = datetime.now().strftime("%H:%M")
    
    if role == "user":
        prefix = "You"
        color = COLORS["accent_blue"]
    elif role == "system":
        prefix = "ℹ️"
        color = COLORS["text_secondary"]
    else:  # assistant
        prefix = "Assistant"
        color = COLORS["accent_green"]
    
    formatted = f"[{timestamp}] {prefix}: {text}"
    _messages.append(formatted)
    
    # Keep only last 20 messages
    if len(_messages) > 20:
        _messages.pop(0)
    
    # Update display
    try:
        if dpg.does_item_exist(_MESSAGES_CONTAINER):
            full_text = "\n\n".join(_messages)
            dpg.set_value(_MESSAGES_CONTAINER, full_text)
    except Exception:
        pass


def _on_search_click():
    """Handle search button click."""
    global _work_in_progress
    
    with _work_lock:
        if _work_in_progress:
            return
        _work_in_progress = True
    
    try:
        query = dpg.get_value(_SEARCH_INPUT).strip()
        if not query:
            dpg.set_value(_STATUS_TEXT, "Please enter a search term")
            with _work_lock:
                _work_in_progress = False
            return
        
        # Add user message
        _add_message("user", f"Search: {query}")
        dpg.set_value(_SEARCH_INPUT, "")
        dpg.set_value(_STATUS_TEXT, "Searching...")
        
        # Search
        results = _KB.search(query, limit=1)
        
        if results:
            topic = results[0]
            _add_message("assistant", topic["answer"])
            
            # Add related questions
            related = _KB.get_related_topics(topic["id"], limit=3)
            if related:
                related_text = "Related topics:\n"
                for rel in related:
                    related_text += f"• {rel['question']}\n"
                _add_message("system", related_text)
            
            dpg.set_value(_STATUS_TEXT, "Ready")
        else:
            _add_message("system", "Sorry, no topics found. Try different keywords!")
            dpg.set_value(_STATUS_TEXT, "No results")
        
    except Exception as e:
        dpg.set_value(_STATUS_TEXT, f"Error: {e}")
    finally:
        with _work_lock:
            _work_in_progress = False


def _on_suggestion_click(sender, app_data, user_data):
    """Handle suggestion button click."""
    global _work_in_progress
    
    with _work_lock:
        if _work_in_progress:
            return
        _work_in_progress = True
    
    try:
        question = user_data
        
        # Add user message
        _add_message("user", question)
        dpg.set_value(_STATUS_TEXT, "Retrieving...")
        
        # Search
        results = _KB.search(question, limit=1)
        
        if results:
            topic = results[0]
            _add_message("assistant", topic["answer"])
            
            # Add related questions
            related = _KB.get_related_topics(topic["id"], limit=3)
            if related:
                related_text = "Related topics:\n"
                for rel in related:
                    related_text += f"• {rel['question']}\n"
                _add_message("system", related_text)
            
            dpg.set_value(_STATUS_TEXT, "Ready")
        else:
            _add_message("system", "Topic not found!")
            dpg.set_value(_STATUS_TEXT, "Error")
        
    except Exception as e:
        dpg.set_value(_STATUS_TEXT, f"Error: {e}")
    finally:
        with _work_lock:
            _work_in_progress = False


def _toggle_cyberlearn():
    """Open CyberLearn chat window."""
    global _KB
    
    if _KB is None:
        possible_paths = [
            "cyberlearn_knowledge_base.json",
            os.path.join(os.path.dirname(__file__), "cyberlearn_knowledge_base.json"),
            os.path.join(os.path.dirname(__file__), "..", "cyberlearn_knowledge_base.json")
        ]
        
        kb_path = None
        for path in possible_paths:
            if os.path.exists(path):
                kb_path = path
                break
        
        if kb_path:
            _KB = KnowledgeBase(kb_path)
        else:
            _KB = KnowledgeBase()
    
    if dpg.does_item_exist(_CHAT_WINDOW):
        dpg.show_item(_CHAT_WINDOW)
        dpg.focus_item(_CHAT_WINDOW)
        return
    
    # Create chat window
    with dpg.window(label="🎓 CyberLearn Assistant", tag=_CHAT_WINDOW, width=600, height=700,
                    pos=(800, 100)):
        
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
        
        dpg.add_text("🎓 CyberLearn Assistant", color=COLORS["accent_blue"])
        dpg.add_text("Learn about cybersecurity, malware, and detection", color=COLORS["text_secondary"])
        dpg.add_spacer(height=10)
        
        # Search area
        dpg.add_text("Search:", color=COLORS["text_secondary"])
        dpg.add_spacer(height=5)
        with dpg.group(horizontal=True):
            dpg.add_input_text(
                tag=_SEARCH_INPUT,
                default_value="",
                width=-1,
                hint="Type keywords (e.g., 'Trojan', 'malware', 'entropy')...",
                callback=_on_search_click,  # Trigger search on enter key
                on_enter=True
            )
            dpg.add_button(label="Search", width=80, height=32, callback=_on_search_click)
        
        dpg.add_spacer(height=10)
        
        # Chat history
        dpg.add_text("Chat:", color=COLORS["text_secondary"])
        dpg.add_spacer(height=5)
        with dpg.child_window(width=-1, height=300, border=True):
            dpg.add_spacer(height=10)
            with dpg.group(horizontal=True):
                dpg.add_spacer(width=10)
                dpg.add_text("", tag=_MESSAGES_CONTAINER, wrap=550, color=COLORS["text_primary"])
        
        dpg.add_spacer(height=10)
        
        # Popular topics
        dpg.add_text("📚 Popular Topics:", color=COLORS["text_secondary"])
        dpg.add_spacer(height=5)
        with dpg.child_window(width=-1, height=120, border=True):
            questions = _KB.get_all_questions()[:6]
            for i, question in enumerate(questions):
                btn_label = question[:45] + "..." if len(question) > 45 else question
                dpg.add_button(
                    label=btn_label,
                    width=-1,
                    height=32,
                    tag=f"{_SUGGESTION_PREFIX}{i}",
                    callback=_on_suggestion_click,
                    user_data=question
                )
                dpg.add_spacer(height=5)
        
        dpg.add_spacer(height=10)
        
        # Status
        dpg.add_text("Ready", tag=_STATUS_TEXT, color=COLORS["text_secondary"])
        
        # Initial welcome message
        if not _messages:
            _add_message("system", "👋 Welcome to CyberLearn Assistant!\n\nI'm here to help you understand cybersecurity concepts, malware types, machine learning detection, and best practices.\n\nYou can:\n• Type keywords in the search box\n• Click suggested questions below\n• Ask follow-up questions\n\nWhat would you like to learn about?")


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
    global _KB
    
    if _KB is None:
        possible_paths = [
            "cyberlearn_knowledge_base.json",
            os.path.join(os.path.dirname(__file__), "cyberlearn_knowledge_base.json"),
            os.path.join(os.path.dirname(__file__), "..", "cyberlearn_knowledge_base.json")
        ]
        
        kb_path = None
        for path in possible_paths:
            print(f"Checking for knowledge base at: {path} (exists: {os.path.exists(path)})")
            if os.path.exists(path):
                kb_path = path
                break
        
        if kb_path:
            print(f"Found knowledge base at: {kb_path}")
            _KB = KnowledgeBase(kb_path)
        else:
            print("ERROR: Could not find cyberlearn_knowledge_base.json in any path!")
            _KB = KnowledgeBase()
    
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
