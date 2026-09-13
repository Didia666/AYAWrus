import dearpygui.dearpygui as dpg
from ui.theme import COLORS
import threading
import sys
import os
import system.notifications.telegram as tg
import webbrowser
# Add parent directory to path to import Malware_System
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# try:
#     import Malware_System as ms
#     BACKEND_AVAILABLE = True
# except Exception as e:
#     print(f"Warning: Could not load Malware_System backend: {e}")
#     BACKEND_AVAILABLE = False


AVAILABLE_AI_MODELS = [
    "nvidia/nemotron-3.5-lightning:free",
    "nvidia/nemotron-70b-reward:free",
    "mistralai/mistral-7b-instruct-v0.3",
    "meta-llama/llama-3.1-8b-instruct:free",
    "meta-llama/llama-3.1-70b-instruct:free",
    "openai/chatgpt-4o-latest",
    "anthropic/claude-3.5-sonnet",
    "google/gemini-pro-1.5",
    "custom",
]


def refresh_settings():
    """Refresh settings view"""
    config = tg.load_config()
    if dpg.does_item_exist("telegram_token"):
        dpg.set_value("telegram_token", config.get("telegram_bot_token", ""))
    if dpg.does_item_exist("telegram_chat_id"):
        dpg.set_value("telegram_chat_id", config.get("telegram_chat_id", ""))
    if dpg.does_item_exist("ai_api_url"):
        dpg.set_value("ai_api_url", config.get("ai_api_url", ""))
    if dpg.does_item_exist("ai_api_key"):
        dpg.set_value("ai_api_key", config.get("ai_api_key", ""))
    saved_model = config.get("ai_model", "nvidia/nemotron-3.5-lightning:free")
    if dpg.does_item_exist("ai_model_combo"):
        if saved_model in AVAILABLE_AI_MODELS:
            dpg.set_value("ai_model_combo", saved_model)
        else:
            dpg.set_value("ai_model_combo", "custom")
    if dpg.does_item_exist("ai_model_custom"):
        if saved_model not in AVAILABLE_AI_MODELS or saved_model == "custom":
            dpg.set_value("ai_model_custom", saved_model if saved_model != "custom" else "")


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
    config = tg.load_config()
    config["telegram_bot_token"] = dpg.get_value("telegram_token")
    config["telegram_chat_id"] = dpg.get_value("telegram_chat_id")
    config["ai_api_url"] = dpg.get_value("ai_api_url")
    config["ai_api_key"] = dpg.get_value("ai_api_key")
    model_combo = dpg.get_value("ai_model_combo") if dpg.does_item_exist("ai_model_combo") else None
    if model_combo and model_combo != "custom":
        config["ai_model"] = model_combo
    elif dpg.does_item_exist("ai_model_custom"):
        custom_model = dpg.get_value("ai_model_custom").strip()
        if custom_model:
            config["ai_model"] = custom_model
    tg.save_config(config)
    if dpg.does_item_exist("settings_status"):
        dpg.set_value("settings_status", "Settings saved!")


def show_instruction_modal():
    """Show instruction modal for AI API setup"""
    modal_tag = "ai_api_instruction_modal"
    if dpg.does_item_exist(modal_tag):
        dpg.show_item(modal_tag)
        dpg.focus_item(modal_tag)
        return
    
    with dpg.window(label="AI API Setup Instructions", tag=modal_tag, width=700, height=600, modal=True):
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
        
        dpg.add_text("🔑 How to Set Up AI API", color=COLORS["accent_blue"])
        dpg.add_spacer(height=10)
        
        with dpg.child_window(width=-1, height=450, border=True):
            dpg.add_spacer(height=10)
            
            # OpenRouter Setup Instructions
            dpg.add_text("Step 1: Get Your API Key", color=COLORS["text_primary"])
            dpg.add_text("1. Visit https://openrouter.ai", color=COLORS["text_secondary"])
            dpg.add_text("2. Sign up or log in to your account", color=COLORS["text_secondary"])
            dpg.add_text("3. Go to Settings > API Keys", color=COLORS["text_secondary"])
            dpg.add_text("4. Click 'Create Key' and copy your API key", color=COLORS["text_secondary"])
            dpg.add_spacer(height=15)
            
            # API Configuration
            dpg.add_text("Step 2: Configure API Settings", color=COLORS["text_primary"])
            dpg.add_text("API URL (default): https://openrouter.ai/api/v1/chat/completions", color=COLORS["text_secondary"])
            dpg.add_spacer(height=5)
            dpg.add_text("Paste your API Key in the 'API Key' field", color=COLORS["text_secondary"])
            dpg.add_spacer(height=15)
            
            # Model Selection
            dpg.add_text("Step 3: Choose AI Model", color=COLORS["text_primary"])
            dpg.add_text("Select from available models or enter a custom model name:", color=COLORS["text_secondary"])
            dpg.add_text("• nvidia/nemotron-3.5-lightning:free (recommended)", color=COLORS["text_secondary"])
            dpg.add_text("• meta-llama/llama-3.1-8b-instruct:free", color=COLORS["text_secondary"])
            dpg.add_text("• mistralai/mistral-7b-instruct-v0.3", color=COLORS["text_secondary"])
            dpg.add_text("• openai/chatgpt-4o-latest (paid)", color=COLORS["text_secondary"])
            dpg.add_text("• anthropic/claude-3.5-sonnet (paid)", color=COLORS["text_secondary"])
            dpg.add_spacer(height=15)
            
            dpg.add_text("💡 Tips:", color=COLORS["text_primary"])
            dpg.add_text("- Keep your API key secret and never share it", color=COLORS["text_secondary"])
            dpg.add_text("- Free models have rate limits", color=COLORS["text_secondary"])
            dpg.add_text("- Visit OpenRouter.ai for more model options", color=COLORS["text_secondary"])
            dpg.add_spacer(height=10)
        
        dpg.add_spacer(height=10)
        with dpg.group(horizontal=True):
            dpg.add_button(label="Visit OpenRouter.ai", width=150, height=36, callback=lambda: webbrowser.open("https://openrouter.ai"))
            dpg.add_button(label="Close", width=100, height=36, callback=lambda: dpg.hide_item(modal_tag))





def build_settings(parent, fonts, icons):
    dpg.add_spacer(height=20, parent=parent)
    
    with dpg.group(horizontal=True, parent=parent):
        dpg.add_spacer(width=24)
        with dpg.group():
            dpg.add_text("Settings", tag="settings_page_title")
            dpg.bind_item_font("settings_page_title", fonts["heading"])
            dpg.add_text("Configure AI API settings", color=COLORS["text_secondary"])
            dpg.add_spacer(height=15)
            
            # AI API Settings
            with dpg.child_window(width=-1, height=-1, border=False):
                dpg.add_text("AI API Settings", color=COLORS["text_primary"])
                dpg.add_spacer(height=5)
                
                with dpg.group():
                    dpg.add_text("API URL:", color=COLORS["text_secondary"])
                    dpg.add_input_text(tag="ai_api_url", width=-1, hint="e.g. https://openrouter.ai/api/v1/chat/completions")
                
                dpg.add_spacer(height=10)
                
                with dpg.group():
                    dpg.add_text("API Key:", color=COLORS["text_secondary"])
                    dpg.add_input_text(tag="ai_api_key", width=-1, password=True, hint="Enter your OpenRouter or compatible API key")
                
                dpg.add_spacer(height=10)
                
                with dpg.group():
                    dpg.add_text("AI Model:", color=COLORS["text_secondary"])
                    dpg.add_combo(
                        tag="ai_model_combo",
                        items=AVAILABLE_AI_MODELS,
                        default_value="nvidia/nemotron-3.5-lightning:free",
                        width=-1,
                        callback=lambda: dpg.configure_item(
                            "ai_model_custom",
                            show=(dpg.get_value("ai_model_combo") == "custom")
                        )
                    )
                
                dpg.add_spacer(height=5)
                
                with dpg.group(tag="ai_model_custom_group"):
                    dpg.add_input_text(
                        tag="ai_model_custom",
                        width=-1,
                        hint="Enter custom model name (e.g. 'openai/gpt-4')",
                        show=False
                    )
                
                dpg.add_spacer(height=15)
                
                # Buttons below AI API Settings
                with dpg.group(horizontal=True):
                    dpg.add_button(label="Instruction", width=150, height=36, callback=show_instruction_modal)
                    dpg.add_button(label="Save Settings", width=150, height=36, callback=save_settings)
                
                dpg.add_spacer(height=10)
                dpg.add_text("", tag="settings_status", color=COLORS["text_secondary"])
    
    # Apply theme to buttons
    with dpg.theme() as btn_theme:
        with dpg.theme_component(dpg.mvButton):
            dpg.add_theme_color(dpg.mvThemeCol_Button, COLORS["accent_blue"])
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (76, 150, 246))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (46, 120, 236))
    
    # Bind theme to all buttons we created (we need to find them, but alternatively just refresh settings on build)
    refresh_settings()
