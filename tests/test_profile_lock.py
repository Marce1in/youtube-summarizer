from pathlib import Path

import pytest

from errors import BrowserProfileLockError
from profile_lock import BrowserProfileLock, remove_stale_chromium_locks


def test_browser_profile_lock_blocks_second_process(tmp_path: Path) -> None:
    profile_dir = tmp_path / "profile"
    first_lock = BrowserProfileLock(profile_dir)

    first_lock.acquire()
    try:
        with pytest.raises(BrowserProfileLockError, match="already in use"):
            BrowserProfileLock(profile_dir).acquire()
    finally:
        first_lock.release()


def test_browser_profile_lock_releases_for_next_process(tmp_path: Path) -> None:
    profile_dir = tmp_path / "profile"
    first_lock = BrowserProfileLock(profile_dir)

    first_lock.acquire()
    first_lock.release()
    second_lock = BrowserProfileLock(profile_dir)
    second_lock.acquire()
    second_lock.release()


def test_remove_stale_chromium_locks(tmp_path: Path) -> None:
    profile_dir = tmp_path / "profile"
    profile_dir.mkdir()
    stale_files = [
        profile_dir / "SingletonLock",
        profile_dir / "SingletonCookie",
        profile_dir / "SingletonSocket",
    ]
    for stale_file in stale_files:
        stale_file.write_text("stale", encoding="utf-8")

    remove_stale_chromium_locks(profile_dir)

    assert not any(stale_file.exists() for stale_file in stale_files)
