# AYAWrus

## Cleaning detected malware

On the desktop Scan page, select detected files and choose **Clean Selected**.
AYAWrus removes confirmed malicious files and reports the result; if removal is
blocked, it attempts to move the file to quarantine instead. A file that has
changed since scanning is left untouched. Suspicious (not confirmed malicious)
files are quarantined rather than deleted. This clean action removes the whole
file; it does not repair or disinfect code inside an executable.

## Building the Windows installer with AYAWrus Mobile

Build the mobile APK before packaging the desktop app. The PyInstaller spec
includes the APK at the path used by the desktop `/mobile/download` endpoint;
without this step an installed app cannot offer the mobile download.

From the repository root, run:

```powershell
.\AYAWRusMobile\gradlew.bat -p .\AYAWRusMobile assembleDebug
python -m PyInstaller --noconfirm --clean AYAWrus.spec
& "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" AYAWrus.iss
```

This produces `AYAWRusMobile\app\build\outputs\apk\debug\app-debug.apk` and
includes it in `dist\AYAWrus-Setup.exe`.

## System updates

The installed desktop application contains the compiled AYAWrus system, so a
source-code commit by itself cannot update an existing installation. To publish
an update that appears under **Settings > System Update**:

1. Increase `SYSTEM_VERSION` in `system/system_updates.py` to the new version
   and keep it in sync with `MyAppVersion` in `AYAWrus.iss`.
2. Build the Windows installer using the project's PyInstaller and Inno Setup
   packaging process.
3. Create a stable GitHub release tagged `system-vX.Y.Z` (for example,
   `system-v1.0.1`) and attach the installer as `AYAWrus-Setup.exe`.

The app checks only stable `system-vX.Y.Z` releases newer than its embedded
version. When one is found, it opens that release page so the user can review
the notes and run the installer. It does not download or replace application
files automatically. Releases without the required installer are reported as
incomplete.