from dataclasses import dataclass, replace
from datetime import datetime

from playwright.sync_api import BrowserContext, Page
from playwright.sync_api import Error as PlaywrightError

from artifacts import capture_failure_screenshot, failure_message
from browser_session import BrowserSession
from clock import Clock
from config import AppSettings
from database import SummaryDatabase
from display_server import DisplayServer
from errors import AppError, BrowserAutomationError
from gemini import GeminiWebsiteClient
from json_log import JsonLogger
from models import (
    AuthCheckResult,
    RunCounters,
    RunReport,
    SubscriptionVideo,
    VideoStatus,
)
from youtube import YouTubeSubscriptionClient


@dataclass(frozen=True)
class SummaryResources:
    database: SummaryDatabase
    gemini_client: GeminiWebsiteClient
    gemini_page: Page
    settings: AppSettings
    clock: Clock


def execute_summary_run(
    settings: AppSettings,
    clock: Clock,
    since: datetime | None = None,
) -> RunReport:
    """Run one scrape/summarize cycle and persist results.

    Example:
        report = execute_summary_run(settings, clock)
    """

    database = SummaryDatabase(settings.database_path)
    database.initialize()
    started_at = clock.now()
    run_id = database.create_run(started_at)
    display = DisplayServer(settings)
    counters = RunCounters()
    try:
        counters = _execute_with_browser(settings, clock, database, display, since)
        return _finish_report(database, run_id, counters, started_at, clock)
    except (AppError, PlaywrightError):
        database.finish_run(run_id, counters, clock.now())
        raise
    finally:
        display.stop()


def execute_auth_check(settings: AppSettings, clock: Clock) -> AuthCheckResult:
    """Verify the persistent Google profile can access YouTube and Gemini.

    Example:
        result = execute_auth_check(settings, clock)
    """

    display = DisplayServer(settings)
    try:
        display.start(enable_vnc=False)
        with BrowserSession(settings) as context:
            return _check_with_context(context, settings, clock)
    finally:
        display.stop()


def _execute_with_browser(
    settings: AppSettings,
    clock: Clock,
    database: SummaryDatabase,
    display: DisplayServer,
    since: datetime | None,
) -> RunCounters:
    display.start(enable_vnc=False)
    with BrowserSession(settings) as context:
        youtube_page = context.new_page()
        gemini_page = context.new_page()
        videos = _scrape_youtube_videos(youtube_page, settings, clock)
        videos = _filter_videos_since(videos, since)
        gemini_client = GeminiWebsiteClient(gemini_page, settings, clock)
        resources = SummaryResources(
            database, gemini_client, gemini_page, settings, clock
        )
        return _process_videos(videos, resources)


def _scrape_youtube_videos(
    page: Page,
    settings: AppSettings,
    clock: Clock,
) -> list[SubscriptionVideo]:
    try:
        return YouTubeSubscriptionClient(page, settings).recent_videos(clock.now())
    except (AppError, PlaywrightError) as err:
        screenshot = capture_failure_screenshot(
            page, settings.screenshot_dir, "youtube-subscriptions", clock.now()
        )
        message = failure_message(str(err), screenshot)
        raise BrowserAutomationError(message) from err


def _filter_videos_since(
    videos: list[SubscriptionVideo],
    since: datetime | None,
) -> list[SubscriptionVideo]:
    if since is None:
        return videos
    return [video for video in videos if video.published_at_estimate >= since]


def _process_videos(
    videos: list[SubscriptionVideo],
    resources: SummaryResources,
) -> RunCounters:
    counters = RunCounters(videos_seen=len(videos))
    for video in videos:
        if resources.database.video_status(video.video_id) == VideoStatus.SUMMARIZED:
            counters = replace(counters, videos_skipped=counters.videos_skipped + 1)
            continue
        counters = replace(counters, videos_new=counters.videos_new + 1)
        resources.database.insert_pending(video, resources.clock.now())
        counters = _summarize_video(video, counters, resources)
    return counters


def _summarize_video(
    video: SubscriptionVideo,
    counters: RunCounters,
    resources: SummaryResources,
) -> RunCounters:
    try:
        summary = resources.gemini_client.summarize(video.url)
    except (AppError, PlaywrightError) as err:
        screenshot = capture_failure_screenshot(
            resources.gemini_page,
            resources.settings.screenshot_dir,
            f"gemini-{video.video_id}",
            resources.clock.now(),
        )
        resources.database.mark_failed(
            video.video_id, failure_message(str(err), screenshot)
        )
        return replace(counters, videos_failed=counters.videos_failed + 1)
    resources.database.mark_summarized(video.video_id, summary, resources.clock.now())
    return replace(counters, videos_summarized=counters.videos_summarized + 1)


def _finish_report(
    database: SummaryDatabase,
    run_id: int,
    counters: RunCounters,
    started_at: datetime,
    clock: Clock,
) -> RunReport:
    finished_at = clock.now()
    database.finish_run(run_id, counters, finished_at)
    return RunReport(run_id, counters, started_at, finished_at)


def _check_with_context(
    context: BrowserContext,
    settings: AppSettings,
    clock: Clock,
) -> AuthCheckResult:
    youtube_page = context.new_page()
    gemini_page = context.new_page()
    youtube_ok = _youtube_is_ready(youtube_page, settings, clock)
    gemini_ok = _gemini_is_ready(gemini_page, settings, clock)
    detail = _auth_detail(youtube_ok, gemini_ok)
    return AuthCheckResult(youtube_ok, gemini_ok, detail)


def _youtube_is_ready(page: Page, settings: AppSettings, clock: Clock) -> bool:
    try:
        YouTubeSubscriptionClient(page, settings).recent_videos(clock.now())
    except (AppError, PlaywrightError):
        return False
    return True


def _gemini_is_ready(page: Page, settings: AppSettings, clock: Clock) -> bool:
    try:
        GeminiWebsiteClient(page, settings, clock).ensure_ready()
    except (AppError, PlaywrightError):
        return False
    return True


def _auth_detail(youtube_ok: bool, gemini_ok: bool) -> str:
    if youtube_ok and gemini_ok:
        return "YouTube subscriptions and Gemini are accessible."
    if not youtube_ok and not gemini_ok:
        return "YouTube subscriptions and Gemini both need login or selector repair."
    if not youtube_ok:
        return "YouTube subscriptions need login or selector repair."
    return "Gemini needs login or selector repair."


def log_run_report(logger: JsonLogger, report: RunReport) -> None:
    """Write a compact structured event for a completed run.

    Example:
        log_run_report(logger, report)
    """

    logger.event(
        "summary_run_finished",
        {
            "run_id": report.run_id,
            "videos_seen": report.counters.videos_seen,
            "videos_new": report.counters.videos_new,
            "videos_summarized": report.counters.videos_summarized,
            "videos_failed": report.counters.videos_failed,
            "videos_skipped": report.counters.videos_skipped,
        },
    )
