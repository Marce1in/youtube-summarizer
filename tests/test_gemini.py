from typing import cast

import pytest
from playwright.sync_api import Locator, Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from tests.fakes import FakeClock, SequenceTextReader
from yt_gemini.errors import BrowserAutomationError
from yt_gemini.gemini import (
    NewStableResponseCriteria,
    NewStableTextCriteria,
    ResponseSnapshot,
    _first_visible_locator,
    _login_required_visible,
    wait_for_new_stable_response,
    wait_for_new_stable_text,
    wait_for_stable_text,
)


def test_wait_for_stable_text_returns_final_stable_text() -> None:
    clock = FakeClock()
    reader = SequenceTextReader(["", "partial", "final", "final", "final"])

    text = wait_for_stable_text(reader.read_text, clock, 1.0, 10.0)

    assert text == "final"


def test_wait_for_stable_text_times_out_without_text() -> None:
    clock = FakeClock()
    reader = SequenceTextReader(["", "", ""])

    with pytest.raises(BrowserAutomationError, match="did not stabilize"):
        wait_for_stable_text(reader.read_text, clock, 1.0, 2.0)


def test_wait_for_new_stable_text_ignores_baseline_response() -> None:
    clock = FakeClock()
    reader = SequenceTextReader(["old", "old", "new partial", "new final", "new final"])

    text = wait_for_new_stable_text(
        reader.read_text,
        clock,
        _new_text_criteria("old", "prompt"),
    )

    assert text == "new final"


def test_wait_for_new_stable_text_ignores_prompt_echo() -> None:
    clock = FakeClock()
    reader = SequenceTextReader(["old", "prompt", "summary", "summary"])

    text = wait_for_new_stable_text(
        reader.read_text,
        clock,
        _new_text_criteria("old", "prompt"),
    )

    assert text == "summary"


def test_wait_for_new_stable_response_accepts_repeated_text_after_count_change() -> (
    None
):
    clock = FakeClock()
    reader = SequenceSnapshotReader(
        [
            ResponseSnapshot(1, "access denied"),
            ResponseSnapshot(2, "access denied"),
            ResponseSnapshot(2, "access denied"),
        ]
    )

    text = wait_for_new_stable_response(
        reader.read_snapshot,
        clock,
        _new_response_criteria(1, "access denied", "prompt"),
    )

    assert text == "access denied"


def test_wait_for_new_stable_response_ignores_unchanged_baseline() -> None:
    clock = FakeClock()
    reader = SequenceSnapshotReader([ResponseSnapshot(1, "access denied")])

    with pytest.raises(BrowserAutomationError, match="did not stabilize"):
        wait_for_new_stable_response(
            reader.read_snapshot,
            clock,
            _new_response_criteria(1, "access denied", "prompt", timeout=1.0),
        )


def test_wait_for_new_stable_response_ignores_prompt_echo() -> None:
    clock = FakeClock()
    reader = SequenceSnapshotReader(
        [
            ResponseSnapshot(2, "prompt"),
            ResponseSnapshot(2, "summary"),
            ResponseSnapshot(2, "summary"),
        ]
    )

    text = wait_for_new_stable_response(
        reader.read_snapshot,
        clock,
        _new_response_criteria(1, "old", "prompt"),
    )

    assert text == "summary"


def test_wait_for_new_stable_response_keeps_changed_text_fallback() -> None:
    clock = FakeClock()
    reader = SequenceSnapshotReader(
        [
            ResponseSnapshot(1, "new"),
            ResponseSnapshot(1, "new"),
            ResponseSnapshot(1, "new"),
        ]
    )

    text = wait_for_new_stable_response(
        reader.read_snapshot,
        clock,
        _new_response_criteria(1, "old", "prompt"),
    )

    assert text == "new"


def test_login_required_visible_ignores_hidden_sign_in_text() -> None:
    page = cast(Page, FakeGeminiPage([False]))

    assert not _login_required_visible(page)


def test_login_required_visible_detects_visible_sign_in_control() -> None:
    page = cast(Page, FakeGeminiPage([False, True]))

    assert _login_required_visible(page)


def test_first_visible_locator_skips_hidden_candidates() -> None:
    hidden = FakeSignInOption(False)
    visible = FakeSignInOption(True)
    locator = cast(Locator, FakeIndexedLocator([hidden, visible]))

    result = cast(object, _first_visible_locator(locator))

    assert result is visible


def _new_text_criteria(baseline_text: str, ignored_text: str) -> NewStableTextCriteria:
    return NewStableTextCriteria(
        stable_seconds=1.0,
        timeout_seconds=10.0,
        baseline_text=baseline_text,
        ignored_text=ignored_text,
    )


def _new_response_criteria(
    baseline_response_count: int,
    baseline_text: str,
    ignored_text: str,
    timeout: float = 10.0,
) -> NewStableResponseCriteria:
    return NewStableResponseCriteria(
        stable_seconds=1.0,
        timeout_seconds=timeout,
        baseline_response_count=baseline_response_count,
        baseline_text=baseline_text,
        ignored_text=ignored_text,
    )


class SequenceSnapshotReader:
    def __init__(self, values: list[ResponseSnapshot]) -> None:
        self._values = values
        self._index = 0

    def read_snapshot(self) -> ResponseSnapshot:
        if self._index >= len(self._values):
            return self._values[-1]
        value = self._values[self._index]
        self._index += 1
        return value


class FakeGeminiPage:
    def __init__(self, visible_options: list[bool]) -> None:
        self._visible_options = visible_options

    def get_by_text(self, pattern: object) -> "FakeIndexedLocator":
        return FakeIndexedLocator(
            [FakeSignInOption(visible) for visible in self._visible_options]
        )


class FakeIndexedLocator:
    def __init__(self, options: list["FakeSignInOption"]) -> None:
        self._options = options

    def count(self) -> int:
        return len(self._options)

    def nth(self, index: int) -> "FakeSignInOption":
        return self._options[index]


class FakeSignInOption:
    def __init__(self, visible: bool) -> None:
        self._visible = visible

    def wait_for(self, state: str, timeout: int) -> None:
        if not self._visible:
            raise PlaywrightTimeoutError("sign-in control is hidden")
