import traceback
import numpy as np
import dearpygui.dearpygui as dpg
from ui.layout import register_resize

# background.py
# A soft glow + edge vignette drawn as a see-through image behind the UI.
# Clicks pass straight through it. The old flat look stays underneath, this only tints it.
# The viewport drawlist sits behind widgets so it cannot cover their text.
# Set BG_ENABLED = False to get the old look back.

BG_ENABLED = False              # False = old flat look

# ---- Glow (tune here) ----
GLOW_COLOR = (56, 130, 246)    # the blue the glow tints toward (same as accent_blue)
GLOW_ALPHA = 0.15              # strength at the glow's center, 0-1. Raise slowly: 0.12 is already clearly visible
GLOW_CENTER = (0.22, 0.06)     # position as a fraction of the window (x, y). (0, 0) is the top-left corner
GLOW_RADIUS = 0.55             # size as a fraction of the window width

# optional second glow in the opposite corner (the "option 2" idea)
GLOW2_ENABLED = False
GLOW2_COLOR = (20, 184, 166)   # a hair more teal
GLOW2_ALPHA = 0.04
GLOW2_CENTER = (0.92, 0.95)
GLOW2_RADIUS = 0.45

# ---- Edge darkening ----
VIGNETTE_ALPHA = 0.28          # how dark the very corners get, 0-1. 0 = off
VIGNETTE_COLOR = (0, 0, 0)
VIGNETTE_POWER = 1.5           # higher = the middle stays clean longer and the edges darken faster

# ---- Grain (hides banding) ----
NOISE_LEVELS = 1.0             # +/- alpha levels (out of 255). 0 = off
NOISE_SEED = 7                 # same grain every launch

TEX_W = 480                    # made small and stretched to the window (smooth and cheap)
TEX_H = 270

BG_TEX = "bg_overlay_texture"
BG_LAYER = "bg_overlay_layer"
BG_IMAGE = "bg_overlay_image"

_s = {"ready": False}


def _make_pixels():
    """Builds the overlay as a flat list of RGBA floats (0-1). Transparent where nothing is added."""
    ys, xs = np.mgrid[0:TEX_H, 0:TEX_W].astype(np.float32)
    u = xs / (TEX_W - 1)
    v = ys / (TEX_H - 1)
    ratio = TEX_H / TEX_W

    rgb = np.zeros((TEX_H, TEX_W, 3), np.float32)
    a = np.zeros((TEX_H, TEX_W), np.float32)

    def over(color, alpha_map):
        """Lays one colored layer on top of what's there (normal 'over' blending)."""
        keep = a * (1.0 - alpha_map)
        out_a = alpha_map + keep
        safe = np.maximum(out_a, 1e-6)[..., None]
        rgb[:] = (np.array(color, np.float32) * alpha_map[..., None] + rgb * keep[..., None]) / safe
        a[:] = out_a

    def glow_map(center, radius, strength):
        d = np.sqrt((u - center[0]) ** 2 + ((v - center[1]) * ratio) ** 2)
        t = np.clip(1.0 - d / radius, 0.0, 1.0)
        return (t * t * (3.0 - 2.0 * t)) * strength   # smoothstep falloff

    if VIGNETTE_ALPHA > 0:
        cx, cy = (u - 0.5) * 2.0, (v - 0.5) * 2.0
        r2 = np.clip((cx * cx + cy * cy) / 2.0, 0.0, 1.0)
        over(VIGNETTE_COLOR, VIGNETTE_ALPHA * r2 ** VIGNETTE_POWER)

    over(GLOW_COLOR, glow_map(GLOW_CENTER, GLOW_RADIUS, GLOW_ALPHA))
    if GLOW2_ENABLED:
        over(GLOW2_COLOR, glow_map(GLOW2_CENTER, GLOW2_RADIUS, GLOW2_ALPHA))

    if NOISE_LEVELS > 0:
        rng = np.random.default_rng(NOISE_SEED)
        noise = rng.uniform(-NOISE_LEVELS, NOISE_LEVELS, (TEX_H, TEX_W)).astype(np.float32) / 255.0
        a[:] = np.clip(a + noise * np.minimum(1.0, a * 40.0), 0.0, 1.0)   # no grain where there's nothing to tint

    out = np.empty((TEX_H, TEX_W, 4), np.float32)
    out[..., :3] = np.clip(rgb, 0, 255) / 255.0
    out[..., 3] = a
    return out.ravel().tolist()


def _resize(content_w, content_h):
    """Called by ui/layout.py whenever the window size changes. Stretches the overlay over the whole window."""
    if not dpg.does_item_exist(BG_IMAGE):
        return
    dpg.configure_item(BG_IMAGE, pmin=(0, 0),
                       pmax=(dpg.get_viewport_client_width(), dpg.get_viewport_client_height()))


def init_background():
    """Call once in main.py, BEFORE the pages are built, so this layer sits under the toast layer."""
    if not BG_ENABLED or _s["ready"]:
        return
    try:
        pixels = _make_pixels()
        with dpg.texture_registry():
            dpg.add_static_texture(TEX_W, TEX_H, pixels, tag=BG_TEX)
        with dpg.viewport_drawlist(front=False, tag=BG_LAYER):
            dpg.draw_image(BG_TEX, (0, 0), (1600, 900), tag=BG_IMAGE)
    except Exception:
        traceback.print_exc()
        print("[background] could not build the overlay, keeping the flat look")
        return
    register_resize("background", _resize)
    _s["ready"] = True


def set_background_clear_color():
    """Kept so main.py's import and call still work. The overlay doesn't need a clear color, so this does nothing."""
    return