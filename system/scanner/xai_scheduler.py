
import os
import uuid
import json
import threading

from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor

from system.xai.engine import XAIExplanationEngine


XAI_MAX_WORKERS = 2
XAI_MAX_PENDING = 4

# Completed reports kept in RAM.
XAI_CACHE_MAX_REPORTS = 50
XAI_CACHE_MAX_BYTES = 8 * 1024 * 1024
XAI_MAX_REPORT_BYTES = 512 * 1024

# Limit completed status records too.
XAI_MAX_STATUS_RECORDS = 100


_executor = ThreadPoolExecutor(
    max_workers=XAI_MAX_WORKERS,
    thread_name_prefix="AYAWrusXAI"
)

_slots = threading.BoundedSemaphore(
    XAI_MAX_PENDING
)

_lock = threading.RLock()

# detection_id -> report
_cache = OrderedDict()

# detection_id -> {status, error}
_status = OrderedDict()

_cache_bytes = 0
_shutdown = False


def new_detection_id():
    return uuid.uuid4().hex


def _set_status(detection_id, status, error=None):
    with _lock:
        _status[detection_id] = {
            "status": status,
            "error": error,
        }
        _status.move_to_end(detection_id)

        # Remove old terminal states only.
        while len(_status) > XAI_MAX_STATUS_RECORDS:
            oldest_id = next(iter(_status))

            if _status[oldest_id]["status"] == "PENDING":
                break

            _status.pop(oldest_id)


def _store_report(detection_id, report):
    global _cache_bytes

    # Serialize for a consistent size estimate.
    # This assumes reports are JSON-compatible.
    payload = json.dumps(
        report,
        ensure_ascii=False,
        default=str
    )

    size = len(payload.encode("utf-8"))

    if size > XAI_MAX_REPORT_BYTES:
        _set_status(
            detection_id,
            "TOO_LARGE",
            "XAI report exceeds the cache limit"
        )
        return

    with _lock:
        while (
            _cache
            and (
                len(_cache) >= XAI_CACHE_MAX_REPORTS
                or _cache_bytes + size > XAI_CACHE_MAX_BYTES
            )
        ):
            evicted_id, (_, old_size) = _cache.popitem(
                last=False
            )

            _cache_bytes -= old_size

            _set_status(
                evicted_id,
                "EVICTED",
                "Report removed to free cache memory"
            )
        # Store the JSON-decoded copy to avoid retaining
        # large mutable objects from worker instances.
        _cache[detection_id] = (
            json.loads(payload),
            size
        )
        _cache_bytes += size

    _set_status(detection_id, "READY")


def _analyze(
    detection_id,
    file_path,
    features,
    probability,
    result
):
    try:
        if not os.path.isfile(file_path):
            raise FileNotFoundError(
                f"File unavailable for XAI: {file_path}"
            )

        with open(file_path, "rb") as f:
            file_bytes = f.read()

        engine = XAIExplanationEngine()

        report = engine.analyze_file(
            file_path,
            file_bytes,
            features,
            probability,
            result
        )

        if report is None:
            raise RuntimeError(
                "XAI engine returned no report"
            )

        _store_report(detection_id, report)

    except Exception as e:
        _set_status(
            detection_id,
            "ERROR",
            str(e)
        )

        print(
            f"[XAI] {detection_id}: {e}"
        )


def _release_slot(future):
    _slots.release()

    if future.cancelled():
        return

    try:
        future.result()
    except Exception as e:
        print(f"[XAI] Unhandled worker error: {e}")


def schedule_xai(
    file_path,
    features,
    probability,
    result,
    detection_id=None
):
    """
    Returns:
        detection_id: accepted job
        None: queue full or scheduler shut down
    """

    detection_id = (
        detection_id or new_detection_id()
    )

    # No unbounded queue.
    if not _slots.acquire(blocking=False):
        print(
            f"[XAI] Queue full: {file_path}"
        )
        return None

    with _lock:
        if _shutdown:
            _slots.release()
            return None

        if detection_id in _status:
            _slots.release()
            raise ValueError(
                f"Duplicate detection ID: {detection_id}"
            )

        _set_status(detection_id, "PENDING")

        try:
            future = _executor.submit(
                _analyze,
                detection_id,
                file_path,
                features,
                probability,
                result
            )

        except RuntimeError as e:
            _slots.release()
            _set_status(
                detection_id,
                "ERROR",
                str(e)
            )
            return None

    future.add_done_callback(_release_slot)

    return detection_id


def get_xai_status(detection_id):
    if not detection_id:
        return {
            "status": "NOT_SCHEDULED",
            "error": None
        }

    with _lock:
        value = _status.get(detection_id)

        if value is None:
            return {
                "status": "NOT_FOUND",
                "error": None
            }

        return dict(value)


def get_xai_report(detection_id):
    if not detection_id:
        return None

    with _lock:
        entry = _cache.get(detection_id)

        if entry is None:
            return None

        # Most recently accessed report goes last.
        _cache.move_to_end(detection_id)

        return entry[0]


def shutdown_xai():
    global _shutdown

    with _lock:
        if _shutdown:
            return
        _shutdown = True

    _executor.shutdown(
        wait=True,
        cancel_futures=True
    )
