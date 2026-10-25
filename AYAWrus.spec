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
    (
        str(project_root / "Model_Malware" / filename),
        "Model_Malware",
    )
    for filename in (
        "rf_ember_model_malware.onnx",
        "rf_ember_model_malware.pkl",
        "selected_features.pkl",
    )
] + [
    (
        str(project_root / "Model_Behavior" / filename),
        "Model_Behavior",
    )
    for filename in (
        "behavior_label_map.json",
        "behavior_label_mapping.json",
        "behavior_model_metadata.json",
        "model_metrics.json",
        "rf_ember_model.onnx",
        "rf_ember_model.pkl",
        "selected_features.pkl",
    )
]
config_path = project_root / "system" / "config.json"
if not config_path.is_file():
    raise FileNotFoundError(f"API configuration file not found: {config_path}")

mobile_apk_path = (
    project_root
    / "AYAWRusMobile"
    / "app"
    / "build"
    / "outputs"
    / "apk"
    / "debug"
    / "app-debug.apk"
)
if not mobile_apk_path.is_file():
    raise FileNotFoundError(
        f"AYAWrus Mobile APK not found: {mobile_apk_path}. "
        "Build it with AYAWRusMobile\\gradlew.bat assembleDebug first."
    )
mobile_apk_files = [
    (
        str(mobile_apk_path),
        "AYAWRusMobile/app/build/outputs/apk/debug",
    )
]

packaged_config_dir = Path(tempfile.mkdtemp(prefix="ayawrus-build-"))
packaged_config_path = packaged_config_dir / "config.json"
packaged_config_path.write_text(json.dumps({}), encoding="utf-8")
atexit.register(shutil.rmtree, packaged_config_dir, ignore_errors=True)
config_files = [(str(packaged_config_path), "system")]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=(
        font_files
        + icon_files
        + certificate_files
        + model_files
        + config_files
        + mobile_apk_files
    ),
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
