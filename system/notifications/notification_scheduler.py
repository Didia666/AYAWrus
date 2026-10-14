
import threading
from concurrent.futures import ThreadPoolExecutor

from system.notifications import send_telegram_notification


NOTIFICATION_MAX_WORKERS = 1
NOTIFICATION_MAX_PENDING = 10

_notification_executor = ThreadPoolExecutor(
    max_workers=NOTIFICATION_MAX_WORKERS,
    thread_name_prefix="AYAWrusNotify"
)

_notification_slots = threading.BoundedSemaphore(
    NOTIFICATION_MAX_PENDING
)

_notification_lock = threading.Lock()
_notification_shutdown = False


def _send_notification(message):
    try:
        send_telegram_notification(message)
    except Exception as exc:
        print(f"[Notification] Failed: {exc}")


def _release_slot(future):
    _notification_slots.release()


def schedule_notification(message):
    """
    Submit optional Telegram delivery without
    blocking file scanning.

    Returns True if queued successfully.
    """
    with _notification_lock:
        if _notification_shutdown:
            return False

        if not _notification_slots.acquire(blocking=False):
            print("[Notification] Queue full; not delivered.")
            return False

        try:
            future = _notification_executor.submit(
                _send_notification,
                message
            )
        except RuntimeError:
            _notification_slots.release()
            return False

        future.add_done_callback(_release_slot)
        return True


def shutdown_notifications():
    global _notification_shutdown

    with _notification_lock:
        _notification_shutdown = True

    _notification_executor.shutdown(
        wait=True,
        cancel_futures=False
    )
