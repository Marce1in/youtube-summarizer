from datetime import UTC, datetime
from pathlib import Path

import pytest

from cli import main
from database import SummaryDatabase
from models import NormalizedUrl, SubscriptionVideo, VideoId


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
    monkeypatch.setenv("YOUTUBE_SUMMARIZER_DATABASE_PATH", str(database_path))

    exit_code = main(["list", "--limit", "1"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "published_label: 1 hour ago" in output
    assert "published_at_estimate: 2026-06-13T11:00:00+00:00" in output
    assert "discovered_at: 2026-06-13T12:00:00+00:00" in output
    assert "summarized_at: 2026-06-13T12:05:00+00:00" in output


def test_list_command_filters_by_since_date(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    database_path = tmp_path / "app.sqlite3"
    database = SummaryDatabase(database_path)
    database.initialize()
    database.insert_pending(
        _subscription_video(
            video_id="old123xyz00",
            title="Old video",
            published_at=datetime(2026, 6, 12, 23, 59, tzinfo=UTC),
        ),
        datetime(2026, 6, 13, 12, 0, tzinfo=UTC),
    )
    database.insert_pending(
        _subscription_video(
            video_id="new123xyz00",
            title="New video",
            published_at=datetime(2026, 6, 13, 0, 0, tzinfo=UTC),
        ),
        datetime(2026, 6, 13, 12, 5, tzinfo=UTC),
    )
    monkeypatch.setenv("YOUTUBE_SUMMARIZER_DATABASE_PATH", str(database_path))

    exit_code = main(["list", "--since", "2026-06-13", "--limit", "10"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "New video" in output
    assert "Old video" not in output


def test_list_command_filters_by_since_datetime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    database_path = tmp_path / "app.sqlite3"
    database = SummaryDatabase(database_path)
    database.initialize()
    database.insert_pending(
        _subscription_video(
            video_id="old123xyz00",
            title="Old video",
            published_at=datetime(2026, 6, 13, 9, 59, tzinfo=UTC),
        ),
        datetime(2026, 6, 13, 12, 0, tzinfo=UTC),
    )
    database.insert_pending(
        _subscription_video(
            video_id="new123xyz00",
            title="New video",
            published_at=datetime(2026, 6, 13, 10, 0, tzinfo=UTC),
        ),
        datetime(2026, 6, 13, 12, 5, tzinfo=UTC),
    )
    monkeypatch.setenv("YOUTUBE_SUMMARIZER_DATABASE_PATH", str(database_path))

    exit_code = main(["list", "--since", "2026-06-13T10:00:00+00:00"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "New video" in output
    assert "Old video" not in output


def _subscription_video(
    video_id: str = "abc123xyz00",
    title: str = "Video title",
    published_at: datetime = datetime(2026, 6, 13, 11, 0, tzinfo=UTC),
) -> SubscriptionVideo:
    return SubscriptionVideo(
        video_id=VideoId(video_id),
        url=NormalizedUrl(f"https://www.youtube.com/watch?v={video_id}"),
        title=title,
        channel="Channel",
        published_label="1 hour ago",
        published_at_estimate=published_at,
    )
