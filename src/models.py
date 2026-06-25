from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import NewType

VideoId = NewType("VideoId", str)
NormalizedUrl = NewType("NormalizedUrl", str)


class VideoStatus(StrEnum):
    PENDING = "pending"
    SUMMARIZED = "summarized"
    FAILED = "failed"


@dataclass(frozen=True)
class SubscriptionVideo:
    video_id: VideoId
    url: NormalizedUrl
    title: str
    channel: str
    published_label: str
    published_at_estimate: datetime


@dataclass(frozen=True)
class StoredVideoSummary:
    video_id: VideoId
    url: NormalizedUrl
    title: str
    channel: str
    published_label: str
    published_at_estimate: datetime
    discovered_at: datetime
    summarized_at: datetime | None
    status: VideoStatus
    summary: str | None
    error: str | None


@dataclass(frozen=True)
class RunCounters:
    videos_seen: int = 0
    videos_new: int = 0
    videos_summarized: int = 0
    videos_failed: int = 0
    videos_skipped: int = 0


@dataclass(frozen=True)
class RunReport:
    run_id: int
    counters: RunCounters
    started_at: datetime
    finished_at: datetime


@dataclass(frozen=True)
class AuthCheckResult:
    youtube_ok: bool
    gemini_ok: bool
    detail: str
