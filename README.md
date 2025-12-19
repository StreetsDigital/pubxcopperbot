# Copper CRM Slack Bot

A Slack bot that allows resellers and sales people to query Copper CRM using natural language or CSV file uploads directly from Slack channels.

## Features

- **Full CRUD Operations**: Complete Create, Read, Update, Delete for all Copper CRM entities
  - People/Contacts
  - Companies
  - Opportunities/Deals
  - Leads
  - Tasks
  - Projects
  - Admin users can bypass approval; others require approval workflow

- **Natural Language Task Creation**: Create tasks using plain English
  - "remind me to follow up with CNN next Monday"
  - "call John at Acme Corp tomorrow at 2pm"
  - "urgent: review contract for Disney by Friday"
  - Tasks automatically link to companies/opportunities in CRM
  - Syncs to Google Calendar via Copper's native integration

- **Natural Language Queries**: Ask questions in plain English
  - "Find contacts at Acme Corp"
  - "Show me opportunities over $50,000"
  - "Search for tasks due this week"
  - "List active projects"

- **Smart File Processing**: Upload CSV or Excel files for intelligent processing
  - **CRM Lookup**: Enriches file with CRM data (contacts, companies, opportunities)
  - **Opportunity Import**: Bulk create/update opportunities in your pipeline
  - **Contact Reconciliation**: Cross-reference LinkedIn exports with CRM, detect mismatches

- **Admin Users (Bypass Approval)**: Designated admins can execute operations directly
  - Add admins with `/copper-add-admin @user`
  - Admin actions are logged but don't require approval
  - Perfect for RevOps/CRM managers

- **Contact Reconciliation**: Smart data hygiene for your CRM
  - Upload a LinkedIn export or contact list
  - Bot cross-references with CRM contacts
  - Shows mismatches (e.g., "John moved from Acme to TechCorp")
  - One-click "Update these contacts?" confirmation

- **Create Records with Approval**: Create new CRM records directly from Slack
  - Request creation via `/copper-create` command
  - Supports all entity types with full field control
  - Designated approvers review and approve/reject
  - Interactive approval buttons in Slack

- **Update Records with Approval**: Update existing CRM records
  - Request updates via `/copper-update` command
  - Modify any field on any entity type
  - Approvers see before/after details

- **Delete Records with Approval**: Safely delete CRM records
  - Request deletion via `/copper-delete` command
  - Clear warnings about permanent deletion
  - Approvers must explicitly confirm

- **Flexible Integration**:
  - Direct messages to the bot
  - Mention the bot in channels
  - Slash commands for all operations
  - Works in external shared channels with resellers/sales

## Setup

### Prerequisites

- Python 3.8 or higher
- A Copper CRM account with API access
- A Slack workspace with admin permissions

### 1. Copper CRM API Setup

1. Log in to your Copper CRM account
2. Go to **Settings** → **Integrations** → **API Keys**
3. Click **Generate API Key**
4. Save your API key and the email address associated with it

### 2. Slack App Setup

1. Go to [api.slack.com/apps](https://api.slack.com/apps)
2. Click **Create New App** → **From scratch**
3. Name your app (e.g., "Copper CRM Bot") and select your workspace

#### Configure Bot Token Scopes

Under **OAuth & Permissions**, add these Bot Token Scopes:
- `app_mentions:read` - Read messages that mention the bot
- `channels:history` - View messages in public channels
- `channels:read` - View basic channel info
- `chat:write` - Send messages
- `commands` - Add slash commands
- `files:read` - View files shared in channels
- `files:write` - Upload enriched CSV files
- `im:history` - View messages in direct messages
- `im:read` - View basic info about direct messages
- `im:write` - Start direct messages
- `users:read` - View people in the workspace

#### Enable Socket Mode

1. Go to **Socket Mode** in the sidebar
2. Toggle **Enable Socket Mode** to ON
3. Generate an app-level token with `connections:write` scope
4. Save this token (starts with `xapp-`)

#### Enable Events

1. Go to **Event Subscriptions**
2. Toggle **Enable Events** to ON
3. Subscribe to these bot events:
   - `app_mention`
   - `file_shared`
   - `message.im`

#### Add Slash Commands

1. Go to **Slash Commands**
2. Create the following commands (for each: Request URL not needed for Socket Mode):

**Command 1: `/copper`**
- Short Description: "Query Copper CRM"
- Usage Hint: "Find contacts at Acme Corp"

**Command 2: `/copper-update`**
- Short Description: "Request to update a CRM record"
- Usage Hint: "person 12345 email=new@email.com"

**Command 3: `/copper-add-approver`**
- Short Description: "Add an approver for CRM updates"
- Usage Hint: "@username"

**Command 4: `/copper-pending`**
- Short Description: "View pending approval requests"
- Usage Hint: (leave empty)

**Command 5: `/copper-create`**
- Short Description: "Request to create a new CRM record"
- Usage Hint: "person name='John' email=john@example.com"

**Command 6: `/copper-delete`**
- Short Description: "Request to delete a CRM record"
- Usage Hint: "person 12345"

**Command 7: `/copper-task`**
- Short Description: "Create a task with natural language"
- Usage Hint: "follow up with CNN next Monday"

**Command 8: `/copper-add-admin`**
- Short Description: "Add an admin (bypasses approval)"
- Usage Hint: "@username"

**Command 9: `/copper-map-user`**
- Short Description: "Map Slack user to Copper user ID"
- Usage Hint: "@user 12345"

#### Install App

1. Go to **Install App**
2. Click **Install to Workspace**
3. Authorize the app
4. Copy the **Bot User OAuth Token** (starts with `xoxb-`)

### 3. Application Setup

1. Clone this repository:
   ```bash
   git clone <repository-url>
   cd pubxcopperbot
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create `.env` file from template:
   ```bash
   cp .env.example .env
   ```

4. Edit `.env` and add your credentials:
   ```env
   # Slack Bot Configuration
   SLACK_BOT_TOKEN=xoxb-your-bot-token-here
   SLACK_SIGNING_SECRET=your-signing-secret-here
   SLACK_APP_TOKEN=xapp-your-app-token-here

   # Copper CRM Configuration
   COPPER_API_KEY=your-copper-api-key-here
   COPPER_USER_EMAIL=your-email@company.com

   # Optional: Anthropic Claude for enhanced NLP
   ANTHROPIC_API_KEY=your-anthropic-api-key-here

   # Optional: Default pipeline for opportunity imports
   DEFAULT_PIPELINE_NAME=Bid Intelligence - Supply

   # Optional: Default task assignee Copper user ID
   DEFAULT_TASK_ASSIGNEE_ID=12345
   ```

5. Run the bot:
   ```bash
   python app.py
   ```

You should see:
```
Bot is running in Socket Mode!
```

## Usage

### Natural Language Queries

#### In Direct Messages
Simply send a message to the bot:
```
Find contacts named John Smith
Show me companies in New York
List opportunities over $100,000
```

#### In Channels (Bot Must Be Invited)
Mention the bot in your message:
```
@CopperBot Find all leads from Acme Corporation
@CopperBot Show me open opportunities this quarter
```

#### Using Slash Command
Use the `/copper` command:
```
/copper Find contacts at Microsoft
/copper Show companies in San Francisco
```

### CSV File Uploads (with CRM Enrichment)

Upload a CSV file and get it back with three new columns showing if records exist in your CRM:
- **Contact is in CRM**: Yes/No
- **Company is in CRM**: Yes/No
- **Opportunity exists**: Yes/No

#### CSV Format Example

Input CSV:
```csv
name,email,company,opportunity
John Smith,john@example.com,Acme Corp,Q1 Deal
Jane Doe,jane@example.com,TechCo,Enterprise Sale
```

Output CSV (enriched):
```csv
name,email,company,opportunity,Contact is in CRM,Company is in CRM,Opportunity exists
John Smith,john@example.com,Acme Corp,Q1 Deal,Yes,Yes,No
Jane Doe,jane@example.com,TechCo,Enterprise Sale,No,Yes,Yes
```

#### Supported CSV Columns

- `name` or `contact_name`: Person name
- `email`: Email address
- `phone`: Phone number
- `company` or `company_name`: Company name
- `opportunity` or `opportunity_name` or `deal`: Opportunity name
- `city`: City
- `state`: State/Province
- `country`: Country
- `tags`: Comma-separated tags
- `min_value`: Minimum opportunity value (for opportunities)

#### Upload Methods

1. **Drag and drop** the CSV file into a channel where the bot is present
2. **Direct message** the CSV file to the bot
3. Add a comment with your CSV upload for context

## Examples

### Find People by Name
```
Find contacts named Sarah Johnson
```

### Search Companies by Location
```
Show me companies in Austin, Texas
```

### Query Opportunities by Value
```
List opportunities over $25,000
```

### Search with Multiple Criteria
```
Find people at Salesforce in San Francisco
```

### CSV Batch Query
Create `queries.csv`:
```csv
type,name,city
companies,Microsoft,
people,Jane Doe,Chicago
opportunities,Cloud Migration,
```

Upload this file to the bot and receive results for all three queries.

## Full CRUD Operations with Approval Workflow

The bot provides complete Create, Read, Update, and Delete operations for all Copper CRM entities. All modifications (Create, Update, Delete) require approval from designated approvers.

**📚 For complete CRUD documentation, see [CRUD_OPERATIONS.md](CRUD_OPERATIONS.md)**

### Quick Start

### Setting Up Approvers

First, designate who can approve updates:
```
/copper-add-approver @manager
/copper-add-approver @admin
```

### Requesting an Update

Any user can request an update using the `/copper-update` command:

```
/copper-update person 12345 email=newemail@company.com phone=555-1234
/copper-update company 67890 name="New Company Name" city=Seattle
/copper-update opportunity 11111 monetary_value=75000
```

Format: `/copper-update [entity_type] [entity_id] field=value field2=value2`

### Approval Process

1. **Request Created**: User submits update request
2. **Notification Sent**: All approvers receive a DM with an interactive approval card
3. **Review**: Approver sees:
   - Who requested the update
   - Which entity (with name)
   - Proposed changes
   - Approve/Reject buttons
4. **Decision**: Approver clicks Approve or Reject
5. **Execution**: If approved, changes are immediately applied to Copper CRM
6. **Notification**: Requester is notified of the decision

### Viewing Pending Requests

Approvers can view all pending requests:
```
/copper-pending
```

### Operation Examples

**Create a New Contact:**
```
/copper-create person name="Sarah Johnson" email=sarah@company.com phone=555-1234
```

**Update Contact Email:**
```
/copper-update person 12345 email=john.smith@newcompany.com
```

**Delete an Opportunity:**
```
/copper-delete opportunity 11111
```

**Create a Task:**
```
/copper-create task name="Follow up with lead" due_date=2025-12-01
```

**Update Company Information:**
```
/copper-update company 67890 city="San Francisco" state=CA
```

See [CRUD_OPERATIONS.md](CRUD_OPERATIONS.md) for complete documentation on all operations.

## Advanced Features

### OpenAI Integration (Optional)

For enhanced natural language understanding, add an OpenAI API key to your `.env` file:

```env
OPENAI_API_KEY=sk-your-openai-key-here
```

This enables:
- Better query parsing
- Understanding complex queries
- Extracting multiple search criteria from one query

### Rate Limiting

Copper API allows **180 requests per minute**. The bot handles rate limiting gracefully and will notify you if limits are exceeded.

### Result Limits

- Natural language queries: Returns up to 20 results
- CSV queries: Shows first 10 rows in summary (all processed)

## Troubleshooting

### Bot Not Responding

1. Check that the bot is running (`python app.py`)
2. Verify the bot is invited to the channel
3. Check logs for errors

### Authentication Errors

1. Verify your Copper API key is valid
2. Check that the email in `COPPER_USER_EMAIL` matches the API key owner
3. Ensure Slack tokens are correct

### No Results Found

1. Try simplifying your query
2. Check that the data exists in Copper CRM
3. Verify search criteria spelling

### File Upload Issues

1. Ensure file is in CSV format (`.csv` extension)
2. Check CSV has proper headers
3. Verify the bot has `files:read` permission

## Deployment

### Running as a Service (Linux)

1. Create a systemd service file:
   ```bash
   sudo nano /etc/systemd/system/copperbot.service
   ```

2. Add this content:
   ```ini
   [Unit]
   Description=Copper CRM Slack Bot
   After=network.target

   [Service]
   Type=simple
   User=your-user
   WorkingDirectory=/path/to/pubxcopperbot
   ExecStart=/usr/bin/python3 /path/to/pubxcopperbot/app.py
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```

3. Enable and start the service:
   ```bash
   sudo systemctl enable copperbot
   sudo systemctl start copperbot
   sudo systemctl status copperbot
   ```

### Docker Deployment

Create `Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "app.py"]
```

Build and run:
```bash
docker build -t copperbot .
docker run -d --env-file .env copperbot
```

### AWS Lightsail Deployment

Deploy to an Ubuntu Lightsail instance:

1. **Create Lightsail Instance**:
   - Choose Ubuntu 22.04 LTS
   - Select appropriate plan (smallest should work)
   - Open port 22 (SSH) in networking

2. **Connect and Setup**:
   ```bash
   ssh ubuntu@your-lightsail-ip

   # Update system
   sudo apt update && sudo apt upgrade -y

   # Install Python and dependencies
   sudo apt install -y python3 python3-pip python3-venv git

   # Clone repository
   git clone <your-repo-url>
   cd pubxcopperbot

   # Create virtual environment
   python3 -m venv venv
   source venv/bin/activate

   # Install dependencies
   pip install -r requirements.txt
   ```

3. **Configure Environment**:
   ```bash
   # Copy and edit .env file
   cp .env.example .env
   nano .env
   ```

   Add your API keys and tokens

4. **Create Systemd Service**:
   ```bash
   sudo nano /etc/systemd/system/copperbot.service
   ```

   Add:
   ```ini
   [Unit]
   Description=Copper CRM Slack Bot
   After=network.target

   [Service]
   Type=simple
   User=ubuntu
   WorkingDirectory=/home/ubuntu/pubxcopperbot
   Environment="PATH=/home/ubuntu/pubxcopperbot/venv/bin"
   ExecStart=/home/ubuntu/pubxcopperbot/venv/bin/python app.py
   Restart=always
   RestartSec=10

   [Install]
   WantedBy=multi-user.target
   ```

5. **Enable and Start**:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable copperbot
   sudo systemctl start copperbot
   sudo systemctl status copperbot
   ```

6. **View Logs**:
   ```bash
   sudo journalctl -u copperbot -f
   ```

7. **Auto-start on Reboot**:
   The service will automatically start on system reboot due to the `enable` command.

**Quick Deployment Script**: Use `deploy.sh` for automated setup (see repository)

### CI/CD Auto-Deployment to Lightsail

The bot includes a GitHub Actions workflow that automatically deploys to your Lightsail instance when you push to the `main` branch.

**Setup Required Secrets** in your GitHub repository (Settings → Secrets and variables → Actions):

| Secret | Description |
|--------|-------------|
| `LIGHTSAIL_HOST` | Your Lightsail instance IP address |
| `LIGHTSAIL_USER` | SSH username (usually `ubuntu`) |
| `LIGHTSAIL_SSH_KEY` | Private SSH key for authentication |

**How to get your SSH key:**
1. In Lightsail, go to Account → SSH Keys
2. Download your default key or create a new one
3. Copy the contents of the private key file
4. Paste it into the `LIGHTSAIL_SSH_KEY` secret

**Workflow:**
1. Push to `main` branch
2. Tests run automatically
3. If tests pass, deploys to Lightsail
4. Bot restarts with new code

**Manual Deploy:**
```bash
ssh ubuntu@your-lightsail-ip
cd ~/pubxcopperbot
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart copperbot
```

## Security Notes

- Never commit your `.env` file
- Keep API keys secure and rotate them regularly
- Use environment variables for all sensitive data
- Limit bot permissions to only what's needed
- Monitor bot usage and API calls

## Support

For issues or questions:
1. Check the logs: The bot logs all operations
2. Review Copper API docs: [developer.copper.com](https://developer.copper.com/)
3. Check Slack API docs: [api.slack.com](https://api.slack.com/)

## License

MIT License - See LICENSE file for details

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## Changelog

### v4.0.0 (2025-12-19) - RevOps Power Release
- **Natural Language Tasks**: `/copper-task follow up with CNN next Monday`
  - Smart date parsing (tomorrow, next week, Friday, in 3 days)
  - Auto-links to companies/opportunities
  - Syncs to Google Calendar via Copper
- **Admin Users**: `/copper-add-admin` for users who bypass approval
- **Smart File Processing**: Intelligent detection of file type
  - Opportunity import to configured pipeline
  - Contact reconciliation with mismatch detection
  - LinkedIn data cross-referencing
- **Excel Support**: Now accepts .xlsx and .xls files
- **Pipeline Configuration**: Set default pipeline for opportunity imports
- **User Mapping**: `/copper-map-user` maps Slack users to Copper IDs
- **Persistent State**: All data survives bot restarts

### v3.0.0 (2025-11-05) - Full CRUD Release
- **Full CRUD Operations**: Complete Create, Read, Update, Delete for all entities
- **6 Entity Types**: People, Companies, Opportunities, Leads, Tasks, Projects
- **Create Records**: `/copper-create` command with approval workflow
- **Delete Records**: `/copper-delete` command with safety confirmations
- **Enhanced Approval System**: Handles create, update, and delete operations
- **Interactive UI**: Clear operation-specific approval cards
- **Comprehensive Documentation**: New CRUD_OPERATIONS.md guide

### v2.0.0 (2025-11-05)
- **CSV Enrichment**: Upload CSV and get enriched file with CRM existence columns
- **Update Workflow**: Request and approve CRM record updates via Slack
- **Approval System**: Designated approvers can review/approve/reject changes
- **Interactive Buttons**: Approve/reject with one click in Slack
- **Notification System**: Auto-notify requesters of approval decisions

### v1.0.0 (2025-11-05)
- Initial release
- Natural language query support
- CSV file upload processing
- Multiple entity type support
- Claude integration for enhanced NLP
