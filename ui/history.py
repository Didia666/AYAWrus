import os
from collections import OrderedDict
import threading

import dearpygui.dearpygui as dpg
from ui.theme import COLORS
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    import system.history.logs as hl
    from system.history.batches import list_batches, get_batch
    BACKEND_AVAILABLE = True
except Exception as e:
    print(f"Warning [ui/history.py]: Could not load backend history deps: {e}")
    BACKEND_AVAILABLE = False
    list_batches = None
    get_batch = None

ROW_WIDTH = 1240
ROW_HEIGHT = 125
ROW_GAP = 12
BADGE_TOP_OFFSET = 6
ICON_BADGE_SIZE = 40
DATE_COLUMN_WIDTH = 210
GLOBAL_ICONS = None

_DETAIL_ROW_HEIGHT = 84
_DETAIL_ROW_GAP = 8

_BATCH_ROW_MAP = {}
_HISTORY_DETAIL_BATCH = None
_HISTORY_MOUSE_BOUND = False
_LAST_BATCH_LIST = []


def _icon_for_entry(entry, icons):
    result_u = str((entry or {}).get("result") or (entry or {}).get("verdict") or "CLEAN").upper()
    if result_u in ("MALICIOUS", "SUSPICIOUS"):
        return (icons.get("octagon_alert") if icons else None, COLORS["accent_red"])
    if result_u in ("QUARANTINED",):
        return (icons.get("shield_cog") if icons else None, COLORS["accent_orange"])
    if result_u in ("ERROR", "FAILED"):
        return (icons.get("octagon_alert") if icons else None, COLORS["text_secondary"])
    return (icons.get("shield_check") if icons else None, COLORS["accent_green"])


def _looks_like_batch(item) -> bool:
    if not isinstance(item, dict):
        return False
    if item.get("file_path") or item.get("fileName"):
        return False
    return any(k in item for k in ("total_files", "totalFiles", "scan_type", "scanType", "clean_count", "cleanCount"))


def _cleanup_history_item_tags():
    i = 0
    while i < 400:
        for suffix in ("", "_handler", "_icon_bg", "_open_btn"):
            tag = f"batch_row_{i}{suffix}"
            try:
                if dpg.does_item_exist(tag):
                    dpg.delete_item(tag)
            except Exception:
                pass
        i += 1
    j = 0
    while j < 300:
        for suffix in ("", "_icon_bg"):
            tag = f"bd_row_{j}{suffix}"
            try:
                if dpg.does_item_exist(tag):
                    dpg.delete_item(tag)
            except Exception:
                pass
        j += 1


def _schedule_history_render(icons=None):
    def _later():
        try:
            with dpg.mutex():
                _render_history_view(icons=icons)
        except Exception as e:
            print(f"[ui/history] render failed: {e}")
    threading.Timer(0.02, _later).start()


def _on_history_mouse_click(sender, app_data):
    try:
        from ui.sidebar import CURRENT_PAGE
        if CURRENT_PAGE != "history":
            return
    except Exception:
        pass
    if _HISTORY_DETAIL_BATCH is not None:
        return
    hovered = []
    for tag, batch in list(_BATCH_ROW_MAP.items()):
        try:
            if dpg.does_item_exist(tag) and dpg.is_item_hovered(tag):
                hovered.append((tag, batch))
        except Exception:
            continue
    if not hovered:
        return
    _show_batch_files(hovered[0][1])


def _show_batch_files(batch, icons=None):
    global _HISTORY_DETAIL_BATCH
    if not batch:
        return
    _HISTORY_DETAIL_BATCH = dict(batch)
    _schedule_history_render(icons)


def _back_to_batches(sender=None, app_data=None, user_data=None):
    global _HISTORY_DETAIL_BATCH
    _HISTORY_DETAIL_BATCH = None
    def _later():
        try:
            with dpg.mutex():
                _rebuild_history()
        except Exception as e:
            print(f"[ui/history] back to batches failed: {e}")
    threading.Timer(0.02, _later).start()


def _scan_type_label(scan_type: str) -> str:
    st = (scan_type or "").lower()
    if st in ("quick", "fast"):
        return "Quick Scan"
    if st in ("full", "regular", "system"):
        return "Full System Scan"
    if st in ("custom",):
        return "Custom Scan"
    if st == "single":
        return "Single File"
    if not st:
        return "Scan"
    return st.capitalize() + " Scan"


def _scan_type_color(scan_type: str):
    st = (scan_type or "").lower()
    if st in ("quick", "fast"):
        return COLORS["accent_blue"]
    if st in ("full", "regular", "system"):
        return COLORS["accent_purple"] if "accent_purple" in COLORS else (156, 80, 220, 255)
    if st in ("custom",):
        return COLORS["accent_orange"]
    return COLORS["text_secondary"]


def _batch_status_icon(batch, icons):
    status = (batch.get("status") or "").upper()
    threats = int(batch.get("threat_count") or 0)
    if status == "RUNNING":
        return (icons.get("scan"), COLORS["accent_blue"]) if icons else (None, COLORS["accent_blue"])
    if status in ("FAILED", "CANCELLED"):
        return (icons.get("octagon_alert"), COLORS["accent_red"])
    if threats > 0:
        return (icons.get("octagon_alert"), COLORS["accent_red"])
    return (icons.get("shield_check"), COLORS["accent_green"])


def _icon_badge(icon_texture, color, tag_prefix, size=ICON_BADGE_SIZE):
    with dpg.child_window(width=size, height=size, no_scrollbar=True, tag=f"{tag_prefix}_icon_bg"):
        if icon_texture:
            pad_x = max(2, (size - 18) // 2)
            pad_y = max(2, (size - 18) // 2)
            dpg.add_image(icon_texture, width=18, height=18, tint_color=color, pos=(pad_x, pad_y))
    with dpg.theme() as badge_theme:
        with dpg.theme_component(dpg.mvChildWindow):
            muted = tuple(max(0, min(255, c // 5)) for c in color[:3]) + (255,)
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, muted)
    dpg.bind_item_theme(f"{tag_prefix}_icon_bg", badge_theme)


def _format_elapsed(ms: int) -> str:
    if not ms:
        return "0.0s"
    total = max(0, int(ms)) / 1000.0
    if total < 60:
        return f"{total:.1f}s"
    mins = int(total // 60)
    secs = int(total % 60)
    return f"{mins}m {secs:02d}s"


def _truncate_target(target: str, max_len: int = 68) -> str:
    if not target:
        return ""
    t = str(target).strip()
    if len(t) <= max_len:
        return t
    return t[: max_len - 3] + "..."


def _batch_row(batch, index, icons):
    tag_prefix = f"batch_row_{index}"
    scan_type = batch.get("scan_type") or batch.get("scanType") or ""
    st_label = _scan_type_label(scan_type)
    st_color = _scan_type_color(scan_type)
    total = int(batch.get("total_files") or batch.get("totalFiles") or 0)
    threats = int(batch.get("threat_count") or batch.get("threatCount") or 0)
    clean = int(batch.get("clean_count") or batch.get("cleanCount") or 0)
    suspicious = int(batch.get("suspicious_count") or batch.get("suspiciousCount") or 0)
    malicious = int(batch.get("malicious_count") or batch.get("maliciousCount") or 0)
    elapsed = int(batch.get("elapsed_ms") or batch.get("elapsedMs") or 0)
    started = batch.get("started_at") or batch.get("startedAt") or ""
    status = (batch.get("status") or "").upper()
    batch_id = batch.get("id") or ""
    target = batch.get("target") or ""

    icon, color = _batch_status_icon(batch, icons)
    status_label = status or ("COMPLETED" if total > 0 else "UNKNOWN")
    status_color = COLORS["accent_green"]
    if status_label == "RUNNING":
        status_color = COLORS["accent_blue"]
    elif status_label in ("FAILED", "CANCELLED"):
        status_color = COLORS["accent_red"]
    elif threats > 0:
        status_color = COLORS["accent_red"]

    with dpg.child_window(width=ROW_WIDTH, height=ROW_HEIGHT, tag=tag_prefix, no_scrollbar=True, no_scroll_with_mouse=True):
        with dpg.group(horizontal=True):
            dpg.add_spacer(width=12)
            with dpg.group():
                dpg.add_spacer(height=BADGE_TOP_OFFSET)
                _icon_badge(icon, color, tag_prefix)
            dpg.add_spacer(width=12)
            with dpg.group(width=ROW_WIDTH - ICON_BADGE_SIZE - DATE_COLUMN_WIDTH - 72):
                dpg.add_spacer(height=2)
                with dpg.group(horizontal=True):
                    title_text = f"{st_label}"
                    if total > 0:
                        title_text += f"  ·  {total} files"
                    dpg.add_text(title_text, color=COLORS["text_primary"])
                sub1 = []
                if target:
                    sub1.append(_truncate_target(target, 74))
                if clean > 0:
                    sub1.append(f"Clean: {clean}")
                if malicious > 0:
                    sub1.append(f"Malicious: {malicious}")
                if suspicious > 0:
                    sub1.append(f"Suspicious: {suspicious}")
                if threats == 0 and clean == 0 and total > 0:
                    sub1.append(f"Results: {total}")
                dpg.add_text("   ".join(sub1), color=COLORS["text_secondary"])
                elapsed_str = _format_elapsed(elapsed)
                if batch_id:
                    dpg.add_text(f"Duration {elapsed_str}   ·   Batch {batch_id}",
                                 color=COLORS["text_secondary"])
                else:
                    dpg.add_text(f"Duration {elapsed_str}", color=COLORS["text_secondary"])

            dpg.add_spacer(width=8)
            with dpg.group(width=DATE_COLUMN_WIDTH):
                if started:
                    dpg.add_text(started, color=COLORS["text_secondary"])
                dpg.add_text(status_label, color=status_color)
                dpg.add_spacer(height=8)
                with dpg.group(horizontal=True):
                    dpg.add_spacer(width=DATE_COLUMN_WIDTH - 88)
                    dpg.add_button(
                        label="Open",
                        width=88,
                        height=32,
                        callback=lambda s, a, u: _show_batch_files(u, icons),
                        user_data=dict(batch),
                        tag=f"{tag_prefix}_open_btn",
                    )

    _BATCH_ROW_MAP[tag_prefix] = dict(batch)


def _detail_file_row(entry, index, icons):
    tag = f"bd_row_{index}"
    with dpg.child_window(width=ROW_WIDTH, height=_DETAIL_ROW_HEIGHT, tag=tag, no_scrollbar=True, no_scroll_with_mouse=True):
        with dpg.group(horizontal=True):
            dpg.add_spacer(width=14)
            result = entry.get("result") or entry.get("verdict") or "CLEAN"
            result_u = str(result).upper()
            icon_texture, icon_color = _icon_for_entry({"result": result_u}, icons or {})
            with dpg.group():
                dpg.add_spacer(height=6)
                _icon_badge(icon_texture, icon_color, tag, size=32)
            dpg.add_spacer(width=10)
            with dpg.group():
                file_path = entry.get("file_path") or entry.get("fileName") or "Unknown"
                dpg.add_spacer(height=4)
                dpg.add_text(
                    f"{result_u}: {os.path.basename(file_path)}",
                    color=COLORS["text_primary"],
                    wrap=ROW_WIDTH - 110,
                )
                details = str(file_path)
                prob = entry.get("probability")
                if prob is None:
                    prob = entry.get("threatLevel")
                    if prob is not None:
                        try:
                            prob = float(prob) / 100.0
                        except Exception:
                            prob = None
                if prob is not None:
                    try:
                        p = float(prob)
                        if 0.0 <= p <= 1.0:
                            details += f"  (Confidence {p:.0%})"
                        else:
                            details += f"  (Score {p:.0f})"
                    except Exception:
                        pass
                extra = entry.get("details") or entry.get("detail") or ""
                if extra:
                    details += f"   | {_truncate_target(str(extra), 100)}"
                dpg.add_text(
                    _truncate_target(details, 240),
                    color=COLORS["text_secondary"],
                    wrap=ROW_WIDTH - 110,
                )


def _group_entries_by_batch(entries):
    """Fallback grouping helper for log entries that don't have explicit batch_id.
    Groups adjacent entries with identical timestamp (minute bucket) if no batch_id."""
    groups = OrderedDict()
    for e in entries:
        bid = e.get("batch_id")
        if bid:
            key = ("id", bid)
        else:
            ts = str(e.get("timestamp") or "")
            minute_ts = ts[:16] if len(ts) >= 16 else ts
            key = ("ts", minute_ts)
        if key not in groups:
            groups[key] = []
        groups[key].append(e)

    out = []
    for k, files in groups.items():
        if k[0] == "id":
            batch_meta = {}
            if BACKEND_AVAILABLE and get_batch is not None:
                try:
                    b = get_batch(k[1])
                    if b:
                        batch_meta = b
                except Exception:
                    pass
            threats = sum(1 for f in files if (f.get("result") or "").upper() in ("MALICIOUS", "SUSPICIOUS"))
            clean = sum(1 for f in files if (f.get("result") or "").upper() in ("CLEAN", "SAFE", "BENIGN"))
            tss = [f.get("timestamp") for f in files if f.get("timestamp")]
            started = tss[0] if tss else ""
            synthetic = {
                "id": batch_meta.get("id") or k[1],
                "scan_type": batch_meta.get("scan_type") or "custom",
                "target": batch_meta.get("target") or (files[0].get("file_path") and os.path.dirname(files[0].get("file_path")) or ""),
                "started_at": batch_meta.get("started_at") or started,
                "started_at_ms": batch_meta.get("started_at_ms") or 0,
                "completed_at": batch_meta.get("completed_at") or "",
                "elapsed_ms": batch_meta.get("elapsed_ms") or 0,
                "total_files": batch_meta.get("total_files") or len(files),
                "clean_count": batch_meta.get("clean_count") or clean,
                "threat_count": batch_meta.get("threat_count") or threats,
                "suspicious_count": batch_meta.get("suspicious_count") or sum(1 for f in files if (f.get("result") or "").upper() == "SUSPICIOUS"),
                "malicious_count": batch_meta.get("malicious_count") or sum(1 for f in files if (f.get("result") or "").upper() == "MALICIOUS"),
                "error_count": batch_meta.get("error_count") or sum(1 for f in files if (f.get("result") or "").upper() == "ERROR"),
                "status": batch_meta.get("status") or "COMPLETED",
            }
            synthetic["__files"] = list(files)
            out.append(synthetic)
        else:
            threats = sum(1 for f in files if (f.get("result") or "").upper() in ("MALICIOUS", "SUSPICIOUS"))
            clean = sum(1 for f in files if (f.get("result") or "").upper() in ("CLEAN", "SAFE", "BENIGN"))
            started = files[0].get("timestamp") or "" if files else ""
            bid_synth = "SYN-" + (k[1] or "").replace(" ", "").replace(":", "").replace("-", "")
            synthetic = {
                "id": bid_synth,
                "scan_type": "auto",
                "target": (files[0].get("file_path") and os.path.dirname(files[0].get("file_path")) or "") if files else "",
                "started_at": started,
                "started_at_ms": 0,
                "completed_at": "",
                "elapsed_ms": 0,
                "total_files": len(files),
                "clean_count": clean,
                "threat_count": threats,
                "suspicious_count": sum(1 for f in files if (f.get("result") or "").upper() == "SUSPICIOUS"),
                "malicious_count": sum(1 for f in files if (f.get("result") or "").upper() == "MALICIOUS"),
                "error_count": sum(1 for f in files if (f.get("result") or "").upper() == "ERROR"),
                "status": "COMPLETED",
                "__files": list(files),
            }
            out.append(synthetic)

    out.sort(key=lambda b: (b.get("started_at_ms") or 0, b.get("started_at") or ""), reverse=True)
    return out


def _files_for_batch(batch):
    if not batch:
        return []
    if "__files" in batch and batch["__files"]:
        return list(batch["__files"])
    bid = batch.get("id")
    entries = []
    if BACKEND_AVAILABLE and hl is not None:
        try:
            entries = hl.load_log() or []
        except Exception:
            entries = []
    if bid:
        matched = [e for e in entries if e.get("batch_id") == bid]
        if matched:
            return matched
    start = str(batch.get("started_at") or batch.get("startedAt") or "")
    end = str(batch.get("completed_at") or batch.get("completedAt") or "")
    if not start:
        return []
    out = []
    for e in entries:
        ts = str(e.get("timestamp") or "")
        if not ts:
            continue
        if ts < start:
            continue
        if end and ts > end:
            continue
        eb = e.get("batch_id")
        if eb and bid and eb != bid:
            continue
        out.append(e)
    return out


def _render_batch_list(batches, icons):
    global _BATCH_ROW_MAP, _LAST_BATCH_LIST
    _BATCH_ROW_MAP = {}
    _LAST_BATCH_LIST = list(batches or [])
    if not batches:
        with dpg.group(parent="history_group"):
            dpg.add_text("No scan history yet", color=COLORS["text_secondary"])
            dpg.add_spacer(height=6)
            dpg.add_text("Run a scan to see protection batch summaries here. Click a batch or press Open to view its files.",
                         color=COLORS["text_secondary"])
        return

    with dpg.group(parent="history_group"):
        dpg.add_text(f"{len(batches)} scan batch{'es' if len(batches) != 1 else ''}", color=COLORS["text_secondary"])
        dpg.add_spacer(height=10)
        for i, b in enumerate(batches):
            try:
                _batch_row(b, i, icons or {})
            except Exception as re:
                print(f"[ui/history] batch row render failed: {re}")
            if i < len(batches) - 1:
                dpg.add_spacer(height=ROW_GAP)


def _render_batch_detail(batch, icons):
    files = _files_for_batch(batch)
    st = _scan_type_label(batch.get("scan_type") or batch.get("scanType") or "")
    total = int(batch.get("total_files") or batch.get("totalFiles") or 0)
    threats = int(batch.get("threat_count") or batch.get("threatCount") or 0)
    clean = int(batch.get("clean_count") or batch.get("cleanCount") or 0)
    malicious = int(batch.get("malicious_count") or batch.get("maliciousCount") or 0)
    suspicious = int(batch.get("suspicious_count") or batch.get("suspiciousCount") or 0)
    errors = int(batch.get("error_count") or batch.get("errorCount") or 0)
    elapsed = _format_elapsed(int(batch.get("elapsed_ms") or batch.get("elapsedMs") or 0))
    started = batch.get("started_at") or batch.get("startedAt") or ""
    completed = batch.get("completed_at") or batch.get("completedAt") or ""
    target = batch.get("target") or ""
    batch_id = batch.get("id") or ""
    status = (batch.get("status") or "COMPLETED").upper()

    sc = COLORS["accent_green"]
    if status == "RUNNING":
        sc = COLORS["accent_blue"]
    elif status in ("FAILED", "CANCELLED"):
        sc = COLORS["accent_red"]
    elif threats > 0:
        sc = COLORS["accent_red"]

    with dpg.group(parent="history_group"):
        dpg.add_button(label="← Back to all batches", width=200, height=32, callback=_back_to_batches)
        dpg.add_spacer(height=12)
        with dpg.group(horizontal=True):
            dpg.add_text(st, color=COLORS["text_primary"])
            dpg.add_spacer(width=10)
            dpg.add_text(status, color=sc)
        if batch_id:
            dpg.add_text(f"Batch ID: {batch_id}", color=COLORS["text_secondary"])
        if started:
            started_line = f"Started:  {started}"
            if completed:
                started_line += f"   ·   Completed:  {completed}"
            started_line += f"   ·   Duration:  {elapsed}"
            dpg.add_text(started_line, color=COLORS["text_secondary"])
        if target:
            dpg.add_text(
                f"Target:  {_truncate_target(target, 220)}",
                color=COLORS["text_secondary"],
                wrap=ROW_WIDTH - 24,
            )

        dpg.add_spacer(height=10)
        with dpg.group(horizontal=True):
            stats = [
                (f"Total: {total}", COLORS["text_primary"]),
                (f"Clean: {clean}", COLORS["accent_green"]),
            ]
            if malicious > 0:
                stats.append((f"Malicious: {malicious}", COLORS["accent_red"]))
            if suspicious > 0:
                stats.append((f"Suspicious: {suspicious}", (255, 193, 7, 255)))
            if errors > 0:
                stats.append((f"Errors: {errors}", COLORS["text_secondary"]))
            for i, (txt, c) in enumerate(stats):
                if i > 0:
                    dpg.add_spacer(width=18)
                dpg.add_text(txt, color=c)

        dpg.add_spacer(height=14)
        dpg.add_text(f"Files scanned ({len(files)})", color=COLORS["text_primary"])
        dpg.add_spacer(height=6)

        if not files:
            dpg.add_text("No file detail available for this batch.", color=COLORS["text_secondary"])
        else:
            for idx, f in enumerate(files[:250]):
                _detail_file_row(f, idx, icons or {})
                if idx < min(len(files), 250) - 1:
                    dpg.add_spacer(height=_DETAIL_ROW_GAP)
            if len(files) > 250:
                dpg.add_spacer(height=8)
                dpg.add_text(f"… and {len(files) - 250} more files.", color=COLORS["text_secondary"])


def _render_history_view(icons=None):
    global GLOBAL_ICONS, _BATCH_ROW_MAP
    if icons is not None:
        GLOBAL_ICONS = icons
    else:
        icons = GLOBAL_ICONS or {}

    if not dpg.does_item_exist("history_group"):
        return

    _BATCH_ROW_MAP = {}
    try:
        dpg.delete_item("history_group", children_only=True)
    except Exception:
        pass
    _cleanup_history_item_tags()

    if _HISTORY_DETAIL_BATCH is not None:
        _render_batch_detail(_HISTORY_DETAIL_BATCH, icons)
        return
    _render_batch_list(_LAST_BATCH_LIST, icons)


def _build_batches_from_backend(limit=50):
    batches = []
    if BACKEND_AVAILABLE and list_batches is not None:
        try:
            batches = list_batches(limit=limit) or []
        except Exception as b_err:
            print(f"[ui/history] list_batches failed: {b_err}")
            batches = []
    if not batches and BACKEND_AVAILABLE and hl is not None:
        try:
            entries = hl.load_log(limit=max(2000, limit * 60)) or []
            entries = list(reversed(entries))
            batches = _group_entries_by_batch(entries)[:limit]
        except Exception as err:
            print(f"[ui/history] synthetic batch group failed: {err}")
    return batches


def _rebuild_history_from_data(entries, icons=None):
    """Compatibility wrapper. File-level logs must not replace the batch list."""
    if isinstance(entries, list) and entries and _looks_like_batch(entries[0]):
        global _LAST_BATCH_LIST, _HISTORY_DETAIL_BATCH
        _HISTORY_DETAIL_BATCH = None
        _LAST_BATCH_LIST = list(entries)
        _render_history_view(icons=icons)
        return
    _rebuild_history(icons=icons)


def _rebuild_history(icons=None, limit=50):
    global GLOBAL_ICONS, _LAST_BATCH_LIST, _HISTORY_DETAIL_BATCH
    if icons is not None:
        GLOBAL_ICONS = icons
    else:
        icons = GLOBAL_ICONS
    _HISTORY_DETAIL_BATCH = None
    _LAST_BATCH_LIST = _build_batches_from_backend(limit=limit)
    _render_history_view(icons=icons)


def build_history(parent, fonts, icons):
    global GLOBAL_ICONS, _HISTORY_MOUSE_BOUND
    GLOBAL_ICONS = icons
    dpg.add_spacer(height=20, parent=parent)
    if not _HISTORY_MOUSE_BOUND:
        try:
            with dpg.handler_registry():
                dpg.add_mouse_click_handler(callback=_on_history_mouse_click)
            _HISTORY_MOUSE_BOUND = True
        except Exception as e:
            print(f"[ui/history] mouse handler bind failed: {e}")
    with dpg.group(horizontal=True, parent=parent):
        dpg.add_spacer(width=24)
        with dpg.group():
            dpg.add_text("Protection History", tag="history_page_title")
            dpg.bind_item_font("history_page_title", fonts["heading"])
            dpg.add_text("Each scan is one batch. Open a batch to see every file from that run.",
                         color=COLORS["text_secondary"])
            dpg.add_spacer(height=15)

            with dpg.group(tag="history_group"):
                pass
            _rebuild_history(icons)
