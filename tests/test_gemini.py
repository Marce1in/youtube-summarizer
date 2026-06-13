import pytest

from tests.fakes import FakeClock, SequenceTextReader
from yt_gemini.errors import BrowserAutomationError
from yt_gemini.gemini import (
    NewStableResponseCriteria,
    NewStableTextCriteria,
    ResponseSnapshot,
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
