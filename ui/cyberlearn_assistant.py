"""
CyberLearn Assistant - Educational Cybersecurity Chatbot
Searchable knowledge base with keyword matching and intelligent topic suggestions.
No external APIs - fully local implementation.
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Tuple
from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtWidgets import (QPushButton, QDialog, QVBoxLayout, QHBoxLayout,
                             QLabel, QScrollArea, QWidget, QLineEdit, QTextEdit, QFrame)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QIcon


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
    """Main CyberLearn Assistant chat window."""
    
    def __init__(self, kb, parent=None):
        super().__init__(parent)
        self.kb = kb
        self.setWindowTitle("CyberLearn Assistant - Educational Chatbot")
        self.setMinimumSize(600, 700)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        
        self._typing_thread = None
        self._current_answer_widget = None
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)
        
        # Header
        header = QLabel("🎓 CyberLearn Assistant")
        header_font = QFont()
        header_font.setPointSize(13)
        header_font.setBold(True)
        header.setFont(header_font)
        header.setStyleSheet("color: #2c7be5;")
        main_layout.addWidget(header)
        
        subtitle = QLabel("Learn about cybersecurity, malware, and detection")
        subtitle_font = QFont()
        subtitle_font.setPointSize(9)
        subtitle.setFont(subtitle_font)
        subtitle.setStyleSheet("color: #666;")
        main_layout.addWidget(subtitle)
        
        main_layout.addSpacing(8)
        
        # Search bar
        search_layout = QHBoxLayout()
        search_layout.setSpacing(6)
        
        search_label = QLabel("Search:")
        search_layout.addWidget(search_label)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Type keywords (e.g., 'Trojan', 'malware', 'entropy')...")
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
        
        search_btn = QPushButton("Search")
        search_btn.setMaximumWidth(80)
        search_btn.clicked.connect(self._on_search)
        search_layout.addWidget(search_btn)
        
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
        self._add_system_message(
            "👋 Welcome to CyberLearn Assistant!\n\n"
            "I'm here to help you understand cybersecurity concepts, malware types, "
            "machine learning detection, and best practices.\n\n"
            "You can:\n"
            "• Type keywords in the search box\n"
            "• Click suggested questions below\n"
            "• Ask follow-up questions\n\n"
            "What would you like to learn about?"
        )
        
        # Suggestions area
        main_layout.addSpacing(6)
        suggestions_label = QLabel("📚 Popular Topics:")
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
        
        # Show first 6 questions as suggestions
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
    
    def _add_assistant_message_with_typing(self, topic):
        """Add assistant message with typing animation."""
        self._current_answer_widget = MessageBubble(
            role="assistant", 
            text="", 
            timestamp=datetime.now().strftime("%H:%M")
        )
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, self._current_answer_widget)
        self._scroll_to_bottom()
        
        # Get the text edit inside the bubble
        text_edit = self._current_answer_widget.findChild(QTextEdit)
        
        # Start typing
        self._typing_thread = TypingSimulator(topic["answer"], delay_ms=15)
        self._typing_thread.text_update.connect(lambda t: text_edit.setPlainText(t) if text_edit else None)
        self._typing_thread.finished.connect(self._on_typing_finished)
        self._typing_thread.start()
    
    def _add_related_questions(self, topic_id):
        """Add related questions as suggestions."""
        related = self.kb.get_related_topics(topic_id, limit=3)
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
    
    def _on_search(self):
        """Handle search."""
        query = self.search_input.text().strip()
        if not query:
            self.status_label.setText("Please enter a search term")
            return
        
        # Add user message
        self._add_user_message(f"Search: {query}")
        self.search_input.clear()
        self.status_label.setText("Searching...")
        
        # Search knowledge base
        results = self.kb.search(query, limit=1)
        
        if results:
            topic = results[0]
            QTimer.singleShot(600, lambda: self._add_assistant_message_with_typing(topic))
            QTimer.singleShot(2000, lambda: self._add_related_questions(topic["id"]))
        else:
            self.status_label.setText("No topics found")
            self._add_system_message("Sorry, I couldn't find any topics matching that search. Try different keywords!")
    
    def _on_topic_selected(self, question):
        """Handle topic selection from suggestions."""
        # Find the topic
        results = self.kb.search(question, limit=1)
        if results:
            topic = results[0]
            
            # Add user message
            self._add_user_message(question)
            self.status_label.setText("Retrieving information...")
            
            # Show answer with typing animation
            QTimer.singleShot(600, lambda: self._add_assistant_message_with_typing(topic))
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
