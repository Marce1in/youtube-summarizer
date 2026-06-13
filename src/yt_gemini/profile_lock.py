import fcntl
from pathlib import Path
from types import TracebackType
from typing import TextIO

from yt_gemini.errors import BrowserAutomationError, BrowserProfileLockError

_CHROMIUM_LOCK_FILES = ("SingletonLock", "SingletonCookie", "SingletonSocket")


class BrowserProfileLock:
    """Exclusive file lock for the persistent browser profile.

    Example:
        with BrowserProfileLock(Path("/browser-profile")):
            ...
    """

    def __init__(self, profile_dir: Path) -> None:
        self._profile_dir = profile_dir
        self._lock_file: TextIO | None = None

    def __enter__(self) -> None:
        self.acquire()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.release()

    def acquire(self) -> None:
        self._profile_dir.mkdir(parents=True, exist_ok=True)
        lock_file = (self._profile_dir / ".yt-gemini.lock").open("w", encoding="utf-8")
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as err:
            lock_file.close()
            raise BrowserProfileLockError(_locked_message(self._profile_dir)) from err
        self._lock_file = lock_file

    def release(self) -> None:
        if self._lock_file is None:
            return
        fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_UN)
        self._lock_file.close()
        self._lock_file = None


def remove_stale_chromium_locks(profile_dir: Path) -> None:
    """Remove Chromium singleton files after the app profile lock is acquired.

    Example:
        remove_stale_chromium_locks(Path("/browser-profile"))
    """

    for filename in _CHROMIUM_LOCK_FILES:
        _unlink_profile_file(profile_dir / filename)


def _unlink_profile_file(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    try:
        path.unlink()
    except OSError as err:
        raise BrowserAutomationError(_stale_lock_message(path)) from err


def _locked_message(profile_dir: Path) -> str:
    return f"browser profile_dir={str(profile_dir)!r} is already in use"


def _stale_lock_message(path: Path) -> str:
    return f"chromium lock_file={str(path)!r} could not be removed"
