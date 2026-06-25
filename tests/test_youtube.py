from datetime import UTC, datetime, timedelta

import pytest

from errors import VideoUrlError
from youtube import (
    compact_publish_label,
    estimate_published_at,
    extract_recent_publish_label,
    normalize_youtube_video_url,
    parse_publish_age,
)


def test_normalize_youtube_video_url_from_relative_watch_path() -> None:
    normalized = normalize_youtube_video_url("/watch?v=abc123xyz00&list=ignored")

    assert normalized.video_id == "abc123xyz00"
    assert normalized.url == "https://www.youtube.com/watch?v=abc123xyz00"


def test_normalize_youtube_video_url_from_short_url() -> None:
    normalized = normalize_youtube_video_url("https://youtu.be/abc123xyz00?t=3")

    assert normalized.video_id == "abc123xyz00"
    assert normalized.url == "https://www.youtube.com/watch?v=abc123xyz00"


def test_normalize_youtube_video_url_rejects_missing_id() -> None:
    with pytest.raises(VideoUrlError, match="must contain a YouTube video id"):
        normalize_youtube_video_url("https://example.com/watch?v=abc123xyz00")


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("3 minutes ago", timedelta(minutes=3)),
        ("just now", timedelta()),
        ("agora", timedelta()),
        ("an hour ago", timedelta(hours=1)),
        ("23 hours ago", timedelta(hours=23)),
        ("1 day ago", timedelta(days=1)),
        ("há 2 horas", timedelta(hours=2)),
        ("Transmitido há 15 minutos", timedelta(minutes=15)),
        ("1 dia atrás", timedelta(days=1)),
        ("ontem", timedelta(days=1)),
    ],
)
def test_parse_publish_age(label: str, expected: timedelta) -> None:
    assert parse_publish_age(label) == expected


@pytest.mark.parametrize("label", ["1 hour", "a day", "1 hour of music"])
def test_parse_publish_age_rejects_bare_title_like_age(label: str) -> None:
    assert parse_publish_age(label) is None


def test_parse_publish_age_returns_none_for_absolute_dates() -> None:
    assert parse_publish_age("Jun 12, 2026") is None


def test_estimate_published_at_uses_relative_label() -> None:
    now = datetime(2026, 6, 13, 12, 0, tzinfo=UTC)

    assert estimate_published_at(now, "2 hours ago") == now - timedelta(hours=2)


def test_extract_recent_publish_label_prefers_metadata_label() -> None:
    label = extract_recent_publish_label(["6,6 mil visualizações", "há 1 hora"], "")

    assert label == "há 1 hora"


def test_extract_recent_publish_label_falls_back_to_portuguese_card_text() -> None:
    card_text = (
        "12:34\nO governo americano bloqueou o Claude\nmano deyvin\n•\nhá 1 hora"
    )

    label = extract_recent_publish_label([], card_text)

    assert label == "há 1 hora"


def test_extract_recent_publish_label_compacts_single_line_card_text() -> None:
    card_text = "12:34O governo americano bloqueou o Claudemano deyvin • há 1 hora"

    label = extract_recent_publish_label([], card_text)

    assert label == "há 1 hora"


def test_extract_recent_publish_label_ignores_bare_title_age() -> None:
    card_text = "1 hour of music\nAmbient Channel\n10 mil visualizações\n3 days ago"

    label = extract_recent_publish_label([], card_text)

    assert label == "3 days ago"


def test_compact_publish_label_returns_none_without_relative_age() -> None:
    assert compact_publish_label("O governo americano bloqueou o Claude") is None
