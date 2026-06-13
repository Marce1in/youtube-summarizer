from datetime import UTC, datetime
from pathlib import Path

from yt_gemini.artifacts import (
    FailureScreenshot,
    capture_failure_screenshot,
    failure_message,
)


def test_capture_failure_screenshot_writes_sanitized_path(tmp_path: Path) -> None:
    page = RecordingScreenshotPage()
    captured_at = datetime(2026, 6, 13, 12, 30, tzinfo=UTC)

    artifact = capture_failure_screenshot(page, tmp_path, "gemini:abc/123", captured_at)

    assert artifact.error is None
    assert artifact.path == tmp_path / "20260613T123000+0000-gemini-abc-123.png"
    assert page.last_path == artifact.path
    assert artifact.path.read_bytes() == b"fake-png"


def test_capture_failure_screenshot_reports_write_failure(tmp_path: Path) -> None:
    page = FailingScreenshotPage()

    artifact = capture_failure_screenshot(page, tmp_path, "gemini", datetime.now(UTC))

    assert artifact.path is None
    assert artifact.error == "screenshot capture failed: disk full"


def test_failure_message_appends_screenshot_path(tmp_path: Path) -> None:
    artifact = FailureScreenshot(tmp_path / "failure.png", None)

    assert failure_message("gemini timeout", artifact).endswith(
        f"(screenshot: {tmp_path / 'failure.png'})"
    )


def test_failure_message_appends_screenshot_error() -> None:
    artifact = FailureScreenshot(None, "screenshot capture failed: denied")

    assert failure_message("gemini timeout", artifact) == (
        "gemini timeout (screenshot capture failed: denied)"
    )


class RecordingScreenshotPage:
    def __init__(self) -> None:
        self.last_path: Path | None = None

    def screenshot(self, *, path: str, full_page: bool) -> bytes:
        self.last_path = Path(path)
        self.last_path.write_bytes(b"fake-png")
        assert full_page
        return b"fake-png"


class FailingScreenshotPage:
    def screenshot(self, *, path: str, full_page: bool) -> bytes:
        raise OSError("disk full")
