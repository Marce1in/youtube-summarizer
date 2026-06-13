import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

JsonScalar = str | int | float | bool | None


class JsonLogger:
    """Append structured runtime events without exposing secrets.

    Example:
        JsonLogger(Path("events.jsonl")).event("job_started", {"run_id": 1})
    """

    def __init__(self, log_path: Path) -> None:
        self._log_path = log_path

    def event(self, event_name: str, fields: Mapping[str, JsonScalar]) -> None:
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, JsonScalar] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event": event_name,
        }
        payload.update(fields)
        with self._log_path.open("a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(payload, sort_keys=True) + "\n")
