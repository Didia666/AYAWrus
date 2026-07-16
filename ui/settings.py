import dearpygui.dearpygui as dpg
from ui.theme import COLORS
import threading
import sys
import os
import notifications.telegram as tg
# Add parent directory to path to import Malware_System
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# try:
#     import Malware_System as ms
#     BACKEND_AVAILABLE = True
# except Exception as e:
#     print(f"Warning: Could not load Malware_System backend: {e}")
#     BACKEND_AVAILABLE = False


def refresh_settings():
    """Refresh settings view"""
    config = tg.load_config()
    if dpg.does_item_exist("telegram_token"):
        dpg.set_value("telegram_token", config.get("telegram_bot_token", ""))
    if dpg.does_item_exist("telegram_chat_id"):
        dpg.set_value("telegram_chat_id", config.get("telegram_chat_id", ""))


def send_report_to_telegram():
    """Send a full scan report to Telegram"""
    if dpg.does_item_exist("report_status"):
        dpg.set_value("report_status", "Sending report...")
    
    def send_in_thread():
        try:
            success = tg.send_scan_report()
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
        "telegram_chat_id": dpg.get_value("telegram_chat_id")
    }
    tg.save_config(config)
    if dpg.does_item_exist("settings_status"):
        dpg.set_value("settings_status", "Settings saved!")


def show_instruction_modal():
    """Show instruction modal for getting Telegram bot token and chat ID"""
    modal_tag = "telegram_instruction_modal"
    if dpg.does_item_exist(modal_tag):
        dpg.show_item(modal_tag)
        dpg.focus_item(modal_tag)
        return
    
    with dpg.window(label="Telegram Setup Instructions", tag=modal_tag, width=600, height=550, modal=True):
        with dpg.theme() as modal_theme:
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
        
        dpg.bind_item_theme(modal_tag, modal_theme)
        
        dpg.add_text("📱 How to Get Telegram Bot Token & Chat ID", color=COLORS["accent_blue"])
        dpg.add_spacer(height=10)
        
        with dpg.child_window(width=-1, height=400, border=True):
            dpg.add_spacer(height=10)
            
            # Bot Token Instructions
            dpg.add_text("Step 1: Get Bot Token", color=COLORS["text_primary"])
            dpg.add_text("1. Open Telegram and search for @BotFather", color=COLORS["text_secondary"])
            dpg.add_text("2. Start a chat with BotFather and send /newbot", color=COLORS["text_secondary"])
            dpg.add_text("3. Follow the instructions to create your bot", color=COLORS["text_secondary"])
            dpg.add_text("4. BotFather will give you a token (looks like 123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11)", color=COLORS["text_secondary"])
            dpg.add_spacer(height=15)
            
            # Chat ID Instructions
            dpg.add_text("Step 2: Get Chat ID", color=COLORS["text_primary"])
            dpg.add_text("1. Start a chat with your newly created bot", color=COLORS["text_secondary"])
            dpg.add_text("2. Send any message to the bot", color=COLORS["text_secondary"])
            dpg.add_text("3. Visit this URL in your browser (replace YOUR_BOT_TOKEN):", color=COLORS["text_secondary"])
            dpg.add_text("   https://api.telegram.org/botYOUR_BOT_TOKEN/getUpdates", color=COLORS["accent_blue"])
            dpg.add_text("4. Look for \"chat\":{\"id\":123456789...} in the response", color=COLORS["text_secondary"])
            dpg.add_text("5. Copy that number as your Chat ID", color=COLORS["text_secondary"])
            dpg.add_spacer(height=15)
            
            dpg.add_text("💡 Tips:", color=COLORS["text_primary"])
            dpg.add_text("- Keep your bot token secret!", color=COLORS["text_secondary"])
            dpg.add_text("- You can always get your token again from @BotFather with /mybots", color=COLORS["text_secondary"])
            dpg.add_spacer(height=10)
        
        dpg.add_spacer(height=10)
        with dpg.group(horizontal=True):
            dpg.add_button(label="Close", width=100, height=36, callback=lambda: dpg.hide_item(modal_tag))


def test_telegram():
    """Test Telegram notification"""
    save_settings()
    success = tg.send_telegram_notification(
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
            dpg.add_text("Configure Telegram notifications", color=COLORS["text_secondary"])
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
                    dpg.add_button(label="Instruction", width=150, height=36, callback=show_instruction_modal)
                    dpg.add_button(label="Test Notification", width=150, height=36, callback=test_telegram)
                    dpg.add_button(label="Save Settings", width=150, height=36, callback=save_settings)
                
                dpg.add_spacer(height=10)
                dpg.add_text("", tag="settings_status", color=COLORS["text_secondary"])
                
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
