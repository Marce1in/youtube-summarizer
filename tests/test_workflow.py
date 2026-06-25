from datetime import UTC, datetime

from models import NormalizedUrl, SubscriptionVideo, VideoId
from workflow import _filter_videos_since


def test_filter_videos_since_uses_estimated_publish_time() -> None:
    videos = [
        _subscription_video(
            video_id="old123xyz00",
            title="Old video",
            published_at=datetime(2026, 6, 12, 23, 59, tzinfo=UTC),
        ),
        _subscription_video(
            video_id="new123xyz00",
            title="New video",
            published_at=datetime(2026, 6, 13, 0, 0, tzinfo=UTC),
        ),
    ]

    filtered = _filter_videos_since(
        videos,
        since=datetime(2026, 6, 13, 0, 0, tzinfo=UTC),
    )

    assert [video.title for video in filtered] == ["New video"]


def _subscription_video(
    video_id: str,
    title: str,
    published_at: datetime,
) -> SubscriptionVideo:
    return SubscriptionVideo(
        video_id=VideoId(video_id),
        url=NormalizedUrl(f"https://www.youtube.com/watch?v={video_id}"),
        title=title,
        channel="Channel",
        published_label="1 hour ago",
        published_at_estimate=published_at,
    )
