import os
import json
import requests
from typing import List, Dict, Optional, Callable


DEFAULT_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "nvidia/nemotron-3.5-lightning:free"

SYSTEM_PROMPT = """You are CyberLearn Assistant, an educational cybersecurity chatbot.
Your purpose is to help users learn about cybersecurity concepts, malware types,
detection techniques, and best practices in a clear, friendly, and educational way.

Guidelines:
- Explain technical concepts in simple terms when needed
- Use examples to illustrate points
- Categorize information when helpful (e.g., by type, severity, prevention method)
- Encourage safe computing practices
- If asked about illegal activities, refuse to help and explain why
- Keep responses well-structured with clear sections
- Feel free to use bullet points, numbered lists, or bold text for emphasis
"""


def _get_config_path():
    """Get absolute path to config.json in system directory."""
    ai_dir = os.path.dirname(os.path.abspath(__file__))
    system_dir = os.path.dirname(ai_dir)
    return os.path.join(system_dir, "config.json")


def load_ai_config():
    """Load AI-related configuration from config.json."""
    config_path = _get_config_path()
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            config = json.load(f)
    else:
        config = {}
    return {
        "api_url": config.get("ai_api_url", DEFAULT_OPENROUTER_URL),
        "api_key": config.get("ai_api_key", ""),
        "model": config.get("ai_model", DEFAULT_MODEL),
    }


def save_ai_config(api_key: str = None, api_url: str = None, model: str = None):
    """Save AI-related configuration to config.json without overwriting other keys."""
    config_path = _get_config_path()
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            config = json.load(f)
    else:
        config = {}
    if api_key is not None:
        config["ai_api_key"] = api_key
    if api_url is not None:
        config["ai_api_url"] = api_url
    if model is not None:
        config["ai_model"] = model
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, "w") as f:
        json.dump(config, f, indent=4)


class OpenRouterClient:
    """Client for interacting with the OpenRouter API with conversation history."""

    def __init__(self, api_key: str = None, api_url: str = None, model: str = None):
        config = load_ai_config()
        self.api_key = api_key if api_key is not None else config["api_key"]
        self.api_url = api_url if api_url is not None else (config["api_url"] or DEFAULT_OPENROUTER_URL)
        self.model = model if model is not None else config["model"]
        self.messages: List[Dict] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

    def reset(self):
        """Reset conversation history."""
        self.messages = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

    def is_configured(self) -> bool:
        """Check if API key is configured."""
        return bool(self.api_key and self.api_key.strip())

    def chat(self, user_message: str, callback: Optional[Callable] = None):
        """
        Send a message and get a response synchronously.
        Preserves reasoning_details for multi-turn reasoning.
        """
        self.messages.append({"role": "user", "content": user_message})

        payload = {
            "model": self.model,
            "messages": self.messages,
            "reasoning": {"enabled": True}
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(
                url=self.api_url,
                headers=headers,
                data=json.dumps(payload),
                timeout=120
            )
            response.raise_for_status()
            result = response.json()

            assistant_msg = result["choices"][0]["message"]
            content = assistant_msg.get("content", "")
            reasoning_details = assistant_msg.get("reasoning_details")

            msg_entry = {
                "role": "assistant",
                "content": content,
            }
            if reasoning_details is not None:
                msg_entry["reasoning_details"] = reasoning_details
            self.messages.append(msg_entry)

            if callback:
                callback(True, content, None)
            return content

        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP Error {e.response.status_code if e.response else 'Unknown'}: {str(e)}"
            try:
                err_body = e.response.json() if e.response else {}
                detail = err_body.get("error", {}).get("message", str(e))
                error_msg = f"API Error: {detail}"
            except Exception:
                pass
            if callback:
                callback(False, None, error_msg)
            return None
        except requests.exceptions.ConnectionError:
            error_msg = "Connection Error: Could not reach the OpenRouter API. Please check your internet connection."
            if callback:
                callback(False, None, error_msg)
            return None
        except requests.exceptions.Timeout:
            error_msg = "Request timed out. Please try again."
            if callback:
                callback(False, None, error_msg)
            return None
        except Exception as e:
            error_msg = f"Unexpected Error: {str(e)}"
            if callback:
                callback(False, None, error_msg)
            return None

    def chat_async(self, user_message: str, callback: Callable):
        """
        Send a message asynchronously in a separate thread.
        callback(success: bool, content: str or None, error: str or None)
        """
        import threading
        thread = threading.Thread(
            target=self.chat,
            args=(user_message, callback),
            daemon=True
        )
        thread.start()
        return thread
