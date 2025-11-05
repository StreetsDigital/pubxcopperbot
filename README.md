# Copper CRM Slack Bot

A Slack bot that allows resellers and sales people to query Copper CRM using natural language or CSV file uploads directly from Slack channels.

## Features

- **Natural Language Queries**: Ask questions in plain English
  - "Find contacts at Acme Corp"
  - "Show me opportunities over $50,000"
  - "Search for companies in San Francisco"

- **CSV Batch Queries**: Upload a CSV file with multiple search criteria
  - Process multiple queries at once
  - Get structured results for each row

- **Multiple Entity Types**: Search across different Copper entities
  - People/Contacts
  - Companies
  - Opportunities/Deals
  - Leads

- **Flexible Integration**:
  - Direct messages to the bot
  - Mention the bot in channels
  - Use `/copper` slash command
  - Works in external shared channels

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

#### Add Slash Command

1. Go to **Slash Commands**
2. Click **Create New Command**
3. Command: `/copper`
4. Request URL: (not needed for Socket Mode)
5. Short Description: "Query Copper CRM"
6. Usage Hint: "Find contacts at Acme Corp"

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

   # Optional: OpenAI for enhanced NLP
   OPENAI_API_KEY=your-openai-api-key-here
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

### CSV File Uploads

Upload a CSV file to query multiple records at once.

#### CSV Format Example

```csv
type,name,email,city
people,John Smith,john@example.com,
companies,Acme Corp,,San Francisco
opportunities,Enterprise Deal,,
```

#### Supported CSV Columns

- `type` or `entity_type`: people, companies, opportunities, leads
- `name`: Person or company name
- `email`: Email address
- `phone`: Phone number
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

### v1.0.0 (2025-11-05)
- Initial release
- Natural language query support
- CSV file upload processing
- Multiple entity type support
- OpenAI integration for enhanced NLP
