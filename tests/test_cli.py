from datetime import UTC, datetime
from pathlib import Path

import pytest

from yt_gemini.cli import main
from yt_gemini.database import SummaryDatabase
from yt_gemini.models import NormalizedUrl, SubscriptionVideo, VideoId


def test_list_command_prints_stored_dates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    database_path = tmp_path / "app.sqlite3"
    database = SummaryDatabase(database_path)
    database.initialize()
    discovered_at = datetime(2026, 6, 13, 12, 0, tzinfo=UTC)
    summarized_at = datetime(2026, 6, 13, 12, 5, tzinfo=UTC)
    database.insert_pending(_subscription_video(), discovered_at)
    database.mark_summarized(VideoId("abc123xyz00"), "summary text", summarized_at)
    monkeypatch.setenv("YT_GEMINI_DATABASE_PATH", str(database_path))

    exit_code = main(["list", "--limit", "1"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "published_label: 1 hour ago" in output
    assert "published_at_estimate: 2026-06-13T11:00:00+00:00" in output
    assert "discovered_at: 2026-06-13T12:00:00+00:00" in output
    assert "summarized_at: 2026-06-13T12:05:00+00:00" in output


def _subscription_video() -> SubscriptionVideo:
    return SubscriptionVideo(
        video_id=VideoId("abc123xyz00"),
        url=NormalizedUrl("https://www.youtube.com/watch?v=abc123xyz00"),
        title="Video title",
        channel="Channel",
        published_label="1 hour ago",
        published_at_estimate=datetime(2026, 6, 13, 11, 0, tzinfo=UTC),
    )
