#!/bin/bash
set -e
pushd "$(dirname "$0")/.."
git pull
uv sync --locked
uv run python manage.py collectstatic --noinput
uv run python manage.py migrate
# A reload (HUP) forks new workers from the running master, which keeps the
# interpreter it started with, so restart when the venv's Python differs.
running_python=$(readlink -f "/proc/$(systemctl show -p MainPID --value surfcams)/exe" || true)
if [ "$running_python" = "$(readlink -f .venv/bin/python)" ]; then
    sudo systemctl reload surfcams
else
    sudo systemctl restart surfcams
fi
sudo systemctl restart surfcams-worker
echo `date "+%Y-%m-%d %H:%M:%S.%3N"` ' Updated' >> update.log
popd
