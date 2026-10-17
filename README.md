# Surfcams API

API for the surfcams app

## Development

You need [uv](https://docs.astral.sh/uv/), [just](https://just.systems/) and a
Postgres server.

```bash
cp .env.example .env    # then point DATABASE_URL at your Postgres
createdb surfcams
just install
just migrate
just server             # http://localhost:8003
```

Run `just worker` in a second terminal for background tasks such as the
periodic cam checks.

## Commands

| Command | What it does |
| --- | --- |
| `just install` | Install dependencies from `uv.lock` |
| `just server` | Run the dev server on port 8003 |
| `just worker` | Run the potatoq worker (also runs the periodic schedule) |
| `just migrate` | Apply database migrations |
| `just test` | Run the tests; pass pytest arguments, e.g. `just test cams/tests.py` |
| `just lint` | Lint with ruff and check formatting |
| `just format` | Fix lint errors and format the code |
| `just lint-templates` | Lint the Django templates with djlint |
| `just import-json <file>` | Replace all cams and categories from a JSON export |
| `just check` | Lint and run the tests; run this before pushing |

Run `just` on its own to list them all.
