#!/bin/bash

# Copper CRM Slack Bot - Deployment Script for Ubuntu/Lightsail
# This script automates the deployment process

set -e  # Exit on any error

echo "================================"
echo "Copper CRM Slack Bot Deployment"
echo "================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [ "$EUID" -eq 0 ]; then
  echo -e "${RED}Please do not run this script as root${NC}"
  exit 1
fi

echo -e "${GREEN}Step 1: Updating system packages...${NC}"
sudo apt update && sudo apt upgrade -y

echo -e "${GREEN}Step 2: Installing dependencies...${NC}"
sudo apt install -y python3 python3-pip python3-venv git

echo -e "${GREEN}Step 3: Setting up virtual environment...${NC}"
if [ ! -d "venv" ]; then
  python3 -m venv venv
fi
source venv/bin/activate

echo -e "${GREEN}Step 4: Installing Python packages...${NC}"
pip install --upgrade pip
pip install -r requirements.txt

echo -e "${GREEN}Step 5: Checking for .env file...${NC}"
if [ ! -f ".env" ]; then
  echo -e "${YELLOW}Creating .env file from template...${NC}"
  cp .env.example .env
  echo -e "${YELLOW}Please edit .env file with your credentials:${NC}"
  echo "  nano .env"
  echo ""
  echo "Press ENTER when you've configured the .env file..."
  read -r
else
  echo -e "${GREEN}.env file already exists${NC}"
fi

echo -e "${GREEN}Step 6: Creating systemd service...${NC}"
SERVICE_FILE="/etc/systemd/system/copperbot.service"
CURRENT_DIR=$(pwd)
CURRENT_USER=$(whoami)

sudo tee $SERVICE_FILE > /dev/null <<EOF
[Unit]
Description=Copper CRM Slack Bot
After=network.target

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$CURRENT_DIR
Environment="PATH=$CURRENT_DIR/venv/bin"
ExecStart=$CURRENT_DIR/venv/bin/python app.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

echo -e "${GREEN}Service file created at $SERVICE_FILE${NC}"

echo -e "${GREEN}Step 7: Enabling and starting service...${NC}"
sudo systemctl daemon-reload
sudo systemctl enable copperbot
sudo systemctl start copperbot

echo ""
echo -e "${GREEN}Step 8: Checking service status...${NC}"
sleep 2
sudo systemctl status copperbot --no-pager

echo ""
echo "================================"
echo -e "${GREEN}Deployment Complete!${NC}"
echo "================================"
echo ""
echo "Useful commands:"
echo "  - View logs: sudo journalctl -u copperbot -f"
echo "  - Restart: sudo systemctl restart copperbot"
echo "  - Stop: sudo systemctl stop copperbot"
echo "  - Status: sudo systemctl status copperbot"
echo ""
echo "The bot should now be running and will automatically start on reboot."
echo ""
