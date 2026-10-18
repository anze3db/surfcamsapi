#!/bin/bash
set -e
pushd "$(dirname "$0")/.."
git pull
python_before=$(readlink -f .venv/bin/python || true)
uv sync --locked
uv run python manage.py collectstatic --noinput
uv run python manage.py migrate
# A reload (HUP) forks new workers from the running master, which keeps its
# old interpreter, so a Python upgrade needs a full restart.
if [ "$(readlink -f .venv/bin/python)" = "$python_before" ]; then
    sudo systemctl reload surfcams
else
    sudo systemctl restart surfcams
fi
sudo systemctl restart surfcams-worker
echo `date "+%Y-%m-%d %H:%M:%S.%3N"` ' Updated' >> update.log
popd
