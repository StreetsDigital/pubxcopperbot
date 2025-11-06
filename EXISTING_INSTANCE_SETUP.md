# Multi-Application Folder Structure for Lightsail

## Recommended Folder Organization

```
/home/ubuntu/
├── apps/                          # All applications here
│   ├── copperbot/                 # Your Copper CRM Slack bot
│   │   ├── venv/                  # Python virtual environment
│   │   ├── app.py
│   │   ├── .env                   # Environment variables
│   │   └── ...                    # Other bot files
│   │
│   ├── other-app-1/               # Your other applications
│   ├── other-app-2/
│   └── ...
│
├── logs/                          # Centralized logs (optional)
│   ├── copperbot/
│   ├── other-app-1/
│   └── ...
│
└── backups/                       # Backups (optional)
    └── copperbot/
```

## Quick Setup Commands

### Step 1: Create Apps Directory

```bash
# SSH into your Lightsail instance
ssh ubuntu@YOUR-LIGHTSAIL-IP

# Create apps directory
mkdir -p ~/apps
cd ~/apps
```

### Step 2: Clone the Repository

```bash
# Clone into apps/copperbot
git clone <your-repo-url> copperbot
cd copperbot

# Checkout the branch
git checkout claude/slack-integration-tool-011CUqcdXJrYcTqZjJahg3Lf
```

### Step 3: Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit with your credentials
nano .env
```

Paste your:
- SLACK_BOT_TOKEN
- SLACK_SIGNING_SECRET
- SLACK_APP_TOKEN
- COPPER_API_KEY
- COPPER_USER_EMAIL

Save: `Ctrl+X`, then `Y`, then `Enter`

### Step 4: Install Dependencies

```bash
# Install Python (if not already installed)
sudo apt update
sudo apt install -y python3 python3-pip python3-venv

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 5: Test Run (Optional)

```bash
# Test the bot manually first
python app.py
```

You should see: `Bot is running in Socket Mode!`

Press `Ctrl+C` to stop.

### Step 6: Create Systemd Service

```bash
# Create service file
sudo nano /etc/systemd/system/copperbot.service
```

Paste this (adjust paths if needed):

```ini
[Unit]
Description=Copper CRM Slack Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/apps/copperbot
Environment="PATH=/home/ubuntu/apps/copperbot/venv/bin"
ExecStart=/home/ubuntu/apps/copperbot/venv/bin/python app.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Save: `Ctrl+X`, then `Y`, then `Enter`

### Step 7: Start the Service

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable auto-start on boot
sudo systemctl enable copperbot

# Start the bot
sudo systemctl start copperbot

# Check status
sudo systemctl status copperbot
```

You should see: `Active: active (running)`

### Step 8: View Logs

```bash
# View live logs
sudo journalctl -u copperbot -f

# View last 50 lines
sudo journalctl -u copperbot -n 50
```

---

## Managing Multiple Apps on Same Instance

### Systemd Services

Each app gets its own service:

```bash
# List all your services
sudo systemctl list-units --type=service | grep -E 'copperbot|your-other-app'

# Restart specific service
sudo systemctl restart copperbot

# View status of all your apps
systemctl status copperbot other-app-1 other-app-2
```

### Port Management

If you have multiple web apps:

```bash
# copperbot doesn't use HTTP ports (Socket Mode)
# But if you have other apps:

# App 1 on port 3000
# App 2 on port 3001
# App 3 on port 3002
# etc.
```

Update `.env` for each app:
```env
PORT=3000  # copperbot (though it doesn't need this for Socket Mode)
```

### Nginx Reverse Proxy (If Needed)

If you have web apps, use nginx:

```bash
sudo apt install nginx

# Configure proxy
sudo nano /etc/nginx/sites-available/myapps
```

```nginx
# Example for web apps (not needed for copperbot)
server {
    listen 80;
    server_name app1.yourdomain.com;

    location / {
        proxy_pass http://localhost:3001;
    }
}

server {
    listen 80;
    server_name app2.yourdomain.com;

    location / {
        proxy_pass http://localhost:3002;
    }
}
```

---

## Resource Management

### Check Resource Usage

```bash
# Check memory usage
free -h

# Check disk usage
df -h

# Check running processes
htop  # or: top

# Check your apps
ps aux | grep python
```

### Lightsail Instance Recommendations

For Copper Bot + Other Apps:

| Apps Running | Recommended Plan | Cost |
|--------------|------------------|------|
| 1-2 light apps | $5/mo (512 MB) | $5 |
| 2-3 medium apps | $10/mo (1 GB) | $10 |
| 4+ apps or heavy | $20/mo (2 GB) | $20 |

**Copper bot is very light** - uses ~50-100 MB RAM

### Monitor Your Instance

```bash
# Install monitoring tools
sudo apt install htop ncdu

# Check what's using memory
htop

# Check what's using disk space
ncdu /home/ubuntu
```

---

## File Permissions Best Practice

```bash
# Set correct ownership
sudo chown -R ubuntu:ubuntu /home/ubuntu/apps/copperbot

# Set correct permissions
chmod 600 /home/ubuntu/apps/copperbot/.env  # Secure env file
chmod +x /home/ubuntu/apps/copperbot/deploy.sh
```

---

## Backup Strategy

### Create Backup Script

```bash
mkdir -p ~/backups
nano ~/backup-copperbot.sh
```

```bash
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/home/ubuntu/backups/copperbot"
APP_DIR="/home/ubuntu/apps/copperbot"

mkdir -p $BACKUP_DIR

# Backup env file and config
tar -czf $BACKUP_DIR/copperbot_$DATE.tar.gz \
    $APP_DIR/.env \
    $APP_DIR/*.py \
    $APP_DIR/*.md \
    $APP_DIR/requirements.txt

# Keep only last 7 backups
cd $BACKUP_DIR
ls -t | tail -n +8 | xargs rm -f

echo "Backup completed: copperbot_$DATE.tar.gz"
```

```bash
chmod +x ~/backup-copperbot.sh

# Run manually
~/backup-copperbot.sh

# Or schedule with cron
crontab -e
# Add: 0 2 * * * /home/ubuntu/backup-copperbot.sh
```

---

## Quick Commands Cheat Sheet

```bash
# Navigate to bot
cd ~/apps/copperbot

# Activate virtual environment
source venv/bin/activate

# Restart bot
sudo systemctl restart copperbot

# View logs
sudo journalctl -u copperbot -f

# Edit environment
nano .env
# Then: sudo systemctl restart copperbot

# Update code
git pull
pip install -r requirements.txt
sudo systemctl restart copperbot

# Check status
sudo systemctl status copperbot
```

---

## Troubleshooting

### Bot Won't Start

```bash
# Check logs
sudo journalctl -u copperbot -n 100

# Common issues:
# 1. Virtual environment path wrong in service file
# 2. .env file permissions
# 3. Missing dependencies

# Fix:
cd ~/apps/copperbot
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart copperbot
```

### Python Version Issues

```bash
# Check Python version
python3 --version  # Should be 3.8+

# If old version, update:
sudo apt update
sudo apt install python3.11 python3.11-venv python3-pip
```

### Out of Memory

```bash
# Check memory
free -h

# If tight on memory, upgrade Lightsail plan
# Or reduce other apps
```

---

## Summary

**Your Setup:**
```
/home/ubuntu/apps/copperbot/  ← Bot lives here
/etc/systemd/system/copperbot.service  ← Service config
Logs: sudo journalctl -u copperbot
```

**Next Steps:**
1. SSH to your Lightsail instance
2. Create `/home/ubuntu/apps/`
3. Clone repo there
4. Follow steps 3-8 above
5. Done!

The bot runs independently and won't interfere with your other apps! 🚀
