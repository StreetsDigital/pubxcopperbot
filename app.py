"""Copper CRM Slack Bot - Simplified Version.

Core functionality:
- Natural language business intelligence queries
- CSV file processing and enrichment
- Direct integration with Copper CRM API
"""

import json
import logging
import os
import sys

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk import WebClient

from business_intelligence import BusinessIntelligence
from config import Config
from copper_client import CopperClient
from csv_handler import CSVHandler

# Configure logging
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Type aliases
SlackEvent = dict
SlackCommand = dict
AckFunction = callable
SayFunction = callable
SlackAction = dict

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
business_intel = BusinessIntelligence(copper_client)
csv_handler = CSVHandler(copper_client)

# State tracking for confirmations
# Key: (user_id, channel_id), Value: {confirmation_data, analysis, timestamp}
pending_confirmations = {}


def handle_confirmation_response(text: str, user: str, channel: str, say: SayFunction) -> None:
    """Handle user's confirmation response to ambiguous matches.

    Args:
        text: User's response text
        user: User ID
        channel: Channel ID
        say: Function to send messages
    """
    confirmation_key = (user, channel)

    try:
        # Get pending confirmation
        pending = pending_confirmations.get(confirmation_key)
        if not pending:
            say(text="❌ No pending confirmation found. Please start a new query.")
            return

        confirmation_data = pending["confirmation_data"]
        analysis = pending["analysis"]
        matches = confirmation_data.get("matches", [])

        # Check for cancel
        if text.lower() in ["cancel", "abort", "quit", "exit"]:
            del pending_confirmations[confirmation_key]
            say(text="✅ Cancelled. Feel free to start a new query!")
            return

        # Try to parse selection number
        try:
            selection = int(text.strip())
            if selection < 1 or selection > len(matches):
                say(text=f"❌ Please enter a number between 1 and {len(matches)}, or 'cancel'")
                return
        except ValueError:
            say(text="❌ Please enter a valid number (1-5) or 'cancel'")
            return

        # User confirmed a selection
        selected_entity, score = matches[selection - 1]
        entity_type = confirmation_data.get("entity_type")

        logger.info(f"User {user} confirmed selection {selection}: {selected_entity.get('name')} (score: {score:.1f})")

        # Clear the pending confirmation
        del pending_confirmations[confirmation_key]

        # Now process with the confirmed entity
        say(text=f"✅ Got it! Gathering information about *{selected_entity.get('name')}*...")

        # Rebuild intelligence with confirmed entity
        intelligence = {
            "needs_confirmation": False,
            "primary_entity": selected_entity,
            "related_contacts": [],
            "related_companies": [],
            "related_opportunities": [],
            "related_leads": [],
            "related_tasks": []
        }

        # Gather related data based on the original analysis
        primary_id = selected_entity.get("id")
        include = analysis.get("include", [])

        if "contacts" in include or "all" in include:
            intelligence["related_contacts"] = business_intel._get_related_contacts(
                primary_id, entity_type
            )

        if "opportunities" in include or "deals" in include or "all" in include:
            intelligence["related_opportunities"] = business_intel._get_related_opportunities(
                primary_id, entity_type
            )

        if "leads" in include or "all" in include:
            intelligence["related_leads"] = business_intel._get_related_leads(
                primary_id, entity_type
            )

        if "tasks" in include or "all" in include:
            intelligence["related_tasks"] = business_intel._get_related_tasks(
                primary_id, entity_type
            )

        if "companies" in include or "all" in include:
            intelligence["related_companies"] = business_intel._get_related_companies(
                primary_id, entity_type
            )

        # Format and send
        result_message = business_intel.format_intelligence(intelligence, "")
        say(text=result_message)

    except Exception as e:
        logger.error(f"Error handling confirmation response: {e}", exc_info=True)
        # Clear the confirmation on error
        if confirmation_key in pending_confirmations:
            del pending_confirmations[confirmation_key]
        say(text=f"❌ Error processing confirmation: {str(e)}")


@app.event("app_mention")
def handle_mention(event: SlackEvent, say: SayFunction, client: WebClient) -> None:
    """Handle when the bot is mentioned in a channel.

    Args:
        event: Slack event data
        say: Function to send messages
        client: Slack client
    """
    try:
        user: str = event.get("user", "")
        text: str = event.get("text", "")
        channel: str = event.get("channel", "")

        # Remove bot mention from text
        bot_user_id: str = client.auth_test()["user_id"]
        text = text.replace(f"<@{bot_user_id}>", "").strip()

        if not text:
            say(
                text=f"Hi <@{user}>! I'm your intelligent Copper CRM assistant. "
                     "Ask me anything in natural language!\n\n"
                     "*Examples:*\n"
                     "• 'What's the status of PubX?'\n"
                     "• 'Show me everything about Acme Corp'\n"
                     "• 'Who are we talking to at Microsoft?'\n"
                     "• 'What deals are in progress?'\n\n"
                     "*CSV Upload:*\n"
                     "• Upload a CSV file to enrich with Copper data"
            )
            return

        # Check for confirmation response
        confirmation_key = (user, channel)
        if confirmation_key in pending_confirmations:
            handle_confirmation_response(text, user, channel, say)
            return

        # Process as an intelligent business query
        logger.info(f"Processing business intelligence query from {user}: {text}")
        say(text=f"🔍 Gathering intelligence from Copper CRM...")

        # Use business intelligence to process the query
        result = business_intel.process_query(text)

        # Check if confirmation is needed
        if result.get("needs_confirmation"):
            # Store confirmation state
            pending_confirmations[confirmation_key] = {
                "confirmation_data": result["confirmation_data"],
                "analysis": result["analysis"],
                "timestamp": __import__("time").time()
            }

        say(text=result["message"])

    except Exception as e:
        logger.error(f"Error handling mention: {str(e)}", exc_info=True)
        say(text=f"Sorry, I encountered an error: {str(e)}")


@app.event("message")
def handle_message(event: SlackEvent, say: SayFunction, client: WebClient) -> None:
    """Handle direct messages to the bot.

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
        channel: str = event.get("channel", "")

        if not text:
            return

        # Check for help commands
        if text.lower() in ["help", "?", "commands"]:
            say(
                text="*Copper CRM Bot - Intelligent Assistant*\n\n"
                     "*Business Intelligence:*\n"
                     "Ask me anything about your business! Examples:\n"
                     "• 'What's the status of PubX?'\n"
                     "• 'Show me everything about Acme Corp'\n"
                     "• 'Who are we talking to at Microsoft?'\n"
                     "• 'What deals are in progress?'\n\n"
                     "*CSV Upload:*\n"
                     "• Upload a CSV file for data enrichment"
            )
            return

        # Check for confirmation response
        confirmation_key = (user, channel)
        if confirmation_key in pending_confirmations:
            handle_confirmation_response(text, user, channel, say)
            return

        # Process as an intelligent business query
        logger.info(f"Processing business intelligence query from {user} (DM): {text}")
        say(text="🔍 Gathering intelligence from Copper CRM...")

        # Use business intelligence to process the query
        result = business_intel.process_query(text)

        # Check if confirmation is needed
        if result.get("needs_confirmation"):
            # Store confirmation state
            pending_confirmations[confirmation_key] = {
                "confirmation_data": result["confirmation_data"],
                "analysis": result["analysis"],
                "timestamp": __import__("time").time()
            }

        say(text=result["message"])

    except Exception as e:
        logger.error(f"Error handling message: {str(e)}", exc_info=True)
        say(text=f"Sorry, I encountered an error: {str(e)}")


@app.event("file_shared")
def handle_file_upload(event: SlackEvent, client: WebClient, say: SayFunction) -> None:
    """Handle CSV file uploads for processing.

    Args:
        event: Slack event data
        client: Slack client
        say: Function to send messages
    """
    try:
        file_id = event.get("file_id")
        user_id = event.get("user_id")

        if not file_id:
            return

        # Get file info
        file_info = client.files_info(file=file_id)
        file_data = file_info.get("file", {})

        file_name = file_data.get("name", "")
        file_url = file_data.get("url_private_download", "")

        # Check if it's a CSV or Excel file
        if not (file_name.endswith('.csv') or
                file_name.endswith('.xlsx') or
                file_name.endswith('.xls')):
            logger.info(f"Ignoring non-CSV file: {file_name}")
            return

        logger.info(f"Processing file upload from {user_id}: {file_name}")
        say(text=f"📄 Processing {file_name}... this may take a moment.")

        # Download the file
        import requests
        headers = {"Authorization": f"Bearer {Config.SLACK_BOT_TOKEN}"}
        response = requests.get(file_url, headers=headers)

        if response.status_code != 200:
            say(text=f"❌ Failed to download file: {file_name}")
            return

        # Save temporarily
        temp_path = f"/tmp/{file_name}"
        with open(temp_path, 'wb') as f:
            f.write(response.content)

        # Process the CSV
        result = csv_handler.process_csv(temp_path, user_id)

        # Clean up
        os.remove(temp_path)

        # Send results
        if result.get("success"):
            output_file = result.get("output_file")
            summary = result.get("summary", "")

            # Upload the result
            client.files_upload_v2(
                channel=event.get("channel_id"),
                file=output_file,
                title=f"Enriched_{file_name}",
                initial_comment=f"✅ Processing complete!\n\n{summary}"
            )

            # Clean up output file
            if os.path.exists(output_file):
                os.remove(output_file)
        else:
            error = result.get("error", "Unknown error")
            say(text=f"❌ Error processing file: {error}")

    except Exception as e:
        logger.error(f"Error handling file upload: {str(e)}", exc_info=True)
        say(text=f"Sorry, I encountered an error processing your file: {str(e)}")


def main():
    """Start the bot."""
    try:
        logger.info("Starting Copper CRM Slack Bot...")
        logger.info("Bot is running in Socket Mode!")
        logger.info("Press Ctrl+C to stop")

        handler = SocketModeHandler(app, Config.SLACK_APP_TOKEN)
        handler.start()

    except KeyboardInterrupt:
        logger.info("Shutting down gracefully...")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
