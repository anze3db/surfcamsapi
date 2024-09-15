#!/bin/bash
set -e
pushd "$(dirname "$0")/.."
uv run gunicorn surfcamsapi.asgi:application
popd
