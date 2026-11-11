#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
test -f "$repo_dir/data/raw/LLCP2023XPT.zip"
test -f "$repo_dir/data/raw/LLCP2024XPT.zip"

if ! id -u satyasetu >/dev/null 2>&1; then
  sudo useradd --system --home-dir /var/lib/satyasetu --shell /usr/sbin/nologin satyasetu
fi
sudo install -d -o satyasetu -g satyasetu -m 0750 /opt/satyasetu /var/lib/satyasetu
sudo install -d -m 0755 /opt/satyasetu/app
sudo cp -R "$repo_dir"/{src,data,examples,config,pyproject.toml} /opt/satyasetu/app/
sudo chown -R satyasetu:satyasetu /opt/satyasetu/app
sudo chmod -R u+rX /opt/satyasetu/app
sudo -u satyasetu python3 -m venv /opt/satyasetu/venv
sudo -u satyasetu /opt/satyasetu/venv/bin/python -m pip install --no-cache-dir '/opt/satyasetu/app[local,portal]'
sudo install -m 0644 "$repo_dir/deployment/azure-portal/satyasetu.service" /etc/systemd/system/satyasetu.service
sudo systemctl daemon-reload
sudo systemctl enable satyasetu
sudo systemctl restart satyasetu
