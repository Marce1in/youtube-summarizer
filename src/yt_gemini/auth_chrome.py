import subprocess
from types import TracebackType
from typing import Protocol, Self

from yt_gemini.config import AppSettings
from yt_gemini.errors import BrowserAutomationError
from yt_gemini.profile_lock import BrowserProfileLock, remove_stale_chromium_locks


class ChromeStarter(Protocol):
    def __call__(self, settings: AppSettings) -> subprocess.Popen[bytes]: ...


class AuthChromeProcess:
    """Run real Chrome for manual Google login without Playwright control.

    Example:
        with AuthChromeProcess(settings):
            ...
    """

    def __init__(
        self,
        settings: AppSettings,
        process_starter: ChromeStarter | None = None,
    ) -> None:
        self._settings = settings
        self._process_starter = (
            start_auth_chrome if process_starter is None else process_starter
        )
        self._profile_lock: BrowserProfileLock | None = None
        self._process: subprocess.Popen[bytes] | None = None

    def __enter__(self) -> Self:
        self._acquire_profile()
        try:
            self._process = self._process_starter(self._settings)
            self.ensure_running()
        except OSError as err:
            self.stop()
            raise BrowserAutomationError(_chrome_start_error(err)) from err
        except BrowserAutomationError:
            self.stop()
            raise
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.stop()

    def stop(self) -> None:
        try:
            _stop_process(self._process)
        finally:
            self._process = None
            self._release_profile()

    def ensure_running(self) -> None:
        """Raise when the direct Chrome login browser has exited.

        Example:
            auth_chrome.ensure_running()
        """

        if self._process is None:
            raise BrowserAutomationError("auth chrome process was not started")
        exit_code = self._process.poll()
        if exit_code is None:
            return
        raise BrowserAutomationError(_chrome_exit_error(exit_code))

    def _acquire_profile(self) -> None:
        self._profile_lock = BrowserProfileLock(self._settings.browser_profile_dir)
        self._profile_lock.acquire()
        remove_stale_chromium_locks(self._settings.browser_profile_dir)

    def _release_profile(self) -> None:
        if self._profile_lock is None:
            return
        self._profile_lock.release()
        self._profile_lock = None


def build_auth_chrome_command(settings: AppSettings) -> tuple[str, ...]:
    """Build the direct Chrome command used for manual login.

    Example:
        command = build_auth_chrome_command(settings)
    """

    return (
        str(settings.auth_chrome_executable),
        f"--user-data-dir={settings.browser_profile_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-dev-shm-usage",
        "--no-sandbox",
        "--password-store=basic",
        "--use-mock-keychain",
        settings.youtube_subscriptions_url,
        settings.gemini_url,
    )


def start_auth_chrome(settings: AppSettings) -> subprocess.Popen[bytes]:
    """Start direct Chrome for manual login.

    Example:
        process = start_auth_chrome(settings)
    """

    return subprocess.Popen(
        build_auth_chrome_command(settings),
        env=_chrome_environment(settings),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _chrome_environment(settings: AppSettings) -> dict[str, str]:
    return {"DISPLAY": settings.display, "HOME": str(settings.browser_home_dir)}


def _stop_process(process: subprocess.Popen[bytes] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def _chrome_start_error(err: OSError) -> str:
    return f"auth chrome executable failed to start: {err}"


def _chrome_exit_error(exit_code: int) -> str:
    return (
        f"auth chrome exited with code={exit_code}; expected login browser to stay open"
    )
