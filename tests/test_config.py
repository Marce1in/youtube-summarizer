from pathlib import Path

import pytest

from yt_gemini.config import load_settings
from yt_gemini.errors import ConfigError


def test_load_settings_uses_typed_defaults() -> None:
    settings = load_settings({})

    assert settings.database_path == Path(".data/app.sqlite3")
    assert settings.max_feed_items == 100
    assert settings.browser_channel == "chrome"
    assert settings.youtube_lookback.total_seconds() == 86400
    assert settings.auth_chrome_executable == Path("/usr/bin/google-chrome")


def test_load_settings_allows_no_browser_channel() -> None:
    settings = load_settings({"YT_GEMINI_BROWSER_CHANNEL": "none"})

    assert settings.browser_channel is None


def test_load_settings_accepts_channel_override() -> None:
    settings = load_settings({"YT_GEMINI_BROWSER_CHANNEL": "chromium"})

    assert settings.browser_channel == "chromium"


def test_load_settings_rejects_bad_integer() -> None:
    with pytest.raises(ConfigError, match="YT_GEMINI_MAX_FEED_ITEMS"):
        load_settings({"YT_GEMINI_MAX_FEED_ITEMS": "many"})


def test_load_settings_rejects_bad_boolean() -> None:
    with pytest.raises(ConfigError, match="YT_GEMINI_HEADLESS"):
        load_settings({"YT_GEMINI_HEADLESS": "maybe"})
