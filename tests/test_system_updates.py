import io
import json

import pytest

from system import system_updates


def _response(releases):
    return io.BytesIO(json.dumps(releases).encode("utf-8"))


def _release(tag_name, *, assets=None, prerelease=False, draft=False):
    return {
        "tag_name": tag_name,
        "assets": assets if assets is not None else [
            {"name": system_updates.INSTALLER_ASSET}
        ],
        "prerelease": prerelease,
        "draft": draft,
    }


def test_check_for_system_update_returns_latest_stable_system_release():
    releases = [
        _release("system-v1.0.0"),
        _release("system-v1.0.2"),
        _release("system-v1.0.3", prerelease=True),
        _release("v9.0.0"),
    ]

    update = system_updates.check_for_system_update(
        opener=lambda request, timeout: _response(releases)
    )

    assert update.version == (1, 0, 2)
    assert update.release_url.endswith("/tag/system-v1.0.2")


def test_check_for_system_update_returns_none_when_no_new_system_release():
    releases = [_release("system-v1.0.0"), _release("system-v1.1.0", draft=True)]

    update = system_updates.check_for_system_update(
        opener=lambda request, timeout: _response(releases)
    )

    assert update is None


def test_check_for_system_update_reports_missing_installer():
    releases = [_release("system-v1.0.1", assets=[])]

    with pytest.raises(system_updates.UpdateCheckError, match="missing AYAWrus-Setup.exe"):
        system_updates.check_for_system_update(
            opener=lambda request, timeout: _response(releases)
        )
