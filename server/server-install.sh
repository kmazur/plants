#!/bin/bash

# Variables
APP_DIR="/opt/fastapi_app"
SERVICE_FILE="/etc/systemd/system/fastapi.service"
SECRET_FILE="/tmp/secret.txt"
PYTHON_BIN="/usr/local/bin/uvicorn"

# Functions
function install_if_needed {
      apt-get install -y "$1"
}

function pip_install_if_needed {
      pip install "$1"
}

# Update and install required packages
sudo apt-get update

install_if_needed "python3"
install_if_needed "python3-pip"
install_if_needed "nginx"

# Install Python packages
pip_install_if_needed "fastapi"
pip_install_if_needed "uvicorn"

# Create application directory if it doesn't exist
if [ ! -d "$APP_DIR" ]; then
    mkdir -p $APP_DIR
    chown www-data:www-data $APP_DIR
fi

# Ensure the auth code file exists
if [ ! -f "$SECRET_FILE" ]; then
    echo "Auth code file $SECRET_FILE does not exist. Please create it with your secret auth code."
    exit 1
fi

# Read the auth code from file
SECRET_AUTH_CODE=$(cat $SECRET_FILE)

# Ensure main.py exists in the application directory
if [ ! -f "$APP_DIR/main.py" ]; then
    echo "main.py not found in $APP_DIR. Please ensure your application code is present."
    exit 1
fi

# Create systemd service file
cat > $SERVICE_FILE << EOF
[Unit]
Description=FastAPI Service
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=$APP_DIR
ExecStart=$PYTHON_BIN main:app --host 0.0.0.0 --port 8089
Environment="SECRET_AUTH_CODE=$SECRET_AUTH_CODE"
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd to apply the new service file
systemctl daemon-reload

# Start and enable the FastAPI service
systemctl start fastapi
systemctl enable fastapi

# Check the status of the service
systemctl status fastapi
