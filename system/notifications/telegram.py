import os
import json
import requests
import threading
from system.config import CONFIG_FILE

def load_config():
    """Load configuration from config.json"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}

def save_config(config):
    """Save configuration to config.json"""
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

def _send_telegram_sync(message):
    """Synchronous Telegram notification (internal use)"""
    config = load_config()
    bot_token = config.get("telegram_bot_token")
    chat_id = config.get("telegram_chat_id")
    
    if not bot_token or not chat_id:
        return False
    
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        params = {
            "chat_id": chat_id,
            "text": message
        }
        # Add timeout to prevent hanging
        response = requests.post(url, params=params, timeout=5)
        return response.status_code == 200
    except Exception:
        return False

def send_telegram_notification(message):
    """Send notification via Telegram bot asynchronously"""
    thread = threading.Thread(target=_send_telegram_sync, args=(message,), daemon=True)
    thread.start()
    return True
