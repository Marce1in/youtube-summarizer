import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from playwright.sync_api import Error as PlaywrightError


class ScreenshotCapable(Protocol):
    def screenshot(self, *, path: str, full_page: bool) -> bytes: ...


@dataclass(frozen=True)
class FailureScreenshot:
    path: Path | None
    error: str | None


def capture_failure_screenshot(
    page: ScreenshotCapable,
    screenshot_dir: Path,
    label: str,
    captured_at: datetime,
) -> FailureScreenshot:
    """Capture a best-effort screenshot for selector or login failures.

    Example:
        artifact = capture_failure_screenshot(page, screenshots, "gemini", now)
    """

    screenshot_path = _screenshot_path(screenshot_dir, label, captured_at)
    try:
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(screenshot_path), full_page=True)
    except (OSError, PlaywrightError) as err:
        return FailureScreenshot(None, f"screenshot capture failed: {err}")
    return FailureScreenshot(screenshot_path, None)


def failure_message(error: str, screenshot: FailureScreenshot) -> str:
    """Attach screenshot details to a user-facing automation error.

    Example:
        text = failure_message("gemini timed out", artifact)
    """

    if screenshot.path is not None:
        return f"{error} (screenshot: {screenshot.path})"
    if screenshot.error is not None:
        return f"{error} ({screenshot.error})"
    return error


def _screenshot_path(screenshot_dir: Path, label: str, captured_at: datetime) -> Path:
    timestamp = captured_at.strftime("%Y%m%dT%H%M%S%z")
    return screenshot_dir / f"{timestamp}-{_safe_label(label)}.png"


def _safe_label(label: str) -> str:
    safe_label = re.sub(r"[^a-zA-Z0-9_-]+", "-", label).strip("-")
    if safe_label:
        return safe_label
    return "failure"
