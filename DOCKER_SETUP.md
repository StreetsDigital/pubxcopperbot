# Docker Setup with Claude OAuth Support

This setup runs a Claude API proxy service that supports OAuth authentication, allowing you to use your Claude Code OAuth token instead of an API key.

## Architecture

```
┌─────────────────┐      HTTP       ┌──────────────────┐
│                 │  ────────────>  │                  │
│  Slack Bot      │                 │  Claude Proxy    │
│  (Python)       │  <────────────  │  (FastAPI)       │
│                 │                 │                  │
└─────────────────┘                 └──────────────────┘
                                            │
                                            │ OAuth/API Key
                                            ▼
                                    ┌──────────────────┐
                                    │  Anthropic API   │
                                    └──────────────────┘
```

## Quick Start

### 1. Configure Environment

Make sure your `.env` file has the OAuth token:

```bash
# Claude AI Configuration
CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-...
# Optional fallback
ANTHROPIC_API_KEY=sk-ant-api03-...

# Proxy URL (for local development)
CLAUDE_PROXY_URL=http://localhost:6969
```

### 2. Start Services

```bash
# Start both the Claude proxy and the bot
docker-compose up -d

# View logs
docker-compose logs -f

# Check health
curl http://localhost:6969/health
```

### 3. Run Locally (without Docker)

If you want to run the bot locally but use the Docker proxy:

```bash
# Terminal 1: Start the Claude proxy
docker-compose up claude-proxy

# Terminal 2: Run the bot locally
./venv/bin/python app.py
```

## How It Works

1. **Claude Proxy Service** (`claude_proxy.py`):
   - Runs on port 6969
   - Accepts HTTP POST requests at `/v1/messages`
   - Authenticates with Anthropic API using OAuth token (preferred) or API key
   - Returns Claude's response in a simplified format

2. **Business Intelligence Module** (`business_intelligence.py`):
   - Checks if Claude proxy is available on startup
   - Makes HTTP requests to proxy instead of using Anthropic SDK directly
   - Falls back to basic query parsing if proxy is unavailable

3. **Docker Compose**:
   - Orchestrates both services
   - Creates a bridge network for communication
   - Handles health checks and dependencies

## Endpoints

### Claude Proxy

#### `POST /v1/messages`
Request:
```json
{
  "prompt": "Your question here",
  "max_tokens": 1024,
  "model": "claude-3-5-haiku-20241022",
  "temperature": 0.0
}
```

Response:
```json
{
  "content": "Claude's response",
  "model": "claude-3-5-haiku-20241022",
  "stop_reason": "end_turn"
}
```

#### `GET /health`
Response:
```json
{
  "status": "healthy",
  "auth_method": "oauth",
  "configured": true
}
```

## Troubleshooting

### Proxy not starting
```bash
# Check logs
docker-compose logs claude-proxy

# Rebuild
docker-compose build claude-proxy
docker-compose up -d claude-proxy
```

### Bot can't connect to proxy
```bash
# Check proxy health
curl http://localhost:6969/health

# Check if proxy is running
docker ps | grep claude-proxy

# Verify network
docker network inspect copperbot_copperbot
```

### OAuth token not working
```bash
# Check proxy logs for authentication errors
docker-compose logs claude-proxy | grep -i auth

# Verify token in .env file
cat .env | grep CLAUDE_CODE_OAUTH_TOKEN
```

## Development

### Local Development (No Docker)

1. Install proxy dependencies:
```bash
pip install -r requirements-proxy.txt
```

2. Start proxy:
```bash
python claude_proxy.py
```

3. Start bot:
```bash
./venv/bin/python app.py
```

### Testing the Proxy

```bash
curl -X POST http://localhost:6969/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "What is 2+2?",
    "max_tokens": 100,
    "model": "claude-3-5-haiku-20241022"
  }'
```

## Production Deployment

For production, you can run this on your home machine:

```bash
# Start in detached mode
docker-compose up -d

# Enable restart on boot
docker-compose up -d --restart unless-stopped

# View logs
docker-compose logs -f
```

The bot will automatically reconnect if the proxy restarts.
