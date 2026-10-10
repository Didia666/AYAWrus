import os
import json
import math
import time
import threading
import traceback
import numpy as np
import dearpygui.dearpygui as dpg
from ui.theme import COLORS

# boot.py
# The intro: skull flickers in, "WE KEEP YOU SAFE" fades in word by word, then everything fades out and the app shows.
# Backdrop: a soft glow behind the skull (synced to its blinks, then a slow breathing), a light vignette, and thin
# vertical scan lines on the left and right that get stronger toward the window border.
# It is a full-window cover on the FRONT viewport layer (same trick as ui/toast.py and ui/background.py), so it loads nothing.
# Clicks pass through it, so a click or Esc skips it. If anything fails, the cover removes itself.

# ---- When it plays ----
BOOT_MODE = "always"           # "always" | "once_per_boot" (once until the PC restarts) | "never". A "boot_mode" key in ui_prefs.json overrides this
BOOT_SAME_TOLERANCE = 120      # seconds: two boot-time readings closer than this count as the same PC start
PREFS_FILE = "ui_prefs.json"   # next to main.py. Add it to .gitignore (it's per machine)

# ---- Content ----
SKULL_PATH = "assets/icons/skull.png"   # transparent PNG, shown at its native size
SKULL_SCALE = 1.0
SKULL_FLICKER = True           # False = plain cut-in
SKULL_FLICKER_PATTERN = (1, 0, 1, 0, 1)   # 1 = visible, 0 = hidden, one step each. It stays visible after the last step
SKULL_FLICKER_STEP = 0.07      # seconds per flicker step
TAGLINE = "WE KEEP YOU SAFE"
ACCENT_WORDS = ("SAFE",)       # these words pop in the accent color

# ---- Look ----
BOOT_BG = COLORS["bg_main"]    # the cover color
TEXT_SIZE = 28                 # tagline size in px (drawn with the default font, so it is scaled up)
TEXT_COLOR = COLORS["text_primary"]
ACCENT_COLOR = (96, 165, 250)  # a little brighter than accent_blue so SAFE pops
WORD_GAP = 14                  # px between words
SKULL_TEXT_GAP = 30            # px between the skull and the tagline
BLOCK_BIAS = 10                # raises the whole block a little above the exact center
BODY_FONT_SIZE = 18            # FONT_BODY_SIZE in ui/fonts.py. Words are measured with the default font, then scaled by TEXT_SIZE / this
FALLBACK_CHAR_W = 0.62         # only used if DPG can't measure text: character width as a share of TEXT_SIZE

# ---- Backdrop: glow behind the skull ----
GLOW_ENABLED = True
GLOW_COLOR = (40, 150, 230)    # cyan-leaning blue, pulled from the skull's lighter edge
GLOW_ALPHA = 0.10              # brightness at the center, 0-1. "Faint but you notice it" is about 0.15-0.25
GLOW_RADIUS = 250              # px from the skull's center to where the glow ends
GLOW_RISE_LAG = 0.05           # seconds the glow takes to catch up when the skull blinks ON (a little lag = light spilling out)
GLOW_FALL_LAG = 0.03           # same, when the skull blinks OFF
GLOW_BREATH_DEPTH = 0.30       # after the blinks the glow slowly dips by this much and comes back. 0 = steady
GLOW_BREATH_PERIOD = 2.4       # seconds for one breath
GLOW_TEX = 128                 # texture size (it gets stretched, smooth)

# ---- Backdrop: vignette ----
VIGNETTE_ENABLED = True
VIGNETTE_ALPHA = 0.35          # how dark the very corners get, 0-1
VIGNETTE_POWER = 1.6           # higher = the middle stays clean longer
VIGNETTE_TEX_W = 128
VIGNETTE_TEX_H = 72

# ---- Backdrop: scan lines on the left and right ----
LINES_ENABLED = True
LINES_REACH = 0.15             # share of the window width, from each border inward, that has lines
LINES_SPACING = 8              # px between one group and the next
LINES_PER_GROUP = 2            # 2 = a pair of thin lines per step, 1 = single lines
LINES_PAIR_GAP = 3             # px between the two lines of a pair
LINES_EDGE_INSET = 2           # px from the window border to the first line
LINES_COLOR = COLORS["accent_blue"]
LINES_MAX_ALPHA = 0.32         # opacity of the lines right at the border, 0-1 (they fade to nothing at the inner end)
LINES_POWER = 1.7              # higher = the lines stay faint longer and ramp up near the border
LINES_FADE_IN = 0.60           # seconds for the lines to fade in at the start
LINES_MAX_REACH_PX = 700       # size of the line pool. Raise only for huge windows (width * LINES_REACH above this gets capped)

# ---- Timing (seconds from the first rendered frame) ----
TEXT_START = 0.65              # when the first word starts to appear
WORD_STEP = 0.35               # time between one word starting and the next
WORD_FADE = 0.30               # fade-in time of each word
HOLD = 0.70                    # pause after the last word is fully in
FADE_OUT = 0.50                # everything fading out
SKIP_FADE = 0.25               # fade-out when the user clicks or presses Esc
START_FRAME = 3                # the clock starts once DPG has drawn this many frames
FRAME_SECONDS = 0.016          # ~60 fps ticker

LAYER = "boot_layer"
RECT = "boot_rect"
VIGNETTE = "boot_vignette"
VIGNETTE_TEX_TAG = "boot_vignette_tex"
GLOW = "boot_glow"
GLOW_TEX_TAG = "boot_glow_tex"
SKULL = "boot_skull"
SKULL_TEX = "boot_skull_tex"
WORD_TAG = "boot_word_{i}"
LINE_TAG = "boot_line_{n}"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORDS = TAGLINE.split()
LINES_POOL = 2 * LINES_PER_GROUP * (int(LINES_MAX_REACH_PX // LINES_SPACING) + 1)

_s = {"mode": "wait", "t0": None, "skip_t": None, "widths": None,
      "skull_w": 0.0, "skull_h": 0.0,
      "last_t": 0.0, "glow": 0.0,
      "vw": None, "vh": None, "lines": [], "lines_used": 0, "lines_shown": None,
      "glow_on": False, "vignette_on": False, "lines_on": False}


# ---------------------------------------------------------------------------
# When to play (prefs file + PC boot time)
# ---------------------------------------------------------------------------

def _load_prefs():
    path = os.path.join(ROOT, PREFS_FILE)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        traceback.print_exc()
        return {}


def _save_prefs(prefs):
    try:
        with open(os.path.join(ROOT, PREFS_FILE), "w") as f:
            json.dump(prefs, f, indent=4)
    except Exception:
        traceback.print_exc()


def _boot_timestamp():
    """When this PC started (Windows), as a unix time. None if it can't be read."""
    try:
        import ctypes
        kernel = ctypes.windll.kernel32
        kernel.GetTickCount64.restype = ctypes.c_ulonglong
        return time.time() - kernel.GetTickCount64() / 1000.0
    except Exception:
        traceback.print_exc()
        return None


def _should_play():
    prefs = _load_prefs()
    mode = prefs.get("boot_mode", BOOT_MODE)
    if mode == "never":
        return False
    if mode == "always":
        return True
    if mode == "once_per_boot":
        boot = _boot_timestamp()
        if boot is None:
            print("[boot] can't read the PC start time, playing the intro every launch instead")
            return True
        last = prefs.get("last_boot_ts")
        if last is not None and abs(float(last) - boot) <= BOOT_SAME_TOLERANCE:
            return False
        prefs["last_boot_ts"] = boot
        _save_prefs(prefs)
        return True
    print(f"[boot] unknown boot mode '{mode}', playing the intro")
    return True


# ---------------------------------------------------------------------------
# Backdrop textures (made once, small, stretched over the window)
# ---------------------------------------------------------------------------

def _glow_pixels():
    n = GLOW_TEX
    ys, xs = np.mgrid[0:n, 0:n].astype(np.float32)
    d = np.sqrt((xs / (n - 1) * 2 - 1) ** 2 + (ys / (n - 1) * 2 - 1) ** 2)
    t = np.clip(1.0 - d, 0.0, 1.0)
    alpha = (t * t * (3.0 - 2.0 * t)) * GLOW_ALPHA            # smoothstep falloff
    rgba = np.empty((n, n, 4), np.float32)
    rgba[..., :3] = np.array(GLOW_COLOR, np.float32) / 255.0
    rgba[..., 3] = alpha
    return rgba.ravel().tolist()


def _vignette_pixels():
    w, h = VIGNETTE_TEX_W, VIGNETTE_TEX_H
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = (xs / (w - 1) - 0.5) * 2.0, (ys / (h - 1) - 0.5) * 2.0
    r2 = np.clip((cx * cx + cy * cy) / 2.0, 0.0, 1.0)
    rgba = np.zeros((h, w, 4), np.float32)
    rgba[..., 3] = VIGNETTE_ALPHA * r2 ** VIGNETTE_POWER
    return rgba.ravel().tolist()


# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------

def _end_times():
    """(when the fade-out starts, how long it lasts)."""
    if _s["skip_t"] is not None:
        return _s["skip_t"], SKIP_FADE
    return TEXT_START + (len(WORDS) - 1) * WORD_STEP + WORD_FADE + HOLD, FADE_OUT


def _alphas(t):
    """(skull opacity, [word opacities], overall opacity), all 0-1."""
    if SKULL_FLICKER and SKULL_FLICKER_PATTERN:
        idx = int(t / SKULL_FLICKER_STEP)
        skull = float(SKULL_FLICKER_PATTERN[idx]) if idx < len(SKULL_FLICKER_PATTERN) else 1.0
    else:
        skull = 1.0
    words = []
    for i in range(len(WORDS)):
        p = max(0.0, min(1.0, (t - (TEXT_START + i * WORD_STEP)) / WORD_FADE))
        words.append(p * (2.0 - p))   # ease-out
    end, dur = _end_times()
    g = 1.0 if t < end else max(0.0, 1.0 - (t - end) / dur)
    return skull, words, g


def _glow_target(t):
    """Where the glow wants to be: follows the skull's blinks, then breathes slowly."""
    flicker_len = 0.0
    if SKULL_FLICKER and SKULL_FLICKER_PATTERN:
        flicker_len = len(SKULL_FLICKER_PATTERN) * SKULL_FLICKER_STEP
        if t < flicker_len:
            return float(SKULL_FLICKER_PATTERN[int(t / SKULL_FLICKER_STEP)])
    tau = t - flicker_len
    if GLOW_BREATH_DEPTH <= 0:
        return 1.0
    return 1.0 - GLOW_BREATH_DEPTH * (0.5 - 0.5 * math.cos(2 * math.pi * tau / GLOW_BREATH_PERIOD))   # starts at 1, so no jump after the blinks


def _glow_level(t):
    """The glow's current brightness 0-1: the target, but a few frames late (smoothed)."""
    dt = max(0.0, t - _s["last_t"])
    _s["last_t"] = t
    target = _glow_target(t)
    lag = GLOW_RISE_LAG if target > _s["glow"] else GLOW_FALL_LAG
    k = 1.0 - math.exp(-dt / max(lag, 1e-4))
    _s["glow"] += (target - _s["glow"]) * k
    return _s["glow"]


def _measure_words():
    """Width of each word at TEXT_SIZE. Done once the window is drawing, because text measured at build time can be wrong."""
    scale = TEXT_SIZE / BODY_FONT_SIZE
    widths = []
    for w in WORDS:
        try:
            size = dpg.get_text_size(w)
            widths.append(size[0] * scale if size else len(w) * TEXT_SIZE * FALLBACK_CHAR_W)
        except Exception:
            print("[boot] could not measure the text, using the fallback width")
            widths.append(len(w) * TEXT_SIZE * FALLBACK_CHAR_W)
    return widths


# ---------------------------------------------------------------------------
# Scan lines (individual lines, so they stay 1px and crisp at any window size)
# ---------------------------------------------------------------------------

def _layout_lines(vw, vh):
    """Places the lines for this window size and remembers each line's own strength. Runs on the first frame and on resize."""
    reach = vw * LINES_REACH
    entries = []
    n = 0
    for side in (0, 1):
        k = 0
        while n < LINES_POOL:
            base = LINES_EDGE_INSET + k * LINES_SPACING
            if base >= reach:
                break
            strength = LINES_MAX_ALPHA * (1.0 - base / reach) ** LINES_POWER   # 1 at the border, 0 at the inner end
            for j in range(LINES_PER_GROUP):
                if n >= LINES_POOL:
                    break
                x = base + j * LINES_PAIR_GAP
                x = x if side == 0 else vw - x
                dpg.configure_item(LINE_TAG.format(n=n), p1=(x + 0.5, 0), p2=(x + 0.5, vh))
                entries.append((n, strength))
                n += 1
            k += 1
    for m in range(n, _s["lines_used"]):   # lines used before a resize but not any more
        dpg.configure_item(LINE_TAG.format(n=m), color=(0, 0, 0, 0))
    _s["lines"] = entries
    _s["lines_used"] = n
    _s["lines_shown"] = None


def _apply_lines(scale):
    for n, strength in _s["lines"]:
        dpg.configure_item(LINE_TAG.format(n=n), color=(*LINES_COLOR, int(255 * strength * scale)))


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------

def _paint(t):
    vw = dpg.get_viewport_client_width()
    vh = dpg.get_viewport_client_height()
    if t is None:
        skull_a, word_a, g = 0.0, [0.0] * len(WORDS), 1.0
    else:
        skull_a, word_a, g = _alphas(t)

    dpg.configure_item(RECT, pmin=(0, 0), pmax=(vw, vh), fill=(*BOOT_BG, int(255 * g)))

    if _s["vignette_on"]:
        dpg.configure_item(VIGNETTE, pmin=(0, 0), pmax=(vw, vh), color=(255, 255, 255, int(255 * g)))

    sw, sh = _s["skull_w"], _s["skull_h"]
    text_h = TEXT_SIZE * 1.2
    total_h = sh + (SKULL_TEXT_GAP if sh else 0) + text_h
    y0 = (vh - total_h) / 2 - BLOCK_BIAS

    if _s["glow_on"]:
        level = 0.0 if t is None else _glow_level(t)
        cx = vw / 2
        cy = y0 + (sh / 2 if sh else total_h / 2)
        dpg.configure_item(GLOW, pmin=(cx - GLOW_RADIUS, cy - GLOW_RADIUS), pmax=(cx + GLOW_RADIUS, cy + GLOW_RADIUS),
                           color=(255, 255, 255, int(255 * max(0.0, min(1.0, level)) * g)))

    if _s["lines_on"]:
        if vw != _s["vw"] or vh != _s["vh"]:
            _s["vw"], _s["vh"] = vw, vh
            _layout_lines(vw, vh)
        scale = 0.0 if t is None else min(1.0, t / max(LINES_FADE_IN, 1e-4)) * g
        shown = int(scale * 255)
        if shown != _s["lines_shown"]:        # only touch the lines when their brightness actually changed
            _s["lines_shown"] = shown
            _apply_lines(scale)

    if sh:
        x = (vw - sw) / 2
        dpg.configure_item(SKULL, pmin=(x, y0), pmax=(x + sw, y0 + sh),
                           color=(255, 255, 255, int(255 * skull_a * g)))

    widths = _s["widths"]
    if widths:
        text_y = y0 + sh + (SKULL_TEXT_GAP if sh else 0)
        x = (vw - (sum(widths) + WORD_GAP * (len(widths) - 1))) / 2
        for i, word in enumerate(WORDS):
            base = ACCENT_COLOR if word in ACCENT_WORDS else TEXT_COLOR
            dpg.configure_item(WORD_TAG.format(i=i), pos=(x, text_y), color=(*base, int(255 * word_a[i] * g)))
            x += widths[i] + WORD_GAP
    return g <= 0.0 and t is not None


def _finish():
    _s["mode"] = "done"
    if dpg.does_item_exist(LAYER):
        dpg.delete_item(LAYER)
    for tex in (SKULL_TEX, GLOW_TEX_TAG, VIGNETTE_TEX_TAG):
        if dpg.does_item_exist(tex):
            dpg.delete_item(tex)


def _ticker_loop():
    while _s["mode"] != "done":
        time.sleep(FRAME_SECONDS)
        try:
            with dpg.mutex():
                if _s["t0"] is None:
                    if dpg.get_frame_count() >= START_FRAME:   # the clock starts on the first drawn frames, not at import
                        _s["t0"] = time.time()
                        _s["widths"] = _measure_words()
                    else:
                        continue
                t = time.time() - _s["t0"]
                if _paint(t):
                    _finish()
        except Exception:
            traceback.print_exc()
            print("[boot] intro failed, removing the cover")
            try:
                with dpg.mutex():
                    _finish()
            except Exception:
                traceback.print_exc()
            return


def _skip(sender=None, app_data=None, user_data=None):
    """Click or Esc: start the quick fade-out (only once, and only while the intro is running)."""
    if _s["mode"] == "run" and _s["skip_t"] is None and _s["t0"] is not None:
        _s["skip_t"] = max(time.time() - _s["t0"], 0.0)


# ---------------------------------------------------------------------------
# Public
# ---------------------------------------------------------------------------

def init_boot():
    """Call once in main.py AFTER everything else is built, so this cover is the top layer."""
    if not _should_play():
        return
    try:
        loaded = dpg.load_image(os.path.join(ROOT, SKULL_PATH))
        if loaded:
            w, h, _channels, data = loaded
            with dpg.texture_registry():
                dpg.add_static_texture(w, h, data, tag=SKULL_TEX)
            _s["skull_w"], _s["skull_h"] = w * SKULL_SCALE, h * SKULL_SCALE
        else:
            print(f"[boot] skull image not found or unreadable: {SKULL_PATH} (the intro plays without it)")
    except Exception:
        traceback.print_exc()
        _s["skull_w"] = _s["skull_h"] = 0.0

    # backdrop textures: if one fails, that piece is skipped and the rest still plays
    try:
        with dpg.texture_registry():
            if GLOW_ENABLED:
                dpg.add_static_texture(GLOW_TEX, GLOW_TEX, _glow_pixels(), tag=GLOW_TEX_TAG)
                _s["glow_on"] = True
            if VIGNETTE_ENABLED:
                dpg.add_static_texture(VIGNETTE_TEX_W, VIGNETTE_TEX_H, _vignette_pixels(), tag=VIGNETTE_TEX_TAG)
                _s["vignette_on"] = True
    except Exception:
        traceback.print_exc()
        print("[boot] could not build the backdrop textures, playing without the glow / vignette")
        _s["glow_on"] = _s["vignette_on"] = False
    _s["lines_on"] = LINES_ENABLED

    try:
        with dpg.viewport_drawlist(front=True, tag=LAYER):
            dpg.draw_rectangle((0, 0), (1600, 900), color=(0, 0, 0, 0), fill=(*BOOT_BG, 255), tag=RECT)   # opaque from the very first frame
            if _s["vignette_on"]:
                dpg.draw_image(VIGNETTE_TEX_TAG, (0, 0), (1, 1), color=(255, 255, 255, 0), tag=VIGNETTE)
            if _s["glow_on"]:
                dpg.draw_image(GLOW_TEX_TAG, (0, 0), (1, 1), color=(255, 255, 255, 0), tag=GLOW)
            if _s["lines_on"]:
                for n in range(LINES_POOL):
                    dpg.draw_line((0, 0), (0, 0), color=(0, 0, 0, 0), thickness=1, tag=LINE_TAG.format(n=n))
            if _s["skull_h"]:
                dpg.draw_image(SKULL_TEX, (0, 0), (1, 1), color=(255, 255, 255, 0), tag=SKULL)
            for i, word in enumerate(WORDS):
                dpg.draw_text((0, 0), word, color=(255, 255, 255, 0), size=TEXT_SIZE, tag=WORD_TAG.format(i=i))
        with dpg.handler_registry():
            dpg.add_key_press_handler(dpg.mvKey_Escape, callback=_skip)
            dpg.add_mouse_click_handler(callback=_skip)
    except Exception:
        traceback.print_exc()
        print("[boot] could not build the intro, skipping it")
        if dpg.does_item_exist(LAYER):
            dpg.delete_item(LAYER)
        return

    _s["mode"] = "run"
    threading.Thread(target=_ticker_loop, daemon=True).start()