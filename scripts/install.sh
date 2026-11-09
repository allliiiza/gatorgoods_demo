#!/usr/bin/env bash

ORIGINAL_DIR="$(pwd)"

SCRIPT_DIR="$(dirname "${BASH_SOURCE[0]}")"

cd "$SCRIPT_DIR"
cd ..

sudo apt install git \
	nginx \
	python3 \
	python-is-python3 \
	python3.12-venv

python3.12 -m venv venv
source venv/bin/activate

python3.12 -m pip install -r scripts/requirements.txt

deactivate

sudo cp scripts/nginx/team-conf /etc/nginx/sites-available
sudo cp scripts/nginx/nginx.conf /etc/nginx
sudo ln -s /etc/nginx/sites-available/team-conf /etc/nginx/sites-enabled

sudo systemctl enable scripts/wsgi-server.service
sudo systemctl start wsgi-server.service

sudo systemctl reload nginx

cd "$ORIGINAL_DIR"
