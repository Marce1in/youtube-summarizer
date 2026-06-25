# Operator Runbook

This guide tells you how to operate Youtube Summarizer on a homelab.
You are the operator: you run commands, interpret results, report problems, and
ask for human help when Google authentication is required.

## Main Rule

Never automate Google username, password, 2FA, recovery prompts, or any other
sensitive login step. If the Google session expires, open the temporary browser
and ask a human to log in manually.

## Important Components

- `app`: Docker service used for `auth-check`, `run`, and `list`.
- `auth`: temporary Docker service that opens Chrome through noVNC for manual
  login.
- `youtube_summarizer_browser_profile`: Docker volume with Google cookies and browser
  state.
- `youtube_summarizer_data`: Docker volume with SQLite, logs, and screenshots.
- `/data/app.sqlite3`: SQLite database inside the container.
- `/data/logs/automation.jsonl`: structured run log.
- `/data/screenshots`: screenshots captured on YouTube or Gemini failures.

## Normal Flow

Your default flow is:

1. Check authentication.
2. Run the automation.
3. List the results.
4. Report the run summary.
5. Troubleshoot only if something failed.

## Build The Image

Run this after project changes or when preparing a new machine:

```bash
docker compose build
```

## Check Authentication

Before an important manual run, execute:

```bash
docker compose run --rm app youtube-summarizer auth-check
```

Expected success output:

```text
auth-check: ok
YouTube subscriptions and Gemini are accessible.
```

If this passes, continue to the normal run.

If this fails, assume the Google session expired or a website selector broke.
Try manual authentication first.

## Manual Login

Start the temporary authentication browser:

```bash
docker compose --profile auth up auth
```

Open:

```text
http://localhost:6080/vnc.html
```

For a remote homelab, use an SSH tunnel:

```bash
ssh -L 6080:localhost:6080 user@homelab
```

Then open `http://localhost:6080/vnc.html` on the local machine.

Ask a human to:

1. open noVNC;
2. log in to the Google account;
3. open YouTube and Gemini;
4. confirm both sites are accessible;
5. stop the `auth` service with `Ctrl+C`.

After that, run `auth-check` again.

## Run The Automation

With valid authentication, execute:

```bash
docker compose run --rm app youtube-summarizer run
```

To process only videos whose estimated publish time is on or after an ISO date
or datetime:

```bash
docker compose run --rm app youtube-summarizer run --since 2026-06-13
```

`--since` uses the scraper's `published_at_estimate` field, not the official
YouTube publish timestamp. Dates without timezone are interpreted as UTC.

This command:

- opens the YouTube subscriptions page;
- finds recent videos;
- skips videos that were already summarized;
- retries pending or failed videos;
- sends each video URL to Gemini;
- stores summary, status, and timestamps in SQLite.

Typical successful output:

```text
run 5 finished
seen=17 new=16 skipped=1
summarized=16 failed=0
```

Meaning:

- `seen`: recent videos found on YouTube.
- `new`: videos that were not already summarized.
- `skipped`: videos already summarized before this run.
- `summarized`: videos summarized successfully in this run.
- `failed`: videos that failed in this run.

If `failed=0`, the cycle succeeded.

If `failed` is greater than zero, list the results and inspect the errors before
deciding the next action.

## List Results

List stored summaries:

```bash
docker compose run --rm app youtube-summarizer list
```

Limit the output:

```bash
docker compose run --rm app youtube-summarizer list --limit 20
```

Filter by estimated publish time:

```bash
docker compose run --rm app youtube-summarizer list --since 2026-06-13 --limit 20
```

Each item can include:

- title;
- URL;
- channel;
- `published_label`;
- `published_at_estimate`;
- `discovered_at`;
- `summarized_at`;
- status;
- summary;
- error, if present.

## Timestamp Fields

Use the timestamp fields like this:

- `published_label`: visible YouTube text, for example `há 1 hora`.
- `published_at_estimate`: estimated publish time calculated by the scraper.
- `discovered_at`: when the scraper found the video.
- `summarized_at`: when Gemini returned the summary.

Important: `published_at_estimate` is not the official exact YouTube publish
time. It is estimated from relative text shown on the subscriptions page.

## Decide After A Run

If `run` ends with `failed=0`:

- report videos seen, new, skipped, and summarized;
- use `list --limit 10` if recent summaries are needed;
- do not open the authentication browser.

If `run` ends with failures:

- run `list --limit 20`;
- find items with status `failed`;
- read the `error` field;
- check whether the error mentions a screenshot;
- inspect `/data/screenshots` if a screenshot exists.

If the error indicates login or a Google redirect:

- do not enter credentials yourself;
- run the manual login flow;
- run `auth-check` again afterward.

If the error indicates a Gemini timeout or selector issue:

- start the `auth` service;
- ask a human to inspect Gemini through noVNC;
- update selectors in `src/gemini.py` if needed.

If the error indicates an empty YouTube subscriptions page:

- confirm the account has subscriptions;
- confirm the subscriptions page is logged in;
- update selectors in `src/youtube.py` if the interface changed.

## Scheduling

For cron or systemd, schedule only:

```bash
docker compose run --rm app youtube-summarizer run
```

Optionally list recent results after the run:

```bash
docker compose run --rm app youtube-summarizer list --limit 10
```

Do not schedule `auth-server`. It is only for manual intervention.

## Safety Rules

- Do not automate Google login.
- Do not save usernames, passwords, or 2FA codes.
- Do not expose noVNC outside `localhost`.
- Use SSH tunneling or Tailscale for remote access.
- Do not delete `youtube_summarizer_browser_profile` unless intentionally resetting login.
- Do not run `auth-server`, `auth-check`, and `run` at the same time.
- Do not move YouTube or Gemini selectors outside their adapter modules.

## Browser Profile

All commands share one persistent browser profile. Only one process should use
that profile at a time.

If you see a profile-in-use error:

1. stop any still-running containers;
2. run `docker compose ps`;
3. confirm no `auth` service is active;
4. retry the command.

## Quick Diagnostics

| Symptom | Action |
| --- | --- |
| `auth-check` fails | Run manual login and repeat `auth-check`. |
| Redirects to Google | Session expired; ask for human login. |
| Empty subscriptions page | Confirm subscriptions and account login. |
| Gemini timeout | Inspect Gemini through noVNC and review selectors. |
| Screenshot path in error | Open the PNG under `/data/screenshots`. |
| Profile already in use | Stop concurrent processes. |
| Duplicate video | Expected; YouTube ID prevents duplicate summaries. |
| Failed video appears again | Expected; failed videos are retried. |
| Chrome `--no-sandbox` warning | Expected in Docker; not a login failure. |

## Database Inspection

Use SQLite only for diagnostics:

```bash
docker compose run --rm app sqlite3 /data/app.sqlite3
```

Useful queries:

```sql
select status, count(*) from videos group by status;
select title, status, discovered_at, summarized_at from videos order by id desc limit 10;
select * from runs order by id desc limit 5;
```

Do not manually change data unless there is a clear reason.

## Expected Operator Report

After a normal cycle, report:

- run time;
- videos seen;
- new videos;
- summarized videos;
- failures;
- latest summary titles or links, when requested.

When there is a failure, report:

- failed command;
- exit code, if available;
- error message;
- related screenshot, if available;
- recommended next action.
