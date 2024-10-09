#!/bin/bash
set -e
pushd "$(dirname "$0")/.."
uv run --frozen gunicorn surfcamsapi.asgi:application
popd
