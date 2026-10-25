"""AYAWrus release integrity verification. Trust requires a trusted copy of this module."""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import threading

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature

# Release tool replaces this once, with your public key. NEVER store the private key here.
PUBLIC_KEY_B64 = "aMr65CvM779plBdFcr9k7mkubki2nFYf9n0Lg9jmh0o="
_MANIFEST_NAME = "integrity_manifest.json"
_VERIFIED = False
_LOCK = threading.Lock()

class IntegrityError(RuntimeError):
    pass


def _root():
    return Path(__file__).resolve().parents[2]


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _payload_bytes(files):
    return json.dumps({"schema": 1, "files": files}, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def verify_installation(force=False):
    """Fail closed on absent/unsigned manifest or altered protected file."""
    global _VERIFIED
    with _LOCK:
        if _VERIFIED and not force:
            return True
        if PUBLIC_KEY_B64 == "REPLACE_WITH_RELEASE_PUBLIC_KEY":
            raise IntegrityError("Release public key has not been configured")
        root = _root()
        manifest_path = root / _MANIFEST_NAME
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("schema") != 1:
                raise IntegrityError("Unsupported integrity manifest schema")
            files = manifest["files"]
            signature = base64.b64decode(manifest["signature"], validate=True)
            key = Ed25519PublicKey.from_public_bytes(base64.b64decode(PUBLIC_KEY_B64, validate=True))
            key.verify(signature, _payload_bytes(files))
            if not isinstance(files, dict) or not files:
                raise IntegrityError("Empty or invalid integrity manifest")
            root_real = root.resolve()
            for relative, expected in files.items():
                if not isinstance(relative, str) or not isinstance(expected, str):
                    raise IntegrityError("Invalid integrity manifest entry")
                candidate = (root / relative).resolve(strict=True)
                if not candidate.is_relative_to(root_real) or not candidate.is_file():
                    raise IntegrityError(f"Invalid protected path: {relative}")
                if _hash_file(candidate) != expected:
                    raise IntegrityError(f"Protected component altered: {relative}")
        except IntegrityError:
            raise
        except (OSError, ValueError, KeyError, TypeError, InvalidSignature) as exc:
            raise IntegrityError(f"Integrity verification failed: {exc}") from exc
        _VERIFIED = True
        return True
