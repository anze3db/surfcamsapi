#!/bin/bash
set -e
cd "$(dirname "$0")/.."
exec uv run --locked python manage.py potatoq worker
