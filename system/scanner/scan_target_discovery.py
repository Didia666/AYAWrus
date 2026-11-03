
"""
scan_target_discovery.py

Discovers files that match the potential target categories
provided by malware_impact_engine.py.

Safety:
- Metadata only.
- Never opens or executes discovered files.
- Does not modify or delete files.
- Skips symlinks and junctions.
- Excludes specified protected directories.
- Supports file and time limits.
"""

import os
import time
import ntpath
from pathlib import Path
from datetime import datetime


HIGH_MIN_SCORE = 0.75
MEDIUM_MIN_SCORE = 0.50

DEFAULT_MAX_FILES = 100_000
DEFAULT_TIMEOUT = 120

# Categories are imported from the impact engine.
from .malware_impact_engine import FILE_CATEGORY_RULES


def _normalize_path(path):
    return os.path.normcase(
        os.path.abspath(os.path.expanduser(str(path)))
    )


def _is_inside(path, excluded_roots):
    """Check whether a path is inside an excluded directory."""

    normalized = _normalize_path(path)

    for root in excluded_roots:
        root = _normalize_path(root)

        try:
            if os.path.commonpath(
                [normalized, root]
            ) == root:
                return True
        except ValueError:
            # Different drives on Windows.
            continue

    return False


def _risk_level(score):
    if score >= HIGH_MIN_SCORE:
        return "high"

    if score >= MEDIUM_MIN_SCORE:
        return "medium"

    return "low"


def _is_junction(entry):
    """
    Detect Windows junctions when supported.
    Older Python versions simply return False.
    """

    try:
        return entry.is_junction()
    except (AttributeError, OSError):
        return False


def discover_likely_targets(
    impact_result,
    search_roots,
    excluded_roots=None,
    max_files=DEFAULT_MAX_FILES,
    timeout=DEFAULT_TIMEOUT,
    progress_callback=None,
):
    """
    Search selected directories for files matching
    the predicted target categories.

    Args:
        impact_result:
            Output from analyze_behavior_predictions().

        search_roots:
            Directories explicitly selected for discovery.

        excluded_roots:
            AYAWrus installation and quarantine directories.

        max_files:
            Maximum number of matching files returned.

        timeout:
            Maximum discovery duration in seconds.

        progress_callback:
            Optional callback(scanned_count, matched_count).

    Returns:
        Dictionary compatible with scan_targets.py.
    """

    started = time.monotonic()

    excluded_roots = excluded_roots or []

    categories = impact_result.get("categories", {})

    sample = impact_result.get("sample", "Unknown")

    # Build an extension-to-category lookup.
    extension_lookup = {}

    for category, info in categories.items():

        extensions = info.get("extensions", [])

        for ext in extensions:
            extension_lookup[ext.lower()] = category

    category_results = {}

    for category, info in categories.items():
        category_results[category] = {
            "score": info.get("support_score", 0.0),
            "source": "behavior_mapping",
            "count": 0
        }

    flagged = [
        category
        for category, info in categories.items()
        if info.get("support_score", 0.0) >= 0.50
    ]

    files = []
    by_folder = {}

    files_scanned = 0
    files_skipped_permission = 0

    state = "done"
    message = None

    deadline = started + timeout

    def check_limits():
        if len(files) >= max_files:
            return "partial", "File discovery limit reached"

        if time.monotonic() >= deadline:
            return "partial", "Discovery time limit reached"

        return None, None

    # Use an explicit directory stack instead of os.walk
    # so that symlinks and junctions can be skipped.
    stack = [
        _normalize_path(root)
        for root in search_roots
        if os.path.isdir(root)
        and not _is_inside(root, excluded_roots)
    ]

    try:
        while stack:

            limit_state, limit_message = check_limits()

            if limit_state:
                state = limit_state
                message = limit_message
                break

            current_dir = stack.pop()

            if _is_inside(current_dir, excluded_roots):
                continue

            try:
                with os.scandir(current_dir) as entries:

                    for entry in entries:

                        limit_state, limit_message = check_limits()

                        if limit_state:
                            state = limit_state
                            message = limit_message
                            break

                        try:
                            if entry.is_symlink():
                                continue

                            if _is_junction(entry):
                                continue

                            if _is_inside(
                                entry.path, excluded_roots
                            ):
                                continue

                            if entry.is_dir(
                                follow_symlinks=False
                            ):
                                stack.append(entry.path)
                                continue

                            if not entry.is_file(
                                follow_symlinks=False
                            ):
                                continue

                            files_scanned += 1

                            extension = Path(
                                entry.name
                            ).suffix.lower()

                            category = extension_lookup.get(
                                extension
                            )

                            if not category:
                                continue

                            info = categories[category]

                            score = float(
                                info.get("support_score", 0.0)
                            )

                            # Metadata only. No file opening.
                            stat = entry.stat(
                                follow_symlinks=False
                            )

                            if stat.st_size <= 0:
                                continue

                            folder = ntpath.dirname(
                                entry.path
                            )

                            category_results[
                                category
                            ]["count"] += 1

                            by_folder[folder] = (
                                by_folder.get(folder, 0) + 1
                            )

                            behaviors = info.get(
                                "behaviors", []
                            )

                            reason = (
                                "Matched file extension "
                                f"{extension}; associated "
                                "behavior labels: "
                                + ", ".join(behaviors)
                            )

                            files.append({
                                "path": entry.path,
                                "category": category,

                                # Behavior-derived category support,
                                # NOT individual file attack probability.
                                "support_score": round(score, 4),

                                # Preserve which predictions contributed.
                                "associated_behaviors": behaviors,

                                "reason": reason,

                                "size": stat.st_size,

                                "modified_time": datetime.fromtimestamp(
                                    stat.st_mtime
                                ).isoformat(timespec="seconds")
                            })


                        except PermissionError:
                            files_skipped_permission += 1

                        except OSError:
                            files_skipped_permission += 1

                        if progress_callback:
                            progress_callback(
                                files_scanned,
                                len(files)
                            )

                    if state == "partial":
                        break

            except PermissionError:
                files_skipped_permission += 1

            except OSError:
                files_skipped_permission += 1

    except Exception as exc:
        state = "error"
        message = str(exc)

    return {
        "sample": sample,
        "state": state,
        "scan_complete": state == "done",

        "files_scanned": files_scanned,
        "files_skipped_permission": files_skipped_permission,

        "at_risk_count": len(files),

        "last_scanned": datetime.now().strftime(
            "%H:%M"
        ),

        "categories": category_results,
        "flagged": flagged,

        "by_folder": by_folder,
        "files": files,

        "message": message
    }
