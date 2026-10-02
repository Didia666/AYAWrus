# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import atexit
import json
import mscerts
import shutil
import tempfile

project_root = Path(SPECPATH)
mscerts_dir = Path(mscerts.__file__).resolve().parent
font_files = [
    (str(font_path), "assets/fonts")
    for font_path in (project_root / "assets" / "fonts").glob("*.ttf")
]
icon_files = [
    (str(icon_path), "assets/icons")
    for icon_path in (project_root / "assets" / "icons").glob("*.png")
]
certificate_files = [
    (str(certificate_path), "mscerts")
    for certificate_path in mscerts_dir.glob("*.stl")
] + [
    (str(certificate_path), "mscerts")
    for certificate_path in mscerts_dir.glob("*.pem")
]
model_files = [
    (str(project_root / "rf_ember_model.pkl"), "."),
    (str(project_root / "selected_features.pkl"), "system"),
    (str(project_root / "system" / "rf_ember_model.onnx"), "system"),
    (
        str(project_root / "Model_Behavior" / "rf_ember_model.pkl"),
        "Model_Behavior",
    ),
    (
        str(project_root / "Model_Behavior" / "selected_features.pkl"),
        "Model_Behavior",
    ),
]
config_path = project_root / "system" / "config.json"
if not config_path.is_file():
    raise FileNotFoundError(f"API configuration file not found: {config_path}")

with config_path.open(encoding="utf-8") as config_file:
    user_config = json.load(config_file)

api_key = user_config.get("ai_api_key")
api_url = user_config.get("ai_api_url")
if not isinstance(api_key, str) or not api_key.strip():
    raise ValueError("Set ai_api_key in system/config.json before building.")
if not isinstance(api_url, str) or not api_url.strip():
    raise ValueError("Set ai_api_url in system/config.json before building.")

packaged_config_dir = Path(tempfile.mkdtemp(prefix="ayawrus-build-"))
packaged_config_path = packaged_config_dir / "config.json"
packaged_config_path.write_text(
    json.dumps({"ai_api_key": api_key, "ai_api_url": api_url}),
    encoding="utf-8",
)
atexit.register(shutil.rmtree, packaged_config_dir, ignore_errors=True)
config_files = [(str(packaged_config_path), "system")]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=font_files + icon_files + certificate_files + model_files + config_files,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AYAWrus',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AYAWrus',
)
