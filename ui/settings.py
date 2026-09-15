import dearpygui.dearpygui as dpg
from ui.theme import COLORS
import threading
import sys
import os
import json
import socket
import tempfile
import webbrowser
from urllib.parse import urlencode
from urllib.request import urlopen

import system.notifications.telegram as tg
from system.mobile_pairing import generate_pairing_payload, mobile_status_payload, SYSTEM_ID

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


def get_active_local_address():
    candidates = []
    try:
        addrs = socket.getaddrinfo(socket.gethostname(), None, type=socket.SOCK_DGRAM)
        for item in addrs:
            ip = item[4][0]
            if ip and ip != "127.0.0.1":
                candidates.append(ip)
    except Exception:
        pass
    try:
        for intf in socket.if_nameindex():
            name = intf[1]
            if not name or name.startswith("lo"):
                continue
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                    s.connect(("8.8.8.8", 80))
                    ip = s.getsockname()[0]
                    if ip and ip != "127.0.0.1":
                        candidates.append(ip)
            except Exception:
                pass
    except Exception:
        pass
    seen = set()
    uniq = []
    for ip in candidates:
        if ip not in seen:
            seen.add(ip)
            uniq.append(ip)
    for ip in uniq:
        if ip.startswith(("192.168.", "10.", "172.")):
            return ip
    return uniq[0] if uniq else "127.0.0.1"


def _generate_qr_file_and_payload():
    import qrcode
    host = get_active_local_address()
    port = int(os.environ.get("SERVER_PORT", "5001"))
    api_url = f"http://127.0.0.1:{port}/api/mobile/qr?{urlencode({'host': host, 'port': port})}"
    with urlopen(api_url, timeout=3) as response:
        api_payload = json.loads(response.read().decode("utf-8"))
    payload = json.loads(api_payload["qr_payload"])
    payload["apk_url"] = f"http://{host}:{port}/mobile/download"
    setup_url = f"http://{host}:{port}/mobile/setup"
    qr_value = f"{setup_url}?{urlencode({'pairing_token': payload['pairing_token'], 'port': payload['port'], 'system_id': payload['system_id']})}"
    qr_file = os.path.join(tempfile.gettempdir(), f"ayawrus_mobile_pair_{os.getpid()}.png")
    qr = qrcode.QRCode(version=2, box_size=6, border=2)
    qr.add_data(qr_value)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGBA")
    img.save(qr_file)
    return qr_file, payload


def regenerate_mobile_qr():
    try:
        qr_file, payload = _generate_qr_file_and_payload()

        if dpg.does_item_exist("mobile_qr_modal"):
            dpg.delete_item("mobile_qr_modal")
        if dpg.does_item_exist("mobile_qr_image"):
            dpg.delete_item("mobile_qr_image")
        if dpg.does_item_exist("mobile_qr_texture"):
            dpg.delete_item("mobile_qr_texture")

        width, height, channels, data = dpg.load_image(qr_file)
        if not dpg.does_item_exist("mobile_qr_texture_registry"):
            dpg.add_texture_registry(tag="mobile_qr_texture_registry")
        dpg.add_static_texture(width, height, data, parent="mobile_qr_texture_registry", tag="mobile_qr_texture")

        dpg.add_image("mobile_qr_texture", parent="mobile_qr_parent", tag="mobile_qr_image", width=150, height=150)

        if dpg.does_item_exist("mobile_qr_status"):
            dpg.set_value("mobile_qr_status", f"Status: Mobile Connection Available\nSystem Name: {socket.gethostname()}\nLocal Address: {payload['host']}:{payload['port']}\nSystem ID: {SYSTEM_ID}")
        if dpg.does_item_exist("mobile_qr_expiry"):
            dpg.set_value("mobile_qr_expiry", f"Pairing code expires in: {payload['expires_at']}")
        return payload
    except Exception as exc:
        if dpg.does_item_exist("mobile_qr_status"):
            dpg.set_value("mobile_qr_status", f"QR generation unavailable: {exc}")
        return None


def show_qr_modal():
    if not dpg.does_item_exist("mobile_qr_modal"):
        with dpg.window(label="AYAWrus Mobile Pairing QR", tag="mobile_qr_modal", width=420, height=420, modal=True):
            dpg.add_text("Scan this QR code with AYAWrus Mobile", color=COLORS["text_primary"])
            dpg.add_spacer(height=10)
            with dpg.group(horizontal=True):
                dpg.add_spacer(width=90)
                dpg.add_image("mobile_qr_texture", width=220, height=220)
            dpg.add_spacer(height=10)
            dpg.add_text("System: AYAWrus", color=COLORS["text_secondary"])
            dpg.add_button(label="Close", width=100, height=34, callback=lambda: dpg.hide_item("mobile_qr_modal"))
    dpg.show_item("mobile_qr_modal")
    dpg.focus_item("mobile_qr_modal")


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
            dpg.add_text("Configure AI API settings and mobile pairing", color=COLORS["text_secondary"])
            dpg.add_spacer(height=15)

            with dpg.child_window(width=-1, height=420, border=False):
                dpg.add_text("AYAWrus Settings", color=COLORS["text_primary"])
                dpg.add_spacing(count=8)
                status = mobile_status_payload()
                connection_status = "Status: Mobile Connection Available" if status.get("connected_devices", 0) >= 0 else "Status: Mobile Connection Available"
                dpg.add_text(connection_status, color=COLORS["accent_blue"])
                dpg.add_text(f"System Name: {socket.gethostname()}", color=COLORS["text_primary"])
                local_address = get_active_local_address()
                dpg.add_text(f"Local Address: {local_address}:5000", color=COLORS["text_primary"])
                dpg.add_text(f"System ID: {SYSTEM_ID}", color=COLORS["text_secondary"])
                dpg.add_text("Pair Mobile Device", color=COLORS["text_primary"])
                dpg.add_spacer(height=8)
                with dpg.group(tag="mobile_qr_parent"):
                    pass
                dpg.add_spacer(height=6)
                dpg.add_button(label="View QR Code", width=150, height=36, callback=show_qr_modal)
                dpg.add_spacer(height=10)
                dpg.add_button(label="Generate New QR", width=180, height=36, callback=regenerate_mobile_qr)
                dpg.add_spacer(height=10)
                dpg.add_text("Pairing code expires in: 05:00", tag="mobile_qr_expiry", color=COLORS["text_secondary"])
                dpg.add_spacer(height=10)
                dpg.add_text("", tag="mobile_qr_status", color=COLORS["text_secondary"])

            dpg.add_spacer(height=20)

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

                with dpg.group(horizontal=True):
                    dpg.add_button(label="Instruction", width=150, height=36, callback=show_instruction_modal)
                    dpg.add_button(label="Save Settings", width=150, height=36, callback=save_settings)

                dpg.add_spacer(height=10)
                dpg.add_text("", tag="settings_status", color=COLORS["text_secondary"])

    with dpg.theme() as btn_theme:
        with dpg.theme_component(dpg.mvButton):
            dpg.add_theme_color(dpg.mvThemeCol_Button, COLORS["accent_blue"])
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (76, 150, 246))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (46, 120, 236))

    refresh_settings()
    regenerate_mobile_qr()
