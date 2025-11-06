# Copper CRM Slack Bot - Deployment Checklist

Follow these steps in order to deploy your bot to production.

## Phase 1: Get API Credentials (15 minutes)

### Step 1: Copper CRM API Key

1. Log in to Copper CRM: https://app.copper.com
2. Click **Settings** (gear icon) → **Integrations** → **API Keys**
3. Click **Generate API Key**
4. **Copy and save:**
   - API Key (starts with a long string)
   - Your email address (the one you're logged in with)

### Step 2: Create Slack App

1. Go to https://api.slack.com/apps
2. Click **Create New App** → **From scratch**
3. App Name: `Copper CRM Bot`
4. Pick your workspace
5. Click **Create App**

### Step 3: Configure Slack Bot Permissions

**In OAuth & Permissions section:**

Add these **Bot Token Scopes**:
- `app_mentions:read`
- `channels:history`
- `channels:read`
- `chat:write`
- `commands`
- `files:read`
- `files:write`
- `im:history`
- `im:read`
- `im:write`
- `users:read`

Click **Install to Workspace** → **Allow**

**Copy the Bot User OAuth Token** (starts with `xoxb-`)

### Step 4: Enable Socket Mode

1. Go to **Socket Mode** in sidebar
2. Toggle **Enable Socket Mode** → ON
3. Generate an app-level token
   - Name it: `copper-bot-socket`
   - Add scope: `connections:write`
4. **Copy the App Token** (starts with `xapp-`)

### Step 5: Enable Events

1. Go to **Event Subscriptions**
2. Toggle **Enable Events** → ON
3. Under **Subscribe to bot events**, add:
   - `app_mention`
   - `file_shared`
   - `message.im`
4. Click **Save Changes**

### Step 6: Add Slash Commands

Go to **Slash Commands** → Create each command:

**Command 1:**
- Command: `/copper`
- Short Description: `Query Copper CRM`
- Usage Hint: `Find contacts at Acme Corp`

**Command 2:**
- Command: `/copper-update`
- Short Description: `Request to update a CRM record`
- Usage Hint: `person 12345 email=new@email.com`

**Command 3:**
- Command: `/copper-create`
- Short Description: `Request to create a new CRM record`
- Usage Hint: `person name="John" email=john@example.com`

**Command 4:**
- Command: `/copper-delete`
- Short Description: `Request to delete a CRM record`
- Usage Hint: `person 12345`

**Command 5:**
- Command: `/copper-add-approver`
- Short Description: `Add an approver for CRM updates`
- Usage Hint: `@username`

**Command 6:**
- Command: `/copper-pending`
- Short Description: `View pending approval requests`
- Usage Hint: (leave empty)

Click **Save** after each command.

### Step 7: Get Your Signing Secret

1. Go to **Basic Information** in sidebar
2. Scroll to **App Credentials**
3. **Copy the Signing Secret**

---

## Phase 2: Deploy to AWS Lightsail (20 minutes)

### Step 1: Create Lightsail Instance

1. Go to https://lightsail.aws.amazon.com/
2. Click **Create instance**
3. Select:
   - Platform: **Linux/Unix**
   - Blueprint: **OS Only** → **Ubuntu 22.04 LTS**
   - Instance plan: **$5/month** (512 MB RAM is enough)
4. Name it: `copper-crm-bot`
5. Click **Create instance**
6. Wait for it to start (shows "Running")

### Step 2: Connect to Instance

**Option A: Browser SSH (easiest)**
1. Click the instance name
2. Click **Connect using SSH**
3. A terminal window opens

**Option B: SSH Client**
```bash
ssh ubuntu@YOUR-LIGHTSAIL-IP
```

### Step 3: Clone the Repository

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install git if needed
sudo apt install -y git

# Clone your repository
git clone http://local_proxy@127.0.0.1:YOUR-PORT/git/StreetsDigital/pubxcopperbot
cd pubxcopperbot

# Checkout the branch
git checkout claude/slack-integration-tool-011CUqcdXJrYcTqZjJahg3Lf
```

### Step 4: Configure Environment Variables

```bash
# Copy the example env file
cp .env.example .env

# Edit the file
nano .env
```

**Fill in your credentials:**
```env
# Slack Bot Configuration
SLACK_BOT_TOKEN=xoxb-your-bot-token-from-step-3
SLACK_SIGNING_SECRET=your-signing-secret-from-step-7
SLACK_APP_TOKEN=xapp-your-app-token-from-step-4

# Copper CRM Configuration
COPPER_API_KEY=your-copper-api-key-from-step-1
COPPER_USER_EMAIL=your-email@company.com

# Optional: OpenAI for enhanced NLP
OPENAI_API_KEY=sk-your-openai-key-here

# Application Settings
PORT=3000
LOG_LEVEL=INFO
```

**Save:** Press `Ctrl+X`, then `Y`, then `Enter`

### Step 5: Run Automated Deployment

```bash
# Make script executable
chmod +x deploy.sh

# Run deployment
./deploy.sh
```

**The script will:**
- Install Python and dependencies
- Create virtual environment
- Set up systemd service
- Start the bot
- Enable auto-start on reboot

**You should see:** `Bot is running in Socket Mode!`

### Step 6: Verify Deployment

```bash
# Check bot status
sudo systemctl status copperbot

# View logs
sudo journalctl -u copperbot -f
```

**Look for:** `Bot is running in Socket Mode!`

Press `Ctrl+C` to exit logs.

---

## Phase 3: Test the Bot (10 minutes)

### Step 1: Add First Approver

In Slack:
```
/copper-add-approver @yourusername
```

You should see: ✅ Added @yourusername as an approver.

### Step 2: Test Natural Language Query

```
/copper Find contacts at Acme Corp
```

or in a channel where bot is invited:
```
@Copper CRM Bot show me companies in San Francisco
```

### Step 3: Test CSV Upload

Create a test CSV file `test.csv`:
```csv
name,email,company,opportunity
John Doe,john@example.com,Acme Corp,Q1 Deal
Jane Smith,jane@example.com,TechCo,Big Sale
```

Upload it to a DM with the bot or a channel where it's present.

**You should get back:** An enriched CSV with 3 new columns!

### Step 4: Test Create Request

```
/copper-create person name="Test User" email=test@example.com
```

**You should:**
1. See: "Create request submitted!"
2. Receive a DM with Approve/Reject buttons
3. Click **Approve**
4. See: "✅ Approved and created person..."

### Step 5: Test Update Request

```
/copper-update person 12345 email=newemail@example.com
```

(Use an actual person ID from your CRM)

### Step 6: Invite to Channel

1. Go to a Slack channel
2. Type: `/invite @Copper CRM Bot`
3. Now the bot works in that channel!

---

## Troubleshooting

### Bot Not Responding

```bash
# Check if bot is running
sudo systemctl status copperbot

# Restart bot
sudo systemctl restart copperbot

# Check logs for errors
sudo journalctl -u copperbot -n 50
```

### Common Issues

**"No module named 'dotenv'"**
```bash
cd /home/ubuntu/pubxcopperbot
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart copperbot
```

**"Invalid token"**
- Check your `.env` file has correct tokens
- Make sure no extra spaces around the `=` sign
- Tokens should not have quotes

**"Rate limit exceeded"**
- Copper allows 180 requests/min
- Wait a minute and try again

### Useful Commands

```bash
# Restart bot
sudo systemctl restart copperbot

# Stop bot
sudo systemctl stop copperbot

# Start bot
sudo systemctl start copperbot

# View logs (live)
sudo journalctl -u copperbot -f

# View last 100 log lines
sudo journalctl -u copperbot -n 100

# Edit .env file
cd /home/ubuntu/pubxcopperbot
nano .env
# Then restart: sudo systemctl restart copperbot
```

---

## Phase 4: Add to External Channels (5 minutes)

### For Reseller/Sales Channels

1. Go to the external Slack channel
2. Type: `/invite @Copper CRM Bot`
3. The bot now works in that channel!

**Everyone in the channel can:**
- Query the CRM with natural language
- Upload CSV files for enrichment
- Request creates/updates/deletes

**Only designated approvers can:**
- Approve/reject modification requests

---

## Security Checklist

✅ Keep your `.env` file secure (never commit it)
✅ Only add trusted users as approvers
✅ Regularly rotate API keys
✅ Monitor bot logs for unusual activity
✅ Review pending requests regularly

---

## Quick Reference

**Useful URLs:**
- Lightsail Console: https://lightsail.aws.amazon.com/
- Slack Apps: https://api.slack.com/apps
- Copper CRM: https://app.copper.com

**SSH to Server:**
```bash
ssh ubuntu@YOUR-LIGHTSAIL-IP
cd /home/ubuntu/pubxcopperbot
```

**View Logs:**
```bash
sudo journalctl -u copperbot -f
```

**Restart Bot:**
```bash
sudo systemctl restart copperbot
```

---

## You're Done! 🎉

Your Copper CRM Slack Bot is now:
- ✅ Deployed to AWS Lightsail
- ✅ Running 24/7 with auto-restart
- ✅ Connected to Slack and Copper CRM
- ✅ Ready for your resellers and sales team

**Next Steps:**
1. Invite bot to your external channels
2. Add more approvers as needed
3. Share the bot with your team!

Need help? Check the logs or review the main README.md
