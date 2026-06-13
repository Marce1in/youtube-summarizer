import subprocess
from pathlib import Path
from typing import cast

import pytest

from yt_gemini.auth_chrome import AuthChromeProcess, build_auth_chrome_command
from yt_gemini.config import AppSettings, load_settings
from yt_gemini.errors import BrowserAutomationError
from yt_gemini.profile_lock import BrowserProfileLock


def test_build_auth_chrome_command_uses_persistent_profile() -> None:
    settings = load_settings(
        {
            "YT_GEMINI_BROWSER_PROFILE_DIR": "/browser-profile",
            "YT_GEMINI_AUTH_CHROME_EXECUTABLE": "/usr/bin/google-chrome-stable",
        }
    )

    command = build_auth_chrome_command(settings)

    assert command[0] == "/usr/bin/google-chrome-stable"
    assert "--user-data-dir=/browser-profile" in command
    assert settings.browser_profile_dir == Path("/browser-profile")


def test_build_auth_chrome_command_opens_login_targets() -> None:
    settings = load_settings({})

    command = build_auth_chrome_command(settings)

    assert settings.youtube_subscriptions_url in command
    assert settings.gemini_url in command


def test_build_auth_chrome_command_avoids_playwright_control_flags() -> None:
    command = build_auth_chrome_command(load_settings({}))

    assert not any("remote-debugging" in argument for argument in command)
    assert not any("enable-automation" in argument for argument in command)


def test_auth_chrome_process_detects_exited_browser() -> None:
    auth_chrome = AuthChromeProcess(load_settings({}))
    auth_chrome._process = cast(subprocess.Popen[bytes], ExitedChromeProcess())

    with pytest.raises(BrowserAutomationError, match="exited with code=17"):
        auth_chrome.ensure_running()


def test_auth_chrome_process_releases_profile_when_browser_exits_early(
    tmp_path: Path,
) -> None:
    settings = load_settings(
        {"YT_GEMINI_BROWSER_PROFILE_DIR": str(tmp_path / "profile")}
    )
    auth_chrome = AuthChromeProcess(settings, ExitedChromeStarter())

    with (
        pytest.raises(BrowserAutomationError, match="exited with code=17"),
        auth_chrome,
    ):
        pass

    profile_lock = BrowserProfileLock(settings.browser_profile_dir)
    profile_lock.acquire()
    profile_lock.release()


class ExitedChromeProcess:
    def poll(self) -> int:
        return 17


class ExitedChromeStarter:
    def __call__(self, settings: AppSettings) -> subprocess.Popen[bytes]:
        return cast(subprocess.Popen[bytes], ExitedChromeProcess())
