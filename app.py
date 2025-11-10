"""Copper CRM Slack Bot - Main Application."""

import os
import re
import logging
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from config import Config
from copper_client import CopperClient
from query_processor import QueryProcessor
from csv_handler import CSVHandler
from approval_system import ApprovalSystem

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


# Add middleware to log all incoming events
@app.middleware
def log_request(logger, body, next):
    """Log all incoming requests for debugging."""
    event_type = body.get("event", {}).get("type", "unknown")
    logger.info(f"=== Received event: {event_type} ===")
    logger.info(f"Full body: {body}")
    return next()


@app.event("app_mention")
def handle_mention(event, say, client):
    """
    Handle when the bot is mentioned in a channel.

    Args:
        event: Slack event data
        say: Function to send messages
        client: Slack client
    """
    logger.info(f">>> APP_MENTION event handler triggered")
    try:
        user = event.get("user")
        text = event.get("text", "")

        # Remove bot mention from text
        bot_user_id = client.auth_test()["user_id"]
        text = text.replace(f"<@{bot_user_id}>", "").strip()

        if not text:
            say(
                text=f"Hi <@{user}>! Ask me anything about your Copper CRM data. "
                     "For example:\n"
                     "• 'Find contacts at Acme Corp'\n"
                     "• 'Show me opportunities over $50k'\n"
                     "• 'Search for companies in San Francisco'\n"
                     "• Or upload a CSV file with search criteria!"
            )
            return

        # Process the query
        logger.info(f"Processing query from {user}: {text}")
        say(text=f"Searching Copper CRM... :mag:")

        # Parse query
        parsed = query_processor.parse_query(text)
        entity_type = parsed["entity_type"]
        criteria = parsed["search_criteria"]

        logger.info(f"Entity: {entity_type}, Criteria: {criteria}")

        # Check if query is too vague (no specific criteria)
        if not criteria or len(criteria) == 0:
            say(
                text=f"I'm not sure exactly what you're looking for. Could you be more specific?\n\n"
                     f"For example:\n"
                     f"• 'Find contacts at Venatus'\n"
                     f"• 'Show me people at NY Times'\n"
                     f"• 'Search for john@example.com'\n"
                     f"• 'Companies in San Francisco'\n\n"
                     f"Or try including a company name, person's name, email, location, or other specific details."
            )
            return

        # Query Copper
        results = []
        if entity_type == "activities":
            # Search for activities/communications
            if 'company_name' in criteria:
                # Use fuzzy search to find matching companies
                companies = copper_client.find_companies_fuzzy(criteria['company_name'])

                if not companies:
                    say(text=f"❌ No companies found matching '{criteria['company_name']}'.\n\n"
                             f"Try:\n"
                             f"• Using a different spelling\n"
                             f"• Using the full company name\n"
                             f"• Checking if the company exists in your CRM")
                    return

                # If multiple matches, show "Did you mean?" suggestions
                if len(companies) > 1:
                    company_list = "\n".join([f"• {c.get('name')}" for c in companies[:5]])
                    say(text=f"🤔 I found {len(companies)} companies matching '{criteria['company_name']}':\n\n{company_list}\n\n"
                             f"Please be more specific, like:\n"
                             f"• 'latest with {companies[0].get('name')}'\n"
                             f"• 'comms from {companies[1].get('name') if len(companies) > 1 else companies[0].get('name')}'")
                    return

                # Single match - proceed with activities search
                logger.info(f"✅ Using company: {companies[0].get('name')}")
                results = copper_client.search_activities_by_company(criteria['company_name'])
            else:
                say(text="To search for activities, please specify a company name.\nFor example: 'latest comms from Venatus' or 'emails with Guardian'")
                return
        elif entity_type == "people":
            # If searching for people by company name, find the company first
            if 'name' in criteria and not any(k in criteria for k in ['emails', 'phone_numbers']):
                logger.info(f"Searching for company '{criteria['name']}' first...")
                # Use fuzzy search for companies
                companies = copper_client.find_companies_fuzzy(criteria['name'])

                if not companies:
                    say(text=f"❌ No companies found matching '{criteria['name']}'.\n\nTry using the full company name or check if it exists in your CRM.")
                    return

                # If multiple matches, show "Did you mean?" suggestions
                if len(companies) > 1:
                    company_list = "\n".join([f"• {c.get('name')}" for c in companies[:5]])
                    say(text=f"🤔 I found {len(companies)} companies matching '{criteria['name']}':\n\n{company_list}\n\n"
                             f"Please be more specific, like:\n"
                             f"• 'contacts at {companies[0].get('name')}'\n"
                             f"• 'people from {companies[1].get('name') if len(companies) > 1 else companies[0].get('name')}'")
                    return

                if companies:
                    # Get people from all matching companies
                    logger.info(f"✅ Using company: {companies[0].get('name')}")
                    logger.info(f"Searching for people...")
                    for company in companies:
                        company_id = company.get('id')
                        if company_id:
                            people = copper_client.search_people({'company_ids': [company_id]})
                            results.extend(people)
                    logger.info(f"Found {len(results)} total people across all matching companies")
                else:
                    logger.info(f"No companies found matching '{criteria['name']}'")
            else:
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
        logger.info("=" * 60)
        logger.info("📤 STEP 3: FORMATTING AND SENDING RESPONSE TO USER")
        logger.info(f"Found {len(results)} {entity_type}")

        formatted_results = query_processor.format_results(results, entity_type)

        response_text = f"*Query*: {text}\n*Found*: {len(results)} {entity_type}\n\n{formatted_results}"

        logger.info(f"Response preview (first 200 chars): {response_text[:200]}...")
        say(text=response_text)
        logger.info("✅ Response sent to user successfully!")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Error handling mention: {str(e)}", exc_info=True)
        say(text=f"Sorry, I encountered an error: {str(e)}")


@app.event("message")
def handle_message(event, say, client):
    """
    Handle direct messages to the bot.

    Args:
        event: Slack event data
        say: Function to send messages
        client: Slack client
    """
    logger.info(f">>> MESSAGE event handler triggered")
    logger.info(f"Event details: channel_type={event.get('channel_type')}, subtype={event.get('subtype')}, user={event.get('user')}")

    # Only respond to DMs (channel_type = 'im')
    if event.get("channel_type") != "im":
        logger.info(f"Ignoring message - not a DM (channel_type={event.get('channel_type')})")
        return

    # Ignore bot messages
    if event.get("subtype") == "bot_message":
        logger.info(f"Ignoring message - bot message")
        return

    try:
        user = event.get("user")
        text = event.get("text", "").strip()

        if not text:
            return

        # Check for help commands
        if text.lower() in ["help", "?", "commands"]:
            say(
                text="*Copper CRM Bot - Help*\n\n"
                     "*Natural Language Queries:*\n"
                     "Just ask me in plain English! Examples:\n"
                     "• 'Find contacts named John Smith'\n"
                     "• 'Show me companies in New York'\n"
                     "• 'List opportunities over $100,000'\n"
                     "• 'Search for leads from Acme Corp'\n\n"
                     "*CSV Upload:*\n"
                     "Upload a CSV file with search criteria. Supported columns:\n"
                     "• type/entity_type: people, companies, opportunities, leads\n"
                     "• name: Person or company name\n"
                     "• email: Email address\n"
                     "• phone: Phone number\n"
                     "• city, state, country: Location info\n"
                     "• tags: Comma-separated tags\n"
                     "• min_value: Minimum opportunity value\n\n"
                     "Need more help? Contact your admin!"
            )
            return

        # Process the query
        logger.info(f"Processing DM query from {user}: {text}")
        say(text="Searching Copper CRM... :mag:")

        # Parse query
        parsed = query_processor.parse_query(text)
        entity_type = parsed["entity_type"]
        criteria = parsed["search_criteria"]

        logger.info(f"Entity: {entity_type}, Criteria: {criteria}")

        # Check if query is too vague (no specific criteria)
        if not criteria or len(criteria) == 0:
            say(
                text=f"I'm not sure exactly what you're looking for. Could you be more specific?\n\n"
                     f"For example:\n"
                     f"• 'Find contacts at Venatus'\n"
                     f"• 'Show me people at NY Times'\n"
                     f"• 'Search for john@example.com'\n"
                     f"• 'Companies in San Francisco'\n\n"
                     f"Or try including a company name, person's name, email, location, or other specific details."
            )
            return

        # Query Copper
        results = []
        if entity_type == "activities":
            # Search for activities/communications
            if 'company_name' in criteria:
                # Use fuzzy search to find matching companies
                companies = copper_client.find_companies_fuzzy(criteria['company_name'])

                if not companies:
                    say(text=f"❌ No companies found matching '{criteria['company_name']}'.\n\n"
                             f"Try:\n"
                             f"• Using a different spelling\n"
                             f"• Using the full company name\n"
                             f"• Checking if the company exists in your CRM")
                    return

                # If multiple matches, show "Did you mean?" suggestions
                if len(companies) > 1:
                    company_list = "\n".join([f"• {c.get('name')}" for c in companies[:5]])
                    say(text=f"🤔 I found {len(companies)} companies matching '{criteria['company_name']}':\n\n{company_list}\n\n"
                             f"Please be more specific, like:\n"
                             f"• 'latest with {companies[0].get('name')}'\n"
                             f"• 'comms from {companies[1].get('name') if len(companies) > 1 else companies[0].get('name')}'")
                    return

                # Single match - proceed with activities search
                logger.info(f"✅ Using company: {companies[0].get('name')}")
                results = copper_client.search_activities_by_company(criteria['company_name'])
            else:
                say(text="To search for activities, please specify a company name.\nFor example: 'latest comms from Venatus' or 'emails with Guardian'")
                return
        elif entity_type == "people":
            # If searching for people by company name, find the company first
            if 'name' in criteria and not any(k in criteria for k in ['emails', 'phone_numbers']):
                logger.info(f"Searching for company '{criteria['name']}' first...")
                # Use fuzzy search for companies
                companies = copper_client.find_companies_fuzzy(criteria['name'])

                if not companies:
                    say(text=f"❌ No companies found matching '{criteria['name']}'.\n\nTry using the full company name or check if it exists in your CRM.")
                    return

                # If multiple matches, show "Did you mean?" suggestions
                if len(companies) > 1:
                    company_list = "\n".join([f"• {c.get('name')}" for c in companies[:5]])
                    say(text=f"🤔 I found {len(companies)} companies matching '{criteria['name']}':\n\n{company_list}\n\n"
                             f"Please be more specific, like:\n"
                             f"• 'contacts at {companies[0].get('name')}'\n"
                             f"• 'people from {companies[1].get('name') if len(companies) > 1 else companies[0].get('name')}'")
                    return

                if companies:
                    # Get people from all matching companies
                    logger.info(f"✅ Using company: {companies[0].get('name')}")
                    logger.info(f"Searching for people...")
                    for company in companies:
                        company_id = company.get('id')
                        if company_id:
                            people = copper_client.search_people({'company_ids': [company_id]})
                            results.extend(people)
                    logger.info(f"Found {len(results)} total people across all matching companies")
                else:
                    logger.info(f"No companies found matching '{criteria['name']}'")
            else:
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
        logger.info("=" * 60)
        logger.info("📤 STEP 3: FORMATTING AND SENDING RESPONSE TO USER")
        logger.info(f"Found {len(results)} {entity_type}")

        formatted_results = query_processor.format_results(results, entity_type)

        response_text = f"*Query*: {text}\n*Found*: {len(results)} {entity_type}\n\n{formatted_results}"

        logger.info(f"Response preview (first 200 chars): {response_text[:200]}...")
        say(text=response_text)
        logger.info("✅ Response sent to user successfully!")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Error handling message: {str(e)}", exc_info=True)
        say(text=f"Sorry, I encountered an error: {str(e)}")


@app.event("file_shared")
def handle_file_upload(event, say, client):
    """
    Handle CSV file uploads.

    Args:
        event: Slack event data
        say: Function to send messages
        client: Slack client
    """
    logger.info(f">>> FILE_SHARED event handler triggered")
    try:
        file_id = event.get("file_id")
        user_id = event.get("user_id")

        # Get file info
        file_info = client.files_info(file=file_id)
        file_data = file_info["file"]

        # Check if it's a CSV file
        if not file_data["name"].endswith(".csv"):
            say(
                text=f"<@{user_id}> Please upload a CSV file. "
                     f"Received: {file_data['name']}"
            )
            return

        logger.info(f"Processing CSV upload from {user_id}: {file_data['name']}")
        say(text="Processing your CSV file... :page_facing_up:")

        # Download file
        file_content = csv_handler.download_file(
            file_data["url_private"],
            Config.SLACK_BOT_TOKEN
        )

        # Parse CSV
        rows = csv_handler.parse_csv(file_content)

        if not rows:
            say(text="The CSV file appears to be empty.")
            return

        # Process queries and enrich with CRM data
        results = csv_handler.process_csv_queries(rows)

        # Generate enriched CSV
        enriched_csv = csv_handler.generate_enriched_csv(results['enriched_rows'])

        # Upload enriched CSV back to Slack
        channel_id = event.get("channel_id")
        original_filename = file_data['name'].replace('.csv', '')
        enriched_filename = f"{original_filename}_enriched.csv"

        client.files_upload_v2(
            channel=channel_id,
            content=enriched_csv,
            filename=enriched_filename,
            title=f"CRM Lookup Results - {original_filename}",
            initial_comment=csv_handler.format_csv_results(results)
        )

    except Exception as e:
        logger.error(f"Error handling file upload: {str(e)}", exc_info=True)
        say(text=f"Sorry, I encountered an error processing your file: {str(e)}")


@app.command("/copper")
def handle_copper_command(ack, command, say):
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

        # Check if query is too vague (no specific criteria)
        if not criteria or len(criteria) == 0:
            say(
                text=f"I'm not sure exactly what you're looking for. Could you be more specific?\n\n"
                     f"For example:\n"
                     f"• 'Find contacts at Venatus'\n"
                     f"• 'Show me people at NY Times'\n"
                     f"• 'Search for john@example.com'\n"
                     f"• 'Companies in San Francisco'\n\n"
                     f"Or try including a company name, person's name, email, location, or other specific details."
            )
            return

        # Query Copper
        results = []
        if entity_type == "activities":
            # Search for activities/communications
            if 'company_name' in criteria:
                # Use fuzzy search to find matching companies
                companies = copper_client.find_companies_fuzzy(criteria['company_name'])

                if not companies:
                    say(text=f"❌ No companies found matching '{criteria['company_name']}'.\n\n"
                             f"Try:\n"
                             f"• Using a different spelling\n"
                             f"• Using the full company name\n"
                             f"• Checking if the company exists in your CRM")
                    return

                # If multiple matches, show "Did you mean?" suggestions
                if len(companies) > 1:
                    company_list = "\n".join([f"• {c.get('name')}" for c in companies[:5]])
                    say(text=f"🤔 I found {len(companies)} companies matching '{criteria['company_name']}':\n\n{company_list}\n\n"
                             f"Please be more specific, like:\n"
                             f"• 'latest with {companies[0].get('name')}'\n"
                             f"• 'comms from {companies[1].get('name') if len(companies) > 1 else companies[0].get('name')}'")
                    return

                # Single match - proceed with activities search
                logger.info(f"✅ Using company: {companies[0].get('name')}")
                results = copper_client.search_activities_by_company(criteria['company_name'])
            else:
                say(text="To search for activities, please specify a company name.\nFor example: 'latest comms from Venatus' or 'emails with Guardian'")
                return
        elif entity_type == "people":
            # If searching for people by company name, find the company first
            if 'name' in criteria and not any(k in criteria for k in ['emails', 'phone_numbers']):
                logger.info(f"Searching for company '{criteria['name']}' first...")
                # Use fuzzy search for companies
                companies = copper_client.find_companies_fuzzy(criteria['name'])

                if not companies:
                    say(text=f"❌ No companies found matching '{criteria['name']}'.\n\nTry using the full company name or check if it exists in your CRM.")
                    return

                # If multiple matches, show "Did you mean?" suggestions
                if len(companies) > 1:
                    company_list = "\n".join([f"• {c.get('name')}" for c in companies[:5]])
                    say(text=f"🤔 I found {len(companies)} companies matching '{criteria['name']}':\n\n{company_list}\n\n"
                             f"Please be more specific, like:\n"
                             f"• 'contacts at {companies[0].get('name')}'\n"
                             f"• 'people from {companies[1].get('name') if len(companies) > 1 else companies[0].get('name')}'")
                    return

                if companies:
                    # Get people from all matching companies
                    logger.info(f"✅ Using company: {companies[0].get('name')}")
                    logger.info(f"Searching for people...")
                    for company in companies:
                        company_id = company.get('id')
                        if company_id:
                            people = copper_client.search_people({'company_ids': [company_id]})
                            results.extend(people)
                    logger.info(f"Found {len(results)} total people across all matching companies")
                else:
                    logger.info(f"No companies found matching '{criteria['name']}'")
            else:
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
        logger.info("=" * 60)
        logger.info("📤 STEP 3: FORMATTING AND SENDING RESPONSE TO USER")
        logger.info(f"Found {len(results)} {entity_type}")

        formatted_results = query_processor.format_results(results, entity_type)

        response_text = f"*Query*: {text}\n*Found*: {len(results)} {entity_type}\n\n{formatted_results}"

        logger.info(f"Response preview (first 200 chars): {response_text[:200]}...")
        say(text=response_text)
        logger.info("✅ Response sent to user successfully!")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Error handling /copper command: {str(e)}", exc_info=True)
        say(text=f"Sorry, I encountered an error: {str(e)}")


@app.command("/copper-update")
def handle_update_command(ack, command, say, client):
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
        text = command.get("text", "").strip()
        user = command.get("user_id")

        if not text:
            say(
                text=f"<@{user}> Usage: `/copper-update [entity_type] [entity_id] field=value field2=value2`\n"
                     f"Example: `/copper-update person 12345 email=newemail@example.com phone=555-1234`"
            )
            return

        # Parse command: entity_type entity_id field=value field=value
        parts = text.split()
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
def handle_add_approver_command(ack, command, say):
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


@app.command("/copper-pending")
def handle_pending_command(ack, command, say):
    """
    Handle /copper-pending command to view pending approvals.

    Args:
        ack: Acknowledge function
        command: Command data
        say: Function to send messages
    """
    ack()

    try:
        user = command.get("user_id")

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
def handle_approve_button(ack, action, say, client):
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
        request_id = action["value"]
        user_id = action["user"]["id"]

        if not approval_system.is_approver(user_id):
            say(text="You are not authorized to approve requests.")
            return

        request = approval_system.get_request(request_id)
        if not request:
            say(text=f"Request {request_id} not found.")
            return

        # Approve the request
        if not approval_system.approve_request(request_id, user_id):
            say(text="Failed to approve request.")
            return

        # Execute the operation in Copper
        operation = request.get('operation', 'update')
        entity_type = request['entity_type']
        entity_id = request.get('entity_id')
        data = request.get('data', request.get('updates', {}))

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
                # Delete entity
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
                # Update entity
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
def handle_create_command(ack, command, say, client):
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
def handle_delete_command(ack, command, say, client):
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
def handle_reject_button(ack, action, say, client):
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


def main():
    """Start the Slack bot."""
    logger.info("=" * 60)
    logger.info("Starting Copper CRM Slack Bot...")
    logger.info(f"Bot Token configured: {Config.SLACK_BOT_TOKEN[:20]}...")
    logger.info(f"App Token configured: {Config.SLACK_APP_TOKEN[:20]}...")
    logger.info(f"Copper API Key configured: {Config.COPPER_API_KEY[:10] if Config.COPPER_API_KEY else 'NOT SET'}...")
    logger.info(f"Copper Email configured: {Config.COPPER_USER_EMAIL if Config.COPPER_USER_EMAIL else 'NOT SET'}")
    logger.info(f"Anthropic API Key configured: {Config.ANTHROPIC_API_KEY[:10] if Config.ANTHROPIC_API_KEY else 'NOT SET'}...")
    logger.info(f"Log Level: {Config.LOG_LEVEL}")
    logger.info("=" * 60)

    try:
        # Start the app using Socket Mode
        handler = SocketModeHandler(app, Config.SLACK_APP_TOKEN)
        logger.info("✅ Bot is running in Socket Mode!")
        logger.info("Waiting for events... Try sending a message to the bot in Slack")
        logger.info("=" * 60)
        handler.start()

    except Exception as e:
        logger.error(f"Failed to start bot: {str(e)}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
