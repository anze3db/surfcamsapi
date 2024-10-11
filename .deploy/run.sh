#!/bin/bash
set -e
pushd "$(dirname "$0")/.."
uv run --locked gunicorn surfcamsapi.asgi:application
popd
