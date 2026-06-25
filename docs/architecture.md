# Architecture

The project is a frameworkless Python CLI. Composition happens explicitly in
`src/cli.py`, and external systems are isolated behind boundary modules.

## Boundaries

- `config`: reads environment variables and returns typed settings.
- `display_server`: starts Xvfb, openbox, x11vnc, and websockify when needed.
- `browser_session`: owns the Playwright persistent browser context.
- `youtube`: scrapes and normalizes subscription feed videos.
- `gemini`: submits prompts to the Gemini website and reads stable responses.
- `database`: owns SQLite schema and persistence.
- `workflow`: coordinates one run and translates per-video failures into state.

## Runtime State

Docker named volumes hold runtime state:

- `/browser-profile`: Google login cookies and browser storage.
- `/data`: SQLite database, JSON logs, and failure screenshots.

The browser profile is intentionally separate from any personal Chrome profile.
Deleting it resets Google authentication.

## Tradeoffs

The implementation uses browser automation because the requested workflow depends
on the logged-in YouTube and Gemini websites. Selectors are brittle by nature, so
site-specific logic stays in adapter modules.
