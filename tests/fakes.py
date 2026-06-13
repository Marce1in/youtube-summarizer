from datetime import UTC, datetime, timedelta


class FakeClock:
    def __init__(self) -> None:
        self._now = datetime(2026, 6, 13, 12, 0, tzinfo=UTC)
        self._monotonic = 0.0

    def now(self) -> datetime:
        return self._now + timedelta(seconds=self._monotonic)

    def monotonic(self) -> float:
        return self._monotonic

    def sleep(self, seconds: float) -> None:
        self._monotonic += seconds


class SequenceTextReader:
    def __init__(self, values: list[str]) -> None:
        self._values = values
        self._index = 0

    def read_text(self) -> str:
        if self._index >= len(self._values):
            return self._values[-1]
        value = self._values[self._index]
        self._index += 1
        return value
