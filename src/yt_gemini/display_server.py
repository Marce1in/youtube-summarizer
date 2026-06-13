import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from yt_gemini.config import AppSettings
from yt_gemini.errors import DisplayDependencyError


@dataclass(frozen=True)
class ProcessSpec:
    name: str
    command: tuple[str, ...]
    environment: dict[str, str]


class DisplayServer:
    """Start and stop the virtual display stack used by headed browsers.

    Example:
        display = DisplayServer(settings)
        display.start(enable_vnc=True)
    """

    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings
        self._processes: list[subprocess.Popen[bytes]] = []

    def start(self, enable_vnc: bool) -> None:
        if not self._settings.manage_display:
            return
        for spec in build_display_specs(self._settings, enable_vnc):
            process = _start_process(spec)
            self._processes.append(process)
            _wait_after_start(spec, process, self._settings.display)

    def stop(self) -> None:
        for process in reversed(self._processes):
            process.terminate()
        for process in reversed(self._processes):
            _wait_for_exit(process)


def build_display_specs(settings: AppSettings, enable_vnc: bool) -> list[ProcessSpec]:
    """Build process specs for Xvfb and optional noVNC access.

    Example:
        specs = build_display_specs(settings, enable_vnc=True)
    """

    specs = [_xvfb_spec(settings), _openbox_spec(settings)]
    if enable_vnc:
        specs.extend([_x11vnc_spec(settings), _websockify_spec()])
    return specs


def _xvfb_spec(settings: AppSettings) -> ProcessSpec:
    screen = f"{settings.viewport_width}x{settings.viewport_height}x24"
    return ProcessSpec(
        "xvfb", ("/usr/bin/Xvfb", settings.display, "-screen", "0", screen, "-ac"), {}
    )


def _openbox_spec(settings: AppSettings) -> ProcessSpec:
    return ProcessSpec("openbox", ("/usr/bin/openbox",), _display_environment(settings))


def _x11vnc_spec(settings: AppSettings) -> ProcessSpec:
    command = (
        "/usr/bin/x11vnc",
        "-display",
        settings.display,
        "-forever",
        "-shared",
        "-nopw",
    )
    return ProcessSpec("x11vnc", command, _display_environment(settings))


def _websockify_spec() -> ProcessSpec:
    web_root = _novnc_web_root()
    command = (
        "/usr/bin/websockify",
        "--web",
        str(web_root),
        "0.0.0.0:6080",
        "localhost:5900",
    )
    return ProcessSpec("websockify", command, {})


def _display_environment(settings: AppSettings) -> dict[str, str]:
    return {"DISPLAY": settings.display, "HOME": str(settings.browser_home_dir)}


def _novnc_web_root() -> Path:
    return Path("/usr/share/novnc")


def _start_process(spec: ProcessSpec) -> subprocess.Popen[bytes]:
    try:
        return subprocess.Popen(
            spec.command,
            env=spec.environment or None,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError as err:
        raise DisplayDependencyError(
            f"command={spec.command[0]!r} was not found"
        ) from err


def _wait_after_start(
    spec: ProcessSpec,
    process: subprocess.Popen[bytes],
    display: str,
) -> None:
    if spec.name != "xvfb":
        _ensure_running(spec, process)
        return
    _wait_for_x11_socket(display, timeout_seconds=5.0)
    _ensure_running(spec, process)


def _ensure_running(spec: ProcessSpec, process: subprocess.Popen[bytes]) -> None:
    time.sleep(0.1)
    exit_code = process.poll()
    if exit_code is None:
        return
    raise DisplayDependencyError(_process_exit_message(spec, exit_code))


def _wait_for_x11_socket(display: str, timeout_seconds: float) -> None:
    deadline = time.monotonic() + timeout_seconds
    socket_path = x11_socket_path(display)
    while time.monotonic() < deadline:
        if socket_path.exists():
            return
        time.sleep(0.05)
    raise DisplayDependencyError(_x11_timeout_message(display, socket_path))


def x11_socket_path(display: str) -> Path:
    """Return the filesystem socket path for an X11 display name.

    Example:
        x11_socket_path(":99") == Path("/tmp/.X11-unix/X99")
    """

    display_number = display.removeprefix(":").split(".", maxsplit=1)[0]
    if display_number.isdigit():
        return Path("/tmp/.X11-unix") / f"X{display_number}"
    raise DisplayDependencyError(f"display={display!r} must look like ':99'")


def _x11_timeout_message(display: str, socket_path: Path) -> str:
    return f"display={display!r} did not create socket={str(socket_path)!r}"


def _process_exit_message(spec: ProcessSpec, exit_code: int) -> str:
    return f"process={spec.name!r} exited early with code={exit_code}"


def _wait_for_exit(process: subprocess.Popen[bytes]) -> None:
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)
