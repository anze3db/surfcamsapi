default:
    @just --list

# Install dependencies from uv.lock
install:
    uv sync --locked

# Run the dev server on port 8003
server:
    uv run manage.py runserver 8003

# Run the potatoq worker (also runs the periodic schedule)
worker:
    uv run manage.py potatoq worker

# Apply database migrations
migrate:
    uv run manage.py migrate

# Run the tests, e.g. `just test cams/tests.py`
test *args:
    uv run pytest {{ args }}

# Lint and check formatting
lint:
    uv run ruff check .
    uv run ruff format --check .

# Fix lint errors and format the code
format:
    uv run ruff check --fix .
    uv run ruff format .

# Lint the Django templates
lint-templates:
    uv run djlint templates/

# Replace all cams and categories from a JSON export
import-json file:
    uv run manage.py import_json {{ file }}

# Lint and run the tests
check: lint test
