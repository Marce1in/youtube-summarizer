from auth_chrome import AuthChromeProcess
from clock import Clock
from config import AppSettings
from display_server import DisplayServer


def serve_auth_browser(settings: AppSettings, clock: Clock) -> None:
    """Run the temporary noVNC browser session until interrupted.

    Example:
        serve_auth_browser(settings, clock)
    """

    display = DisplayServer(settings)
    try:
        display.start(enable_vnc=True)
        with AuthChromeProcess(settings) as chrome:
            _wait_until_interrupted(clock, chrome)
    finally:
        display.stop()


def _wait_until_interrupted(clock: Clock, chrome: AuthChromeProcess) -> None:
    while True:
        chrome.ensure_running()
        clock.sleep(1.0)
