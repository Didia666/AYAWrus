import dearpygui.dearpygui as dpg
from ui.theme import COLORS
import threading
import time
import sys
import os
import traceback
from ui.activity_feed import _rebuild_activity_feed

# Add parent directory to path to import Malware_System
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    import quarantines.quarantine as qq
    import config as cfg
    import security.exclusions as se
    import Malware_System as ms
    import notifications.telegram as tg
    BACKEND_AVAILABLE = True
except Exception as e:
    print(f"Warning: Could not load Malware_System backend: {e}")
    BACKEND_AVAILABLE = False

#scan.py

CARD_GAP = 20
CONTENT_WIDTH = 400 * 3 + CARD_GAP * 2  # 1240 — shared by cards row and empty-state container
SELECTED_SCAN = "quick"
SCAN_IN_PROGRESS = False
CURRENT_CUSTOM_PATH = ""
DETECTED_THREATS = []
SELECTED_QUARANTINE_ITEMS = set()

READY_HEADING_OFFSET = 567
START_BUTTON_OFFSET = 535
EMPTY_STATE_WIDTH = 1272

SCAN_TYPES = [
    {"key": "quick", "icon": "zap", "label": "Quick Scan", "subtitle": "Checks common areas",
     "label_offset": 155, "subtitle_offset": 120, "subtitle_gap": 1},
    {"key": "full", "icon": "globe", "label": "Full Scan", "subtitle": "Checks all drives and files",
     "label_offset": 160, "subtitle_offset": 108, "subtitle_gap": 1},
    {"key": "custom", "icon": "folder_search", "label": "Custom Scan", "subtitle": "Choose specific folders",
     "label_offset": 148, "subtitle_offset": 118, "subtitle_gap": 1},
]

# Define malware detection steps with descriptions and icons
DETECTION_STEPS = [
    {"title": "File\nSelected", "icon": "search", "description": "Step 1: Target file is loaded and its path verified by the engine."},
    {"title": "File Type\nVerification", "icon": "monitor_cog", "description": "Step 2: Magic bytes and extension analyzed. Confirms PE32/PE64 format."},
    {"title": "PE Analysis", "icon": "chart_area", "description": "Step 3: Portable Executable headers, sections, imports, and entropy calculated."},
    {"title": "Feature\nExtraction", "icon": "chart_bar", "description": "Step 4: 168 features extracted: API calls, section names, byte histograms, metadata."},
    {"title": "Random\nForest AI", "icon": "shield_cog", "description": "Step 5: Feature vector evaluated by 200-tree ensemble model trained on labeled malware."},
    {"title": "Prediction", "icon": "shield_check", "description": "Step 6: Model outputs class (Benign/Malicious) and confidence percentage."},
    {"title": "Quarantine", "icon": "octagon_alert", "description": "Step 7: If malicious, file is isolated from the filesystem in the secure vault."}
]

SELECTED_STEP = 0
g_icons = None  # Global variable to store icons for step card rebuilding
g_step_elements = []  # List to store (step_card_tag, image_tag, text_tag) for each step

def _card_theme(is_active):
    with dpg.theme() as theme:
        with dpg.theme_component(dpg.mvChildWindow):
            bg = COLORS["bg_card"] if is_active else COLORS["bg_sidebar"]
            border = COLORS["accent_blue"] if is_active else COLORS["border"]
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, bg)
            dpg.add_theme_color(dpg.mvThemeCol_Border, border)
    return theme

def _select_scan(sender, app_data, user_data):
    global SELECTED_SCAN
    SELECTED_SCAN = user_data
    for scan in SCAN_TYPES:
        is_active = scan["key"] == SELECTED_SCAN
        dpg.bind_item_theme(f"scan_{scan['key']}_card", _card_theme(is_active))
    _update_start_button()
    _rebuild_custom_path_controls()

def scan_card(key, icon_texture, label, subtitle, label_offset, subtitle_offset, subtitle_gap, fonts, icons):
    is_active = key == SELECTED_SCAN
    with dpg.child_window(width=400, height=120, tag=f"scan_{key}_card", no_scrollbar=True):
        dpg.add_spacer(height=12)
        with dpg.group(horizontal=True):
            dpg.add_spacer(width=175)
            dpg.add_image(icon_texture, width=28, height=28,
                         tint_color=COLORS["accent_blue"] if is_active else COLORS["text_secondary"])
        dpg.add_spacer(height=6)
        with dpg.group(horizontal=True):
            dpg.add_spacer(width=label_offset)
            dpg.add_text(label, color=COLORS["text_primary"] if is_active else COLORS["text_secondary"])
        dpg.add_spacer(height=subtitle_gap)
        with dpg.group(horizontal=True):
            dpg.add_spacer(width=subtitle_offset)
            dpg.add_text(subtitle, color=COLORS["text_secondary"])

    dpg.bind_item_theme(f"scan_{key}_card", _card_theme(is_active))

def _handle_click(sender, app_data):
    # First check for scan type card clicks
    for scan in SCAN_TYPES:
        tag = f"scan_{scan['key']}_card"
        if dpg.is_item_hovered(tag):
            _select_scan(sender, app_data, scan['key'])
            return
    # Now check for step card clicks
    for i, (step_tag, _, _) in enumerate(g_step_elements):
        if dpg.is_item_hovered(step_tag):
            _on_step_click(sender, app_data, i)
            return

def _rebuild_custom_path_controls():
    if dpg.does_item_exist("custom_controls_group"):
        dpg.delete_item("custom_controls_group")
    
    with dpg.group(horizontal=True, parent="scan_button_group", tag="custom_controls_group"):
        if SELECTED_SCAN == "custom":
            dpg.add_spacer(width=10)
            dpg.add_button(label="Select Path", tag="select_path_btn", width=120, height=36,
                          callback=lambda: dpg.show_item("custom_scan_picker"))
            dpg.add_text(CURRENT_CUSTOM_PATH or "No path selected", tag="custom_path_display", color=COLORS["text_secondary"])

def _toggle_select_item(sender, app_data, user_data):
    global SELECTED_QUARANTINE_ITEMS
    file_path = user_data
    is_checked = dpg.get_value(sender)  # Get checkbox state
    print(f"Toggling {file_path}: {is_checked}")
    if is_checked:
        SELECTED_QUARANTINE_ITEMS.add(file_path)
    else:
        if file_path in SELECTED_QUARANTINE_ITEMS:
            SELECTED_QUARANTINE_ITEMS.remove(file_path)

def _quarantine_selected(sender, app_data):
    global DETECTED_THREATS, SELECTED_QUARANTINE_ITEMS
    print(f"Quarantining: {SELECTED_QUARANTINE_ITEMS}")
    if not SELECTED_QUARANTINE_ITEMS:
        print("No items selected!")
        return
    for file_path in SELECTED_QUARANTINE_ITEMS:
        try:
            result = qq.quarantine_file(file_path)
            print(f"Quarantined {file_path}: {result}")
        except Exception as e:
            print(f"Error quarantining {file_path}: {e}")
    DETECTED_THREATS = [t for t in DETECTED_THREATS if t["file_path"] not in SELECTED_QUARANTINE_ITEMS]
    SELECTED_QUARANTINE_ITEMS = set()
    _rebuild_threats_table()
    from ui.history import _rebuild_history
    _rebuild_history()
    _rebuild_activity_feed()


def _open_xai_panel(sender, app_data, user_data):
    """Open the XAI explanation panel for the selected threat."""

    threat = user_data

    # If the panel already exists, delete it first
    if dpg.does_item_exist("xai_panel_window"):
        dpg.delete_item("xai_panel_window")

    with dpg.window(
        label="🎓 AI Explanation Panel",
        tag="xai_panel_window",
        width=800,
        height=700,
        pos=(200, 100),
        modal=True,
        on_close=lambda: dpg.delete_item("xai_panel_window")
    ):

        with dpg.theme() as xai_theme:
            with dpg.theme_component(dpg.mvAll):
                dpg.add_theme_color(dpg.mvThemeCol_WindowBg, COLORS["bg_card"])
                dpg.add_theme_color(dpg.mvThemeCol_Text, COLORS["text_primary"])
                dpg.add_theme_color(dpg.mvThemeCol_Border, COLORS["border"])
                dpg.add_theme_style(dpg.mvStyleVar_WindowRounding, 8)
                dpg.add_theme_style(dpg.mvStyleVar_ChildRounding, 6)
                dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 6)

        dpg.bind_item_theme("xai_panel_window", xai_theme)

        dpg.add_text("🎓 AI Explanation Panel", color=COLORS["accent_blue"])
        dpg.add_text(
            f"File: {os.path.basename(threat['file_path'])}",
            color=COLORS["text_secondary"]
        )
        dpg.add_spacer(height=10)

        # Get XAI report (generate if not present)
        xai_report = threat.get("xai_report")
        if not xai_report and BACKEND_AVAILABLE:
            try:
                file_bytes = threat.get("file_bytes")
                features = threat.get("features")
                if not file_bytes and os.path.exists(threat["file_path"]):
                    with open(threat["file_path"], "rb") as f:
                        file_bytes = f.read()
                xai_report = ms.xai_engine.analyze_file(
                    threat["file_path"],
                    file_bytes or b"",
                    features or [],
                    threat.get("probability", 0),
                    threat["result"]
                )
            except Exception as e:
                print(f"Failed to generate XAI report: {e}")

        if xai_report:
            # Prediction info
            dpg.add_text("Prediction:", color=COLORS["accent_blue"])
            dpg.add_text(xai_report["prediction"], color=COLORS["text_primary"])
            dpg.add_spacer(height=5)

            dpg.add_text("Confidence:", color=COLORS["accent_blue"])
            dpg.add_text(f"{xai_report['confidence']:.1f}%", color=COLORS["text_primary"])
            dpg.add_spacer(height=5)

            dpg.add_text("Risk Level:", color=COLORS["accent_blue"])
            dpg.add_text(xai_report["risk_level"], color=COLORS["accent_orange"])
            dpg.add_spacer(height=10)

            # Scan steps
            dpg.add_text("Scan Process Simulation:", color=COLORS["accent_blue"])
            dpg.add_separator()
            for i, step in enumerate(xai_report["scan_steps"], 1):
                dpg.add_text(f"{i}. {step['title']}")
                dpg.add_text(f"   {step['description']}", color=COLORS["text_secondary"])
                dpg.add_spacer(height=3)
            dpg.add_spacer(height=10)

            # Suspicious characteristics
            if xai_report["suspicious_characteristics"]:
                dpg.add_text("Detected Suspicious Characteristics:", color=COLORS["accent_blue"])
                dpg.add_separator()
                for char in xai_report["suspicious_characteristics"]:
                    dpg.add_text(f"• {char['title']}")
                    dpg.add_text(f"  {char['description']}", color=COLORS["text_secondary"])
                    dpg.add_spacer(height=3)
                dpg.add_spacer(height=10)

            # Detailed explanation
            dpg.add_text("Detailed Explanation:", color=COLORS["accent_blue"])
            dpg.add_separator()
            with dpg.child_window(height=150, width=-1, border=True):
                dpg.add_text(xai_report["explanation"], wrap=750)
            dpg.add_spacer(height=10)

            # Recommendations
            dpg.add_text("Recommended Actions:", color=COLORS["accent_blue"])
            dpg.add_separator()
            for rec in xai_report["recommendations"]:
                dpg.add_text(f"→ {rec}")
            dpg.add_spacer(height=10)

            # Learn Why section
            dpg.add_text("📚 Learn Why:", color=COLORS["accent_blue"])
            dpg.add_separator()
            with dpg.child_window(height=180, width=-1, border=True):
                for topic_key, topic in xai_report["educational_topics"].items():
                    dpg.add_text(topic["title"], color=COLORS["accent_green"])
                    dpg.add_text(topic["content"], wrap=750, color=COLORS["text_secondary"])
                    dpg.add_spacer(height=8)
        else:
            dpg.add_text("XAI explanation not available for this file.", color=COLORS["text_secondary"])
            dpg.add_spacer(height=10)

        dpg.add_button(
            label="Close",
            width=100,
            callback=lambda: (
                dpg.delete_item("xai_panel_window")
                if dpg.does_item_exist("xai_panel_window")
                else None
            )
        )


def _rebuild_threats_table():
    if dpg.does_item_exist("threats_table"):
        # Delete and recreate the entire table to fix column issues
        dpg.delete_item("threats_table")
        with dpg.table(header_row=True, borders_innerH=True, borders_outerH=False,
                      borders_innerV=False, borders_outerV=False,
                      scrollY=True, height=220, width=-1,
                      tag="threats_table", parent="threats_container"):
            pass

    if dpg.does_item_exist("threats_table"):
        dpg.delete_item("threats_table", children_only=True)

        dpg.add_table_column(label="Select", width_stretch=False, init_width_or_weight=60, parent="threats_table")
        dpg.add_table_column(label="Explain", width_stretch=False, init_width_or_weight=90, parent="threats_table")
        dpg.add_table_column(label="File Name", width_stretch=True, init_width_or_weight=200, parent="threats_table")
        dpg.add_table_column(label="Location", width_stretch=True, init_width_or_weight=350, parent="threats_table")
        dpg.add_table_column(label="Confidence", width_stretch=False, init_width_or_weight=100, parent="threats_table")
        dpg.add_table_column(label="Type", width_stretch=False, init_width_or_weight=100, parent="threats_table")

        if not DETECTED_THREATS:
            with dpg.table_row(parent="threats_table"):
                for _ in range(6):
                    if _ == 0:
                        dpg.add_text("No threats detected", color=COLORS["text_secondary"])
                    else:
                        dpg.add_text("")
        else:
            for threat in DETECTED_THREATS:
                with dpg.table_row(parent="threats_table"):
                    # Checkbox
                    checked = threat["file_path"] in SELECTED_QUARANTINE_ITEMS
                    dpg.add_checkbox(default_value=checked, callback=_toggle_select_item, user_data=threat["file_path"])
                    # Explain button placed in the first visible action column
                    dpg.add_button(label="Explain", width=70, height=24, callback=_open_xai_panel, user_data=threat)
                    # File name
                    dpg.add_text(os.path.basename(threat["file_path"]), color=COLORS["text_primary"])
                    # Location
                    dpg.add_text(threat["file_path"], color=COLORS["text_secondary"])
                    # Confidence
                    prob = threat.get("probability")
                    if prob is not None:
                        try:
                            dpg.add_text(f"{float(prob):.1%}", color=COLORS["accent_red"])
                        except:
                            dpg.add_text("-", color=COLORS["text_secondary"])
                    else:
                        dpg.add_text("-", color=COLORS["text_secondary"])
                    # Type
                    type_color = COLORS["accent_red"] if threat["result"] == "MALICIOUS" else COLORS["accent_orange"]
                    dpg.add_text(threat["result"], color=type_color)

def _update_scan_progress():
    global SCAN_IN_PROGRESS, DETECTED_THREATS, SELECTED_QUARANTINE_ITEMS
    try:
        SCAN_IN_PROGRESS = True
        DETECTED_THREATS = []
        SELECTED_QUARANTINE_ITEMS = set()

        # Update UI state
        with dpg.mutex():
            dpg.set_value("scan_ready_heading", "Scanning...")
            dpg.set_item_label("start_scan_btn", "Scanning...")
            dpg.configure_item("start_scan_btn", enabled=False)

            if dpg.does_item_exist("scan_progress_container"):
                dpg.delete_item("scan_progress_container", children_only=True)

                with dpg.group(parent="scan_progress_container"):
                    dpg.add_text("Starting scan...", color=COLORS["text_secondary"], tag="scan_status_text")
                    dpg.add_spacer(height=20)
                    dpg.add_progress_bar(width=EMPTY_STATE_WIDTH - 100, tag="scan_progress_bar")

        if not BACKEND_AVAILABLE:
            time.sleep(2)  # Simulate scan
            with dpg.mutex():
                dpg.set_value("scan_ready_heading", "Scan Complete!")
                if dpg.does_item_exist("scan_status_text"):
                    dpg.set_value("scan_status_text", "Scan completed successfully! (Backend not loaded)")
                if dpg.does_item_exist("scan_progress_bar"):
                    dpg.set_value("scan_progress_bar", 1.0)
        else:
            start_time = time.time()
            files_scanned = 0
            threats_found = 0
            files_to_scan = []

            # Collect files to scan first
            if SELECTED_SCAN == "quick":
                for folder in cfg.QUICK_SCAN_DIRS:
                    if os.path.exists(folder):
                        for root, dirs, files in os.walk(folder):
                            for file in files:
                                file_path = os.path.join(root, file)
                                if not se.is_excluded(file_path):
                                    files_to_scan.append(file_path)

            elif SELECTED_SCAN == "full":
                for folder in cfg.REGULAR_SCAN_DIRS:
                    if os.path.exists(folder):
                        for root, dirs, files in os.walk(folder):
                            skip = False
                            for skip_dir in cfg.SKIP_DIRS:
                                if os.path.abspath(root).lower().startswith(os.path.abspath(skip_dir).lower()):
                                    skip = True
                                    break
                            if skip:
                                continue
                            for file in files:
                                file_path = os.path.join(root, file)
                                if not se.is_excluded(file_path):
                                    files_to_scan.append(file_path)

            elif SELECTED_SCAN == "custom" and CURRENT_CUSTOM_PATH:
                if os.path.isfile(CURRENT_CUSTOM_PATH):
                    if not se.is_excluded(CURRENT_CUSTOM_PATH):
                        files_to_scan.append(CURRENT_CUSTOM_PATH)
                elif os.path.isdir(CURRENT_CUSTOM_PATH):
                    for root, dirs, files in os.walk(CURRENT_CUSTOM_PATH):
                        for file in files:
                            file_path = os.path.join(root, file)
                            if not se.is_excluded(file_path):
                                files_to_scan.append(file_path)

            # Scan files
            total_files = len(files_to_scan)
            for i, file_path in enumerate(files_to_scan):
                # Throttle UI updates to reduce mutex/lock churn on large scans
                if i % 5 == 0 or i == total_files - 1:
                    with dpg.mutex():
                        if dpg.does_item_exist("scan_status_text"):
                            dpg.set_value("scan_status_text", f"Scanning: {os.path.basename(file_path)}")
                        if dpg.does_item_exist("scan_progress_bar"):
                            dpg.set_value("scan_progress_bar", (i + 1) / max(1, total_files))

                result = ms.scan_file(file_path, auto_quarantine=False)
                files_scanned += 1
                if result["result"] in ["MALICIOUS", "SUSPICIOUS"]:
                    threats_found += 1
                    DETECTED_THREATS.append(result)

            duration = time.time() - start_time
            with dpg.mutex():
                dpg.set_value("scan_ready_heading", "Scan Complete!")
                if dpg.does_item_exist("scan_status_text"):
                    dpg.set_value("scan_status_text", f"Scanned {files_scanned} files in {duration:.1f}s. {threats_found} threats found.")
                if dpg.does_item_exist("scan_progress_bar"):
                    dpg.set_value("scan_progress_bar", 1.0)

            # Send Telegram notification
            if BACKEND_AVAILABLE:
                try:
                    config = tg.load_config()
                    if config.get("telegram_bot_token") and config.get("telegram_chat_id"):
                        msg = (
                            f"🔍 Scan Complete!\n"
                            f"Scanned {files_scanned} files in {duration:.1f}s\n"
                            f"Threats found: {threats_found}"
                        )
                        tg.send_telegram_notification(msg)
                except Exception as e:
                    print(f"Error sending Telegram notification: {e}")

            # Show threats table if threats found
            with dpg.mutex():
                if dpg.does_item_exist("threats_container"):
                    dpg.show_item("threats_container")
                    _rebuild_threats_table()

            # Refresh history and activity feed after scan completes
            from ui.history import _rebuild_history
            with dpg.mutex():
                _rebuild_history()
                _rebuild_activity_feed()

    except Exception as e:
        print("=" * 80)
        traceback.print_exc()
        print("=" * 80)

        with dpg.mutex():
            dpg.set_value("scan_ready_heading", "Scan Failed")
            if dpg.does_item_exist("scan_status_text"):
                dpg.set_value("scan_status_text", f"{type(e).__name__}: {e}")

    finally:
        SCAN_IN_PROGRESS = False
        with dpg.mutex():
            dpg.configure_item("start_scan_btn", enabled=True)
            _update_start_button()

def _start_scan(sender, app_data):
    if SCAN_IN_PROGRESS:
        return

    if SELECTED_SCAN == "custom" and not CURRENT_CUSTOM_PATH:
        dpg.show_item("custom_scan_picker")
        return

    if dpg.does_item_exist("threats_container"):
        dpg.hide_item("threats_container")

    thread = threading.Thread(target=_update_scan_progress, daemon=True)
    thread.start()

def _update_start_button():
    if SCAN_IN_PROGRESS:
        return

    button_labels = {
        "quick": "Start Quick Scan",
        "full": "Start Full Scan",
        "custom": "Start Custom Scan"
    }
    dpg.set_item_label("start_scan_btn", button_labels.get(SELECTED_SCAN, "Start Scan"))
    dpg.set_value("scan_ready_heading", "Ready to Scan")

def _folder_picked(sender, app_data):
    global CURRENT_CUSTOM_PATH
    path = app_data.get("file_path_name", "")
    if path:
        CURRENT_CUSTOM_PATH = path
        if dpg.does_item_exist("custom_path_display"):
            dpg.set_value("custom_path_display", path)

def _center_spacer(item_width, container_width=CONTENT_WIDTH):
    return max(0, int((container_width - item_width) / 2))

def _on_step_click(sender, app_data, user_data):
    print(f"_on_step_click called with user_data: {user_data}")
    global SELECTED_STEP
    SELECTED_STEP = user_data
    _update_step_description()

def _build_step_cards(icons):
    global g_step_elements
    g_step_elements = []  # Reset step elements list
    # Build all step cards inside steps_group
    for i, step in enumerate(DETECTION_STEPS):
        # Step card (child window) - perfect size!
        card_width = 130
        card_height = 115
        icon_size = 32
        step_tag = f"step_{i}"
        is_active = i == SELECTED_STEP
        with dpg.child_window(width=card_width, height=card_height, tag=step_tag, no_scrollbar=True, parent="steps_group"):
            dpg.add_spacer(height=18)
            with dpg.group(horizontal=True):
                dpg.add_spacer(width=(card_width - icon_size) // 2)
                # Store image tag
                img_tag = f"step_img_{i}"
                dpg.add_image(icons[step["icon"]], width=icon_size, height=icon_size,
                             tint_color=COLORS["accent_blue"] if is_active else COLORS["text_secondary"],
                             tag=img_tag)
            dpg.add_spacer(height=8)
            with dpg.group(horizontal=True):
                dpg.add_spacer(width=5)
                # Store text tag
                txt_tag = f"step_txt_{i}"
                dpg.add_text(step["title"], color=COLORS["text_primary"] if is_active else COLORS["text_secondary"],
                            wrap=card_width - 10, tag=txt_tag)

        # Apply theme to step card
        with dpg.theme() as step_theme:
            with dpg.theme_component(dpg.mvChildWindow):
                dpg.add_theme_color(dpg.mvThemeCol_ChildBg, COLORS["bg_card"] if is_active else COLORS["bg_sidebar"])
                dpg.add_theme_color(dpg.mvThemeCol_Border, COLORS["accent_blue"] if is_active else COLORS["border"])
        dpg.bind_item_theme(step_tag, step_theme)

        # Store the tags for later use
        g_step_elements.append((step_tag, img_tag, txt_tag))

        # Add spacer + arrow between steps (except last one)
        if i < len(DETECTION_STEPS) - 1:
            dpg.add_spacer(width=10, parent="steps_group")
            with dpg.group(parent="steps_group"):
                dpg.add_spacer(height=40)  # Adjust this value to vertically center
                dpg.add_text("->", color=COLORS["text_secondary"])
            dpg.add_spacer(width=1, parent="steps_group")

def _update_step_description():
    print(f"_update_step_description called, SELECTED_STEP: {SELECTED_STEP}")
    if dpg.does_item_exist("step_description_text"):
        step = DETECTION_STEPS[SELECTED_STEP]
        print(f"Setting description to: {step['description']}")
        dpg.set_value("step_description_text", step["description"])

    # Update all step cards using configure_item (no glitching!)
    for i, (step_tag, img_tag, txt_tag) in enumerate(g_step_elements):
        is_active = i == SELECTED_STEP
        # Update step card theme
        with dpg.theme() as step_theme:
            with dpg.theme_component(dpg.mvChildWindow):
                dpg.add_theme_color(dpg.mvThemeCol_ChildBg, COLORS["bg_card"] if is_active else COLORS["bg_sidebar"])
                dpg.add_theme_color(dpg.mvThemeCol_Border, COLORS["accent_blue"] if is_active else COLORS["border"])
        dpg.bind_item_theme(step_tag, step_theme)

        # Update icon tint color
        new_tint = COLORS["accent_blue"] if is_active else COLORS["text_secondary"]
        dpg.configure_item(img_tag, tint_color=new_tint)

        # Update text color
        new_color = COLORS["text_primary"] if is_active else COLORS["text_secondary"]
        dpg.configure_item(txt_tag, color=new_color)

def build_scan(parent, fonts, icons):
    global g_icons
    g_icons = icons  # Store icons in global variable for later use
    dpg.add_spacer(height=20, parent=parent)
    with dpg.handler_registry():
        dpg.add_mouse_click_handler(callback=_handle_click)

    with dpg.file_dialog(directory_selector=True, show=False, callback=_folder_picked,
                         tag="custom_scan_picker", width=700, height=400):
        pass

    with dpg.group(horizontal=True, parent=parent):
        dpg.add_spacer(width=24)
        with dpg.group():
            dpg.add_text("Virus & Threat Protection", tag="scan_page_title")
            dpg.bind_item_font("scan_page_title", fonts["heading"])
            dpg.add_text("Run a scan to check for malicious files on your system", color=COLORS["text_secondary"])
            dpg.add_spacer(height=15)

            with dpg.group(horizontal=True):
                for i, scan in enumerate(SCAN_TYPES):
                    scan_card(scan["key"], icons[scan["icon"]], scan["label"], scan["subtitle"],
                             scan["label_offset"], scan["subtitle_offset"], scan["subtitle_gap"], fonts, icons)
                    if i < len(SCAN_TYPES) - 1:
                        dpg.add_spacer(width=CARD_GAP)

            dpg.add_spacer(height=CARD_GAP)

            with dpg.child_window(width=EMPTY_STATE_WIDTH, height=260, tag="scan_empty_state", no_scrollbar=True):
                dpg.add_spacer(height=20)

                with dpg.group(horizontal=True):
                    dpg.add_spacer(width=_center_spacer(48))
                    dpg.add_image(icons["search"], width=48, height=48, tint_color=COLORS["accent_blue"])

                dpg.add_spacer(height=3)

                heading_tag = "scan_ready_heading"
                with dpg.group(horizontal=True):
                    dpg.add_spacer(width=READY_HEADING_OFFSET)
                    dpg.add_text("Ready to Scan", color=COLORS["text_primary"], tag=heading_tag)

                dpg.bind_item_font(heading_tag, fonts["heading"])

                dpg.add_spacer(height=5)

                with dpg.group(tag="scan_progress_container"):
                    pass

                dpg.add_spacer(height=10)

                btn_width = 180
                with dpg.group(horizontal=True, tag="scan_button_group"):
                    dpg.add_spacer(width=START_BUTTON_OFFSET)
                    dpg.add_button(label="Start Quick Scan", width=btn_width, height=36, tag="start_scan_btn", callback=_start_scan)
                _rebuild_custom_path_controls()

            dpg.add_spacer(height=20)
            # Threats container (initially hidden)
            with dpg.child_window(width=EMPTY_STATE_WIDTH, height=350, tag="threats_container", show=False, no_scrollbar=True):
                dpg.add_text("Detected Threats", color=COLORS["text_primary"])
                dpg.add_spacer(height=10)
                with dpg.table(header_row=True, borders_innerH=True, borders_outerH=False,
                              borders_innerV=False, borders_outerV=False,
                              scrollY=True, height=220, width=-1,
                              tag="threats_table"):
                    pass
                dpg.add_spacer(height=10)
                dpg.add_button(label="Quarantine Selected", callback=_quarantine_selected, tag="quarantine_btn")

            dpg.add_spacer(height=20)
            # How It Works section - Detection Pipeline (like the photo)
            with dpg.child_window(width=EMPTY_STATE_WIDTH, height=240, tag="how_it_works_container", no_scrollbar=True):
                dpg.add_text("Detection Pipeline", color=COLORS["text_primary"])
                dpg.bind_item_font(dpg.last_item(), fonts["heading"])
                dpg.add_spacer(height=15)

                # Horizontal pipeline of steps
                with dpg.group(horizontal=True, tag="steps_group"):
                    _build_step_cards(icons)

                dpg.add_spacer(height=15)
                # Description panel below - no scrollbar, no cut text!
                with dpg.group(tag="step_description_panel"):
                    # Add a border using a child window with minimal height that expands
                    with dpg.child_window(width=-1, height=60, border=True, tag="step_description_child", no_scrollbar=True):
                        dpg.add_spacer(height=10)
                        with dpg.group(horizontal=True):
                            dpg.add_spacer(width=15)
                            dpg.add_text(DETECTION_STEPS[0]["description"], color=COLORS["text_secondary"],
                                        wrap=EMPTY_STATE_WIDTH - 30, tag="step_description_text")
                        dpg.add_spacer(height=10)

    with dpg.theme() as btn_theme:
        with dpg.theme_component(dpg.mvButton):
            dpg.add_theme_color(dpg.mvThemeCol_Button, COLORS["accent_blue"])
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, COLORS["accent_blue"])
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, COLORS["accent_blue"])
    dpg.bind_item_theme("start_scan_btn", btn_theme)
    dpg.bind_item_theme("quarantine_btn", btn_theme)