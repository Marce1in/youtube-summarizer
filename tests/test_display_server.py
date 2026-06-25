from pathlib import Path

import pytest

from config import load_settings
from display_server import build_display_specs, x11_socket_path
from errors import DisplayDependencyError


def test_build_display_specs_without_vnc() -> None:
    settings = load_settings({"YOUTUBE_SUMMARIZER_MANAGE_DISPLAY": "true"})

    specs = build_display_specs(settings, enable_vnc=False)

    assert [spec.name for spec in specs] == ["xvfb", "openbox"]


def test_build_display_specs_with_vnc() -> None:
    settings = load_settings({"YOUTUBE_SUMMARIZER_VIEWPORT_WIDTH": "1280"})

    specs = build_display_specs(settings, enable_vnc=True)

    assert [spec.name for spec in specs] == ["xvfb", "openbox", "x11vnc", "websockify"]
    assert "1280x1000x24" in specs[0].command


def test_x11_socket_path_for_display_number() -> None:
    assert x11_socket_path(":99") == Path("/tmp/.X11-unix/X99")


def test_x11_socket_path_rejects_bad_display() -> None:
    with pytest.raises(DisplayDependencyError, match="must look like"):
        x11_socket_path("not-a-display")
