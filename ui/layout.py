import dearpygui.dearpygui as dpg

#layout.py

# ---- Layout constants (tune here) ----
LAYOUT_DEBUG = False        # prints sizes to the terminal on every resize; set False once we're happy

SIDEBAR_WIDTH = 220        # must match the sidebar child_window width in sidebar.py
PAGE_CHROME_X = 40         # horizontal space eaten by window padding, item spacing, page padding
PAGE_CHROME_Y = 24         # vertical space eaten by window padding

MIN_CONTENT_WIDTH = 900    # content area never reports smaller than this
MIN_CONTENT_HEIGHT = 560   # (below this, the page just scrolls instead of squishing)

# name -> function(content_width, content_height)
_resize_handlers = {}


def register_resize(name, handler):
    """Pages call this once to say 'tell me when the window size changes'."""
    _resize_handlers[name] = handler


def get_content_size():
    """Size of the area to the right of the sidebar, in pixels."""
    vw = dpg.get_viewport_client_width()
    vh = dpg.get_viewport_client_height()
    w = max(MIN_CONTENT_WIDTH, vw - SIDEBAR_WIDTH - PAGE_CHROME_X)
    h = max(MIN_CONTENT_HEIGHT, vh - PAGE_CHROME_Y)
    return w, h


def apply_layout():
    w, h = get_content_size()
    if LAYOUT_DEBUG:
        print(f"[layout] content area: {w}x{h} | pages registered: {list(_resize_handlers)}")
    for name, handler in list(_resize_handlers.items()):
        try:
            handler(w, h)
        except Exception as e:
            print(f"[layout] handler '{name}' failed: {e}")


def _on_viewport_resize(sender, app_data):
    apply_layout()


def init_layout():
    """Call once after the viewport is shown. Hooks resize and runs one initial pass."""
    dpg.set_viewport_resize_callback(_on_viewport_resize)
    apply_layout()