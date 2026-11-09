#!/usr/bin/env bash

ORIGINAL_DIR="$(pwd)"

SCRIPT_DIR="$(dirname "${BASH_SOURCE[0]}")"

cd "$SCRIPT_DIR"
cd ..

sudo apt install git \
	nginx \
	python3 \
	python-is-python3 \
	python3.12-venv \
	mariadb-server \
	mariadb-client \
	libmariadb-dev \
	libmariadb-dev-compat \
	pkg-config \
	python3-dev \
	build-essential

sudo systemctl enable mariadb
sudo systemctl start mariadb

sudo mysql <<EOF
CREATE DATABASE IF NOT EXISTS teamdb;
CREATE USER IF NOT EXISTS 'teamadmin'@'localhost' IDENTIFIED BY 'closet1wallflower2topography3!';
GRANT ALL PRIVILEGES ON teamdb.* TO 'teamadmin'@'localhost';
FLUSH PRIVILEGES;
EOF

python3.12 -m venv venv
source venv/bin/activate

python3.12 -m pip install -r scripts/requirements.txt

deactivate

sudo cp scripts/nginx/team-conf-local /etc/nginx/sites-available
sudo cp scripts/nginx/nginx.conf /etc/nginx
sudo ln -s /etc/nginx/sites-available/team-conf-local /etc/nginx/sites-enabled

ln -s "$(pwd)" /home/student/csc648-server 

sudo systemctl enable scripts/wsgi-server-local.service
sudo systemctl start wsgi-server-local.service

sudo systemctl reload nginx

cd "$ORIGINAL_DIR"
