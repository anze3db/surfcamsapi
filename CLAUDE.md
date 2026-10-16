# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

This project uses `uv` for dependency management and `just` as a task runner.

```bash
uv sync --locked              # Install/sync dependencies from uv.lock
just server                   # Run dev server on port 8003 (= uv run manage.py runserver 8003)
just worker                   # Run the potatoq worker (also runs the periodic schedule)
uv run pytest                 # Run the full test suite (pytest-django, reuses the DB)
uv run pytest api/tests.py    # Run a single test file
uv run pytest api/tests.py::TestHealthApi::test_health  # Run a single test
uv run ruff check .           # Lint
uv run djlint templates/      # Lint Django templates
uv run python manage.py import_json <file.json>  # Replace all cams/categories from a JSON export
uv run python manage.py collectstatic --no-input # Required before tests in CI
```

Test files are named `tests.py` (not `test_*.py`) — see `[tool.pytest.ini_options]` in `pyproject.toml`. CI (`.github/workflows/python.yml`) runs `collectstatic` then `pytest` against a Postgres service container (production runs on Postgres too), and on `main` deploys via SSH by running `.deploy/update.sh` on the server, which also restarts `surfcams-worker`. Tests that enqueue and `drain()` tasks need `TransactionTestCase` (tasks are sent on commit).

## Architecture

Django app serving surf cam streams plus Surfline forecast data. The codebase is **almost entirely `async`** — views, ORM calls (`aget`, `acount`, `async for`), and HTTP fetches. Keep new code async to match.

**Apps and their roles:**
- `cams/` — the only app with models. `Cam`, `Category`, and the `CategoryCam` through-model (cams belong to ordered categories via `django-admin-sortable2`). `Cam.proxy_url` and the `proxy` view route HLS streams through the server with a `P_REFERER` header to bypass hotlink protection.
- `surfcamsapi/` — project config.
- Background work runs on a separate [potatoq](https://anze3db.github.io/potatoq/) worker (`manage.py potatoq worker`, the `surfcams-worker` systemd service), using the default database as the broker. `POTATOQ["beat_schedule"]` in `settings.py` runs `cams.tasks.check_cams` every 2 hours: it polls every cam URL and sets `Cam.offline_since`. Tasks live in each app's `tasks.py` (autodiscovered).
- `surfline/` — `SurflineFetcher` wraps the unofficial Surfline API (`services.surfline.com`). It uses `curl_cffi` with `impersonate="chrome"` (Surfline blocks normal clients) and `stamina.retry` for resilience. `fetch_all()` concurrently fetches tides/sunlight/wind/waves; `get_surfline_data` reshapes them into per-day forecast rows + JSON chart data rendered into `surfline.html`.
- `api/` — `django-ninja` JSON API (`api.urls.api`) mounted at `/api/`. Schemas alias snake_case model fields to camelCase JSON. Returns 503 on `AssertionError` (used by `/api/health`).

**URL routing** lives across three files: `surfcamsapi/urls.py` (main, includes the HTML views which are `@login_required`), `api/urls.py` (ninja router), and `surfline/urls.py`. The root `/` and `/cams/<slug>/` pages require login; `/api/` does not. Several `api/...` paths in `surfcamsapi/urls.py` are marked `# TODO: remove soon`.

**Templates** in `templates/` render server-side HTML (this is not a JSON-only API despite the repo name). Cam detail pages embed forecast charts built from `chart_days_json`.

## Config

Settings read from `.env` via `django-environ` (see `.env.example`). Key vars: `DATABASE_URL` (Postgres, locally and in production; potatoq uses it as its broker too), `P_REFERER` (for stream proxying), `SENTRY_DNS`, `HOST`. Static files served by WhiteNoise with `CompressedManifestStaticFilesStorage`.
