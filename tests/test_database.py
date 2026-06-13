from datetime import UTC, datetime
from pathlib import Path

from yt_gemini.database import SummaryDatabase
from yt_gemini.models import (
    NormalizedUrl,
    RunCounters,
    SubscriptionVideo,
    VideoId,
    VideoStatus,
)


def test_database_inserts_video_once_and_updates_summary(tmp_path: Path) -> None:
    database = SummaryDatabase(tmp_path / "app.sqlite3")
    database.initialize()
    video = _subscription_video()
    discovered_at = datetime(2026, 6, 13, 12, 0, tzinfo=UTC)

    assert database.insert_pending(video, discovered_at)
    assert not database.insert_pending(video, discovered_at)
    assert database.video_status(video.video_id) == VideoStatus.PENDING

    database.mark_summarized(video.video_id, "summary text", discovered_at)
    assert database.video_status(video.video_id) == VideoStatus.SUMMARIZED
    summaries = database.recent_summaries(5)

    assert len(summaries) == 1
    assert summaries[0].status == VideoStatus.SUMMARIZED
    assert summaries[0].summary == "summary text"
    assert summaries[0].published_label == "1 hour ago"
    assert summaries[0].published_at_estimate == video.published_at_estimate
    assert summaries[0].discovered_at == discovered_at
    assert summaries[0].summarized_at == discovered_at


def test_database_records_failed_video(tmp_path: Path) -> None:
    database = SummaryDatabase(tmp_path / "app.sqlite3")
    database.initialize()
    video = _subscription_video()

    database.insert_pending(video, datetime(2026, 6, 13, 12, 0, tzinfo=UTC))
    database.mark_failed(video.video_id, "gemini timeout")
    assert database.video_status(video.video_id) == VideoStatus.FAILED
    summary = database.recent_summaries(1)[0]

    assert summary.status == VideoStatus.FAILED
    assert summary.error == "gemini timeout"


def test_database_finishes_run(tmp_path: Path) -> None:
    database = SummaryDatabase(tmp_path / "app.sqlite3")
    database.initialize()
    started_at = datetime(2026, 6, 13, 12, 0, tzinfo=UTC)

    run_id = database.create_run(started_at)
    database.finish_run(run_id, counters=_empty_counters(), finished_at=started_at)

    assert run_id == 1


def _subscription_video() -> SubscriptionVideo:
    published_at = datetime(2026, 6, 13, 11, 0, tzinfo=UTC)
    return SubscriptionVideo(
        video_id=VideoId("abc123xyz00"),
        url=NormalizedUrl("https://www.youtube.com/watch?v=abc123xyz00"),
        title="Video title",
        channel="Channel",
        published_label="1 hour ago",
        published_at_estimate=published_at,
    )


def _empty_counters() -> RunCounters:
    return RunCounters()
