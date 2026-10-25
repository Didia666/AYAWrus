# AYAWrus — signed component and ML artifact integrity

## Scope
This patch modifies `system/model_load.py` and adds `system/security/integrity.py` and `tools/sign_release.py`. It DOES NOT include your large ML models or an already signed manifest. Sign against the complete project, including `Model_Malware/` and `Model_Behavior/`.

## Install
1. Back up your original `system/model_load.py` and merge/copy the supplied files into your project root.
2. Install `cryptography` into the AYAWrus environment: `python -m pip install cryptography`.
3. Verify your model directories contain all your expected `.onnx`/`.pkl`, feature-selection `.pkl`, and metadata `.json` files.
4. From the complete project root, sign a **trusted release**:
   `python tools/sign_release.py --root . --key ../ayawrus-signing.key`
   The private key is created **outside** the project. KEEP IT PRIVATE, backed up and not in git, ZIP, or installer. On future releases reuse the same key; don't regenerate it casually.
5. Distribute `integrity_manifest.json` and `system/security/integrity.py` with the signed application. Do not ship `tools/sign_release.py` or the key to users.
6. In **main.py**, before importing `ui`/`system.model_load` or initializing scans, insert:

```python
from system.security.integrity import verify_installation, IntegrityError
try:
    verify_installation()
except IntegrityError as exc:
    import ctypes
    ctypes.windll.user32.MessageBoxW(0, str(exc), "AYAWrus integrity failure", 0x10)
    raise SystemExit(1)
```

If main.py already imports protected modules before this block, move this block above those imports. The patched model loader also refuses to load models/metadata when verification fails.

## Tests
- Run startup unchanged: should pass.
- **On a test copy**, modify any signed `.py`, `.onnx`, `.pkl`, or model metadata `.json` file. Restart: must report integrity failure. Restore the original file and restart: should pass.
- Remove `integrity_manifest.json`: startup must fail closed.
- Modify only a writable `history_log.json`: should not fail (runtime data is deliberately not signed).

## Notes and threat model
- Hash+signature prevents *manifest substitution*, provided the **public key and verification code are trusted** (protect them using a signed installer, trusted executable/code signing, or OS access controls). An attacker who can alter the Python entrypoint and verifier can bypass the check. This is not a kernel-level tamper-proof solution.
- A source-code manifest is intended for the **source-code/development layout**. PyInstaller one-file/one-dir builds need a separate build-time packaging strategy (sign the distributable and verify the executable/package on installation, and sign any external model assets). Do not assume this source-layout manifest will work with bundled `.py` sources.
- Validation runs once per process. It's a startup/content-integrity check, not continuous file monitoring. Keep signing materials securely separated.
- This release tool signs all `.py` files under `system` and `ui`; this is deliberate, but every deliberate code edit requires re-signing before running. It also signs `.pkl`, `.onnx`, `.json`, `.npy`, `.npz` inside model directories. It excludes mutable `system` JSON runtime data.
- A signed `.pkl` is safe to deserialize only if you originally obtained it from a trusted source and trust the signer. Prefer ONNX for model loading where possible.
