"""Run on a trusted build machine, NOT during normal AYAWrus execution.
Usage: python tools/sign_release.py --root . --key ../ayawrus-signing.key
First run creates private key outside project. Subsequent runs reuse it.
Requires cryptography.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

parser = argparse.ArgumentParser()
parser.add_argument("--root", required=True)
parser.add_argument("--key", required=True)
args = parser.parse_args()
root = Path(args.root).resolve()
key_path = Path(args.key).resolve()
if key_path.is_relative_to(root):
    parser.error("Private signing key must be stored OUTSIDE the project")
if key_path.exists():
    key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
else:
    key = Ed25519PrivateKey.generate()
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    try: key_path.chmod(0o600)
    except OSError: pass
pub = base64.b64encode(key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()
integrity_py = root / "system/security/integrity.py"
source = integrity_py.read_text(encoding="utf-8")
import re
source, count = re.subn(r'^PUBLIC_KEY_B64 = "[^"]*"', f'PUBLIC_KEY_B64 = "{pub}"', source, count=1, flags=re.MULTILINE)
if count != 1: raise SystemExit("Cannot configure integrity public key")
integrity_py.write_text(source, encoding="utf-8")
# Include security/scan modules and full model directories, except runtime data.
for model_name in ("Model_Malware", "Model_Behavior"):
    folder = root / model_name
    if not folder.is_dir() or not any(p.suffix.lower() in {".onnx", ".pkl"} for p in folder.iterdir() if p.is_file()):
        parser.error(f"Missing model artifacts in {model_name}; sign from complete project root")
if not (root / "system/model_load.py").is_file():
    parser.error("Missing system/model_load.py")
paths = [root / "system/model_load.py"]
for directory in (root / "system/security", root / "system/scanner", root / "Model_Malware", root / "Model_Behavior"):
    if directory.exists():
        paths.extend(p for p in directory.rglob("*") if p.is_file() and p.suffix.lower() in {".py", ".pkl", ".onnx", ".json", ".npy", ".npz"})
# Also protect all user interface application source files and other fixed system source.
for directory in (root / "ui", root / "system"):
    if directory.exists():
        paths.extend(p for p in directory.rglob("*.py") if "__pycache__" not in p.parts)
paths = sorted(set(paths))
files = {}
for p in paths:
    rel = p.relative_to(root).as_posix()
    h = hashlib.sha256()
    with p.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    files[rel] = h.hexdigest()
if not files: raise SystemExit("No protected files found")
payload = json.dumps({"schema": 1, "files": files}, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
manifest = {"schema": 1, "files": files, "signature": base64.b64encode(key.sign(payload)).decode()}
(root / "integrity_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print(f"Signed {len(files)} components. Signing key: {key_path} (DO NOT DISTRIBUTE)")
