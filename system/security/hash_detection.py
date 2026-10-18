
import hashlib
import re
import threading
from pathlib import Path

HASH_DATABASE = (
    Path(__file__).resolve().parent / "hashes.txt"
)

_HASH_PATTERN = re.compile(r"^[a-fA-F0-9]{64}$")
_HASH_LOCK = threading.Lock()
_HASHES = frozenset()
_DB_SIGNATURE = None


def load_malware_hashes(force=False):
    """Load local hashes, reloading when the database changes."""
    global _HASHES, _DB_SIGNATURE

    with _HASH_LOCK:
        try:
            stat = HASH_DATABASE.stat()
            signature = (stat.st_mtime_ns, stat.st_size)
        except FileNotFoundError:
            signature = None

        if not force and signature == _DB_SIGNATURE:
            return _HASHES

        hashes = set()

        if signature is not None:
            with HASH_DATABASE.open(
                "r", encoding="utf-8"
            ) as database:
                for line in database:
                    value = line.split("#", 1)[0].strip()

                    if _HASH_PATTERN.fullmatch(value):
                        hashes.add(value.lower())

        _HASHES = frozenset(hashes)
        _DB_SIGNATURE = signature

        return _HASHES


def calculate_sha256(file_path):
    """Hash file contents without loading them all into RAM."""
    sha256 = hashlib.sha256()

    with open(file_path, "rb") as file:
        for chunk in iter(
            lambda: file.read(1024 * 1024), b""
        ):
            sha256.update(chunk)

    return sha256.hexdigest()


def check_file_hash(file_path):
    """
    Return:
      matched: True/False
      sha256: calculated digest

    Raises OSError if the file cannot be read.
    """
    known_hashes = load_malware_hashes()

    digest = calculate_sha256(file_path)

    return {
        "matched": digest in known_hashes,
        "sha256": digest,
        "detection_method": (
            "SHA256_SIGNATURE"
            if digest in known_hashes
            else None
        ),
    }
