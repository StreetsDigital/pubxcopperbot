"""Copper CRM Slack Bot - Main Application."""

import json
import logging
import os
import re
import signal
import sys
import threading
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from types import FrameType
from typing import Any, Callable, Dict, List, Optional, Union

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk import WebClient

from approval_system import ApprovalSystem
from business_intelligence import BusinessIntelligence
from config import Config
from copper_client import CopperClient
from csv_handler import CSVHandler
from query_processor import QueryProcessor
from task_processor import TaskProcessor
from validation import validate_and_sanitize, validate_entity_id
from metrics import (
    get_metrics,
    get_metrics_content_type,
    update_approval_gauges,
    update_uptime,
    SLACK_EVENTS_TOTAL,
    ERRORS_TOTAL,
)

# Type aliases for common patterns
JsonDict = Dict[str, Any]
SlackEvent = Dict[str, Any]
SlackCommand = Dict[str, Any]
SlackAction = Dict[str, Any]
SayFunction = Callable[..., Any]
AckFunction = Callable[[], None]
CsvRow = Dict[str, str]
ReconciliationResult = Dict[str, Any]

# Track startup time for uptime calculation
_start_time: datetime = datetime.now()

# Configure logging
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Validate configuration
try:
    Config.validate()
except ValueError as e:
    logger.error(f"Configuration error: {e}")
    exit(1)

# Initialize Slack app
app = App(token=Config.SLACK_BOT_TOKEN)

# Initialize components
copper_client = CopperClient()
query_processor = QueryProcessor()
csv_handler = CSVHandler(copper_client)
approval_system = ApprovalSystem()
business_intel = BusinessIntelligence(copper_client)
task_processor = TaskProcessor(copper_client)


@app.event("app_mention")
def handle_mention(event: SlackEvent, say: SayFunction, client: WebClient) -> None:
    """
    Handle when the bot is mentioned in a channel.

    Args:
        event: Slack event data
        say: Function to send messages
        client: Slack client
    """
    try:
        user: str = event.get("user", "")
        text: str = event.get("text", "")

        # Remove bot mention from text
        bot_user_id: str = client.auth_test()["user_id"]
        text = text.replace(f"<@{bot_user_id}>", "").strip()

        if not text:
            say(
                text=f"Hi <@{user}>! I'm your intelligent Copper CRM assistant. "
                     "Ask me anything in natural language!\n\n"
                     "*Business Intelligence:*\n"
                     "• 'What's the status of PubX?'\n"
                     "• 'Show me everything about Acme Corp'\n"
                     "• 'Who are we talking to at Microsoft?'\n"
                     "• 'What deals are in progress?'\n\n"
                     "*Tasks:*\n"
                     "• 'Remind me to follow up with CNN next week'\n\n"
                     "*Updates:*\n"
                     "• 'Update the PubX deal status to closed'\n"
                     "• _(Will notify admins for approval)_"
            )
            return

        # Check if this is a task request
        if task_processor.is_task_request(text):
            _handle_task_request(text, user, say, client)
            return

        # Check if this is an update request
        text_lower = text.lower()
        if any(word in text_lower for word in ["update", "change", "modify", "set", "edit"]):
            # This is an update request - notify for approval
            logger.info(f"Update request from {user}: {text}")
            say(text=f"🔔 Update request received from <@{user}>:\n\n_{text}_\n\n"
                     f"An admin will review this request shortly.")

            # Notify admins/approvers
            approvers = approval_system.get_approvers()
            admins = approval_system.get_admins()
            all_reviewers = list(set(approvers + admins))

            if all_reviewers:
                for reviewer in all_reviewers:
                    try:
                        client.chat_postMessage(
                            channel=reviewer,
                            text=f"📝 *Update Request*\n\n"
                                 f"From: <@{user}>\n"
                                 f"Request: _{text}_\n\n"
                                 f"Please review and process this update in Copper CRM."
                        )
                    except Exception as e:
                        logger.error(f"Error notifying reviewer {reviewer}: {e}")
            return

        # Process as an intelligent business query
        logger.info(f"Processing business intelligence query from {user}: {text}")
        say(text=f"🔍 Gathering intelligence from Copper CRM...")

        # Use business intelligence to process the query
        result = business_intel.process_query(text)

        say(text=result)

    except Exception as e:
        logger.error(f"Error handling mention: {str(e)}", exc_info=True)
        say(text=f"Sorry, I encountered an error: {str(e)}")


@app.event("message")
def handle_message(event: SlackEvent, say: SayFunction, client: WebClient) -> None:
    """
    Handle direct messages to the bot.

    Args:
        event: Slack event data
        say: Function to send messages
        client: Slack client
    """
    # Only respond to DMs (channel_type = 'im')
    if event.get("channel_type") != "im":
        return

    # Ignore bot messages
    if event.get("subtype") == "bot_message":
        return

    try:
        user: str = event.get("user", "")
        text: str = event.get("text", "").strip()

        if not text:
            return

        # Check for help commands
        if text.lower() in ["help", "?", "commands"]:
            say(
                text="*Copper CRM Bot - Intelligent Assistant*\n\n"
                     "*Business Intelligence:*\n"
                     "Ask me anything about your business! I'll gather comprehensive information:\n"
                     "• 'What's the status of PubX?'\n"
                     "• 'Show me everything about Acme Corp'\n"
                     "• 'Who are we talking to at Microsoft?'\n"
                     "• 'What deals are in progress?'\n\n"
                     "*Task Creation:*\n"
                     "• 'Remind me to follow up with CNN next week'\n"
                     "• 'Call John at Acme tomorrow at 2pm'\n\n"
                     "*Update Requests:*\n"
                     "• 'Update the PubX deal to closed won'\n"
                     "• _(Sends notification to admins for approval)_\n\n"
                     "*CSV Upload:*\n"
                     "Upload a CSV file for data enrichment.\n\n"
                     "Need more help? Contact your admin!"
            )
            return

        # Check if this is a task request
        if task_processor.is_task_request(text):
            _handle_task_request(text, user, say, client)
            return

        # Check if this is an update request
        text_lower = text.lower()
        if any(word in text_lower for word in ["update", "change", "modify", "set", "edit"]):
            # This is an update request - notify for approval
            logger.info(f"Update request from {user} (DM): {text}")
            say(text=f"🔔 Update request received:\n\n_{text}_\n\n"
                     f"An admin will review this request shortly.")

            # Notify admins/approvers
            approvers = approval_system.get_approvers()
            admins = approval_system.get_admins()
            all_reviewers = list(set(approvers + admins))

            if all_reviewers:
                for reviewer in all_reviewers:
                    try:
                        client.chat_postMessage(
                            channel=reviewer,
                            text=f"📝 *Update Request*\n\n"
                                 f"From: <@{user}>\n"
                                 f"Request: _{text}_\n\n"
                                 f"Please review and process this update in Copper CRM."
                        )
                    except Exception as e:
                        logger.error(f"Error notifying reviewer {reviewer}: {e}")
            return

        # Process as an intelligent business query
        logger.info(f"Processing business intelligence query from {user} (DM): {text}")
        say(text="🔍 Gathering intelligence from Copper CRM...")

        # Use business intelligence to process the query
        result = business_intel.process_query(text)

        say(text=result)

    except Exception as e:
        logger.error(f"Error handling message: {str(e)}", exc_info=True)
        say(text=f"Sorry, I encountered an error: {str(e)}")


@app.event("file_shared")
def handle_file_upload(event: SlackEvent, say: SayFunction, client: WebClient) -> None:
    """
    Handle file uploads for CSV/Excel processing.

    Supports:
    - CRM lookup/enrichment
    - Opportunity import to pipeline
    - Contact reconciliation (LinkedIn data, etc.)

    Args:
        event: Slack event data
        say: Function to send messages
        client: Slack client
    """
    try:
        file_id: str = event.get("file_id", "")
        user_id: str = event.get("user_id", "")
        channel_id: str = event.get("channel_id", "")

        if not file_id:
            say(text="No file ID found in event.")
            return

        # Get file info
        file_info = client.files_info(file=file_id)
        file_data: JsonDict = file_info["file"]
        filename: str = file_data["name"]

        # Check if it's a supported file type
        supported_extensions = ('.csv', '.xlsx', '.xls')
        if not any(filename.lower().endswith(ext) for ext in supported_extensions):
            say(
                text=f"<@{user_id}> Please upload a CSV or Excel file. "
                     f"Received: {filename}"
            )
            return

        logger.info(f"Processing file upload from {user_id}: {filename}")
        say(text="Processing your file... :page_facing_up:")

        # Download file
        token: str = Config.SLACK_BOT_TOKEN or ""
        file_content = csv_handler.download_file(
            file_data["url_private"],
            token
        )

        # Parse file (CSV or Excel)
        rows = csv_handler.parse_file(file_content, filename)

        if not rows:
            say(text="The file appears to be empty.")
            return

        # Detect the type of operation based on columns
        mode = csv_handler.detect_import_mode(rows)
        is_admin = approval_system.is_admin(user_id)

        # Check for contact reconciliation indicators
        has_contact_data = _has_contact_data(rows)
        has_opportunity_data = mode == 'import'

        if has_opportunity_data:
            # Process as opportunity import
            _handle_opportunity_import(rows, user_id, channel_id, say, client, is_admin)
        elif has_contact_data:
            # Process as contact reconciliation
            _handle_contact_reconciliation(rows, user_id, channel_id, say, client, is_admin)
        else:
            # Default: CRM lookup/enrichment
            _handle_crm_lookup(rows, filename, channel_id, say, client)

    except Exception as e:
        logger.error(f"Error handling file upload: {str(e)}", exc_info=True)
        say(text=f"Sorry, I encountered an error processing your file: {str(e)}")


def _has_contact_data(rows: List[CsvRow]) -> bool:
    """Check if rows contain contact/person data for reconciliation."""
    if not rows:
        return False
    columns = set(k.lower() for k in rows[0].keys())
    contact_indicators = {'email', 'first name', 'last name', 'firstname', 'lastname',
                          'full name', 'name', 'company', 'position', 'title', 'linkedin'}
    return len(columns.intersection(contact_indicators)) >= 2


def _handle_crm_lookup(
    rows: List[CsvRow],
    filename: str,
    channel_id: str,
    say: SayFunction,
    client: WebClient
) -> None:
    """Handle CRM lookup/enrichment for file."""
    results = csv_handler.process_csv_queries(rows)
    enriched_csv = csv_handler.generate_enriched_csv(results['enriched_rows'])

    original_filename = filename.rsplit('.', 1)[0]
    enriched_filename = f"{original_filename}_enriched.csv"

    client.files_upload_v2(
        channel=channel_id,
        content=enriched_csv,
        filename=enriched_filename,
        title=f"CRM Lookup Results - {original_filename}",
        initial_comment=csv_handler.format_csv_results(results)
    )


def _handle_opportunity_import(
    rows: List[CsvRow],
    user_id: str,
    channel_id: str,
    say: SayFunction,
    client: WebClient,
    is_admin: bool
) -> None:
    """Handle opportunity import from file."""
    import_results = csv_handler.process_opportunity_import(rows)
    preview = csv_handler.format_import_preview(import_results)

    if is_admin:
        say(text=f"{preview}\n\nExecuting import (admin bypass)...")
        execution = csv_handler.execute_opportunity_import(import_results)
        say(text=csv_handler.format_import_results(execution))

        # Log to history
        from datetime import datetime
        approval_system.approval_history.append({
            'operation': 'bulk_import',
            'entity_type': 'opportunity',
            'created': len(execution['created']),
            'updated': len(execution['updated']),
            'failed': len(execution['failed']),
            'requester_id': user_id,
            'status': 'auto_approved',
            'approved_at': datetime.now().isoformat()
        })
        approval_system._save_state()
    else:
        request_id = approval_system.create_request(
            requester_id=user_id,
            operation='bulk_import',
            entity_type='opportunity',
            data={
                'to_create': len(import_results['to_create']),
                'to_update': len(import_results['to_update']),
                'import_data': import_results
            },
            entity_name=f"Opportunity Import ({len(rows)} rows)"
        )

        say(text=f"{preview}\n\n*Submitted for approval.*\nRequest ID: `{request_id}`")

        request = approval_system.get_request(request_id)
        for approver_id in approval_system.get_approvers():
            try:
                blocks = approval_system.create_approval_blocks(request_id, request)
                client.chat_postMessage(
                    channel=approver_id,
                    text=f"New bulk import request from <@{user_id}>",
                    blocks=blocks
                )
            except Exception as e:
                logger.error(f"Failed to notify approver: {e}")


def _handle_contact_reconciliation(
    rows: List[CsvRow],
    user_id: str,
    channel_id: str,
    say: SayFunction,
    client: WebClient,
    is_admin: bool
) -> None:
    """Handle contact reconciliation (LinkedIn exports, etc.)."""
    say(text="Cross-referencing contacts with CRM... :mag:")

    reconciliation: ReconciliationResult = {
        'matches': [],
        'not_found': [],
        'mismatches': [],
        'total': len(rows)
    }

    for row in rows:
        row_lower = {k.lower(): v for k, v in row.items()}

        # Extract person info
        email = row_lower.get('email', row_lower.get('e-mail', ''))
        name = row_lower.get('name', row_lower.get('full name', ''))
        if not name:
            first = row_lower.get('first name', row_lower.get('firstname', ''))
            last = row_lower.get('last name', row_lower.get('lastname', ''))
            name = f"{first} {last}".strip()

        company = row_lower.get('company', row_lower.get('company name', row_lower.get('organization', '')))

        if not (email or name):
            continue

        # Search in CRM
        criteria = {'emails': [email]} if email else {'name': name}
        crm_results = copper_client.search_people(criteria)

        if crm_results:
            crm_person = crm_results[0]
            crm_company = crm_person.get('company_name', '')

            mismatched_fields = []
            if company and crm_company and company.lower() != crm_company.lower():
                mismatched_fields.append({
                    'field': 'company',
                    'crm_value': crm_company,
                    'file_value': company
                })

            if mismatched_fields:
                reconciliation['mismatches'].append({
                    'name': name or email,
                    'crm_id': crm_person['id'],
                    'crm_data': crm_person,
                    'file_data': row,
                    'mismatched_fields': mismatched_fields
                })
            else:
                reconciliation['matches'].append({'name': name or email, 'crm_id': crm_person['id']})
        else:
            reconciliation['not_found'].append({
                'name': name or email, 'email': email, 'company': company, 'file_data': row
            })

    # Format results
    summary = [
        "*Contact Reconciliation Results*\n",
        f"📊 Total contacts: {reconciliation['total']}",
        f"✅ Matches: {len(reconciliation['matches'])}",
        f"⚠️ Mismatches: {len(reconciliation['mismatches'])}",
        f"❓ Not in CRM: {len(reconciliation['not_found'])}"
    ]

    if reconciliation['mismatches']:
        summary.append("\n*Mismatches Found:*")
        for item in reconciliation['mismatches'][:10]:
            for field in item['mismatched_fields']:
                summary.append(
                    f"  • *{item['name']}*: {field['field']} is \"{field['crm_value']}\" "
                    f"in CRM but \"{field['file_value']}\" in file"
                )

    say(text='\n'.join(summary))

    if reconciliation['mismatches']:
        request_id = approval_system.create_request(
            requester_id=user_id,
            operation='reconciliation',
            entity_type='person',
            data={'mismatches': reconciliation['mismatches'], 'not_found': reconciliation['not_found']},
            entity_name=f"Contact Reconciliation ({len(reconciliation['mismatches'])} updates)"
        )

        if is_admin:
            say(
                text=f"\n*Do you want to update these {len(reconciliation['mismatches'])} contacts?*",
                blocks=[
                    {"type": "section", "text": {"type": "mrkdwn",
                        "text": f"Update {len(reconciliation['mismatches'])} contacts with file data?"}},
                    {"type": "actions", "elements": [
                        {"type": "button", "text": {"type": "plain_text", "text": "Yes, Update"},
                         "style": "primary", "value": request_id, "action_id": f"approve_{request_id}"},
                        {"type": "button", "text": {"type": "plain_text", "text": "No, Cancel"},
                         "style": "danger", "value": request_id, "action_id": f"reject_{request_id}"}
                    ]}
                ]
            )
        else:
            say(text=f"\nSubmitted for approval. Request ID: `{request_id}`")
            for approver_id in approval_system.get_approvers():
                try:
                    blocks = approval_system.create_approval_blocks(request_id, approval_system.get_request(request_id))
                    client.chat_postMessage(channel=approver_id,
                        text=f"Contact reconciliation from <@{user_id}>", blocks=blocks)
                except Exception as e:
                    logger.error(f"Failed to notify approver: {e}")


@app.command("/copper")
def handle_copper_command(ack: AckFunction, command: SlackCommand, say: SayFunction) -> None:
    """
    Handle /copper slash command.

    Args:
        ack: Acknowledge function
        command: Command data
        say: Function to send messages
    """
    ack()

    try:
        text = command.get("text", "").strip()
        user = command.get("user_id")

        if not text:
            say(
                text=f"<@{user}> Please provide a query. Example: `/copper Find contacts at Acme Corp`"
            )
            return

        # Process the query
        logger.info(f"Processing /copper command from {user}: {text}")
        say(text="Searching Copper CRM... :mag:")

        # Parse query
        parsed = query_processor.parse_query(text)
        entity_type = parsed["entity_type"]
        criteria = parsed["search_criteria"]

        logger.info(f"Entity: {entity_type}, Criteria: {criteria}")

        # Query Copper
        results = []
        if entity_type == "people":
            results = copper_client.search_people(criteria)
        elif entity_type == "companies":
            results = copper_client.search_companies(criteria)
        elif entity_type == "opportunities":
            results = copper_client.search_opportunities(criteria)
        elif entity_type == "leads":
            results = copper_client.search_leads(criteria)
        elif entity_type == "tasks":
            results = copper_client.search_tasks(criteria)
        elif entity_type == "projects":
            results = copper_client.search_projects(criteria)

        # Format and send results
        formatted_results = query_processor.format_results(results, entity_type)

        response_text = f"*Query*: {text}\n*Found*: {len(results)} {entity_type}\n\n{formatted_results}"

        say(text=response_text)

    except Exception as e:
        logger.error(f"Error handling /copper command: {str(e)}", exc_info=True)
        say(text=f"Sorry, I encountered an error: {str(e)}")


@app.command("/copper-update")
def handle_update_command(
    ack: AckFunction,
    command: SlackCommand,
    say: SayFunction,
    client: WebClient
) -> None:
    """
    Handle /copper-update slash command to request CRM record updates.

    Args:
        ack: Acknowledge function
        command: Command data
        say: Function to send messages
        client: Slack client
    """
    ack()

    try:
        text: str = command.get("text", "").strip()
        user: str = command.get("user_id", "")

        if not text:
            say(
                text=f"<@{user}> Usage: `/copper-update [entity_type] [entity_id] field=value field2=value2`\n"
                     f"Example: `/copper-update person 12345 email=newemail@example.com phone=555-1234`"
            )
            return

        # Parse command: entity_type entity_id field=value field=value
        parts: List[str] = text.split()
        if len(parts) < 3:
            say(text="Invalid format. Need at least: entity_type entity_id field=value")
            return

        entity_type = parts[0].lower()
        try:
            entity_id = int(parts[1])
        except ValueError:
            say(text=f"Invalid entity ID: {parts[1]}")
            return

        # Parse updates
        updates = {}
        for part in parts[2:]:
            if '=' in part:
                key, value = part.split('=', 1)
                updates[key] = value

        if not updates:
            say(text="No updates specified. Use format: field=value")
            return

        # Get entity details for display
        entity_data = None
        if entity_type in ['person', 'people']:
            entity_data = copper_client.get_person(entity_id)
            entity_type = 'person'
        elif entity_type in ['company', 'companies']:
            entity_data = copper_client.get_company(entity_id)
            entity_type = 'company'
        elif entity_type in ['opportunity', 'opportunities']:
            entity_data = copper_client.get_opportunity(entity_id)
            entity_type = 'opportunity'

        if not entity_data:
            say(text=f"Could not find {entity_type} with ID {entity_id}")
            return

        entity_name = entity_data.get('name', 'Unknown')

        # Create update request
        request_id = approval_system.create_update_request(
            requester_id=user,
            entity_type=entity_type,
            entity_id=entity_id,
            updates=updates,
            entity_name=entity_name
        )

        request = approval_system.get_request(request_id)

        # Notify user
        say(text=f"Update request created! Request ID: `{request_id}`\n"
                 f"Waiting for approval from authorized users.")

        # Notify approvers
        approvers = approval_system.get_approvers()
        if approvers:
            for approver_id in approvers:
                try:
                    blocks = approval_system.create_approval_blocks(request_id, request)
                    client.chat_postMessage(
                        channel=approver_id,
                        text=f"New update request from <@{user}>",
                        blocks=blocks
                    )
                except Exception as e:
                    logger.error(f"Failed to notify approver {approver_id}: {e}")
        else:
            say(text="⚠️ Warning: No approvers configured! Use `/copper-add-approver` to add approvers.")

    except Exception as e:
        logger.error(f"Error handling /copper-update command: {str(e)}", exc_info=True)
        say(text=f"Sorry, I encountered an error: {str(e)}")


@app.command("/copper-add-approver")
def handle_add_approver_command(
    ack: AckFunction,
    command: SlackCommand,
    say: SayFunction
) -> None:
    """
    Handle /copper-add-approver command (admin only).

    Args:
        ack: Acknowledge function
        command: Command data
        say: Function to send messages
    """
    ack()

    try:
        text = command.get("text", "").strip()
        user = command.get("user_id")

        if not text:
            say(text="Usage: `/copper-add-approver @user` or `/copper-add-approver USER_ID`")
            return

        # Extract user ID from mention or direct ID
        approver_id = text.strip('<@>').split('|')[0]

        approval_system.add_approver(approver_id)
        say(text=f"✅ Added <@{approver_id}> as an approver.\n"
                 f"Current approvers: {len(approval_system.get_approvers())}")

    except Exception as e:
        logger.error(f"Error handling /copper-add-approver command: {str(e)}", exc_info=True)
        say(text=f"Sorry, I encountered an error: {str(e)}")


@app.command("/copper-add-admin")
def handle_add_admin_command(
    ack: AckFunction,
    command: SlackCommand,
    say: SayFunction
) -> None:
    """
    Handle /copper-add-admin command to add admin users who bypass approval.

    Args:
        ack: Acknowledge function
        command: Command data
        say: Function to send messages
    """
    ack()

    try:
        text = command.get("text", "").strip()
        user = command.get("user_id")

        if not text:
            say(
                text="*Add an admin (bypasses approval for their own actions)*\n\n"
                     "Usage: `/copper-add-admin @user`\n"
                     "Example: `/copper-add-admin @john`\n\n"
                     "Admins can create/update/delete records directly without approval."
            )
            return

        # Extract user ID from mention or direct ID
        admin_id = text.strip('<@>').split('|')[0]

        approval_system.add_admin(admin_id)
        say(text=f"Added <@{admin_id}> as an admin.\n"
                 f"They can now bypass approval for their own actions.\n"
                 f"Current admins: {len(approval_system.get_admins())}")

    except Exception as e:
        logger.error(f"Error handling /copper-add-admin command: {str(e)}", exc_info=True)
        say(text=f"Sorry, I encountered an error: {str(e)}")


@app.command("/copper-pending")
def handle_pending_command(
    ack: AckFunction,
    command: SlackCommand,
    say: SayFunction
) -> None:
    """
    Handle /copper-pending command to view pending approvals.

    Args:
        ack: Acknowledge function
        command: Command data
        say: Function to send messages
    """
    ack()

    try:
        user: str = command.get("user_id", "")

        if not approval_system.is_approver(user):
            say(text="You are not authorized to view pending approvals.")
            return

        pending = approval_system.get_pending_requests()

        if not pending:
            say(text="No pending approval requests.")
            return

        message = f"*Pending Approval Requests: {len(pending)}*\n\n"

        for req in pending[:10]:  # Show first 10
            message += approval_system.format_request_for_approval(req)
            message += f"Request ID: `{req['request_id']}`\n"
            message += "─" * 40 + "\n\n"

        if len(pending) > 10:
            message += f"\n_Showing first 10 of {len(pending)} requests_"

        say(text=message)

    except Exception as e:
        logger.error(f"Error handling /copper-pending command: {str(e)}", exc_info=True)
        say(text=f"Sorry, I encountered an error: {str(e)}")


@app.action(re.compile("^approve_"))
def handle_approve_button(
    ack: AckFunction,
    action: SlackAction,
    say: SayFunction,
    client: WebClient
) -> None:
    """
    Handle approve button clicks.

    Args:
        ack: Acknowledge function
        action: Action data
        say: Function to send messages
        client: Slack client
    """
    ack()

    try:
        request_id: str = action["value"]
        user_id: str = action["user"]["id"]

        if not approval_system.is_approver(user_id):
            say(text="You are not authorized to approve requests.")
            return

        request: Optional[JsonDict] = approval_system.get_request(request_id)
        if not request:
            say(text=f"Request {request_id} not found.")
            return

        # Approve the request
        if not approval_system.approve_request(request_id, user_id):
            say(text="Failed to approve request.")
            return

        # Execute the operation in Copper
        operation: str = request.get('operation', 'update')
        entity_type: str = request['entity_type']
        entity_id: Optional[int] = request.get('entity_id')
        data: JsonDict = request.get('data', request.get('updates', {}) or {})

        result = None
        success = False

        try:
            if operation == 'create':
                # Create new entity
                if entity_type in ['person', 'people']:
                    result = copper_client.create_person(data)
                elif entity_type in ['company', 'companies']:
                    result = copper_client.create_company(data)
                elif entity_type in ['opportunity', 'opportunities']:
                    result = copper_client.create_opportunity(data)
                elif entity_type in ['lead', 'leads']:
                    result = copper_client.create_lead(data)
                elif entity_type in ['task', 'tasks']:
                    result = copper_client.create_task(data)
                elif entity_type in ['project', 'projects']:
                    result = copper_client.create_project(data)

                if result:
                    success = True
                    new_id = result.get('id', 'Unknown')
                    new_name = result.get('name', request['entity_name'])
                    approval_system.complete_request(request_id)
                    say(text=f"✅ Approved and created {entity_type} '{new_name}' (ID: {new_id}) in Copper CRM!")

                    # Notify requester
                    requester_id = request['requester_id']
                    try:
                        client.chat_postMessage(
                            channel=requester_id,
                            text=f"Your create request for {entity_type} has been approved!\nNew record: {new_name} (ID: {new_id})"
                        )
                    except Exception as e:
                        logger.error(f"Failed to notify requester: {e}")

            elif operation == 'delete':
                # Delete entity (requires valid entity_id)
                if entity_id is None:
                    say(text="❌ Cannot delete: entity ID is missing.")
                    return
                if entity_type in ['person', 'people']:
                    success = copper_client.delete_person(entity_id)
                elif entity_type in ['company', 'companies']:
                    success = copper_client.delete_company(entity_id)
                elif entity_type in ['opportunity', 'opportunities']:
                    success = copper_client.delete_opportunity(entity_id)
                elif entity_type in ['lead', 'leads']:
                    success = copper_client.delete_lead(entity_id)
                elif entity_type in ['task', 'tasks']:
                    success = copper_client.delete_task(entity_id)
                elif entity_type in ['project', 'projects']:
                    success = copper_client.delete_project(entity_id)

                if success:
                    approval_system.complete_request(request_id)
                    say(text=f"✅ Approved and deleted {entity_type} '{request['entity_name']}' from Copper CRM!")

                    # Notify requester
                    requester_id = request['requester_id']
                    try:
                        client.chat_postMessage(
                            channel=requester_id,
                            text=f"Your delete request for {entity_type} '{request['entity_name']}' has been approved and completed!"
                        )
                    except Exception as e:
                        logger.error(f"Failed to notify requester: {e}")

            else:  # update
                # Update entity (requires valid entity_id)
                if entity_id is None:
                    say(text="❌ Cannot update: entity ID is missing.")
                    return
                if entity_type in ['person', 'people']:
                    result = copper_client.update_person(entity_id, data)
                elif entity_type in ['company', 'companies']:
                    result = copper_client.update_company(entity_id, data)
                elif entity_type in ['opportunity', 'opportunities']:
                    result = copper_client.update_opportunity(entity_id, data)
                elif entity_type in ['lead', 'leads']:
                    result = copper_client.update_lead(entity_id, data)
                elif entity_type in ['task', 'tasks']:
                    result = copper_client.update_task(entity_id, data)
                elif entity_type in ['project', 'projects']:
                    result = copper_client.update_project(entity_id, data)

                if result:
                    success = True
                    approval_system.complete_request(request_id)
                    say(text=f"✅ Approved and updated {entity_type} '{request['entity_name']}' in Copper CRM!")

                    # Notify requester
                    requester_id = request['requester_id']
                    try:
                        client.chat_postMessage(
                            channel=requester_id,
                            text=f"Your update request for {entity_type} '{request['entity_name']}' has been approved and completed!"
                        )
                    except Exception as e:
                        logger.error(f"Failed to notify requester: {e}")

            if not success and not result:
                say(text=f"❌ Approved but failed to {operation} in Copper CRM. Please check manually.")

        except Exception as e:
            logger.error(f"Error executing {operation}: {e}")
            say(text=f"❌ Error executing {operation}: {str(e)}")

    except Exception as e:
        logger.error(f"Error handling approve button: {str(e)}", exc_info=True)
        say(text=f"Sorry, I encountered an error: {str(e)}")


@app.command("/copper-create")
def handle_create_command(
    ack: AckFunction,
    command: SlackCommand,
    say: SayFunction,
    client: WebClient
) -> None:
    """
    Handle /copper-create slash command to request CRM record creation.

    Args:
        ack: Acknowledge function
        command: Command data
        say: Function to send messages
        client: Slack client
    """
    ack()

    try:
        text = command.get("text", "").strip()
        user = command.get("user_id")

        if not text:
            say(
                text=f"<@{user}> Usage: `/copper-create [entity_type] field=value field2=value2`\n"
                     f"Example: `/copper-create person name=\"John Smith\" email=john@example.com`\n"
                     f"Supported types: person, company, opportunity, lead, task, project"
            )
            return

        # Parse command: entity_type field=value field=value
        parts = text.split()
        if len(parts) < 2:
            say(text="Invalid format. Need at least: entity_type field=value")
            return

        entity_type = parts[0].lower()

        # Parse data
        data = {}
        for part in parts[1:]:
            if '=' in part:
                key, value = part.split('=', 1)
                # Remove quotes if present
                value = value.strip('"').strip("'")
                data[key] = value

        if not data:
            say(text="No data specified. Use format: field=value")
            return

        # Validate required fields
        if 'name' not in data and entity_type not in ['person', 'people']:
            say(text=f"Missing required field: 'name'")
            return

        entity_name = data.get('name', 'New Record')

        # Create request
        request_id = approval_system.create_request(
            requester_id=user,
            operation='create',
            entity_type=entity_type,
            data=data,
            entity_name=entity_name
        )

        request = approval_system.get_request(request_id)

        # Notify user
        say(text=f"Create request submitted! Request ID: `{request_id}`\n"
                 f"Waiting for approval from authorized users.")

        # Notify approvers
        approvers = approval_system.get_approvers()
        if approvers:
            for approver_id in approvers:
                try:
                    blocks = approval_system.create_approval_blocks(request_id, request)
                    client.chat_postMessage(
                        channel=approver_id,
                        text=f"New create request from <@{user}>",
                        blocks=blocks
                    )
                except Exception as e:
                    logger.error(f"Failed to notify approver {approver_id}: {e}")
        else:
            say(text="⚠️ Warning: No approvers configured! Use `/copper-add-approver` to add approvers.")

    except Exception as e:
        logger.error(f"Error handling /copper-create command: {str(e)}", exc_info=True)
        say(text=f"Sorry, I encountered an error: {str(e)}")


@app.command("/copper-delete")
def handle_delete_command(
    ack: AckFunction,
    command: SlackCommand,
    say: SayFunction,
    client: WebClient
) -> None:
    """
    Handle /copper-delete slash command to request CRM record deletion.

    Args:
        ack: Acknowledge function
        command: Command data
        say: Function to send messages
        client: Slack client
    """
    ack()

    try:
        text = command.get("text", "").strip()
        user = command.get("user_id")

        if not text:
            say(
                text=f"<@{user}> Usage: `/copper-delete [entity_type] [entity_id]`\n"
                     f"Example: `/copper-delete person 12345`\n"
                     f"Supported types: person, company, opportunity, lead, task, project"
            )
            return

        # Parse command: entity_type entity_id
        parts = text.split()
        if len(parts) < 2:
            say(text="Invalid format. Need: entity_type entity_id")
            return

        entity_type = parts[0].lower()
        try:
            entity_id = int(parts[1])
        except ValueError:
            say(text=f"Invalid entity ID: {parts[1]}")
            return

        # Get entity details for display
        entity_data = None
        if entity_type in ['person', 'people']:
            entity_data = copper_client.get_person(entity_id)
            entity_type = 'person'
        elif entity_type in ['company', 'companies']:
            entity_data = copper_client.get_company(entity_id)
            entity_type = 'company'
        elif entity_type in ['opportunity', 'opportunities']:
            entity_data = copper_client.get_opportunity(entity_id)
            entity_type = 'opportunity'
        elif entity_type in ['lead', 'leads']:
            entity_data = copper_client.get_lead(entity_id)
            entity_type = 'lead'
        elif entity_type in ['task', 'tasks']:
            entity_data = copper_client.get_task(entity_id)
            entity_type = 'task'
        elif entity_type in ['project', 'projects']:
            entity_data = copper_client.get_project(entity_id)
            entity_type = 'project'

        if not entity_data:
            say(text=f"Could not find {entity_type} with ID {entity_id}")
            return

        entity_name = entity_data.get('name', 'Unknown')

        # Create delete request
        request_id = approval_system.create_request(
            requester_id=user,
            operation='delete',
            entity_type=entity_type,
            entity_id=entity_id,
            entity_name=entity_name
        )

        request = approval_system.get_request(request_id)

        # Notify user
        say(text=f"⚠️ Delete request created! Request ID: `{request_id}`\n"
                 f"Entity: {entity_name}\n"
                 f"Waiting for approval from authorized users.")

        # Notify approvers
        approvers = approval_system.get_approvers()
        if approvers:
            for approver_id in approvers:
                try:
                    blocks = approval_system.create_approval_blocks(request_id, request)
                    client.chat_postMessage(
                        channel=approver_id,
                        text=f"⚠️ DELETE request from <@{user}>",
                        blocks=blocks
                    )
                except Exception as e:
                    logger.error(f"Failed to notify approver {approver_id}: {e}")
        else:
            say(text="⚠️ Warning: No approvers configured! Use `/copper-add-approver` to add approvers.")

    except Exception as e:
        logger.error(f"Error handling /copper-delete command: {str(e)}", exc_info=True)
        say(text=f"Sorry, I encountered an error: {str(e)}")


@app.action(re.compile("^reject_"))
def handle_reject_button(
    ack: AckFunction,
    action: SlackAction,
    say: SayFunction,
    client: WebClient
) -> None:
    """
    Handle reject button clicks.

    Args:
        ack: Acknowledge function
        action: Action data
        say: Function to send messages
        client: Slack client
    """
    ack()

    try:
        request_id = action["value"]
        user_id = action["user"]["id"]

        if not approval_system.is_approver(user_id):
            say(text="You are not authorized to reject requests.")
            return

        request = approval_system.get_request(request_id)
        if not request:
            say(text=f"Request {request_id} not found.")
            return

        # Reject the request
        if not approval_system.reject_request(request_id, user_id, "Rejected by approver"):
            say(text="Failed to reject request.")
            return

        say(text=f"❌ Rejected update request for {request['entity_type']} '{request['entity_name']}'")

        # Notify requester
        requester_id = request['requester_id']
        try:
            client.chat_postMessage(
                channel=requester_id,
                text=f"Your update request for {request['entity_type']} '{request['entity_name']}' has been rejected."
            )
        except Exception as e:
            logger.error(f"Failed to notify requester: {e}")

    except Exception as e:
        logger.error(f"Error handling reject button: {str(e)}", exc_info=True)
        say(text=f"Sorry, I encountered an error: {str(e)}")


# =============================================================================
# Task Creation (Natural Language)
# =============================================================================

def _execute_copper_operation(
    operation: str,
    entity_type: str,
    data: JsonDict,
    entity_id: Optional[int] = None,
    skip_validation: bool = False
) -> Optional[Union[JsonDict, bool, Dict[str, Any]]]:
    """
    Execute a Copper CRM operation directly with input validation.

    Args:
        operation: 'create', 'update', or 'delete'
        entity_type: Entity type (task, person, company, opportunity, etc.)
        data: Data for create/update operations
        entity_id: Entity ID for update/delete operations
        skip_validation: Skip validation (for internal trusted calls)

    Returns:
        Result from Copper API, validation error dict, or None on failure
    """
    try:
        # Validate and sanitize input for create/update operations
        if operation in ['create', 'update'] and not skip_validation:
            is_valid, sanitized_data, errors = validate_and_sanitize(
                entity_type, data, operation
            )
            if not is_valid:
                logger.warning(
                    f"Validation failed for {operation} {entity_type}: {errors}"
                )
                return {
                    "validation_error": True,
                    "errors": errors
                }
            data = sanitized_data

        # Validate entity_id for update/delete operations
        if operation in ['update', 'delete']:
            validated_id = validate_entity_id(entity_id)
            if validated_id is None:
                logger.warning(f"Invalid entity_id: {entity_id}")
                return None
            entity_id = validated_id

        if operation == 'create':
            if entity_type in ['task', 'tasks']:
                return copper_client.create_task(data)
            elif entity_type in ['person', 'people']:
                return copper_client.create_person(data)
            elif entity_type in ['company', 'companies']:
                return copper_client.create_company(data)
            elif entity_type in ['opportunity', 'opportunities']:
                return copper_client.create_opportunity(data)
            elif entity_type in ['lead', 'leads']:
                return copper_client.create_lead(data)
            elif entity_type in ['project', 'projects']:
                return copper_client.create_project(data)
        elif operation == 'update':
            if entity_id is None:
                return None
            if entity_type in ['task', 'tasks']:
                return copper_client.update_task(entity_id, data)
            elif entity_type in ['person', 'people']:
                return copper_client.update_person(entity_id, data)
            elif entity_type in ['company', 'companies']:
                return copper_client.update_company(entity_id, data)
            elif entity_type in ['opportunity', 'opportunities']:
                return copper_client.update_opportunity(entity_id, data)
            elif entity_type in ['lead', 'leads']:
                return copper_client.update_lead(entity_id, data)
            elif entity_type in ['project', 'projects']:
                return copper_client.update_project(entity_id, data)
        elif operation == 'delete':
            if entity_id is None:
                return None
            if entity_type in ['task', 'tasks']:
                return copper_client.delete_task(entity_id)
            elif entity_type in ['person', 'people']:
                return copper_client.delete_person(entity_id)
            elif entity_type in ['company', 'companies']:
                return copper_client.delete_company(entity_id)
            elif entity_type in ['opportunity', 'opportunities']:
                return copper_client.delete_opportunity(entity_id)
            elif entity_type in ['lead', 'leads']:
                return copper_client.delete_lead(entity_id)
            elif entity_type in ['project', 'projects']:
                return copper_client.delete_project(entity_id)
    except Exception as e:
        logger.error(f"Error executing {operation} on {entity_type}: {e}")
        return None

    return None


def _handle_task_request(
    text: str,
    user: str,
    say: SayFunction,
    client: WebClient
) -> None:
    """
    Handle a natural language task request.

    Args:
        text: The task request text
        user: Slack user ID of the requester
        say: Function to send messages
        client: Slack client
    """
    try:
        # Check if user is admin (can bypass approval)
        is_admin = approval_system.is_admin(user)

        if is_admin:
            say(text="Creating task... :pencil:")
        else:
            say(text="Submitting task for approval... :pencil:")

        # Parse the task
        parsed = task_processor.parse_task(text, user)
        logger.info(f"Parsed task: {parsed}")

        # Find related entity in Copper
        related_entity = None
        if parsed.get('related_entity_name'):
            related_entity = task_processor.find_related_entity(
                parsed['related_entity_name'],
                parsed.get('related_entity_type')
            )

        # Get Copper user ID for assignee
        assignee_slack_id = parsed.get('assignee_slack_id', user)
        assignee_copper_id = approval_system.get_copper_user_id(assignee_slack_id)

        # Fall back to default if no mapping
        if not assignee_copper_id and Config.DEFAULT_TASK_ASSIGNEE_ID:
            try:
                assignee_copper_id = int(Config.DEFAULT_TASK_ASSIGNEE_ID)
            except (ValueError, TypeError):
                pass

        # Build the Copper task payload
        task_data = task_processor.build_copper_task(
            parsed,
            assignee_copper_id=assignee_copper_id,
            related_entity=related_entity
        )

        # Format confirmation
        confirmation = task_processor.format_task_confirmation(parsed, related_entity)

        # If admin, execute directly
        if is_admin:
            result = _execute_copper_operation('create', 'task', task_data)
            if result:
                task_id = result.get('id', 'Unknown')
                say(text=f"Task created directly (admin bypass):\n\n{confirmation}\n\n"
                         f"Copper Task ID: `{task_id}`")

                # Log to history
                approval_system.approval_history.append({
                    'operation': 'create',
                    'entity_type': 'task',
                    'entity_name': parsed['task_description'],
                    'data': task_data,
                    'requester_id': user,
                    'status': 'auto_approved',
                    'approved_by': user,
                    'approved_at': __import__('datetime').datetime.now().isoformat(),
                    'copper_id': task_id
                })
                approval_system._save_state()
            else:
                say(text=f"Failed to create task in Copper. Please try again.")
            return

        # Non-admin: Create approval request
        request_id = approval_system.create_request(
            requester_id=user,
            operation='create',
            entity_type='task',
            data=task_data,
            entity_name=parsed['task_description']
        )

        say(text=f"Task request submitted for approval:\n\n{confirmation}\n\n"
                 f"Request ID: `{request_id}`")

        # Notify approvers
        request = approval_system.get_request(request_id)
        approvers = approval_system.get_approvers()
        if approvers:
            for approver_id in approvers:
                try:
                    blocks = approval_system.create_approval_blocks(request_id, request)
                    client.chat_postMessage(
                        channel=approver_id,
                        text=f"New task request from <@{user}>",
                        blocks=blocks
                    )
                except Exception as e:
                    logger.error(f"Failed to notify approver {approver_id}: {e}")
        else:
            say(text="Warning: No approvers configured. Use `/copper-add-approver` to add approvers.")

    except Exception as e:
        logger.error(f"Error handling task request: {str(e)}", exc_info=True)
        say(text=f"Sorry, I couldn't create that task: {str(e)}")


@app.command("/copper-task")
def handle_task_command(
    ack: AckFunction,
    command: SlackCommand,
    say: SayFunction,
    client: WebClient
) -> None:
    """
    Handle /copper-task slash command for natural language task creation.

    Usage: /copper-task follow up with CNN next Monday
    """
    ack()

    try:
        text: str = command.get("text", "").strip()
        user: str = command.get("user_id", "")

        if not text:
            say(
                text="*Create a task with natural language!*\n\n"
                     "*Examples:*\n"
                     "• `/copper-task follow up with CNN next Monday`\n"
                     "• `/copper-task call John at Acme Corp tomorrow at 2pm`\n"
                     "• `/copper-task send proposal to Netflix by Friday`\n"
                     "• `/copper-task urgent: review contract for Disney`\n\n"
                     "*Supported date formats:*\n"
                     "• today, tomorrow, next week\n"
                     "• Monday, Tuesday, etc. (this week)\n"
                     "• next Monday, next Friday\n"
                     "• in 3 days, in 2 weeks\n"
                     "• by Jan 15, on 1/20"
            )
            return

        _handle_task_request(text, user, say, client)

    except Exception as e:
        logger.error(f"Error handling /copper-task command: {str(e)}", exc_info=True)
        say(text=f"Sorry, I encountered an error: {str(e)}")


@app.command("/copper-map-user")
def handle_map_user_command(
    ack: AckFunction,
    command: SlackCommand,
    say: SayFunction
) -> None:
    """
    Handle /copper-map-user command to map Slack users to Copper users.

    Usage: /copper-map-user @slackuser 12345
    """
    ack()

    try:
        text = command.get("text", "").strip()
        user = command.get("user_id")

        if not text:
            say(
                text="*Map a Slack user to their Copper user ID*\n\n"
                     "Usage: `/copper-map-user @user COPPER_USER_ID`\n"
                     "Example: `/copper-map-user @john 12345`\n\n"
                     "To find your Copper user ID, go to Settings > Users in Copper."
            )
            return

        parts = text.split()
        if len(parts) < 2:
            say(text="Invalid format. Use: `/copper-map-user @user COPPER_USER_ID`")
            return

        # Extract Slack user ID from mention
        slack_user_id = parts[0].strip('<@>').split('|')[0]

        try:
            copper_user_id = int(parts[1])
        except ValueError:
            say(text=f"Invalid Copper user ID: {parts[1]}. Must be a number.")
            return

        # Save the mapping
        approval_system.set_user_mapping(slack_user_id, copper_user_id)

        say(text=f"Mapped <@{slack_user_id}> to Copper user ID `{copper_user_id}`")

    except Exception as e:
        logger.error(f"Error handling /copper-map-user command: {str(e)}", exc_info=True)
        say(text=f"Sorry, I encountered an error: {str(e)}")


# =============================================================================
# Health Check Endpoint
# =============================================================================

class HealthHandler(BaseHTTPRequestHandler):
    """HTTP handler for health check endpoint."""

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default HTTP logging to avoid noise."""
        pass

    def do_GET(self) -> None:
        """Handle GET requests."""
        if self.path == '/health':
            self._handle_health()
        elif self.path == '/metrics':
            self._handle_metrics()
        elif self.path == '/':
            self._handle_root()
        else:
            self.send_error(404, 'Not Found')

    def _handle_health(self) -> None:
        """Return health status with component checks."""
        uptime = datetime.now() - _start_time
        uptime_seconds = int(uptime.total_seconds())

        # Check component availability
        components = {
            'slack_app': app is not None,
            'copper_client': copper_client is not None,
            'approval_system': approval_system is not None,
            'query_processor': query_processor is not None,
            'csv_handler': csv_handler is not None,
            'task_processor': task_processor is not None,
        }

        # Check approval system state
        try:
            pending_count = len(approval_system.get_pending_requests())
            approver_count = len(approval_system.get_approvers())
            admin_count = len(approval_system.get_admins())
            components['approval_state'] = True
        except Exception:
            pending_count = -1
            approver_count = -1
            admin_count = -1
            components['approval_state'] = False

        all_healthy = all(components.values())

        health = {
            'status': 'healthy' if all_healthy else 'degraded',
            'uptime_seconds': uptime_seconds,
            'uptime_human': str(uptime).split('.')[0],
            'started_at': _start_time.isoformat(),
            'components': components,
            'stats': {
                'pending_approvals': pending_count,
                'approvers': approver_count,
                'admins': admin_count,
            }
        }

        self.send_response(200 if all_healthy else 503)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(health, indent=2).encode())

    def _handle_metrics(self) -> None:
        """Return Prometheus metrics."""
        try:
            # Update gauges with current values
            uptime = datetime.now() - _start_time
            update_uptime(_start_time.timestamp())

            # Update approval gauges
            try:
                pending_count = len(approval_system.get_pending_requests())
                approver_count = len(approval_system.get_approvers())
                update_approval_gauges(pending_count, approver_count)
            except Exception:
                pass  # Silently ignore if approval system is unavailable

            # Generate metrics
            metrics_output = get_metrics()

            self.send_response(200)
            self.send_header('Content-Type', get_metrics_content_type())
            self.end_headers()
            self.wfile.write(metrics_output)
        except Exception as e:
            logger.error(f"Error generating metrics: {e}")
            self.send_error(500, 'Error generating metrics')

    def _handle_root(self) -> None:
        """Simple root response."""
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'Copper CRM Slack Bot - OK')


# Global references for graceful shutdown
_health_server: Optional[HTTPServer] = None
_socket_handler: Optional[SocketModeHandler] = None
_shutdown_event: threading.Event = threading.Event()


def start_health_server(port: int, server_ready: threading.Event) -> None:
    """Start the health check HTTP server in a background thread."""
    global _health_server
    _health_server = HTTPServer(('0.0.0.0', port), HealthHandler)
    logger.info(f"Health server running on port {port}")
    server_ready.set()
    _health_server.serve_forever()


def shutdown_handler(signum: int, frame: Optional[FrameType]) -> None:
    """Handle graceful shutdown on SIGTERM/SIGINT."""
    sig_name = signal.Signals(signum).name
    logger.info(f"Received {sig_name}, initiating graceful shutdown...")

    # Prevent multiple shutdown attempts
    if _shutdown_event.is_set():
        logger.warning("Shutdown already in progress, forcing exit...")
        sys.exit(1)
    _shutdown_event.set()

    try:
        # Save approval system state
        logger.info("Saving approval system state...")
        approval_system._save_state()
        logger.info("Approval state saved successfully")

        # Stop the Socket Mode handler
        if _socket_handler is not None:
            logger.info("Stopping Slack Socket Mode handler...")
            _socket_handler.close()
            logger.info("Socket Mode handler stopped")

        # Stop the health server
        if _health_server is not None:
            logger.info("Stopping health server...")
            _health_server.shutdown()
            logger.info("Health server stopped")

        logger.info("Graceful shutdown complete")
        sys.exit(0)

    except Exception as e:
        logger.error(f"Error during shutdown: {e}", exc_info=True)
        sys.exit(1)


def main() -> None:
    """Start the Slack bot."""
    global _socket_handler

    logger.info("Starting Copper CRM Slack Bot...")

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)
    logger.info("Registered signal handlers for graceful shutdown")

    try:
        # Start health check server in background thread
        health_port = int(os.getenv('PORT', 3000))
        server_ready = threading.Event()
        health_thread = threading.Thread(
            target=start_health_server,
            args=(health_port, server_ready),
            daemon=True
        )
        health_thread.start()
        server_ready.wait(timeout=5)  # Wait for server to be ready
        logger.info(f"Health endpoint available at http://localhost:{health_port}/health")

        # Start the app using Socket Mode
        _socket_handler = SocketModeHandler(app, Config.SLACK_APP_TOKEN)
        logger.info("Bot is running in Socket Mode!")
        logger.info("Press Ctrl+C to stop gracefully")
        _socket_handler.start()

    except Exception as e:
        logger.error(f"Failed to start bot: {str(e)}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
