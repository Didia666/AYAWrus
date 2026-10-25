import json
import re
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


GITHUB_RELEASES_API = "https://api.github.com/repos/Didia666/AYAWrus/releases?per_page=100"
GITHUB_RELEASES_PAGE = "https://github.com/Didia666/AYAWrus/releases"
SYSTEM_VERSION = (1, 0, 0)
SYSTEM_RELEASE_TAG = re.compile(r"system-v(\d+)\.(\d+)\.(\d+)")
INSTALLER_ASSET = "AYAWrus-Setup.exe"
MAX_RELEASES_RESPONSE_BYTES = 1_000_000


class UpdateCheckError(RuntimeError):
    pass


@dataclass(frozen=True)
class SystemUpdate:
    version: tuple[int, int, int]
    release_url: str


def _parse_system_version(tag_name):
    match = SYSTEM_RELEASE_TAG.fullmatch(tag_name)
    if match is None:
        return None
    return tuple(int(part) for part in match.groups())


def check_for_system_update(opener=None):
    request = Request(
        GITHUB_RELEASES_API,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "AYAWrus-System-Updater",
        },
    )
    open_url = opener or urlopen

    try:
        with open_url(request, timeout=10) as response:
            raw_payload = response.read(MAX_RELEASES_RESPONSE_BYTES + 1)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise UpdateCheckError(f"Couldn't check GitHub releases: {exc}") from exc

    if len(raw_payload) > MAX_RELEASES_RESPONSE_BYTES:
        raise UpdateCheckError("GitHub returned an unexpectedly large release list.")

    try:
        releases = json.loads(raw_payload)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise UpdateCheckError("GitHub returned invalid release data.") from exc

    if not isinstance(releases, list):
        raise UpdateCheckError("GitHub returned an unexpected release list.")

    newer_releases = []
    for release in releases:
        if not isinstance(release, dict):
            raise UpdateCheckError("GitHub returned an unexpected release entry.")
        if release.get("draft") or release.get("prerelease"):
            continue
        version = _parse_system_version(release.get("tag_name", ""))
        if version is not None and version > SYSTEM_VERSION:
            newer_releases.append((version, release))

    if not newer_releases:
        return None

    version, release = max(newer_releases, key=lambda item: item[0])
    assets = release.get("assets")
    if not isinstance(assets, list):
        raise UpdateCheckError(
            f"System update {'.'.join(map(str, version))} has no installer attached."
        )
    if not any(
        isinstance(asset, dict) and asset.get("name") == INSTALLER_ASSET
        for asset in assets
    ):
        raise UpdateCheckError(
            f"System update {'.'.join(map(str, version))} is missing {INSTALLER_ASSET}."
        )

    tag_name = release["tag_name"]
    return SystemUpdate(
        version=version,
        release_url=f"{GITHUB_RELEASES_PAGE}/tag/{tag_name}",
    )
