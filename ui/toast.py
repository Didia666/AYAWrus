"""
toast.py - a small pop-up message at the bottom of the window (like on mobile).

Use from any tab:
    from ui.toast import init_toast, show_toast
    init_toast()                          # once, in the tab's build function
    show_toast("Saved", "success")        # kinds: "success", "warning", "error", "info"

It never blocks clicks. It fades in, stays a few seconds, fades out. A new toast replaces the current one.
show_toast only stores the message; a ticker thread does all the drawing, so calling it from a callback is safe.

Used by: ui/quarantine.py (Restore / Delete results), ui/exclusions.py (add / remove results).      <- add new users to this list
"""
import time
import threading
import traceback
import dearpygui.dearpygui as dpg
from ui.theme import COLORS
from ui.layout import SIDEBAR_WIDTH

# toast.py

# ---- Look (tune here) ----
TOAST_HEIGHT = 44
TOAST_PAD_X = 18
TOAST_ROUNDING = 12
TOAST_FONT_SIZE = 18           # must match FONT_BODY_SIZE in ui/fonts.py, otherwise the width is measured wrong
TOAST_DOT_RADIUS = 5
TOAST_DOT_GAP = 12             # space between the colored dot and the text
TOAST_BG = (*COLORS["bg_card"], 245)
TOAST_BORDER_ALPHA = 200
TOAST_BORDER_THICKNESS = 1.5
TOAST_BOTTOM_MARGIN = 36       # distance from the bottom of the window
TOAST_SIDE_MARGIN = 24         # never closer than this to the sidebar / right edge

# ---- Timing ----
TOAST_SECONDS = 2.8            # fully visible time
TOAST_FADE_IN = 0.18
TOAST_FADE_OUT = 0.35
TOAST_SLIDE_PX = 14            # how far it rises while fading in (0 = no slide)
TOAST_FRAME_SECONDS = 0.016    # ~60 fps ticker

# ---- Only used if DPG can't measure text ----
TOAST_FALLBACK_CHAR_W = 9
TOAST_FALLBACK_LINE_H = 22
TOAST_MIN_CHARS = 10           # long messages are shortened with "..." but never below this

KIND_COLORS = {
    "success": COLORS["accent_green"],
    "warning": COLORS["accent_orange"],
    "error": COLORS["accent_red"],
    "info": COLORS["accent_blue"],
}

LAYER = "toast_layer"
RECT = "toast_rect"
DOT = "toast_dot"
TEXT = "toast_text"

_s = {"ready": False, "pending": None, "mode": "idle", "t0": 0.0,
      "text": " ", "kind": "info", "tw": 0.0, "th": 20.0}


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------

def _measure(text):
    try:
        size = dpg.get_text_size(text)
        if size:
            return size[0], size[1]
    except Exception:
        print("[toast] could not measure the text, using the fallback size")
    return len(text) * TOAST_FALLBACK_CHAR_W, TOAST_FALLBACK_LINE_H


def _load(text, kind):
    """Takes over a new message: shortens it if it would not fit, and measures it."""
    vw = dpg.get_viewport_client_width()
    avail = vw - SIDEBAR_WIDTH - 2 * TOAST_SIDE_MARGIN - 2 * TOAST_PAD_X - 2 * TOAST_DOT_RADIUS - TOAST_DOT_GAP
    tw, th = _measure(text)
    while tw > avail and len(text) > TOAST_MIN_CHARS:
        text = text[:-4].rstrip() + "..."
        tw, th = _measure(text)
    _s["text"], _s["kind"], _s["tw"], _s["th"] = text, kind, tw, th


def _paint(a, rise):
    """a = opacity 0..1, rise = how many px the toast is currently lowered (it slides up as it appears)."""
    color = KIND_COLORS.get(_s["kind"], KIND_COLORS["info"])
    vw = dpg.get_viewport_client_width()
    vh = dpg.get_viewport_client_height()
    box_w = _s["tw"] + 2 * TOAST_PAD_X + 2 * TOAST_DOT_RADIUS + TOAST_DOT_GAP
    cx = SIDEBAR_WIDTH + (vw - SIDEBAR_WIDTH) / 2        # centered on the content area, not the whole window
    x0 = cx - box_w / 2
    y0 = vh - TOAST_BOTTOM_MARGIN - TOAST_HEIGHT + rise
    cy = y0 + TOAST_HEIGHT / 2
    dot_x = x0 + TOAST_PAD_X + TOAST_DOT_RADIUS

    dpg.configure_item(RECT, pmin=(x0, y0), pmax=(x0 + box_w, y0 + TOAST_HEIGHT),
                       fill=(*TOAST_BG[:3], int(TOAST_BG[3] * a)), color=(*color, int(TOAST_BORDER_ALPHA * a)))
    dpg.configure_item(DOT, center=(dot_x, cy), fill=(*color, int(255 * a)), color=(*color, int(255 * a)))
    dpg.configure_item(TEXT, pos=(dot_x + TOAST_DOT_RADIUS + TOAST_DOT_GAP, cy - _s["th"] / 2),
                       text=_s["text"], color=(*COLORS["text_primary"], int(255 * a)))


def _step():
    now = time.time()
    pending = _s["pending"]
    if pending is not None:
        _s["pending"] = None
        _load(pending[0], pending[1])
        if _s["mode"] == "idle":
            _s["mode"] = "in"            # nothing on screen: fade in
        else:
            _s["mode"] = "hold"          # already visible: swap the text instantly
        _s["t0"] = now

    mode = _s["mode"]
    t = now - _s["t0"]
    if mode == "in":
        p = min(1.0, t / TOAST_FADE_IN)
        a = p * (2.0 - p)                # ease-out
        if p >= 1.0:
            _s["mode"], _s["t0"] = "hold", now
    elif mode == "hold":
        a = 1.0
        if t >= TOAST_SECONDS:
            _s["mode"], _s["t0"] = "out", now
    else:                                # "out"
        p = min(1.0, t / TOAST_FADE_OUT)
        a = 1.0 - p
        if p >= 1.0:
            _s["mode"] = "idle"
    _paint(a, (1.0 - a) * TOAST_SLIDE_PX)


def _ticker_loop():
    while True:
        time.sleep(TOAST_FRAME_SECONDS)
        if _s["mode"] == "idle" and _s["pending"] is None:
            continue
        try:
            with dpg.mutex():
                _step()
        except Exception:
            traceback.print_exc()
            _s["mode"] = "idle"          # fail-safe: never leave a toast stuck on screen
            _s["pending"] = None
            try:
                with dpg.mutex():
                    _paint(0.0, 0.0)
            except Exception:
                traceback.print_exc()


# ---------------------------------------------------------------------------
# Public
# ---------------------------------------------------------------------------

def init_toast():
    """Call once from a tab's build function (safe to call again)."""
    if _s["ready"]:
        return
    with dpg.viewport_drawlist(front=True, tag=LAYER):
        dpg.draw_rectangle((0, 0), (10, 10), color=(0, 0, 0, 0), fill=(0, 0, 0, 0),
                           rounding=TOAST_ROUNDING, thickness=TOAST_BORDER_THICKNESS, tag=RECT)
        dpg.draw_circle((0, 0), TOAST_DOT_RADIUS, color=(0, 0, 0, 0), fill=(0, 0, 0, 0), tag=DOT)
        dpg.draw_text((0, 0), " ", color=(255, 255, 255, 0), size=TOAST_FONT_SIZE, tag=TEXT)
    _s["ready"] = True
    threading.Thread(target=_ticker_loop, daemon=True).start()


def show_toast(message, kind="info"):
    """Shows a message. kind: "success", "warning", "error" or "info"."""
    if not _s["ready"]:
        print(f"[toast] not initialised, message dropped: {message}")
        return
    _s["pending"] = (str(message), kind)