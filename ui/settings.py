import dearpygui.dearpygui as dpg
from ui.theme import COLORS
import threading
import sys
import os

# Add parent directory to path to import Malware_System
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    import Malware_System as ms
    BACKEND_AVAILABLE = True
except Exception as e:
    print(f"Warning: Could not load Malware_System backend: {e}")
    BACKEND_AVAILABLE = False


def refresh_settings():
    """Refresh settings view"""
    config = ms.load_config()
    if dpg.does_item_exist("telegram_token"):
        dpg.set_value("telegram_token", config.get("telegram_bot_token", ""))
    if dpg.does_item_exist("telegram_chat_id"):
        dpg.set_value("telegram_chat_id", config.get("telegram_chat_id", ""))
    if dpg.does_item_exist("ai_api_url"):
        dpg.set_value("ai_api_url", config.get("ai_api_url", ""))
    # Do not pre-fill API key in UI for security, but allow editing if stored
    if dpg.does_item_exist("ai_api_key"):
        dpg.set_value("ai_api_key", config.get("ai_api_key", ""))


def send_report_to_telegram():
    """Send a full scan report to Telegram"""
    if dpg.does_item_exist("report_status"):
        dpg.set_value("report_status", "Sending report...")
    
    def send_in_thread():
        try:
            success = ms.send_scan_report()
            if dpg.does_item_exist("report_status"):
                if success:
                    dpg.set_value("report_status", "Report sent!")
                else:
                    dpg.set_value("report_status", "Failed to send report!")
        except Exception as e:
            if dpg.does_item_exist("report_status"):
                dpg.set_value("report_status", f"Error: {e}")
            print(f"Error: {e}")
    
    threading.Thread(target=send_in_thread, daemon=True).start()


def save_settings():
    """Save settings"""
    config = {
        "telegram_bot_token": dpg.get_value("telegram_token"),
        "telegram_chat_id": dpg.get_value("telegram_chat_id"),
        "ai_api_url": dpg.get_value("ai_api_url"),
        # Store API key only if provided; empty string will remove it from config
        "ai_api_key": dpg.get_value("ai_api_key")
    }
    ms.save_config(config)
    if dpg.does_item_exist("settings_status"):
        dpg.set_value("settings_status", "Settings saved!")


def test_telegram():
    """Test Telegram notification"""
    save_settings()
    success = ms.send_telegram_notification(
        "[OK] Test Notification\n"
        "Your Telegram bot is configured correctly!"
    )
    if dpg.does_item_exist("settings_status"):
        if success:
            dpg.set_value("settings_status", "Test notification sent!")
        else:
            dpg.set_value("settings_status", "Failed to send notification!")


def build_settings(parent, fonts, icons):
    dpg.add_spacer(height=20, parent=parent)
    
    with dpg.group(horizontal=True, parent=parent):
        dpg.add_spacer(width=24)
        with dpg.group():
            dpg.add_text("Settings", tag="settings_page_title")
            dpg.bind_item_font("settings_page_title", fonts["heading"])
            dpg.add_text("Configure Telegram notifications and AI API", color=COLORS["text_secondary"])
            dpg.add_spacer(height=15)
            
            # Telegram Settings
            with dpg.child_window(width=-1, height=-1, border=False):
                dpg.add_text("Telegram Notifications", color=COLORS["text_primary"])
                dpg.add_spacer(height=5)
                
                with dpg.group():
                    dpg.add_text("Bot Token:", color=COLORS["text_secondary"])
                    dpg.add_input_text(tag="telegram_token", width=-1, password=True, hint="Enter your Telegram bot token")
                
                dpg.add_spacer(height=10)
                
                with dpg.group():
                    dpg.add_text("Chat ID:", color=COLORS["text_secondary"])
                    dpg.add_input_text(tag="telegram_chat_id", width=-1, hint="Enter your Telegram chat ID")
                
                dpg.add_spacer(height=10)
                
                with dpg.group(horizontal=True):
                    dpg.add_button(label="Test Notification", width=150, height=36, callback=test_telegram)
                    dpg.add_button(label="Save Settings", width=150, height=36, callback=save_settings)
                
                dpg.add_spacer(height=10)
                dpg.add_text("", tag="settings_status", color=COLORS["text_secondary"])
                
                dpg.add_separator()
                dpg.add_spacer(height=15)
                
                # AI API Settings
                dpg.add_text("AI API Configuration", color=COLORS["text_primary"])
                dpg.add_spacer(height=5)
                
                with dpg.group():
                    dpg.add_text("API URL:", color=COLORS["text_secondary"])
                    dpg.add_input_text(tag="ai_api_url", width=-1, hint="Enter AI API URL (e.g., https://api.openai.com/v1)")
                
                dpg.add_spacer(height=10)
                
                with dpg.group():
                    dpg.add_text("API Key:", color=COLORS["text_secondary"])
                    dpg.add_input_text(tag="ai_api_key", width=-1, password=True, hint="Enter your API key")
                
                dpg.add_spacer(height=10)
                dpg.add_button(label="Save API Settings", width=150, height=36, callback=save_settings)
                
                dpg.add_separator()
                dpg.add_spacer(height=15)
                
                # Report Sending
                dpg.add_text("Scan Report", color=COLORS["text_primary"])
                dpg.add_spacer(height=5)
                dpg.add_button(label="Send Last Report to Telegram", width=220, height=36, callback=send_report_to_telegram)
                dpg.add_spacer(height=5)
                dpg.add_text("", tag="report_status", color=COLORS["text_secondary"])
    
    # Apply theme to buttons
    with dpg.theme() as btn_theme:
        with dpg.theme_component(dpg.mvButton):
            dpg.add_theme_color(dpg.mvThemeCol_Button, COLORS["accent_blue"])
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (76, 150, 246))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (46, 120, 236))
    
    # Bind theme to all buttons we created (we need to find them, but alternatively just refresh settings on build)
    refresh_settings()
