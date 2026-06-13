from types import TracebackType

from playwright.sync_api import (
    BrowserContext,
    Playwright,
    ViewportSize,
    sync_playwright,
)
from playwright.sync_api import (
    Error as PlaywrightError,
)

from yt_gemini.config import AppSettings
from yt_gemini.errors import BrowserAutomationError
from yt_gemini.profile_lock import BrowserProfileLock, remove_stale_chromium_locks


class BrowserSession:
    """Context manager for the persistent Playwright browser profile.

    Example:
        with BrowserSession(settings) as context:
            page = context.new_page()
    """

    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings
        self._playwright: Playwright | None = None
        self._context: BrowserContext | None = None
        self._profile_lock: BrowserProfileLock | None = None

    def __enter__(self) -> BrowserContext:
        self._acquire_profile()
        try:
            self._playwright = sync_playwright().start()
            self._context = self._launch_context(self._playwright)
            self._context.set_default_timeout(self._settings.operation_timeout_ms)
            return self._context
        except PlaywrightError as err:
            self._release_resources()
            raise BrowserAutomationError(_launch_failure_message(err)) from err

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._release_resources()

    def _acquire_profile(self) -> None:
        self._profile_lock = BrowserProfileLock(self._settings.browser_profile_dir)
        self._profile_lock.acquire()
        remove_stale_chromium_locks(self._settings.browser_profile_dir)

    def _release_resources(self) -> None:
        try:
            self._close_context()
            self._stop_playwright()
        finally:
            self._release_profile()

    def _close_context(self) -> None:
        if self._context is None:
            return
        self._context.close()
        self._context = None

    def _stop_playwright(self) -> None:
        if self._playwright is None:
            return
        self._playwright.stop()
        self._playwright = None

    def _release_profile(self) -> None:
        if self._profile_lock is None:
            return
        self._profile_lock.release()
        self._profile_lock = None

    def _launch_context(self, playwright: Playwright) -> BrowserContext:
        if self._settings.browser_channel is None:
            return self._launch_default_context(playwright)
        return self._launch_channel_context(playwright)

    def _launch_default_context(self, playwright: Playwright) -> BrowserContext:
        return playwright.chromium.launch_persistent_context(
            user_data_dir=str(self._settings.browser_profile_dir),
            headless=self._settings.browser_headless,
            viewport=_viewport(self._settings),
            env=_browser_environment(self._settings),
        )

    def _launch_channel_context(self, playwright: Playwright) -> BrowserContext:
        return playwright.chromium.launch_persistent_context(
            user_data_dir=str(self._settings.browser_profile_dir),
            headless=self._settings.browser_headless,
            viewport=_viewport(self._settings),
            env=_browser_environment(self._settings),
            channel=self._settings.browser_channel,
        )


def _viewport(settings: AppSettings) -> ViewportSize:
    return {"width": settings.viewport_width, "height": settings.viewport_height}


def _browser_environment(settings: AppSettings) -> dict[str, str | float | bool]:
    return {"DISPLAY": settings.display, "HOME": str(settings.browser_home_dir)}


def _launch_failure_message(err: PlaywrightError) -> str:
    first_line = str(err).splitlines()[0]
    return f"browser profile launch failed: {first_line}"
