import dearpygui.dearpygui as dpg
from PIL import Image
import numpy as np
import os
from pathlib import Path
import sys
import tempfile

#icons.py

ICON_PATHS = {
    "shield_check": "assets/icons/shield-check.png",
    "shield_alert": "assets/icons/shield-alert.png",
    "circle_check": "assets/icons/circle-check.png",
    "octagon_alert": "assets/icons/octagon-alert.png",
    "chart_bar": "assets/icons/chart-bar.png",
    "clock_check": "assets/icons/clock-check.png",
    "monitor_cog": "assets/icons/monitor-cog.png",
    "chart_area": "assets/icons/chart-area.png",
    "layout_dashboard": "assets/icons/layout-dashboard.png",
    "scan_search": "assets/icons/scan-search.png",
    "shield_cog": "assets/icons/shield-cog-corner.png",
    "history": "assets/icons/history.png",
    "sliders_horizontal": "assets/icons/sliders-horizontal.png",
    "settings": "assets/icons/settings.png",
    "zap": "assets/icons/zap.png",
    "globe": "assets/icons/globe-check.png",
    "folder_search": "assets/icons/folder-search.png",
    "folder": "assets/icons/folder.png",
    "eye": "assets/icons/eye.png",
    "eye_off": "assets/icons/eye-off.png",
    "smartphone": "assets/icons/smartphone.png",
    "key_round": "assets/icons/key-round.png",
    "qr_code": "assets/icons/qr-code.png",
    "copy": "assets/icons/copy.png",
    "search": "assets/icons/search.png",
    "play": "assets/icons/play.png",
    "lock": "assets/icons/lock.png",
    "refresh": "assets/icons/refresh-cw.png",
    "trash": "assets/icons/trash-2.png",
    "logo": "assets/icons/ayawrus_logo.png",
    "help_chat": "assets/icons/message-circle-question-mark.png",
    "loader_circle": "assets/icons/loader-circle.png",
    "circle_x": "assets/icons/circle-x.png",
    "file_x": "assets/icons/file-x.png",
    "crosshair": "assets/icons/crosshair.png",            # Likely Targets tab icon
    "triangle_alert": "assets/icons/triangle-alert.png",  # "predictions, not confirmed" note
}

def _asset_path(relative_path):
    if getattr(sys, "frozen", False):
        resource_root = Path(sys._MEIPASS)
    else:
        resource_root = Path(__file__).resolve().parent.parent
    return str(resource_root / relative_path)


def _whiten_icon(path):
    """Converts a black/colored icon to pure white while preserving its alpha (transparency).
    This lets DPG's tint_color actually work, since tinting multiplies against pixel color —
    white pixels take the tint fully, black pixels stay black regardless of tint."""
    img = Image.open(path).convert("RGBA")
    arr = np.array(img)

    # Set RGB channels to white (255,255,255), keep original alpha channel untouched
    arr[:, :, 0] = 255
    arr[:, :, 1] = 255
    arr[:, :, 2] = 255

    whitened = Image.fromarray(arr, "RGBA")

    # Save to a temp cache folder so we don't overwrite your original downloaded files
    cache_dir = os.path.join(tempfile.gettempdir(), "ayawrus_icon_cache")
    os.makedirs(cache_dir, exist_ok=True)
    cached_path = os.path.join(cache_dir, os.path.basename(path))
    whitened.save(cached_path)
    return cached_path

def load_icons():
    textures = {}
    with dpg.texture_registry():
        for name, relative_path in ICON_PATHS.items():
            path = _asset_path(relative_path)
            if not os.path.exists(path):
                print(f"Warning [ui/icons.py]: icon file not found: {path}")
                continue
            white_path = _whiten_icon(path)
            width, height, channels, data = dpg.load_image(white_path)
            texture_tag = dpg.add_static_texture(width, height, data, tag=f"tex_{name}")
            textures[name] = texture_tag
    return textures