class AppError(Exception):
    """Base expected application error.

    Example:
        raise AppError("operation failed for value='x'")
    """

    exit_code = 1


class ConfigError(AppError):
    """Raised when environment configuration is missing or malformed.

    Example:
        raise ConfigError("YT_GEMINI_MAX_FEED_ITEMS='x' must be an integer")
    """

    exit_code = 2


class VideoUrlError(AppError):
    """Raised when a YouTube URL cannot be normalized.

    Example:
        raise VideoUrlError("url='bad' must contain a YouTube video id")
    """


class BrowserAutomationError(AppError):
    """Raised when Playwright cannot complete an expected browser action.

    Example:
        raise BrowserAutomationError("selector='button' was not visible")
    """


class BrowserProfileLockError(AppError):
    """Raised when another process is already using the browser profile.

    Example:
        raise BrowserProfileLockError("profile_dir='/browser-profile' is locked")
    """


class DisplayDependencyError(AppError):
    """Raised when the virtual display stack cannot be started.

    Example:
        raise DisplayDependencyError("command='/usr/bin/Xvfb' was not found")
    """
