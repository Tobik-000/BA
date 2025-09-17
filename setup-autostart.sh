#!/bin/bash

SERVICE_NAME=dac-controller.service
SERVICE_PATH="/etc/systemd/system/$SERVICE_NAME"

echo "Creating systemd service file at $SERVICE_PATH"

sudo bash -c "cat > $SERVICE_PATH" <<EOF
[Unit]
Description=DAC Controller on Raspberry Pi
After=network-online.target
Wants=network-online.target

[Service]
User=admin
Group=admin
WorkingDirectory=/home/admin/RIS
ExecStart=/home/admin/RIS/myenv/bin/python /home/admin/RIS/DAC_Controller_PI.py
Restart=on-failure
RestartSec=3
Environment=PYTHONUNBUFFERED=1
KillMode=process
TimeoutStopSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

echo "Reloading systemd daemon..."
sudo systemctl daemon-reexec
sudo systemctl daemon-reload

echo "Enabling $SERVICE_NAME to start on boot..."
sudo systemctl enable "$SERVICE_NAME"

echo "Starting $SERVICE_NAME..."
sudo systemctl start "$SERVICE_NAME"

echo "Done. Check status with:"
echo "  sudo systemctl status $SERVICE_NAME"

sudo systemctl status $SERVICE_NAME

