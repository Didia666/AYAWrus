import os
import json
import stat
import hashlib
import secrets
import tempfile
import threading
from pathlib import Path
from datetime import datetime

from system.config import (
    QUARANTINE_INDEX_FILE,
    QUARANTINE_DIR,
    _normalize_path,
    DETECTED_MALWARE,
    DETECTED_SUSPICIOUS,
)

from system.history.logs import (
    load_log,
    add_log_entry,
)

_QUARANTINE_LOCK = threading.RLock()

QUARANTINE_ROOT = Path(QUARANTINE_DIR).resolve()
INDEX_PATH = Path(QUARANTINE_INDEX_FILE)

QUARANTINE_ROOT.mkdir(
    parents=True,
    exist_ok=True,
)


def _sha256(file_path):
    digest = hashlib.sha256()

    with open(file_path, "rb") as file:
        for chunk in iter(
            lambda: file.read(1024 * 1024),
            b""
        ):
            digest.update(chunk)

    return digest.hexdigest()


def _reject_symlink(path):
    if Path(path).is_symlink():
        raise ValueError(
            "Symbolic links are not permitted"
        )


def _require_quarantine_path(path):
    candidate = Path(
        os.path.abspath(os.fspath(path))
    )

    _reject_symlink(candidate)

    if candidate.parent != QUARANTINE_ROOT:
        raise ValueError(
            "Path is outside the quarantine directory"
        )

    if not candidate.is_file():
        raise FileNotFoundError(candidate)

    return candidate




def _load_quarantine_index():
    if not INDEX_PATH.exists():
        return []

    with INDEX_PATH.open(
        "r", encoding="utf-8"
    ) as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise ValueError("Invalid quarantine index")

    return data


def _save_quarantine_index(entries):
    """
    Save through a temporary file, then atomically
    replace the current JSON index.
    """
    fd, temp_path = tempfile.mkstemp(
        prefix=".quarantine-index-",
        suffix=".tmp",
        dir=QUARANTINE_ROOT,
    )

    try:
        with os.fdopen(
            fd, "w", encoding="utf-8"
        ) as file:
            json.dump(entries, file, indent=4)
            file.flush()
            os.fsync(file.fileno())

        os.replace(temp_path, INDEX_PATH)

    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def quarantine_file(file_path):
    with _QUARANTINE_LOCK:
        original = Path(os.path.abspath(file_path))

        try:
            _reject_symlink(original)

            if not original.is_file():
                return (
                    f"Failed to quarantine {file_path}: "
                    "Source file does not exist"
                )

            if (
                original == QUARANTINE_ROOT
                or QUARANTINE_ROOT in original.parents
            ):
                raise ValueError(
                    "Cannot quarantine a quarantine file"
                )

            entries = _load_quarantine_index()

            normalized = _normalize_path(str(original))

            for entry in entries:
                if (
                    _normalize_path(
                        entry.get("original_path", "")
                    ) == normalized
                ):
                    return (
                        f"{file_path} -> "
                        "ALREADY IN QUARANTINE"
                    )

            original_stat = original.stat()
            original_hash = _sha256(original)

            # Generate an unpredictable ID.
            quarantine_id = secrets.token_hex(16)
            random_name = (
                f"{quarantine_id}.quarantine"
            )

            dest = QUARANTINE_ROOT / random_name

            # Exclusive creation prevents accidental
            # overwriting of another quarantine object.
            try:
                with original.open("rb") as source:
                    with dest.open("xb") as target:
                        for chunk in iter(
                            lambda: source.read(1024 * 1024),
                            b""
                        ):
                            target.write(chunk)

                        target.flush()
                        os.fsync(target.fileno())

                copied_hash = _sha256(dest)

                # Detect a file that changed while
                # being copied.
                source_hash_after = _sha256(original)

                if (
                    copied_hash != original_hash
                    or source_hash_after != original_hash
                ):
                    raise RuntimeError(
                        "File changed during quarantine"
                    )

                if dest.stat().st_size != original_stat.st_size:
                    raise RuntimeError(
                        "File size changed during quarantine"
                    )

                os.chmod(dest, stat.S_IREAD)

                # Preserve existing detection metadata.
                probability = None
                result = None

                try:
                    history = load_log()

                    for log in reversed(history):
                        if (
                            _normalize_path(log.get("file_path"))
                            == normalized
                        ):
                            probability = log.get(
                                "probability"
                            )
                            result = log.get("result")
                            break

                except Exception:
                    pass

                entry = {
                    "id": quarantine_id,
                    "dest_path": str(dest),
                    "original_path": str(original),
                    "original_name": original.name,
                    "timestamp": datetime.now().isoformat(),
                    "size": original_stat.st_size,
                    "sha256": original_hash,
                    "original_mode": stat.S_IMODE(
                        original_stat.st_mode
                    ),
                    "result": result,
                    "probability": probability,
                    "status": "PENDING_REMOVAL",
                }

                entries.append(entry)
                _save_quarantine_index(entries)

            except Exception:
                # Original file is still present.
                # Do not leave a partial payload.
                if dest.exists():
                    os.chmod(dest, stat.S_IWRITE)
                    dest.unlink()

                raise

            # Only remove the source after the
            # quarantined copy has been verified.
            try:
                original.unlink()

            except OSError as exc:
                # Retain the verified copy and index.
                # Never claim full quarantine succeeded.
                return (
                    f"Failed to fully quarantine "
                    f"{file_path}: original file "
                    f"could not be removed ({exc})"
                )

            entry["status"] = "QUARANTINED"
            _save_quarantine_index(entries)

            try:
                add_log_entry(
                    str(original),
                    "QUARANTINED",
                    probability,
                    f"SHA-256: {original_hash}",
                )
            except Exception as exc:
                print(
                    f"Quarantine logging failed: {exc}"
                )

            return (
                f"{file_path} -> MOVED TO QUARANTINE"
            )

        except Exception as exc:
            return (
                f"Failed to quarantine "
                f"{file_path}: {exc}"
            )

    
def process_quarantine():
    if not DETECTED_MALWARE:
        print("\nNo malware detected.")
        if DETECTED_SUSPICIOUS:
            print("\n=== SUSPICIOUS FILES ===")
            for file_path in DETECTED_SUSPICIOUS:
                print(f" - {file_path}")
        return

    print("\n=== MALWARE DETECTED ===")
    for i, file in enumerate(DETECTED_MALWARE):
        print(f"[{i}] {file}")

    if DETECTED_SUSPICIOUS:
        print("\n=== SUSPICIOUS FILES ===")
        for file_path in DETECTED_SUSPICIOUS:
            print(f" - {file_path}")

    print("\nChoose files to quarantine:")
    print("Example: 0,2,3  or  'all'")

    choice = input("> ")

    if choice.lower() == "all":
        for file in DETECTED_MALWARE:
            print(quarantine_file(file))
        return
    
    try:
        indexes = [int(x) for x in choice.split(",")]
        for idx in indexes:
            if 0 <= idx < len(DETECTED_MALWARE):
                print(quarantine_file(DETECTED_MALWARE[idx]))
    except ValueError:
        print("Invalid input. Skipping quarantine.")

def list_quarantine_items():
    entries = _load_quarantine_index()
    # annotate existence so UI can show missing items instead of hiding them
    for e in entries:
        # Check both original dest_path and current quarantine dir
        dest = e.get("dest_path", "")
        if not os.path.exists(dest):
            # Try checking in current QUARANTINE_DIR by filename
            fname = os.path.basename(dest)
            alt_dest = os.path.join(QUARANTINE_DIR, fname)
            e['_exists'] = os.path.exists(alt_dest)
            if e['_exists']:
                e['_alt_dest'] = alt_dest
        else:
            e['_exists'] = True

    # Return latest entries first
    try:
        return sorted(entries, key=lambda e: e.get("timestamp", ""), reverse=True)
    except Exception:
        return list(reversed(entries))

def is_quarantined(file_path: str) -> bool:
    entries = _load_quarantine_index()
    normalized_fp = _normalize_path(file_path)
    return any(_normalize_path(e.get("original_path")) == normalized_fp for e in entries)


def restore_file(dest_path, confirmed=False, add_to_exclusions=False):
    if not confirmed:
        return "Restore requires explicit confirmation"

    with _QUARANTINE_LOCK:
        try:
            entries = _load_quarantine_index()
            normalized = _normalize_path(dest_path)

            entry = next(
                (
                    e for e in entries
                    if _normalize_path(
                        e.get("dest_path", "")
                    ) == normalized
                ),
                None,
            )

            if entry is None:
                return "Quarantine record not found"

            if entry.get("status") != "QUARANTINED":
                return "Quarantine record is not finalized"

            if not entry.get("sha256"):
                return (
                    "Legacy record: integrity hash "
                    "is unavailable"
                )

            source = _require_quarantine_path(
                entry["dest_path"]
            )

            original = Path(
                os.path.abspath(
                    entry["original_path"]
                )
            )

            _reject_symlink(original)
            _reject_symlink(original.parent)

            # Check quarantine integrity.
            current_hash = _sha256(source)

            if current_hash != entry["sha256"]:
                return (
                    "RESTORE BLOCKED: "
                    "SHA-256 integrity mismatch"
                )

            if source.stat().st_size != entry["size"]:
                return (
                    "RESTORE BLOCKED: "
                    "File size mismatch"
                )

            # Refuse overwrites.
            if original.exists() or original.is_symlink():
                return (
                    "RESTORE BLOCKED: "
                    "Destination already exists"
                )

            # Do not create arbitrary destination
            # directories automatically.
            if not original.parent.is_dir():
                return (
                    "RESTORE BLOCKED: "
                    "Original directory is missing"
                )

            # Exclusive creation ensures an existing
            # destination file is not overwritten.
            with source.open("rb") as src:
                with original.open("xb") as target:
                    for chunk in iter(
                        lambda: src.read(1024 * 1024),
                        b""
                    ):
                        target.write(chunk)

                    target.flush()
                    os.fsync(target.fileno())

            restored_hash = _sha256(original)

            if restored_hash != entry["sha256"]:
                original.unlink()
                return (
                    "RESTORE FAILED: "
                    "Restored hash mismatch"
                )

            # Keep restoration restrictive.
            os.chmod(original, stat.S_IREAD)

            entry["status"] = "RESTORED_PENDING_CLEANUP"
            _save_quarantine_index(entries)

            # Remove quarantined copy.
            os.chmod(source, stat.S_IWRITE)
            source.unlink()

            entries.remove(entry)
            _save_quarantine_index(entries)

            exclusion_error = None
            if add_to_exclusions:
                # This is an explicit user trust decision, never automatic.
                try:
                    from system.security.exclusions import add_exclusion
                    add_exclusion(str(original))
                except Exception as exc:
                    exclusion_error = str(exc)

            try:
                add_log_entry(
                    str(original),
                    "RESTORED",
                    entry.get("probability"),
                    "Restored after SHA-256 verification",
                )
            except Exception as exc:
                print(f"Restore logging failed: {exc}")

            if exclusion_error:
                return (f"Restored to {original} (WARNING: could not add exclusion: "
                        f"{exclusion_error}; the file may be detected again)")
            return f"Restored to {original}"

        except Exception as exc:
            return f"Failed to restore: {exc}"


def delete_file(dest_path):
    with _QUARANTINE_LOCK:
        try:
            entries = _load_quarantine_index()
            normalized = _normalize_path(dest_path)

            entry = next(
                (
                    e for e in entries
                    if _normalize_path(
                        e.get("dest_path", "")
                    ) == normalized
                ),
                None,
            )

            if entry is None:
                return (
                    "Deletion blocked: "
                    "No matching quarantine record"
                )

            if entry.get("status") != "QUARANTINED":
                return (
                    "Deletion blocked: "
                    "Quarantine operation is incomplete"
                )

            target = _require_quarantine_path(
                entry["dest_path"]
            )

            # Only operate on a verified registered file.
            expected_hash = entry.get("sha256")

            if not expected_hash:
                return (
                    "Deletion blocked: "
                    "Missing integrity metadata"
                )

            if _sha256(target) != expected_hash:
                return (
                    "Deletion blocked: "
                    "Quarantine file has changed"
                )

            os.chmod(target, stat.S_IWRITE)
            target.unlink()

            entries.remove(entry)
            _save_quarantine_index(entries)

            try:
                add_log_entry(
                    entry["original_path"],
                    "DELETED",
                    entry.get("probability"),
                    "Quarantined file deleted",
                )
            except Exception as exc:
                print(f"Deletion log failed: {exc}")

            return "Deleted"

        except Exception as exc:
            return f"Failed to delete: {exc}"
