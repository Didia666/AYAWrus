"""
CyberLearn Assistant - Educational Cybersecurity Chatbot
Dynamic AI-powered chatbot using OpenRouter API with local knowledge base fallback.
"""

import json
import os
import sys
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtWidgets import (QPushButton, QDialog, QVBoxLayout, QHBoxLayout,
                             QLabel, QScrollArea, QWidget, QLineEdit, QTextEdit, QFrame)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QIcon

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from system.ai import OpenRouterClient, load_ai_config, save_ai_config


class KnowledgeBase:
    """Load and manage the cybersecurity knowledge base."""
    
    def __init__(self, kb_path="cyberlearn_knowledge_base.json"):
        self.kb_path = kb_path
        self.data = {}
        self.all_topics = []
        self.categories = {}
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
            self.data = {}
            self.categories = {}
    
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
        
        # Exact match on question first
        for topic in self.all_topics:
            if query_lower in topic.get("question", "").lower():
                results.append((topic, 100))  # High score for question match
        
        # Keyword matching
        for topic in self.all_topics:
            keywords = topic.get("keywords", [])
            for keyword in keywords:
                if query_lower in keyword.lower():
                    results.append((topic, 80))
                    break
        
        # Content matching (answer text)
        for topic in self.all_topics:
            if query_lower in topic.get("answer", "").lower():
                results.append((topic, 60))
        
        # Remove duplicates, keep highest score
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
        """Get related topics for a given topic."""
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
        """Get all questions for suggestion display."""
        return [t["question"] for t in self.all_topics]
    
    def get_categories_overview(self) -> List[Tuple[str, str, str]]:
        """Get (icon, name, description) for each category."""
        result = []
        for key, data in self.categories.items():
            result.append((
                data.get("icon", ""),
                data.get("name", key),
                data.get("description", "")
            ))
        return result


class TypingSimulator(QThread):
    """Simulate typing animation."""
    
    text_update = pyqtSignal(str)
    finished = pyqtSignal()
    
    def __init__(self, text, delay_ms=20):
        super().__init__()
        self.text = text
        self.delay_ms = delay_ms / 1000.0
    
    def run(self):
        """Simulate typing character by character."""
        current_text = ""
        for char in self.text:
            current_text += char
            self.text_update.emit(current_text)
            self.msleep(int(self.delay_ms * 1000))
        self.finished.emit()


class MessageBubble(QFrame):
    """Chat message bubble widget."""
    
    def __init__(self, role="user", text="", timestamp=None):
        super().__init__()
        self.role = role
        self.setFrameShape(QFrame.Shape.RoundedRect)
        self.setFrameShadow(QFrame.Shadow.Plain)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)
        
        # Timestamp
        if timestamp:
            time_label = QLabel(timestamp)
            time_font = QFont()
            time_font.setPointSize(7)
            time_label.setFont(time_font)
            time_label.setStyleSheet("color: #999;")
            layout.addWidget(time_label)
        
        # Message content
        msg_edit = QTextEdit()
        msg_edit.setReadOnly(True)
        msg_edit.setPlainText(text)
        msg_edit.setMinimumHeight(50)
        msg_edit.setMaximumWidth(450)
        msg_edit.setWordWrapMode(1)
        layout.addWidget(msg_edit)
        
        # Style based on role
        if role == "user":
            self.setStyleSheet("""
                MessageBubble {
                    background-color: #2c7be5;
                    border-radius: 12px;
                    border: 1px solid #1b6fd8;
                }
            """)
            msg_edit.setStyleSheet("""
                QTextEdit {
                    border: none;
                    background: transparent;
                    color: white;
                    padding: 0px;
                    margin: 0px;
                }
            """)
        elif role == "system":
            self.setStyleSheet("""
                MessageBubble {
                    background-color: #e8f1ff;
                    border-radius: 12px;
                    border: 1px solid #b3d9ff;
                }
            """)
            msg_edit.setStyleSheet("""
                QTextEdit {
                    border: none;
                    background: transparent;
                    color: #0056b3;
                    padding: 0px;
                    margin: 0px;
                    font-weight: bold;
                }
            """)
        else:  # assistant
            self.setStyleSheet("""
                MessageBubble {
                    background-color: #f8f9fa;
                    border-radius: 12px;
                    border: 1px solid #dee2e6;
                }
            """)
            msg_edit.setStyleSheet("""
                QTextEdit {
                    border: none;
                    background: transparent;
                    color: #333;
                    padding: 0px;
                    margin: 0px;
                }
            """)


class SuggestionButton(QPushButton):
    """Styled suggestion button."""
    
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setWordWrap(True)
        self.setMinimumHeight(40)
        self.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                border: 2px solid #ddd;
                border-radius: 8px;
                padding: 8px;
                text-align: left;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #f0f7ff;
                border: 2px solid #2c7be5;
                color: #2c7be5;
                font-weight: bold;
            }
            QPushButton:pressed {
                background-color: #2c7be5;
                color: white;
                border: 2px solid #1b6fd8;
            }
        """)


class CyberLearnWindow(QDialog):
    """Main CyberLearn Assistant chat window - AI-powered with OpenRouter API."""
    
    def __init__(self, kb, parent=None):
        super().__init__(parent)
        self.kb = kb
        self.ai_client = OpenRouterClient()
        self._ai_enabled = self.ai_client.is_configured()
        self._pending_query = None
        self._thinking_bubble = None
        
        self.setWindowTitle("CyberLearn Assistant - AI Educational Chatbot")
        self.setMinimumSize(600, 750)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        
        self._typing_thread = None
        self._current_answer_widget = None
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)
        
        # Header
        header_layout = QHBoxLayout()
        
        header = QLabel("🎓 CyberLearn Assistant")
        header_font = QFont()
        header_font.setPointSize(13)
        header_font.setBold(True)
        header.setFont(header_font)
        header.setStyleSheet("color: #2c7be5;")
        header_layout.addWidget(header)
        
        header_layout.addStretch()
        
        # AI status indicator
        ai_cfg = load_ai_config()
        self.ai_status_label = QLabel()
        self.ai_status_label.setStyleSheet("font-size: 9px; padding: 3px 8px; border-radius: 10px;")
        self._update_ai_status()
        header_layout.addWidget(self.ai_status_label)
        
        main_layout.addLayout(header_layout)
        
        subtitle_layout = QHBoxLayout()
        subtitle = QLabel("Learn about cybersecurity, malware, and detection")
        subtitle_font = QFont()
        subtitle_font.setPointSize(9)
        subtitle.setFont(subtitle_font)
        subtitle.setStyleSheet("color: #666;")
        subtitle_layout.addWidget(subtitle)
        subtitle_layout.addStretch()
        
        model_name = ai_cfg.get("model", "default")
        model_label = QLabel(f"Model: {model_name}")
        model_label_font = QFont()
        model_label_font.setPointSize(8)
        model_label.setFont(model_label_font)
        model_label.setStyleSheet("color: #888;")
        subtitle_layout.addWidget(model_label)
        
        main_layout.addLayout(subtitle_layout)
        
        main_layout.addSpacing(8)
        
        # Search / Query bar
        search_layout = QHBoxLayout()
        search_layout.setSpacing(6)
        
        search_label = QLabel("Ask:")
        search_layout.addWidget(search_label)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Ask anything about cybersecurity (e.g., 'What is a Trojan?', 'How does ransomware work?')...")
        self.search_input.returnPressed.connect(self._on_search)
        self.search_input.setStyleSheet("""
            QLineEdit {
                border: 2px solid #ddd;
                border-radius: 6px;
                padding: 6px;
                font-size: 10px;
            }
            QLineEdit:focus {
                border: 2px solid #2c7be5;
            }
        """)
        search_layout.addWidget(self.search_input)
        
        search_btn = QPushButton("Send")
        search_btn.setMaximumWidth(80)
        search_btn.clicked.connect(self._on_search)
        search_layout.addWidget(search_btn)
        
        clear_btn = QPushButton("New Chat")
        clear_btn.setMaximumWidth(90)
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                border-radius: 6px;
                padding: 5px;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
        """)
        clear_btn.clicked.connect(self._on_clear_chat)
        search_layout.addWidget(clear_btn)
        
        main_layout.addLayout(search_layout)
        
        main_layout.addSpacing(6)
        
        # Chat display area
        self.chat_area = QScrollArea(self)
        self.chat_area.setWidgetResizable(True)
        self.chat_area.setStyleSheet("""
            QScrollArea {
                border: 1px solid #ddd;
                border-radius: 8px;
                background: white;
            }
        """)
        
        self.chat_widget = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_widget)
        self.chat_layout.setContentsMargins(8, 8, 8, 8)
        self.chat_layout.setSpacing(8)
        self.chat_layout.addStretch()
        
        self.chat_area.setWidget(self.chat_widget)
        main_layout.addWidget(self.chat_area, 1)
        
        # Welcome message
        welcome_extra = ""
        if not self._ai_enabled:
            welcome_extra = (
                "\n\n⚠️ Note: No API key configured. Go to Settings > AI API Settings to add your key. "
                "Using local knowledge base for now."
            )
        self._add_system_message(
            "👋 Welcome to CyberLearn Assistant!\n\n"
            "I'm an AI-powered cybersecurity educator. I can help you understand "
            "cybersecurity concepts, malware types, machine learning detection, and best practices.\n\n"
            "You can:\n"
            "• Ask any question in the text box above\n"
            "• Click suggested questions below to get started\n"
            "• Ask follow-up questions - I remember our conversation!\n\n"
            "What would you like to learn about?" + welcome_extra
        )
        
        # Suggestions area
        main_layout.addSpacing(6)
        suggestions_label = QLabel("� Suggested Questions:")
        suggestions_font = QFont()
        suggestions_font.setPointSize(10)
        suggestions_font.setBold(True)
        suggestions_label.setFont(suggestions_font)
        main_layout.addWidget(suggestions_label)
        
        suggestions_scroll = QScrollArea(self)
        suggestions_scroll.setWidgetResizable(True)
        suggestions_scroll.setMaximumHeight(150)
        suggestions_scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid #ddd;
                border-radius: 8px;
            }
        """)
        
        suggestions_widget = QWidget()
        suggestions_layout = QVBoxLayout(suggestions_widget)
        suggestions_layout.setContentsMargins(4, 4, 4, 4)
        suggestions_layout.setSpacing(4)
        
        self.suggestion_buttons = []
        for question in self.kb.get_all_questions()[:6]:
            btn = SuggestionButton(question, self)
            btn.clicked.connect(lambda checked, q=question: self._on_topic_selected(q))
            suggestions_layout.addWidget(btn)
            self.suggestion_buttons.append(btn)
        
        suggestions_layout.addStretch()
        suggestions_scroll.setWidget(suggestions_widget)
        main_layout.addWidget(suggestions_scroll)
        
        # Status bar
        bottom_layout = QHBoxLayout()
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #666; font-size: 9px;")
        bottom_layout.addWidget(self.status_label)
        bottom_layout.addStretch()
        
        close_btn = QPushButton("Close")
        close_btn.setMaximumWidth(80)
        close_btn.clicked.connect(self.close)
        bottom_layout.addWidget(close_btn)
        main_layout.addLayout(bottom_layout)
    
    def _update_ai_status(self):
        """Update the AI status indicator label."""
        if hasattr(self, 'ai_client') and self.ai_client.is_configured():
            self.ai_status_label.setText("🤖 AI Online")
            self.ai_status_label.setStyleSheet(
                "font-size: 9px; padding: 3px 8px; border-radius: 10px;"
                "background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb;"
            )
        else:
            self.ai_status_label.setText("📚 Local Mode")
            self.ai_status_label.setStyleSheet(
                "font-size: 9px; padding: 3px 8px; border-radius: 10px;"
                "background-color: #fff3cd; color: #856404; border: 1px solid #ffeeba;"
            )
    
    def _add_system_message(self, text):
        """Add system/info message."""
        bubble = MessageBubble(role="system", text=text, timestamp=datetime.now().strftime("%H:%M"))
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, bubble)
        self._scroll_to_bottom()
    
    def _add_user_message(self, text):
        """Add user message."""
        bubble = MessageBubble(role="user", text=text, timestamp=datetime.now().strftime("%H:%M"))
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, bubble)
        self._scroll_to_bottom()
    
    def _add_thinking_bubble(self):
        """Show a loading/thinking bubble while waiting for API."""
        self._thinking_bubble = MessageBubble(
            role="assistant",
            text="🧠 Thinking...",
            timestamp=datetime.now().strftime("%H:%M")
        )
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, self._thinking_bubble)
        self._scroll_to_bottom()
    
    def _remove_thinking_bubble(self):
        """Remove the thinking bubble if it exists."""
        if self._thinking_bubble:
            self._thinking_bubble.setParent(None)
            self._thinking_bubble.deleteLater()
            self._thinking_bubble = None
    
    def _add_assistant_text_with_typing(self, text_content: str):
        """Add assistant message with typing animation using plain text."""
        self._current_answer_widget = MessageBubble(
            role="assistant",
            text="",
            timestamp=datetime.now().strftime("%H:%M")
        )
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, self._current_answer_widget)
        self._scroll_to_bottom()
        
        text_edit = self._current_answer_widget.findChild(QTextEdit)
        
        delay = 8 if len(text_content) > 1500 else (5 if len(text_content) > 500 else 12)
        self._typing_thread = TypingSimulator(text_content, delay_ms=delay)
        self._typing_thread.text_update.connect(lambda t: text_edit.setPlainText(t) if text_edit else None)
        self._typing_thread.finished.connect(self._on_typing_finished)
        self._typing_thread.start()
    
    def _add_related_questions(self, topic_id=None, fallback_query=None):
        """Add related questions as suggestions."""
        related = []
        if topic_id:
            related = self.kb.get_related_topics(topic_id, limit=3)
        elif fallback_query:
            results = self.kb.search(fallback_query, limit=3)
            related = results[1:4] if len(results) > 1 else []
        
        if related:
            related_text = "📌 You might also want to know:\n\n"
            for idx, rel_topic in enumerate(related, 1):
                related_text += f"{idx}. {rel_topic['question']}\n"
            
            bubble = MessageBubble(role="system", text=related_text)
            self.chat_layout.insertWidget(self.chat_layout.count() - 1, bubble)
            self._scroll_to_bottom()
    
    def _scroll_to_bottom(self):
        """Auto-scroll to bottom."""
        QtCore.QTimer.singleShot(100, lambda: self.chat_area.verticalScrollBar().setValue(
            self.chat_area.verticalScrollBar().maximum()
        ))
    
    def _on_typing_finished(self):
        """Called when typing animation completes."""
        self.status_label.setText("Ready")
        self._typing_thread = None
    
    def _on_clear_chat(self):
        """Clear chat history and reset AI conversation."""
        if self._typing_thread:
            self._typing_thread.terminate()
            self._typing_thread = None
        
        while self.chat_layout.count() > 1:
            item = self.chat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self.ai_client.reset()
        self._thinking_bubble = None
        self._current_answer_widget = None
        
        self._add_system_message(
            "🔄 New conversation started!\n\n"
            "What would you like to learn about?"
        )
        self.status_label.setText("Ready")
    
    def _fallback_to_kb_search(self, query: str, show_error: bool = False, error_msg: str = None):
        """Fallback to local knowledge base search when API is unavailable."""
        if show_error and error_msg:
            self._add_system_message(
                f"⚠️ {error_msg}\n\n"
                "Falling back to local knowledge base..."
            )
        
        results = self.kb.search(query, limit=1)
        
        if results:
            topic = results[0]
            QTimer.singleShot(400, lambda: self._add_assistant_text_with_typing(topic["answer"]))
            QTimer.singleShot(max(1500, int(len(topic["answer"]) * 12)), lambda: self._add_related_questions(topic["id"]))
        else:
            self.status_label.setText("No topics found")
            self._add_system_message(
                "Sorry, I couldn't find any information on that topic. "
                "Try different keywords or make sure your API key is configured in Settings."
            )
    
    def _on_ai_response(self, success: bool, content: Optional[str], error: Optional[str], original_query: str):
        """Callback when AI API response arrives."""
        self._remove_thinking_bubble()
        self.search_input.setEnabled(True)
        
        if success and content:
            self._add_assistant_text_with_typing(content)
            char_count = len(content)
            est_delay = max(1500, int(char_count * 10))
            QTimer.singleShot(est_delay, lambda: self._add_related_questions(fallback_query=original_query))
            self.status_label.setText("AI response received")
        else:
            self._fallback_to_kb_search(original_query, show_error=True, error_msg=error or "AI request failed")
    
    def _on_search(self):
        """Handle user query - send to AI API with KB fallback."""
        query = self.search_input.text().strip()
        if not query:
            self.status_label.setText("Please enter a question")
            return
        
        if self._thinking_bubble:
            self.status_label.setText("Still processing previous request...")
            return
        
        self._add_user_message(query)
        self.search_input.clear()
        self.search_input.setEnabled(False)
        self._pending_query = query
        
        if self._ai_enabled:
            self.status_label.setText("Contacting AI...")
            self._add_thinking_bubble()
            
            captured_query = query
            self.ai_client.chat_async(
                query,
                callback=lambda s, c, e: QTimer.singleShot(0, lambda: self._on_ai_response(s, c, e, captured_query))
            )
        else:
            self.status_label.setText("Searching local knowledge base...")
            self._fallback_to_kb_search(query)
    
    def _on_topic_selected(self, question):
        """Handle topic selection from suggestions - send to AI."""
        if self._thinking_bubble:
            self.status_label.setText("Still processing previous request...")
            return
        
        self._add_user_message(question)
        self.search_input.setEnabled(False)
        self._pending_query = question
        
        if self._ai_enabled:
            self.status_label.setText("Generating AI answer...")
            self._add_thinking_bubble()
            
            captured_question = question
            self.ai_client.chat_async(
                question,
                callback=lambda s, c, e: QTimer.singleShot(0, lambda: self._on_ai_response(s, c, e, captured_question))
            )
        else:
            self.status_label.setText("Retrieving from knowledge base...")
            results = self.kb.search(question, limit=1)
            if results:
                topic = results[0]
                QTimer.singleShot(400, lambda: self._add_assistant_text_with_typing(topic["answer"]))
                QTimer.singleShot(2000, lambda: self._add_related_questions(topic["id"]))


class FloatingButton(QtWidgets.QWidget):
    """Floating button to open CyberLearn Assistant."""
    
    def __init__(self, kb, parent=None):
        super().__init__(parent)
        self.kb = kb
        self.chat_window = None
        
        # Setup floating window
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Button
        self.button = QPushButton("🎓")
        self.button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                          stop:0 #2c7be5, stop:1 #1b6fd8);
                color: white;
                border-radius: 30px;
                border: none;
                padding: 5px;
                font-size: 22px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                          stop:0 #1b6fd8, stop:1 #0f4fa6);
            }
            QPushButton:pressed {
                background: #0f4fa6;
            }
        """)
        self.button.setFixedSize(60, 60)
        self.button.setCursor(QtGui.QCursor(Qt.CursorShape.PointingHandCursor))
        self.button.clicked.connect(self._open_chat)
        
        layout.addWidget(self.button)
        
        # Position at bottom-right
        screen = QtWidgets.QApplication.primaryScreen().availableGeometry()
        margin = 20
        x = screen.right() - 60 - margin
        y = screen.bottom() - 60 - margin
        self.move(x, y)
    
    def _open_chat(self):
        """Open or focus chat window."""
        if self.chat_window is None or not self.chat_window.isVisible():
            self.chat_window = CyberLearnWindow(self.kb, self)
            geo = self.geometry()
            screen = QtWidgets.QApplication.primaryScreen().availableGeometry()
            
            # Position near button
            wx = screen.right() - 620
            wy = screen.bottom() - 720
            self.chat_window.move(max(10, wx), max(10, wy))
            self.chat_window.show()
            self.chat_window.raise_()
        else:
            self.chat_window.activateWindow()
            self.chat_window.raise_()


# Global instance
_kb = None
_floating_instance = None


def initialize_cyberlearn():
    """Initialize CyberLearn knowledge base."""
    global _kb
    if _kb is None:
        kb_path = "cyberlearn_knowledge_base.json"
        if not os.path.exists(kb_path):
            kb_path = os.path.join(os.path.dirname(__file__), "..", "cyberlearn_knowledge_base.json")
        _kb = KnowledgeBase(kb_path)


def show_cyberlearn_widget():
    """Show floating CyberLearn widget."""
    global _kb, _floating_instance
    
    if _kb is None:
        initialize_cyberlearn()
    
    if _floating_instance is None:
        _floating_instance = FloatingButton(_kb)
        _floating_instance.show()
    else:
        _floating_instance.raise_()


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    initialize_cyberlearn()
    show_cyberlearn_widget()
    sys.exit(app.exec())
