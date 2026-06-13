import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Literal, cast

from yt_gemini.errors import ConfigError

BrowserChannel = Literal["chrome", "chrome-beta", "chromium"]

_CHANNELS = ("chrome", "chrome-beta", "chromium")


@dataclass(frozen=True)
class AppSettings:
    database_path: Path
    browser_profile_dir: Path
    screenshot_dir: Path
    log_path: Path
    youtube_lookback: timedelta
    max_feed_items: int
    browser_headless: bool
    browser_channel: BrowserChannel | None
    display: str
    manage_display: bool
    viewport_width: int
    viewport_height: int
    navigation_timeout_ms: int
    operation_timeout_ms: int
    response_stable_seconds: float
    response_timeout_seconds: float
    youtube_subscriptions_url: str
    gemini_url: str
    browser_home_dir: Path
    auth_chrome_executable: Path


def load_settings(raw_environment: Mapping[str, str] | None = None) -> AppSettings:
    """Load typed settings from environment variables.

    Example:
        settings = load_settings({"YT_GEMINI_MAX_FEED_ITEMS": "20"})
    """

    environment = os.environ if raw_environment is None else raw_environment
    return _settings_from_environment(environment)


def _settings_from_environment(environment: Mapping[str, str]) -> AppSettings:
    return AppSettings(
        database_path=_path_var(
            environment, "YT_GEMINI_DATABASE_PATH", ".data/app.sqlite3"
        ),
        browser_profile_dir=_path_var(
            environment, "YT_GEMINI_BROWSER_PROFILE_DIR", ".data/browser-profile"
        ),
        screenshot_dir=_path_var(
            environment, "YT_GEMINI_SCREENSHOT_DIR", ".data/screenshots"
        ),
        log_path=_path_var(
            environment, "YT_GEMINI_LOG_PATH", ".data/logs/automation.jsonl"
        ),
        youtube_lookback=_lookback(environment),
        max_feed_items=_int_var(environment, "YT_GEMINI_MAX_FEED_ITEMS", 100),
        browser_headless=_bool_var(environment, "YT_GEMINI_HEADLESS", False),
        browser_channel=_channel_var(environment, "YT_GEMINI_BROWSER_CHANNEL"),
        display=_str_var(environment, "YT_GEMINI_DISPLAY", ":99"),
        manage_display=_bool_var(environment, "YT_GEMINI_MANAGE_DISPLAY", False),
        viewport_width=_viewport_width(environment),
        viewport_height=_viewport_height(environment),
        navigation_timeout_ms=_navigation_timeout(environment),
        operation_timeout_ms=_operation_timeout(environment),
        response_stable_seconds=_response_stable_seconds(environment),
        response_timeout_seconds=_response_timeout_seconds(environment),
        youtube_subscriptions_url=_youtube_subscriptions_url(environment),
        gemini_url=_gemini_url(environment),
        browser_home_dir=_path_var(
            environment, "YT_GEMINI_BROWSER_HOME_DIR", "/home/pwuser"
        ),
        auth_chrome_executable=_path_var(
            environment, "YT_GEMINI_AUTH_CHROME_EXECUTABLE", "/usr/bin/google-chrome"
        ),
    )


def _lookback(environment: Mapping[str, str]) -> timedelta:
    return timedelta(
        hours=_int_var(environment, "YT_GEMINI_YOUTUBE_LOOKBACK_HOURS", 24)
    )


def _viewport_width(environment: Mapping[str, str]) -> int:
    return _int_var(environment, "YT_GEMINI_VIEWPORT_WIDTH", 1440)


def _viewport_height(environment: Mapping[str, str]) -> int:
    return _int_var(environment, "YT_GEMINI_VIEWPORT_HEIGHT", 1000)


def _navigation_timeout(environment: Mapping[str, str]) -> int:
    return _int_var(environment, "YT_GEMINI_NAVIGATION_TIMEOUT_MS", 60000)


def _operation_timeout(environment: Mapping[str, str]) -> int:
    return _int_var(environment, "YT_GEMINI_OPERATION_TIMEOUT_MS", 120000)


def _response_stable_seconds(environment: Mapping[str, str]) -> float:
    return _float_var(environment, "YT_GEMINI_RESPONSE_STABLE_SECONDS", 3.0)


def _response_timeout_seconds(environment: Mapping[str, str]) -> float:
    return _float_var(environment, "YT_GEMINI_RESPONSE_TIMEOUT_SECONDS", 240.0)


def _youtube_subscriptions_url(environment: Mapping[str, str]) -> str:
    return _str_var(
        environment,
        "YT_GEMINI_YOUTUBE_SUBSCRIPTIONS_URL",
        "https://www.youtube.com/feed/subscriptions",
    )


def _gemini_url(environment: Mapping[str, str]) -> str:
    return _str_var(
        environment, "YT_GEMINI_GEMINI_URL", "https://gemini.google.com/app"
    )


def _str_var(environment: Mapping[str, str], name: str, default: str) -> str:
    value = environment.get(name, default).strip()
    if value:
        return value
    raise ConfigError(f"{name}={value!r} must be a non-empty string")


def _path_var(environment: Mapping[str, str], name: str, default: str) -> Path:
    return Path(_str_var(environment, name, default))


def _int_var(environment: Mapping[str, str], name: str, default: int) -> int:
    raw_value = environment.get(name, str(default)).strip()
    try:
        value = int(raw_value)
    except ValueError as err:
        raise ConfigError(f"{name}={raw_value!r} must be an integer") from err
    if value > 0:
        return value
    raise ConfigError(f"{name}={raw_value!r} must be greater than 0")


def _float_var(environment: Mapping[str, str], name: str, default: float) -> float:
    raw_value = environment.get(name, str(default)).strip()
    try:
        value = float(raw_value)
    except ValueError as err:
        raise ConfigError(f"{name}={raw_value!r} must be a number") from err
    if value > 0:
        return value
    raise ConfigError(f"{name}={raw_value!r} must be greater than 0")


def _bool_var(environment: Mapping[str, str], name: str, default: bool) -> bool:
    raw_value = environment.get(name, str(default)).strip().lower()
    if raw_value in {"1", "true", "yes", "on"}:
        return True
    if raw_value in {"0", "false", "no", "off"}:
        return False
    raise ConfigError(f"{name}={raw_value!r} must be true or false")


def _channel_var(environment: Mapping[str, str], name: str) -> BrowserChannel | None:
    raw_value = environment.get(name, "chrome").strip().lower()
    if raw_value in {"", "none", "default"}:
        return None
    if raw_value in _CHANNELS:
        return cast(BrowserChannel, raw_value)
    raise ConfigError(f"{name}={raw_value!r} must be one of {_CHANNELS!r} or empty")
