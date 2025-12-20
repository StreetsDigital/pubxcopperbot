# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Slack bot that integrates with Copper CRM, enabling natural language queries, CRUD operations with approval workflows, CSV/Excel file processing, and task management directly from Slack channels.

**Tech Stack**: Python 3.9+, Slack Bolt SDK (Socket Mode), Copper CRM API, Anthropic Claude (optional NLP enhancement)

## Commands

```bash
# Install dependencies
pip install -r requirements.txt
pip install -r requirements-test.txt  # for testing

# Run the bot locally
python app.py

# Run all tests with coverage
pytest

# Run a single test file
pytest tests/test_copper_client.py -v

# Run a specific test
pytest tests/test_copper_client.py::TestCopperClientSearch::test_search_people_success -v

# Lint (matches CI pipeline)
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics

# Format check
black --check .
isort --check-only .

# Security scan
bandit -r .
safety check
```

## Architecture

### Core Components

- **app.py** - Main Slack bot application, event handlers, and slash commands. Orchestrates all components via Slack Bolt Socket Mode.

- **copper_client.py** - Copper CRM API wrapper with full CRUD for: people, companies, opportunities, leads, tasks, projects. Handles rate limiting (180 req/min) and error responses.

- **approval_system.py** - Approval workflow engine. Manages approvers, admins (who bypass approval), pending requests, and persists state to disk. Generates interactive Slack blocks for approve/reject buttons.

- **query_processor.py** - Natural language query parser. Extracts entity types and search criteria from plain English.

- **csv_handler.py** - File processing for CSV/Excel uploads. Three modes: CRM lookup/enrichment, opportunity import, contact reconciliation.

- **task_processor.py** - Natural language task creation. Parses dates ("next Monday", "in 3 days") and links tasks to related CRM entities.

- **config.py** - Environment-based configuration with validation.

### Data Flow

1. Slack events arrive via Socket Mode (no public endpoint needed)
2. `app.py` routes to appropriate handler based on event type
3. Handlers use `query_processor` or `task_processor` for NL parsing
4. `copper_client` executes CRM operations
5. Non-admin write operations go through `approval_system`
6. Approvers receive interactive Slack messages with approve/reject buttons

### Slash Commands

- `/copper` - Natural language CRM queries
- `/copper-create`, `/copper-update`, `/copper-delete` - CRUD with approval
- `/copper-task` - Natural language task creation
- `/copper-pending` - View pending approval requests
- `/copper-add-approver`, `/copper-add-admin` - User management
- `/copper-map-user` - Map Slack users to Copper user IDs

## Testing

Tests live in `tests/` alongside the modules they test. Uses pytest with fixtures that mock the Config class and HTTP requests.

Mock pattern for Copper API calls:
```python
@patch('copper_client.requests.request')
def test_search_people_success(self, mock_request, copper_client):
    mock_response = Mock()
    mock_response.json.return_value = [{"id": 1, "name": "John Doe"}]
    mock_response.status_code = 200
    mock_request.return_value = mock_response
    # ...
```

## Deployment

CI/CD via GitHub Actions (`.github/workflows/ci.yml`):
- Tests run on Python 3.9, 3.10, 3.11
- Auto-deploys to Lightsail on push to `main`
- Requires secrets: `LIGHTSAIL_HOST`, `LIGHTSAIL_USER`, `LIGHTSAIL_SSH_KEY`

Manual deployment: `./deploy.sh` (Ubuntu/Lightsail) - creates systemd service `copperbot`

## Environment Variables

Required:
- `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET`, `SLACK_APP_TOKEN`
- `COPPER_API_KEY`, `COPPER_USER_EMAIL`

Optional:
- `ANTHROPIC_API_KEY` - Enhanced NLP parsing
- `DEFAULT_TASK_ASSIGNEE_ID` - Fallback Copper user ID for task assignment
- `DEFAULT_PIPELINE_NAME` - Pipeline for opportunity imports
- `DATA_DIR` - Persistent storage directory (default: `./data`)
