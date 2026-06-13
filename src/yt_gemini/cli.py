import argparse
import sys
from collections.abc import Sequence

from yt_gemini.auth_server import serve_auth_browser
from yt_gemini.clock import SystemClock
from yt_gemini.config import load_settings
from yt_gemini.database import SummaryDatabase
from yt_gemini.errors import AppError
from yt_gemini.json_log import JsonLogger
from yt_gemini.models import AuthCheckResult, RunReport, StoredVideoSummary
from yt_gemini.workflow import execute_auth_check, execute_summary_run, log_run_report

_SUCCESS = 0
_OPERATIONAL_FAILURE = 1
_INTERRUPTED = 130


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command-line interface.

    Example:
        raise SystemExit(main(["list", "--limit", "5"]))
    """

    parser = _build_parser()
    namespace = parser.parse_args(None if argv is None else list(argv))
    try:
        return _dispatch(namespace)
    except AppError as err:
        print(str(err), file=sys.stderr)
        return err.exit_code
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return _INTERRUPTED


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="yt-gemini")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("auth-server", help="open noVNC login/debug browser")
    subcommands.add_parser("auth-check", help="verify YouTube and Gemini auth")
    subcommands.add_parser("run", help="scrape YouTube and summarize new videos")
    list_parser = subcommands.add_parser("list", help="print stored summaries")
    list_parser.add_argument("--limit", type=int, default=10)
    return parser


def _dispatch(namespace: argparse.Namespace) -> int:
    command = str(namespace.command)
    if command == "auth-server":
        return _auth_server_command()
    if command == "auth-check":
        return _auth_check_command()
    if command == "run":
        return _run_command()
    if command == "list":
        return _list_command(_limit_from_namespace(namespace))
    raise AppError(f"command={command!r} must be a known subcommand")


def _auth_server_command() -> int:
    settings = load_settings()
    print("noVNC is available on http://localhost:6080/vnc.html when port-forwarded.")
    serve_auth_browser(settings, SystemClock())
    return _SUCCESS


def _auth_check_command() -> int:
    result = execute_auth_check(load_settings(), SystemClock())
    _print_auth_result(result)
    if result.youtube_ok and result.gemini_ok:
        return _SUCCESS
    return _OPERATIONAL_FAILURE


def _run_command() -> int:
    settings = load_settings()
    report = execute_summary_run(settings, SystemClock())
    log_run_report(JsonLogger(settings.log_path), report)
    _print_run_report(report)
    if report.counters.videos_failed:
        return _OPERATIONAL_FAILURE
    return _SUCCESS


def _list_command(limit: int) -> int:
    settings = load_settings()
    database = SummaryDatabase(settings.database_path)
    database.initialize()
    _print_summaries(database.recent_summaries(limit))
    return _SUCCESS


def _limit_from_namespace(namespace: argparse.Namespace) -> int:
    limit = int(namespace.limit)
    if limit > 0:
        return limit
    raise AppError(f"limit={limit!r} must be greater than 0")


def _print_auth_result(result: AuthCheckResult) -> None:
    status = "ok" if result.youtube_ok and result.gemini_ok else "failed"
    print(f"auth-check: {status}")
    print(result.detail)


def _print_run_report(report: RunReport) -> None:
    counters = report.counters
    print(f"run {report.run_id} finished")
    seen_line = f"seen={counters.videos_seen} new={counters.videos_new}"
    print(f"{seen_line} skipped={counters.videos_skipped}")
    print(f"summarized={counters.videos_summarized} failed={counters.videos_failed}")


def _print_summaries(summaries: list[StoredVideoSummary]) -> None:
    if not summaries:
        print("No summaries stored.")
        return
    for summary in summaries:
        _print_summary(summary)


def _print_summary(summary: StoredVideoSummary) -> None:
    print(f"{summary.title} [{summary.status.value}]")
    print(str(summary.url))
    summarized_at = (
        "none" if summary.summarized_at is None else summary.summarized_at.isoformat()
    )
    print(f"channel: {summary.channel}")
    print(f"published_label: {summary.published_label}")
    print(f"published_at_estimate: {summary.published_at_estimate.isoformat()}")
    print(f"discovered_at: {summary.discovered_at.isoformat()}")
    print(f"summarized_at: {summarized_at}")
    if summary.summary:
        print(summary.summary)
    if summary.error:
        print(f"error: {summary.error}")
    print("")
