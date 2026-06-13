import re
from collections.abc import Callable
from dataclasses import dataclass

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Locator, Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from yt_gemini.clock import Clock
from yt_gemini.config import AppSettings
from yt_gemini.errors import BrowserAutomationError
from yt_gemini.models import NormalizedUrl

_PROMPT_SELECTORS = (
    "rich-textarea div[contenteditable='true']",
    "div[contenteditable='true'][role='textbox']",
    "textarea",
)
_RESPONSE_SELECTORS = (
    "message-content",
    "div[data-test-id='response']",
    "div.markdown",
    ".model-response-text",
)
_SEND_SELECTORS = (
    "button[aria-label*='Send']",
    "button[aria-label*='Enviar']",
    "button[type='submit']",
)


@dataclass(frozen=True)
class NewStableTextCriteria:
    stable_seconds: float
    timeout_seconds: float
    baseline_text: str
    ignored_text: str


@dataclass(frozen=True)
class ResponseSnapshot:
    response_count: int
    latest_text: str


@dataclass(frozen=True)
class NewStableResponseCriteria:
    stable_seconds: float
    timeout_seconds: float
    baseline_response_count: int
    baseline_text: str
    ignored_text: str


class GeminiWebsiteClient:
    """Submit YouTube URLs to the logged-in Gemini website.

    Example:
        summary = GeminiWebsiteClient(page, settings, clock).summarize(url)
    """

    def __init__(self, page: Page, settings: AppSettings, clock: Clock) -> None:
        self._page = page
        self._settings = settings
        self._clock = clock

    def ensure_ready(self) -> None:
        self._open_gemini()
        self._prompt_box()
        self._raise_if_login_required()

    def summarize(self, video_url: NormalizedUrl) -> str:
        self._open_gemini()
        prompt = f"Summarize this video: {video_url}"
        baseline = self._latest_response_snapshot()
        self._submit_prompt(prompt)
        return wait_for_new_stable_response(
            self._latest_response_snapshot,
            self._clock,
            NewStableResponseCriteria(
                stable_seconds=self._settings.response_stable_seconds,
                timeout_seconds=self._settings.response_timeout_seconds,
                baseline_response_count=baseline.response_count,
                baseline_text=baseline.latest_text,
                ignored_text=prompt,
            ),
        )

    def _open_gemini(self) -> None:
        self._page.goto(
            self._settings.gemini_url,
            wait_until="domcontentloaded",
            timeout=self._settings.navigation_timeout_ms,
        )
        if "accounts.google.com" in self._page.url:
            raise BrowserAutomationError(
                "gemini redirected to Google login; expected app page"
            )
        self._raise_if_login_required()

    def _raise_if_login_required(self) -> None:
        if _login_required_visible(self._page):
            raise BrowserAutomationError(
                "gemini shows a sign-in control; expected logged-in app"
            )

    def _submit_prompt(self, prompt: str) -> None:
        prompt_box = self._prompt_box()
        _write_prompt(
            prompt_box, self._page, prompt, self._settings.operation_timeout_ms
        )
        if self._click_send_button():
            return
        self._page.keyboard.press("Enter")

    def _prompt_box(self) -> Locator:
        for selector in _PROMPT_SELECTORS:
            locator = self._page.locator(selector).last
            if _is_visible(locator):
                return locator
        raise BrowserAutomationError(
            f"gemini prompt selector={_PROMPT_SELECTORS!r} was not visible"
        )

    def _click_send_button(self) -> bool:
        for selector in _SEND_SELECTORS:
            locator = self._page.locator(selector).last
            if _click_if_visible(locator):
                return True
        return False

    def _latest_response_text(self) -> str:
        return self._latest_response_snapshot().latest_text

    def _latest_response_snapshot(self) -> ResponseSnapshot:
        for selector in _RESPONSE_SELECTORS:
            texts = _visible_texts(self._page.locator(selector))
            if texts:
                return ResponseSnapshot(len(texts), texts[-1])
        return ResponseSnapshot(0, "")


def wait_for_stable_text(
    read_text: Callable[[], str],
    clock: Clock,
    stable_seconds: float,
    timeout_seconds: float,
) -> str:
    """Wait until non-empty text stops changing for a stable window.

    Example:
        text = wait_for_stable_text(reader, clock, 1.0, 10.0)
    """

    deadline = clock.monotonic() + timeout_seconds
    last_text = ""
    last_change = clock.monotonic()
    while clock.monotonic() < deadline:
        current_text = read_text().strip()
        if current_text and current_text != last_text:
            last_text = current_text
            last_change = clock.monotonic()
        if last_text and clock.monotonic() - last_change >= stable_seconds:
            return last_text
        clock.sleep(_poll_delay(stable_seconds))
    raise BrowserAutomationError(
        "gemini response text did not stabilize before timeout"
    )


def wait_for_new_stable_text(
    read_text: Callable[[], str],
    clock: Clock,
    criteria: NewStableTextCriteria,
) -> str:
    """Wait until latest text changes from baseline and stabilizes.

    Example:
        text = wait_for_new_stable_text(reader, clock, criteria)
    """

    normalized_baseline = criteria.baseline_text.strip()
    normalized_ignored = criteria.ignored_text.strip()
    return wait_for_stable_text(
        _changed_text_reader(read_text, normalized_baseline, normalized_ignored),
        clock,
        criteria.stable_seconds,
        criteria.timeout_seconds,
    )


def wait_for_new_stable_response(
    read_snapshot: Callable[[], ResponseSnapshot],
    clock: Clock,
    criteria: NewStableResponseCriteria,
) -> str:
    """Wait until a new Gemini response appears and stabilizes.

    Example:
        text = wait_for_new_stable_response(reader, clock, criteria)
    """

    return wait_for_stable_text(
        _new_response_text_reader(read_snapshot, criteria),
        clock,
        criteria.stable_seconds,
        criteria.timeout_seconds,
    )


def _poll_delay(stable_seconds: float) -> float:
    return max(0.1, min(0.5, stable_seconds / 2))


def _is_visible(locator: Locator) -> bool:
    try:
        locator.wait_for(state="visible", timeout=1000)
    except PlaywrightTimeoutError:
        return False
    return True


def _click_if_visible(locator: Locator) -> bool:
    if not _is_visible(locator):
        return False
    if not locator.is_enabled():
        return False
    locator.click()
    return True


def _write_prompt(
    prompt_box: Locator,
    page: Page,
    prompt: str,
    timeout_ms: int,
) -> None:
    try:
        prompt_box.fill(prompt, timeout=timeout_ms)
    except PlaywrightError:
        prompt_box.click(timeout=timeout_ms)
        page.keyboard.insert_text(prompt)


def _visible_texts(locator: Locator) -> list[str]:
    texts = locator.all_text_contents()
    return [" ".join(text.split()) for text in texts if text.strip()]


def _changed_text_reader(
    read_text: Callable[[], str],
    baseline_text: str,
    ignored_text: str,
) -> Callable[[], str]:
    def read_changed_text() -> str:
        text = read_text().strip()
        if text in {baseline_text, ignored_text}:
            return ""
        return text

    return read_changed_text


def _new_response_text_reader(
    read_snapshot: Callable[[], ResponseSnapshot],
    criteria: NewStableResponseCriteria,
) -> Callable[[], str]:
    baseline_text = criteria.baseline_text.strip()
    ignored_text = criteria.ignored_text.strip()

    def read_new_response_text() -> str:
        snapshot = read_snapshot()
        text = snapshot.latest_text.strip()
        if not text or text == ignored_text:
            return ""
        if snapshot.response_count > criteria.baseline_response_count:
            return text
        if text != baseline_text:
            return text
        return ""

    return read_new_response_text


def _login_required_visible(page: Page) -> bool:
    sign_in = page.get_by_text(
        re.compile(r"\b(sign in|fazer login|entrar)\b", re.IGNORECASE)
    )
    return sign_in.first.count() > 0
