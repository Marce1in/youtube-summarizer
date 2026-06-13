import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import ParseResult, parse_qs, urljoin, urlparse

from playwright.sync_api import Locator, Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from yt_gemini.config import AppSettings
from yt_gemini.errors import BrowserAutomationError, VideoUrlError
from yt_gemini.models import NormalizedUrl, SubscriptionVideo, VideoId

_VIDEO_CARD_SELECTOR = (
    "ytd-rich-item-renderer,ytd-grid-video-renderer,ytd-video-renderer"
)
_WATCH_LINK_SELECTOR = "a[href*='watch?v=']"
_WATCH_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}
_SHORT_HOSTS = {"youtu.be", "www.youtu.be"}
_PROMOTED_MARKERS = ("Shorts", "/shorts/")
_TITLE_SELECTORS = (
    "a.ytLockupMetadataViewModelTitle",
    "a[aria-label][href*='watch?v=']",
    "#video-title",
    "a#video-title",
    "h3 a[href*='watch?v=']",
)
_CHANNEL_SELECTORS = (
    "#channel-name a",
    "ytd-channel-name a",
    "a[href^='/@']",
    "a[href*='youtube.com/@']",
)


@dataclass(frozen=True)
class YouTubeVideoUrl:
    video_id: VideoId
    url: NormalizedUrl


def normalize_youtube_video_url(raw_url: str) -> YouTubeVideoUrl:
    """Return a canonical YouTube watch URL and video id.

    Example:
        normalize_youtube_video_url("/watch?v=abc123xyz00").url
    """

    parsed_url = urlparse(_absolute_youtube_url(raw_url))
    video_id = _extract_video_id(parsed_url)
    if video_id is None:
        raise VideoUrlError(f"url={raw_url!r} must contain a YouTube video id")
    return YouTubeVideoUrl(
        video_id=VideoId(video_id),
        url=NormalizedUrl(f"https://www.youtube.com/watch?v={video_id}"),
    )


def parse_publish_age(label: str) -> timedelta | None:
    """Parse visible YouTube relative publish text into an approximate age.

    Example:
        parse_publish_age("há 2 horas") == timedelta(hours=2)
    """

    normalized_label = " ".join(label.strip().lower().split())
    if normalized_label in {"just now", "now", "agora"}:
        return timedelta()
    if normalized_label in {"yesterday", "ontem"}:
        return timedelta(days=1)
    match = _first_age_label_match(normalized_label)
    if match is not None:
        return _age_from_match(match)
    return None


def estimate_published_at(now: datetime, label: str) -> datetime | None:
    """Estimate publish time from a relative YouTube label.

    Example:
        estimate_published_at(now, "2 hours ago")
    """

    age = parse_publish_age(label)
    if age is None:
        return None
    return now - age


def extract_recent_publish_label(labels: Iterable[str], fallback_text: str) -> str:
    """Return the first relative publish label found in metadata or card text.

    Example:
        extract_recent_publish_label([], "Title\nChannel\nhá 1 hora")
    """

    for label in labels:
        compact_label = compact_publish_label(label)
        if compact_label is not None:
            return compact_label
    for line in fallback_text.splitlines():
        compact_label = compact_publish_label(line)
        if compact_label is not None:
            return compact_label
    return compact_publish_label(fallback_text) or ""


def compact_publish_label(candidate: str) -> str | None:
    """Return a compact relative publish label from a candidate text string.

    Example:
        compact_publish_label("Title Channel 6 mil views há 1 hora") == "há 1 hora"
    """

    normalized_candidate = " ".join(candidate.split())
    if len(normalized_candidate) <= 40:
        if parse_publish_age(normalized_candidate) is None:
            return None
        return normalized_candidate
    match = _first_age_search_match(normalized_candidate)
    if match is None:
        return None
    return match.group(0).strip()


class YouTubeSubscriptionClient:
    """Scrape recent subscription videos from the logged-in YouTube feed.

    Example:
        videos = YouTubeSubscriptionClient(page, settings).recent_videos(now)
    """

    def __init__(self, page: Page, settings: AppSettings) -> None:
        self._page = page
        self._settings = settings

    def recent_videos(self, now: datetime) -> list[SubscriptionVideo]:
        self._open_subscriptions()
        self._load_feed_items()
        cards = self._page.locator(_VIDEO_CARD_SELECTOR)
        return self._videos_from_cards(cards, now)

    def _open_subscriptions(self) -> None:
        self._page.goto(
            self._settings.youtube_subscriptions_url,
            wait_until="domcontentloaded",
            timeout=self._settings.navigation_timeout_ms,
        )
        self._raise_if_login_page()

    def _load_feed_items(self) -> None:
        previous_count = -1
        for _ in range(12):
            count = self._page.locator(_VIDEO_CARD_SELECTOR).count()
            if count >= self._settings.max_feed_items or count == previous_count:
                return
            previous_count = count
            self._page.mouse.wheel(0, 1800)
            self._page.wait_for_timeout(800)

    def _videos_from_cards(
        self, cards: Locator, now: datetime
    ) -> list[SubscriptionVideo]:
        found_videos: dict[VideoId, SubscriptionVideo] = {}
        for index in range(min(cards.count(), self._settings.max_feed_items)):
            video = self._video_from_card(cards.nth(index), now)
            if video is not None:
                found_videos[video.video_id] = video
        return list(found_videos.values())

    def _video_from_card(
        self, card: Locator, now: datetime
    ) -> SubscriptionVideo | None:
        href = _first_attribute(card, _WATCH_LINK_SELECTOR, "href")
        if href is None or _is_promoted_href(href):
            return None
        video_url = normalize_youtube_video_url(href)
        publish_label = extract_recent_publish_label(
            card.locator("#metadata-line span").all_text_contents(),
            card.text_content() or "",
        )
        published_at = estimate_published_at(now, publish_label)
        if published_at is None or now - published_at > self._settings.youtube_lookback:
            return None
        return SubscriptionVideo(
            video_id=video_url.video_id,
            url=video_url.url,
            title=_first_text(card, _TITLE_SELECTORS),
            channel=_first_text(card, _CHANNEL_SELECTORS),
            published_label=publish_label,
            published_at_estimate=published_at,
        )

    def _raise_if_login_page(self) -> None:
        if "accounts.google.com" in self._page.url:
            raise BrowserAutomationError(
                "youtube redirected to Google login; expected subscriptions feed"
            )
        try:
            self._page.locator(_VIDEO_CARD_SELECTOR).first.wait_for(timeout=15000)
        except PlaywrightTimeoutError as err:
            if _looks_authenticated(self._page):
                return
            raise BrowserAutomationError(_youtube_feed_error(self._page.url)) from err


_AGE_COUNT_PATTERN = r"(?P<count>\d+|a|an|um|uma)"
_AGE_UNIT_PATTERN = (
    r"(?P<unit>minute|minutes|min|mins|hour|hours|hr|hrs|day|days|"
    r"minuto|minutos|hora|horas|dia|dias)"
)
_AGE_LABEL_PATTERNS = (
    re.compile(rf"^{_AGE_COUNT_PATTERN}\s+{_AGE_UNIT_PATTERN}\s+ago$"),
    re.compile(
        rf"^(?:transmitido\s+)?h[aá]\s+{_AGE_COUNT_PATTERN}\s+{_AGE_UNIT_PATTERN}$"
    ),
    re.compile(rf"^{_AGE_COUNT_PATTERN}\s+{_AGE_UNIT_PATTERN}\s+atr[aá]s$"),
)
_AGE_SEARCH_PATTERNS = (
    re.compile(rf"\b{_AGE_COUNT_PATTERN}\s+{_AGE_UNIT_PATTERN}\s+ago\b"),
    re.compile(
        rf"\b(?:transmitido\s+)?h[aá]\s+{_AGE_COUNT_PATTERN}\s+{_AGE_UNIT_PATTERN}\b"
    ),
    re.compile(rf"\b{_AGE_COUNT_PATTERN}\s+{_AGE_UNIT_PATTERN}\s+atr[aá]s\b"),
)


def _absolute_youtube_url(raw_url: str) -> str:
    raw_value = raw_url.strip()
    if raw_value.startswith("/"):
        return urljoin("https://www.youtube.com", raw_value)
    return raw_value


def _extract_video_id(parsed: ParseResult) -> str | None:
    host = parsed.netloc.lower()
    if host in _SHORT_HOSTS:
        return parsed.path.strip("/") or None
    if host in _WATCH_HOSTS:
        return _video_id_from_query(parsed.query)
    return None


def _video_id_from_query(raw_query: str) -> str | None:
    values = parse_qs(raw_query).get("v", [])
    if not values or not values[0].strip():
        return None
    return values[0].strip()


def _first_age_label_match(label: str) -> re.Match[str] | None:
    for pattern in _AGE_LABEL_PATTERNS:
        match = pattern.search(label)
        if match is not None:
            return match
    return None


def _first_age_search_match(text: str) -> re.Match[str] | None:
    for pattern in _AGE_SEARCH_PATTERNS:
        match = pattern.search(text)
        if match is not None:
            return match
    return None


def _age_from_match(match: re.Match[str]) -> timedelta:
    count = _count_from_text(match.group("count"))
    unit = match.group("unit")
    if unit.startswith(("minute", "minuto", "min")):
        return timedelta(minutes=count)
    if unit.startswith(("hour", "hora", "hr")):
        return timedelta(hours=count)
    return timedelta(days=count)


def _count_from_text(raw_count: str) -> int:
    if raw_count in {"a", "an", "um", "uma"}:
        return 1
    return int(raw_count)


def _first_attribute(card: Locator, selector: str, attribute: str) -> str | None:
    locator = card.locator(selector).first
    if locator.count() == 0:
        return None
    return locator.get_attribute(attribute)


def _first_text(card: Locator, selectors: tuple[str, ...]) -> str:
    for selector in selectors:
        locator = card.locator(selector).first
        if locator.count() == 0:
            continue
        text = locator.text_content()
        if text is not None and text.strip():
            return " ".join(text.split())
    return ""


def _is_promoted_href(href: str) -> bool:
    return any(marker in href for marker in _PROMOTED_MARKERS)


def _looks_authenticated(page: Page) -> bool:
    return page.locator("#avatar-btn, button#avatar-btn").first.count() > 0


def _youtube_feed_error(url: str) -> str:
    return (
        f"youtube url={url!r} did not show subscription video cards or a logged-in "
        "account marker"
    )
