import dearpygui.dearpygui as dpg
from PIL import Image
import numpy as np
import os

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
    "zap": "assets/icons/zap.png",
    "globe": "assets/icons/globe-check.png",
    "folder_search": "assets/icons/folder-search.png",
    "search": "assets/icons/search.png",
    "play": "assets/icons/play.png",
    "lock": "assets/icons/lock.png",
    "refresh": "assets/icons/refresh-cw.png",
    "trash": "assets/icons/trash-2.png",
}

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
    cache_dir = "assets/icons/_cache"
    os.makedirs(cache_dir, exist_ok=True)
    cached_path = os.path.join(cache_dir, os.path.basename(path))
    whitened.save(cached_path)
    return cached_path

def load_icons():
    textures = {}
    with dpg.texture_registry():
        for name, path in ICON_PATHS.items():
            white_path = _whiten_icon(path)
            width, height, channels, data = dpg.load_image(white_path)
            texture_tag = dpg.add_static_texture(width, height, data, tag=f"tex_{name}")
            textures[name] = texture_tag
    return textures