import sqlite3
from datetime import datetime
from pathlib import Path

from yt_gemini.models import (
    NormalizedUrl,
    RunCounters,
    StoredVideoSummary,
    SubscriptionVideo,
    VideoId,
    VideoStatus,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id TEXT NOT NULL UNIQUE,
    url TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    channel TEXT NOT NULL,
    published_label TEXT NOT NULL,
    published_at_estimate TEXT NOT NULL,
    discovered_at TEXT NOT NULL,
    summarized_at TEXT,
    status TEXT NOT NULL,
    summary TEXT,
    error TEXT
);

CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    videos_seen INTEGER NOT NULL DEFAULT 0,
    videos_new INTEGER NOT NULL DEFAULT 0,
    videos_summarized INTEGER NOT NULL DEFAULT 0,
    videos_failed INTEGER NOT NULL DEFAULT 0,
    videos_skipped INTEGER NOT NULL DEFAULT 0
);
"""


class SummaryDatabase:
    """SQLite persistence for run metadata and video summaries.

    Example:
        database = SummaryDatabase(Path("app.sqlite3"))
    """

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def initialize(self) -> None:
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(_SCHEMA)

    def create_run(self, started_at: datetime) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO runs (started_at) VALUES (?)",
                (started_at.isoformat(),),
            )
            if cursor.lastrowid is None:
                raise sqlite3.DatabaseError("run insert returned no id")
            return cursor.lastrowid

    def finish_run(
        self, run_id: int, counters: RunCounters, finished_at: datetime
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE runs
                SET finished_at = ?, videos_seen = ?, videos_new = ?,
                    videos_summarized = ?, videos_failed = ?, videos_skipped = ?
                WHERE id = ?
                """,
                _finish_run_values(run_id, counters, finished_at),
            )

    def insert_pending(self, video: SubscriptionVideo, discovered_at: datetime) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO videos (
                    video_id, url, title, channel, published_label,
                    published_at_estimate, discovered_at, status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                _pending_values(video, discovered_at),
            )
            return cursor.rowcount == 1

    def video_status(self, video_id: VideoId) -> VideoStatus | None:
        with self._connect() as connection:
            cursor = connection.execute(
                "SELECT status FROM videos WHERE video_id = ? LIMIT 1",
                (str(video_id),),
            )
            row = cursor.fetchone()
        if row is None:
            return None
        return VideoStatus(row[0])

    def mark_summarized(
        self, video_id: VideoId, summary: str, summarized_at: datetime
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE videos
                SET status = ?, summary = ?, summarized_at = ?, error = NULL
                WHERE video_id = ?
                """,
                (
                    VideoStatus.SUMMARIZED.value,
                    summary,
                    summarized_at.isoformat(),
                    str(video_id),
                ),
            )

    def mark_failed(self, video_id: VideoId, error: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE videos SET status = ?, error = ? WHERE video_id = ?",
                (VideoStatus.FAILED.value, error, str(video_id)),
            )

    def recent_summaries(self, limit: int) -> list[StoredVideoSummary]:
        with self._connect() as connection:
            rows = connection.execute(_RECENT_SUMMARIES_SQL, (limit,)).fetchall()
        return [_summary_from_row(row) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path)
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection


_RECENT_SUMMARIES_SQL = """
SELECT
    video_id, url, title, channel, published_label, published_at_estimate,
    discovered_at, summarized_at, status, summary, error
FROM videos
ORDER BY COALESCE(summarized_at, discovered_at) DESC
LIMIT ?
"""


def _finish_run_values(
    run_id: int,
    counters: RunCounters,
    finished_at: datetime,
) -> tuple[str, int, int, int, int, int, int]:
    return (
        finished_at.isoformat(),
        counters.videos_seen,
        counters.videos_new,
        counters.videos_summarized,
        counters.videos_failed,
        counters.videos_skipped,
        run_id,
    )


def _pending_values(
    video: SubscriptionVideo,
    discovered_at: datetime,
) -> tuple[str, str, str, str, str, str, str, str]:
    return (
        str(video.video_id),
        str(video.url),
        video.title,
        video.channel,
        video.published_label,
        video.published_at_estimate.isoformat(),
        discovered_at.isoformat(),
        VideoStatus.PENDING.value,
    )


def _summary_from_row(
    row: tuple[
        str,
        str,
        str,
        str,
        str,
        str,
        str,
        str | None,
        str,
        str | None,
        str | None,
    ],
) -> StoredVideoSummary:
    summarized_at = None if row[7] is None else datetime.fromisoformat(row[7])
    return StoredVideoSummary(
        video_id=VideoId(row[0]),
        url=NormalizedUrl(row[1]),
        title=row[2],
        channel=row[3],
        published_label=row[4],
        published_at_estimate=datetime.fromisoformat(row[5]),
        discovered_at=datetime.fromisoformat(row[6]),
        summarized_at=summarized_at,
        status=VideoStatus(row[8]),
        summary=row[9],
        error=row[10],
    )
