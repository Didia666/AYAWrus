import traceback
import dearpygui.dearpygui as dpg

# table_text.py
# Shortens text to fit a pixel width ("game name here" -> "game name h...").
# Used by: ui/scan_threats.py, ui/exclusions.py, ui/history.py (added one at a time)

ELLIPSIS = "..."
FIT_SAFETY_PX = 6              # keeps the cut text slightly inside the cell. Raise if "..." still touches the edge


def text_width(text, font=None):
    """Pixel width of `text` drawn with `font` (None = the default font). Returns 0 if DPG can't measure yet."""
    try:
        size = dpg.get_text_size(text, font=font) if font is not None else dpg.get_text_size(text)
        return size[0] if size else 0
    except Exception:
        traceback.print_exc()
        return 0


def fit_text(text, max_w, font=None):
    """Returns `text` if it fits in max_w pixels, otherwise the longest start of it plus '...' that fits."""
    text = str(text or "")
    max_w = max_w - FIT_SAFETY_PX
    if max_w <= 0 or text_width(text, font) <= max_w:
        return text
    lo, hi = 0, len(text)          # binary search for the longest prefix that still fits with the dots
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if text_width(text[:mid].rstrip() + ELLIPSIS, font) <= max_w:
            lo = mid
        else:
            hi = mid - 1
    return text[:lo].rstrip() + ELLIPSIS if lo > 0 else ELLIPSIS